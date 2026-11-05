"""Commit a data bot's changes under its own name, with a message naming the new numbers.

    python scripts/bot_commit.py <bot>        # e.g. markets; author "markets-bot"

Commits only when series or panels changed (a run that only touched timestamps in
data/meta or data/status.json is not worth a commit), when a source failed, or when a
failing series recovered (so the Status page and the live dashboard show either). Pushes with a rebase-and-retry loop in case another bot pushed
first. Writes `pushed=true|false` to $GITHUB_OUTPUT so the workflow can trigger a deploy.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))   # run as `python scripts/bot_commit.py`: make `pipelines` importable
from pipelines.core import store

MEANINGFUL = ("data/series/", "data/panels/", "data/revisions/", "data/briefings/", "data/newsletter/")


def git(*args: str, check: bool = True) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=check).stdout


def fmt(v: float) -> str:
    return f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.2f}".rstrip("0").rstrip(".")


def latest(path: str) -> tuple[str, str, float] | None:
    """(short title, period, value) of a changed series CSV."""
    sid = Path(path).stem
    spec_file = ROOT / "registry" / "series" / f"{sid}.yaml"
    title = yaml.safe_load(spec_file.read_text())["short_title"] if spec_file.exists() else sid
    df = store.load_series(sid)
    if df.empty:
        return None
    last = df.sort_values("period").iloc[-1]
    return title, last["period"], float(last["value"])


def recovered() -> list[str]:
    """Series failing in the committed data/status.json that this run marked healthy."""
    before = git("show", "HEAD:data/status.json", check=False)
    now = ROOT / "data" / "status.json"
    if not before or not now.exists():
        return []
    old, new = json.loads(before), json.loads(now.read_text())
    return sorted(s for s, st in new.items() if old.get(s, {}).get("stale") and not st.get("stale"))


def worth_committing(changed: list[str], failures: list, back: list[str]) -> bool:
    """New or revised numbers, a failure, or a recovery; not a run that only moved timestamps."""
    return any(p.startswith(MEANINGFUL) for p in changed) or bool(failures) or bool(back)


def subject(bot: str, items: list[str], failures: list, back: list[str]) -> str:
    """'markets: USD/INR 95.23, Nifty 50 22,699 (+3 more)', else what happened to the sources."""
    if items:
        return f"{bot}: " + ", ".join(items[:4]) + (f" (+{len(items) - 4} more)" if len(items) > 4 else "")
    return f"{bot}: " + "; ".join([f"{len(failures)} source failure(s) recorded"] * bool(failures)
                                   + [f"{len(back)} series working again"] * bool(back))


def output(pushed: bool) -> None:
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"pushed={'true' if pushed else 'false'}\n")


def main(bot: str) -> int:
    git("add", "data")
    changed = [p for p in git("diff", "--cached", "--name-only").splitlines()]
    last_run = ROOT / "data" / "raw" / "last_run.json"
    failures = json.loads(last_run.read_text())["failures"] if last_run.exists() else []
    back = recovered()
    if not worth_committing(changed, failures, back):
        git("reset", "-q")
        print(f"{bot}-bot: no new data")
        output(False)
        return 0

    series = [x for p in changed if p.startswith("data/series/") and (x := latest(p))]
    panels = [Path(p).stem for p in changed if p.startswith("data/panels/")]
    items = [f"{t} {fmt(v)}" for t, _, v in series] + panels
    title = subject(bot, items, failures, back)
    body = "\n".join([f"- {t}: {fmt(v)} ({p})" for t, p, v in series] + [f"- panel {n}" for n in panels]
                     + [f"- FAILED {f['series_id']}: {f['error'][:120]}" for f in failures]
                     + [f"- recovered {s}" for s in back])
    name = f"{bot}-bot"
    git("-c", f"user.name={name}", "-c", f"user.email={name}@users.noreply.github.com",
        "commit", "-q", "-m", title, "-m", body)
    for attempt in range(5):
        if subprocess.run(["git", "push", "-q", "origin", "HEAD:main"], cwd=ROOT).returncode == 0:
            print(f"{name}: pushed: {title}")
            output(True)
            return 0
        # Another bot pushed first: replay ours on top. On a clash (data/status.json, or a
        # series two sources share) keep this bot's version, which is the newer fetch.
        time.sleep(5 * (attempt + 1))
        git("pull", "-q", "--rebase", "-X", "theirs", "origin", "main", check=False)
    print(f"{name}: push failed after retries", file=sys.stderr)
    output(False)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "data"))
