"""The map behind the live status dashboard: which bot fetches which source, from which agency,
and how healthy each source's series are as of this build.

Written to site/public/status-map.json on every build, so the deployed site serves it. The
dashboard itself (scheduler/dashboard.js, served by the scheduler Worker) reads this file and
adds what only GitHub knows live: which workflows are running now, recent runs and commits.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime

import yaml

from pipelines.core import store

# Workflows that are not data bots but appear on the dashboard (file -> label).
OTHER_WORKFLOWS = {
    "deploy.yml": "deploy",
    "ci.yml": "ci",
    "newsletter-morning.yml": "morning email",
    "newsletter-release.yml": "release email",
    "briefing.yml": "briefing",
    "probe-sources.yml": "source probes",
    "scheduler.yml": "scheduler deploy",
}


# Long agency names in the registry -> the short form the dashboard's narrow column shows.
SHORT = {"Reserve Bank of India": "RBI", "Airports Authority of India": "AAI", "Controller General of Accounts": "CGA",
         "Department of Commerce": "Commerce", "Labour Bureau": "Labour Bureau", "Ministry of Finance": "MoF",
         "Office of the Economic Adviser": "OEA", "GSTN / Ministry of Finance": "GSTN", "GST portal": "GSTN",
         "custodians' reports": "NSDL", "BSE Ltd.": "BSE / RBI"}


def short_agency(name: str) -> str:
    """'Grid Controller of India (Grid-India)' -> 'Grid-India'; 'FBIL (via ...)' -> 'FBIL';
    'Department of Commerce, Ministry of ...' -> 'Commerce'; 'via RBI home page and ...' -> 'RBI'."""
    m = re.match(r"(.+?)\s*\(([^)]+)\)\s*$", name)
    if m:   # a short name before the brackets wins ('MoSPI (NSO)', 'FBIL (via ...)'), else the acronym
        return m.group(1) if len(m.group(1)) <= 6 or m.group(2).startswith("via ") else m.group(2)
    if name.startswith("via "):
        name = name[4:].split(" and ")[0].removeprefix("the ").split(" home page")[0]
        return SHORT.get(name, name)
    head = name.split(",")[0].strip()
    return SHORT.get(name, SHORT.get(head, head))


def source_row(src, specs: dict, health: dict) -> dict:
    """One source: agency, link, series counts and freshness from the health rows."""
    rows = [health[s] for s in src.series_ids if s in health]
    first = next((specs[s] for s in src.series_ids if s in specs), {})
    live = [r for r in rows if not r.get("discontinued")]
    successes = [r["last_success"] for r in rows if r.get("last_success")]
    periods = [r["last_period"] for r in rows if r.get("last_period")]
    return {
        "name": src.name,
        "agency": "derived" if src.derived else short_agency(first.get("source", {}).get("agency", "")),
        "url": first.get("source", {}).get("url"),
        "series": len(rows),
        "failing": sum(1 for r in live if r["stale"]),
        "overdue": sum(1 for r in live if not r["stale"] and (r.get("overdue_days") or 0) > 0),
        "last_success": max(successes, default=None),
        "last_period": max(periods, default=None),
    }


def build(specs: dict, health_rows: list[dict], calendar_rows: list[dict], actions: dict | None) -> dict:
    """The status map: bots -> sources, manual sources, totals and the next releases."""
    from pipelines.run import discover, fetch_mode
    sources = discover()
    health = {r["id"]: r for r in health_rows}
    bots_yaml = yaml.safe_load((store.ROOT / "registry" / "bots.yaml").read_text())["bots"]
    bots = [{"name": name, "workflow": f"bot-{name}.yml", "when": b["when"],
             "sources": [source_row(sources[s], specs, health) for s in b["sources"] if s in sources]}
            for name, b in bots_yaml.items()]
    manual = [source_row(s, specs, health) for s in sources.values() if fetch_mode(s) == "manual"]
    live = [r for r in health_rows if not r.get("discontinued")]
    failing = sum(1 for r in live if r["stale"])
    overdue = sum(1 for r in live if not r["stale"] and (r.get("overdue_days") or 0) > 0)
    upcoming = [{"date": c["date"], "time": c.get("time_ist"), "publisher": c["publisher"], "title": c["title"],
                 "period": c.get("period")} for c in calendar_rows if c.get("status") == "upcoming"][:6]
    return {
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "totals": {"series": len(live), "ok": len(live) - failing - overdue, "overdue": overdue,
                   "failing": failing, "sources": sum(len(b["sources"]) for b in bots) + len(manual)},
        "bots": bots,
        "manual": manual,
        "workflows": OTHER_WORKFLOWS,
        "upcoming": upcoming,
        "actions": actions,
    }
