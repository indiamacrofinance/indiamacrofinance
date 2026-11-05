"""scripts/report_failures.py: network blips wait a day, other errors report at once."""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location("rf", Path(__file__).parents[1] / "scripts" / "report_failures.py")
rf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rf)
NOW = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)


def test_network_blip_waits():
    dns = "RuntimeError: GET https://www.amfiindia.com/x failed: [Errno -3] Temporary failure in name resolution"
    assert not rf.should_report(dns, NOW - timedelta(hours=5), NOW)
    assert not rf.should_report("RuntimeError: GET https://www.aai.aero/x failed: timed out", NOW - timedelta(hours=5), NOW)
    assert rf.should_report(dns, NOW - timedelta(hours=30), NOW)          # down for over a day
    assert rf.should_report(dns, None, NOW)                               # never succeeded


def test_parser_error_reports_at_once():
    assert rf.should_report("RuntimeError: no CPI-IW press note linked on the Labour Bureau home page",
                            NOW - timedelta(hours=1), NOW)


def test_large_revision_issues(tmp_path, monkeypatch):
    # A revision above a series' revision_alert opens "large-revision: <id>"; a second one
    # comments on the open issue. Failures and recoveries are handled as before.
    import json
    (tmp_path / "data" / "raw").mkdir(parents=True)
    alert = {"series_id": "gsec_10y_yield", "source": "rbi_home_rates", "threshold": 0,
             "rows": [{"period": "2026-11-02", "old": 7.325, "new": 7.3102, "pct": 0.202}]}
    (tmp_path / "data" / "raw" / "last_run.json").write_text(json.dumps(
        {"at": "2026-11-04T05:00:00+00:00", "sources": [], "failures": [], "revisions": [alert]}))
    (tmp_path / "data" / "status.json").write_text("{}")
    monkeypatch.setattr(rf, "ROOT", tmp_path)
    calls = []

    def fake_gh(*args):
        calls.append(args)
        return "[]" if args[:2] == ("issue", "list") else ""
    monkeypatch.setattr(rf, "gh", fake_gh)
    rf.main()
    created = [c for c in calls if c[:2] == ("issue", "create")]
    assert len(created) == 1 and "large-revision: gsec_10y_yield" in created[0] and "large-revision" in created[0]
    body = created[0][created[0].index("--body") + 1]
    assert "| 2026-11-02 | 7.325 | 7.3102 | 0.202% |" in body

    calls.clear()
    monkeypatch.setattr(rf, "gh", lambda *a: (calls.append(a), json.dumps([{"number": 7, "title": "large-revision: gsec_10y_yield"}])
                                              if a[:2] == ("issue", "list") and "large-revision" in a else "[]")[1])
    rf.main()
    assert [c[:3] for c in calls if c[:2] == ("issue", "comment")] == [("issue", "comment", "7")]


def test_run_records_large_revisions(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import pandas as pd

    from pipelines import run
    from pipelines.core import store
    for attr in ("SERIES", "META", "REVISIONS"):
        monkeypatch.setattr(store, attr, tmp_path)
    monkeypatch.setattr(store, "STATUS", tmp_path / "status.json")
    monkeypatch.setattr(store, "archive_raw", lambda *args: [])
    monkeypatch.setattr(run, "ALERTS", [])
    spec = {"validation": {"range": [0, 100], "revision_alert": 0}, "id": "x", "title": "x", "short_title": "x",
            "unit": "percent", "frequency": "D", "base_year": None, "licence": "GODL", "downloadable": True,
            "source": {"agency": "a", "dataset": "d", "url": "", "module": "m"}}
    monkeypatch.setattr(run.registry, "all_series", lambda: {"x": spec})
    (tmp_path / "x.csv").write_text("period,value,vintage,note\n2026-11-02,7.325,2026-11-03,\n")
    rows = pd.DataFrame({"series_id": ["x"], "period": ["2026-11-02"], "value": [7.3102]})
    src = SimpleNamespace(name="rbi_home_rates", series_ids=("x",), panel=False, derived=False,
                          fetch=list, parse=lambda raws: rows)
    assert run.run_source(src) == []
    assert [(a["series_id"], a["rows"][0]["old"], a["rows"][0]["new"]) for a in run.ALERTS] == [("x", 7.325, 7.3102)]
