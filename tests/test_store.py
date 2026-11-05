"""Upsert semantics: add new periods, log revisions, keep absent periods and old vintages."""
import pandas as pd

from pipelines.core import store


def test_upsert(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "SERIES", tmp_path)
    pd.DataFrame({"period": ["2026-01-01", "2026-02-01"], "value": [1.0, 2.0],
                  "vintage": ["2026-02-10", "2026-03-10"], "note": ["", ""]}).to_csv(
        tmp_path / "x.csv", index=False)
    new = pd.DataFrame({"period": ["2026-02-01", "2026-03-01"], "value": [2.5, 3.0]})
    merged, revised = store.upsert("x", new, "2026-04-10")
    assert merged.period.tolist() == ["2026-01-01", "2026-02-01", "2026-03-01"]
    assert merged.value.tolist() == [1.0, 2.5, 3.0]
    assert merged.set_index("period").loc["2026-01-01", "vintage"] == "2026-02-10"
    assert revised.period.tolist() == ["2026-02-01"] and revised.old_value.iloc[0] == 2.0


def test_upsert_unchanged_keeps_vintage(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "SERIES", tmp_path)
    pd.DataFrame({"period": ["2026-01-01"], "value": [1.0], "vintage": ["2026-02-10"],
                  "note": [""]}).to_csv(tmp_path / "x.csv", index=False)
    merged, revised = store.upsert("x", pd.DataFrame({"period": ["2026-01-01"], "value": [1.0]}),
                                   "2026-04-10")
    assert merged.vintage.tolist() == ["2026-02-10"] and revised.empty


def test_upsert_unchanged_value_takes_new_note(tmp_path, monkeypatch):
    # An estimate moving from "Provisional" to "First Revised" at the same value: the note
    # updates, the vintage (first appearance) stays, and nothing is logged as a revision.
    monkeypatch.setattr(store, "SERIES", tmp_path)
    pd.DataFrame({"period": ["2025-04-01"], "value": [7.8], "vintage": ["2026-05-30"],
                  "note": ["Provisional Estimates"]}).to_csv(tmp_path / "x.csv", index=False)
    new = pd.DataFrame({"period": ["2025-04-01"], "value": [7.8], "note": ["First Revised Estimates"]})
    merged, revised = store.upsert("x", new, "2027-02-27")
    row = merged.iloc[0]
    assert (row.note, row.vintage) == ("First Revised Estimates", "2026-05-30") and revised.empty


def test_upsert_panel_unchanged_value_takes_new_note(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "PANELS", tmp_path)
    pd.DataFrame({"entity": ["Mining"], "period": ["2025-04-01"], "value": [3.0], "vintage": ["2026-05-30"],
                  "note": ["Provisional Estimates"]}).to_csv(tmp_path / "p.csv", index=False)
    new = pd.DataFrame({"entity": ["Mining"], "period": ["2025-04-01"], "value": [3.0], "note": ["Final Estimates"]})
    merged = store.upsert_panel("p", new, "2027-02-27")
    assert (merged.iloc[0].note, merged.iloc[0].vintage) == ("Final Estimates", "2026-05-30")


def test_exclude_with_vintage(tmp_path, monkeypatch):
    # RBI's home page dated the 30 Oct yields "November 30" on 3 Nov. An exclude entry with a
    # vintage hides only the row stored that day: kept in the CSV and hidden from readers.
    from pipelines.core import registry
    monkeypatch.setattr(store, "SERIES", tmp_path)
    entry = {"period": "2026-11-30", "vintage": "2026-11-03", "added": "2026-11-05", "reason": "misdated"}
    monkeypatch.setattr(registry, "all_series", lambda: {"x": {"frequency": "D", "exclude": [entry]}})
    (tmp_path / "x.csv").write_text("period,value,vintage,note\n2026-11-03,7.31,2026-11-04,\n"
                                    "2026-11-30,7.42,2026-11-03,\n")
    assert store.load_series("x").period.tolist() == ["2026-11-03"]
    assert store.load_series("x", stored=True).period.tolist() == ["2026-11-03", "2026-11-30"]
    assert store.excluded_periods("x") == set()          # the period itself is not excluded

    merged, _ = store.upsert("x", pd.DataFrame({"period": ["2026-11-04"], "value": [7.21]}), "2026-11-05")
    assert merged.period.tolist() == ["2026-11-03", "2026-11-04", "2026-11-30"]   # kept as a record
    assert [e["period"] for e in store.active_excludes("x")] == ["2026-11-30"]
    # The real value arrives: an ordinary revision, so the misdated row is kept in the revision
    # log (history is never deleted); the entry then matches nothing and lapses.
    merged, revised = store.upsert("x", pd.DataFrame({"period": ["2026-11-30"], "value": [7.05]}), "2026-12-01")
    row = merged.set_index("period").loc["2026-11-30"]
    assert (row.value, row.vintage) == (7.05, "2026-12-01")
    assert revised[["period", "old_value", "old_vintage"]].values.tolist() == [["2026-11-30", 7.42, "2026-11-03"]]
    (tmp_path / "x.csv").write_text(merged.to_csv(index=False))
    assert store.load_series("x").period.tolist()[-1] == "2026-11-30"   # the real value is shown
    assert store.active_excludes("x") == []


def test_vintage_exclude_lapses_even_at_the_same_value(tmp_path, monkeypatch):
    # The real 30 Nov close could equal the misdated 7.4243: it must still replace the hidden
    # row (taking today's vintage), or it would stay hidden for good.
    from pipelines.core import registry
    monkeypatch.setattr(store, "SERIES", tmp_path)
    entry = {"period": "2026-11-30", "vintage": "2026-11-03", "added": "2026-11-05", "reason": "misdated"}
    monkeypatch.setattr(registry, "all_series", lambda: {"x": {"frequency": "D", "exclude": [entry]}})
    (tmp_path / "x.csv").write_text("period,value,vintage,note\n2026-11-30,7.4243,2026-11-03,\n")
    merged, revised = store.upsert("x", pd.DataFrame({"period": ["2026-11-30"], "value": [7.4243]}), "2026-12-01")
    assert merged.vintage.tolist() == ["2026-12-01"] and revised.period.tolist() == ["2026-11-30"]
    (tmp_path / "x.csv").write_text(merged.to_csv(index=False))
    assert store.load_series("x").period.tolist() == ["2026-11-30"] and store.active_excludes("x") == []
