"""Invalid parser output must leave stored observations intact and report failures."""
from types import SimpleNamespace

import pandas as pd
import pytest

from pipelines import run
from pipelines.core import store
from pipelines.core.validate import validate

SPEC = {"validation": {"range": [0, 100]}}


@pytest.mark.parametrize("period", ["2026-99-99", "2026-02-29", "2026-04-31",
                                    "20260101", "2026-1-1", "2026-01-01T00:00:00"])
@pytest.mark.parametrize("panel", [False, True])
def test_invalid_dates_preserve_stored_data(tmp_path, monkeypatch, period, panel):
    monkeypatch.setattr(store, "SERIES", tmp_path)
    monkeypatch.setattr(store, "PANELS", tmp_path)
    monkeypatch.setattr(store, "STATUS", tmp_path / "status.json")
    monkeypatch.setattr(store, "archive_raw", lambda *args: [])
    monkeypatch.setattr(run.registry, "all_series", lambda: {"x": SPEC})
    path = tmp_path / "x.csv"
    original = "entity,period,value,vintage,note\nGoa,2026-01-01,2.0,2026-02-01,\n"
    path.write_text(original)
    rows = pd.DataFrame({"series_id": ["x"], "entity": ["Goa"],
                         "period": [period], "value": [2.0]})
    src = SimpleNamespace(name="test", series_ids=("x",), panel=panel,
                          fetch=list, parse=lambda raws: rows)

    failures = run.run_source(src)

    assert len(failures) == 1 and "invalid periods" in failures[0]["error"]
    assert path.read_text() == original
    assert store.load_status()["x"]["stale"]


@pytest.mark.parametrize("period", ["2024-02-29", "2026-01-01", "2026-12-31"])
def test_valid_iso_dates_are_accepted(period):
    rows = pd.DataFrame({"period": [period], "value": [2.0]})
    assert validate("x", rows, SPEC) == []


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, "bad"])
def test_invalid_panel_preserves_data(tmp_path, monkeypatch, value):
    monkeypatch.setattr(store, "PANELS", tmp_path)
    monkeypatch.setattr(store, "STATUS", tmp_path / "status.json")
    path = tmp_path / "x.csv"
    original = "entity,period,value,vintage,note\nGoa,2026-01-01,2,2026-02-01,\n"
    path.write_text(original)
    store.update_status("x", ok=True, last_period="2026-01-01")
    last_success = store.load_status()["x"]["last_success"]
    parsed = pd.DataFrame({"series_id": ["x"], "entity": ["Goa"],
                           "period": ["2026-01-01"], "value": [value]})

    failures = run.run_panel(SimpleNamespace(name="test", series_ids=("x",)), parsed, {"x": SPEC})

    assert len(failures) == 1 and failures[0]["series_id"] == "x"
    assert path.read_text() == original
    status = store.load_status()["x"]
    assert status["stale"] and status["last_error"]
    assert status["last_success"] == last_success
    assert status["last_period"] == "2026-01-01"


def test_panel_keys_allow_same_period_for_different_entities():
    rows = pd.DataFrame({"entity": ["Goa", "Bihar"], "period": ["2026-01-01"] * 2,
                         "value": [2.0, 3.0]})
    assert validate("x", rows, SPEC, panel=True) == []
    rows.loc[1, "entity"] = "Goa"
    assert "duplicate" in validate("x", rows, SPEC, panel=True)[0]


@pytest.mark.parametrize("key,value", [("entity", None), ("entity", " "), ("period", None)])
def test_missing_panel_keys(key, value):
    rows = pd.DataFrame({"entity": ["Goa"], "period": ["2026-01-01"], "value": [2.0]})
    rows.loc[0, key] = value
    assert f"x: missing {key}" in validate("x", rows, SPEC, panel=True)


@pytest.mark.parametrize("missing", ["series_id", "period", "value", "entity"])
def test_missing_parser_columns_mark_source_stale(tmp_path, monkeypatch, missing):
    monkeypatch.setattr(store, "STATUS", tmp_path / "status.json")
    monkeypatch.setattr(store, "archive_raw", lambda *args: [])
    monkeypatch.setattr(run.registry, "all_series", lambda: {"x": SPEC, "y": SPEC})
    rows = pd.DataFrame({"series_id": ["x"], "entity": ["Goa"],
                         "period": ["2026-01-01"], "value": [2.0]}).drop(columns=missing)
    src = SimpleNamespace(name="test", series_ids=("x", "y"), panel=True,
                          fetch=list, parse=lambda raws: rows)

    failures = run.run_source(src)

    assert {f["series_id"] for f in failures} == {"x", "y"}
    assert all("parser missing columns" in f["error"] for f in failures)
    assert all(s["stale"] for s in store.load_status().values())


def test_object_column_of_numbers_is_accepted():
    from decimal import Decimal
    rows = pd.DataFrame({"period": ["2026-01-01", "2026-02-01", "2026-03-01"],
                         "value": pd.Series([2, 3.5, Decimal("4.25")], dtype=object)})
    assert validate("x", rows, SPEC) == []


@pytest.mark.parametrize("panel", [False, True])
def test_boolean_column_is_rejected(panel):
    rows = pd.DataFrame({"entity": ["Goa"], "period": ["2026-01-01"], "value": [True]})
    assert "boolean values" in validate("x", rows, SPEC, panel=panel)[0]


@pytest.mark.parametrize("value", ["5.2", "bad", True])
def test_text_and_bools_are_rejected(value):
    rows = pd.DataFrame({"period": ["2026-01-01", "2026-02-01"],
                         "value": pd.Series([2.0, value], dtype=object)})
    assert "non-numeric" in validate("x", rows, SPEC)[0]


@pytest.mark.parametrize(("frequency", "days_ahead", "ok"),
                         [("D", 0, True), ("D", 1, True), ("D", 25, False), ("W", 25, False),
                          ("M", 25, True), ("Q", 400, True)])
def test_future_periods(frequency, days_ahead, ok):
    # A daily-to-fortnightly observation dated weeks ahead is a wrong date at the source (RBI's
    # home page once said "as on November 30" on 3 November). Forecasts (Q, A) and the current
    # month (M) are fine; one day ahead is allowed for IST dates read on UTC runners.
    from datetime import date, timedelta
    period = (date.today() + timedelta(days=days_ahead)).isoformat()
    problems = validate("x", pd.DataFrame({"period": [period], "value": [1.0]}), {**SPEC, "frequency": frequency})
    assert (problems == []) is ok, problems


def test_excluded_stored_row_is_kept_but_not_shown(tmp_path, monkeypatch):
    # A wrong value already stored, then excluded in the registry: the CSV keeps it (history is
    # never deleted), but readers, the meta file and the status's latest period do not see it.
    monkeypatch.setattr(store, "SERIES", tmp_path)
    monkeypatch.setattr(store, "META", tmp_path)
    monkeypatch.setattr(store, "REVISIONS", tmp_path)
    monkeypatch.setattr(store, "STATUS", tmp_path / "status.json")
    monkeypatch.setattr(store, "archive_raw", lambda *args: [])
    spec = {"validation": {"range": [0, 100], "revision_alert": 5}, "id": "x", "title": "x", "short_title": "x", "unit": "percent", "frequency": "D",
            "base_year": None, "licence": "GODL", "downloadable": True,
            "source": {"agency": "a", "dataset": "d", "url": "", "module": "m"},
            "exclude": [{"period": "2026-01-30", "added": "2026-01-05", "reason": "wrong date at source"}]}
    monkeypatch.setattr(run.registry, "all_series", lambda: {"x": spec})
    (tmp_path / "x.csv").write_text("period,value,vintage,note\n2026-01-02,7.0,2026-01-03,\n"
                                    "2026-01-30,7.4,2026-01-03,\n")
    rows = pd.DataFrame({"series_id": ["x", "x"], "period": ["2026-01-05", "2026-01-30"], "value": [7.2, 9.9]})
    src = SimpleNamespace(name="test", series_ids=("x",), panel=False, derived=False,
                          fetch=list, parse=lambda raws: rows)

    assert run.run_source(src) == []
    assert store.load_series("x", stored=True).period.tolist() == ["2026-01-02", "2026-01-05", "2026-01-30"]
    assert store.load_series("x", stored=True).set_index("period").loc["2026-01-30", "value"] == 7.4
    assert store.load_series("x").period.tolist() == ["2026-01-02", "2026-01-05"]
    assert store.load_status()["x"]["last_period"] == "2026-01-05"


def test_every_row_excluded_fails_the_series_not_the_run(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "SERIES", tmp_path)
    monkeypatch.setattr(store, "META", tmp_path)
    monkeypatch.setattr(store, "REVISIONS", tmp_path)
    monkeypatch.setattr(store, "STATUS", tmp_path / "status.json")
    monkeypatch.setattr(store, "archive_raw", lambda *args: [])
    # A vintage entry added the same day its row was stored: the source re-sends the row, it is
    # re-stated under today's vintage, which the entry still matches, so nothing is left to show.
    from datetime import date
    today = date.today().isoformat()
    spec = {"validation": {"range": [0, 100], "revision_alert": 5}, "frequency": "D",
            "exclude": [{"period": "2026-01-02", "vintage": today, "added": "x", "reason": "r"}]}
    monkeypatch.setattr(run.registry, "all_series", lambda: {"x": spec})
    (tmp_path / "x.csv").write_text(f"period,value,vintage,note\n2026-01-02,7.0,{today},\n")
    rows = pd.DataFrame({"series_id": ["x"], "period": ["2026-01-02"], "value": [7.0]})
    src = SimpleNamespace(name="test", series_ids=("x",), panel=False, derived=False, fetch=list, parse=lambda raws: rows)
    failures = run.run_source(src)
    assert len(failures) == 1 and "excluded" in failures[0]["error"]
