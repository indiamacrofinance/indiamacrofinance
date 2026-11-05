"""scripts/bot_commit.py: which runs are worth a commit."""
import json

from scripts import bot_commit


def test_recovered(tmp_path, monkeypatch):
    # A series failing in the committed status.json and healthy after this run counts as
    # recovered; one that was never failing, or still is, does not.
    head = {"a": {"stale": True}, "b": {"stale": False}, "c": {"stale": True}, "d": {"stale": True}}
    now = {"a": {"stale": False}, "b": {"stale": False}, "c": {"stale": True}, "e": {"stale": False}}
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "status.json").write_text(json.dumps(now))
    monkeypatch.setattr(bot_commit, "ROOT", tmp_path)
    monkeypatch.setattr(bot_commit, "git", lambda *a, **k: json.dumps(head))
    assert bot_commit.recovered() == ["a"]


def test_recovered_without_history(tmp_path, monkeypatch):
    monkeypatch.setattr(bot_commit, "ROOT", tmp_path)
    monkeypatch.setattr(bot_commit, "git", lambda *a, **k: "")
    assert bot_commit.recovered() == []


def test_worth_committing():
    assert not bot_commit.worth_committing(["data/meta/x.json", "data/status.json"], [], [])
    assert bot_commit.worth_committing(["data/series/x.csv"], [], [])
    assert bot_commit.worth_committing(["data/status.json"], [{"series_id": "x"}], [])
    assert bot_commit.worth_committing(["data/status.json"], [], ["x"])   # a recovery alone


def test_subject():
    assert bot_commit.subject("mospi", ["IIP 124.3"], [], ["x"]) == "mospi: IIP 124.3"
    assert bot_commit.subject("mospi", [], [], ["a", "b"]) == "mospi: 2 series working again"
    assert (bot_commit.subject("mospi", [], [{"series_id": "c"}], ["a"])
            == "mospi: 1 source failure(s) recorded; 1 series working again")


def test_runs_as_a_script():
    # bot.yml runs `python scripts/bot_commit.py`: only scripts/ is on sys.path, so the script
    # must make `pipelines` importable itself (latest() reads series through the store).
    import os
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    code = ("import runpy, sys; sys.path[:] = [p for p in sys.path if p not in ('', '.')]; "
            "m = runpy.run_path('scripts/bot_commit.py'); print(m['latest']('data/series/no_such_series.csv'))")
    out = subprocess.run([sys.executable, "-c", code], cwd=root, env=env, capture_output=True, text=True, check=False)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "None"
