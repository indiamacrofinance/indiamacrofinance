"""Invalid parser output must leave stored observations intact and report failures."""
from types import SimpleNamespace

import pandas as pd
import pytest

from pipelines import run
from pipelines.core import store
from pipelines.core.validate import validate

SPEC = {"validation": {"range": [0, 100]}}


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
