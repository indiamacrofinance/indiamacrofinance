"""Open, update and close `scraper-broken` GitHub issues after a bot run (used by workflows).

Reads data/raw/last_run.json written by pipelines.run, and data/status.json. Needs the `gh`
CLI and GH_TOKEN. One issue per source, titled "scraper-broken: <source>", so repeat failures
comment on the same issue.

- Parser or layout errors open an issue at once.
- Network errors (DNS, timeouts, refused connections, 5xx) are usually one-off blips on the
  runner, so they open an issue only when the source has not succeeded for MIN_OUTAGE.
- A source that ran cleanly closes its open issue (and any older per-series issues for its
  series, titled "scraper-broken: <series_id>") with a "recovered" comment.
- Revisions above a series' `revision_alert` open (or comment on) "large-revision: <series_id>",
  labelled `large-revision`. A person checks them against the release and closes them.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MIN_OUTAGE = timedelta(hours=24)
NETWORK = re.compile(r"name resolution|timed out|timeout|Connection (?:reset|refused|aborted)|"
                     r"RemoteProtocolError|ConnectError|failed: (?:5\d\d|429)\b|Server error '5\d\d", re.I)


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def open_issues(label: str = "scraper-broken") -> dict[str, int]:
    rows = json.loads(gh("issue", "list", "--state", "open", "--label", label,
                         "--limit", "200", "--json", "number,title"))
    return {i["title"].removeprefix(f"{label}: "): i["number"] for i in rows}


def revision_body(alert: dict, at: str, run_url: str) -> str:
    rows = "\n".join(f"| {r['period']} | {r['old']} | {r['new']} | {r['pct']}% |" for r in alert["rows"][:30])
    return (f"`{alert['series_id']}` (source `{alert['source']}`): {len(alert['rows'])} stored value(s) changed by more "
            f"than its `revision_alert` of {alert['threshold']}% at {at}.\n\n| Period | Old | New | Change |\n|---|---|---|---|\n"
            f"{rows}\n\n{run_url}\n\nRevisions are normal for many series; check the new values against the "
            "publisher's release, then close this issue. If a value is wrong at the source, add an `exclude` entry "
            "(runbook: \"A published value looks wrong\"). The old values are in `data/revisions/`.")


def last_success(series: list[str], status: dict) -> datetime | None:
    times = [status.get(s, {}).get("last_success") for s in series]
    times = [datetime.fromisoformat(t) for t in times if t]
    return max(times) if times else None


def should_report(error: str, ok_at: datetime | None, now: datetime) -> bool:
    """Network blips wait until the source has been down for MIN_OUTAGE; other errors report at once."""
    return not (NETWORK.search(error) and ok_at and now - ok_at < MIN_OUTAGE)


def main() -> None:
    report = json.loads((ROOT / "data/raw/last_run.json").read_text())
    status = json.loads((ROOT / "data/status.json").read_text())
    run_url = os.environ.get("RUN_URL", "")
    now = datetime.now(timezone.utc)
    issues = open_issues()

    by_source: dict[str, list[dict]] = {}
    for f in report["failures"]:
        by_source.setdefault(f["source"], []).append(f)

    for source, fails in by_source.items():
        series = [f["series_id"] for f in fails]
        error = fails[0]["error"]
        ok_at = last_success(series, status)
        if not should_report(error, ok_at, now):
            print(f"{source}: network error, last success {ok_at:%Y-%m-%d %H:%M} UTC; not reporting yet")
            continue
        body = (f"Source `{source}` failed at {report['at']} for {len(series)} series: "
                f"{', '.join(f'`{s}`' for s in series)}.\n\n```\n{error[:1500]}\n```\n\n{run_url}\n\n"
                "Fix with docs/guidebook/playbooks/fix-scraper.md. The site keeps the last good values. "
                "This issue closes itself when the source next runs cleanly.")
        if source in issues:
            gh("issue", "comment", str(issues[source]), "--body", body)
            print(f"commented on #{issues[source]} {source}")
        else:
            gh("issue", "create", "--title", f"scraper-broken: {source}", "--label", "scraper-broken", "--body", body)
            print(f"opened issue: {source}")

    from pipelines.run import discover                       # series ids of the sources that ran
    sources = discover()
    for name in sorted(set(report["sources"]) - set(by_source)):
        for key in [name, *getattr(sources.get(name), "series_ids", ())]:
            if key in issues:
                gh("issue", "close", str(issues[key]), "--comment",
                   f"Recovered: `{name}` ran cleanly at {report['at']}. {run_url}")
                print(f"closed #{issues[key]} ({key})")

    revised = open_issues("large-revision")
    for alert in report.get("revisions") or []:
        sid, body = alert["series_id"], revision_body(alert, report["at"], run_url)
        if sid in revised:
            gh("issue", "comment", str(revised[sid]), "--body", body)
            print(f"commented on #{revised[sid]} large-revision {sid}")
        else:
            gh("issue", "create", "--title", f"large-revision: {sid}", "--label", "large-revision", "--body", body)
            print(f"opened issue: large-revision {sid}")


if __name__ == "__main__":
    main()
