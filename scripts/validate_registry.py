"""Validate registry/series/*.yaml against registry/series/_schema.md."""
import csv
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SERIES_DIR = ROOT / "registry" / "series"
PAGES_DIR = ROOT / "docs" / "guidebook" / "05-pages"

AREAS = {"growth", "inflation", "jobs", "activity", "money", "markets", "fiscal", "external", "states"}
FREQS = {"D", "W", "F", "M", "Q", "A"}
FETCH = {"auto", "manual"}
TRANSFORMS = {"level", "yoy", "mom", "mom_saar", "qoq_saar", "3mma", "12mma", "diff", "share_gdp", "7dma", "7dma_yoy"}
REQUIRED = ["id", "title", "short_title", "area", "source", "licence", "downloadable", "fetch",
            "frequency", "unit", "transforms", "release", "validation", "pages", "verified_against"]


def check_series(path: Path, pages: set[str]) -> list[str]:
    """Return a list of problems for one series yaml."""
    s = yaml.safe_load(path.read_text()) or {}
    errs = [f"missing field '{k}'" for k in REQUIRED if k not in s]
    if errs:
        return errs
    if s["id"] != path.stem:
        errs.append(f"id '{s['id']}' does not match filename")
    if not re.fullmatch(r"[a-z0-9]+(_[a-z0-9]+)*", s["id"]):
        errs.append("id must be lower_snake_case")
    if s["area"] not in AREAS:
        errs.append(f"area '{s['area']}' not in {sorted(AREAS)}")
    if s["frequency"] not in FREQS:
        errs.append(f"frequency '{s['frequency']}' not in {sorted(FREQS)}")
    if s["fetch"] not in FETCH:
        errs.append(f"fetch '{s['fetch']}' not in {sorted(FETCH)}")
    lic = str(s["licence"])
    if not (lic in {"GODL", "show-only", "unverified"} or lic.startswith("other:")):
        errs.append(f"licence '{lic}' must be GODL, show-only, unverified or other:<text>")
    if lic in {"show-only", "unverified"} and s["downloadable"]:
        errs.append(f"{lic} series cannot be downloadable")
    bad_t = set(s["transforms"]) - TRANSFORMS
    if bad_t:
        errs.append(f"unknown transforms {sorted(bad_t)}")
    for p in s["pages"]:
        if p.get("page") not in pages:
            errs.append(f"page '{p.get('page')}' has no checklist in 05-pages/")
    for e in s.get("exclude") or []:
        if not (e.get("period") and len(str(e.get("reason", ""))) >= 30):
            errs.append("each exclude entry needs a period and a reason giving the evidence")
        if e.get("vintage") and not vintage_found(s["id"], str(e["period"]), str(e["vintage"])):
            errs.append(f"exclude {e['period']}: no row stored on {e['vintage']} for that period "
                        "(in the CSV or, once replaced, in the revision log); check the vintage")
    rng = s["validation"].get("range")
    if not (isinstance(rng, list) and len(rng) == 2 and rng[0] < rng[1]):
        errs.append("validation.range must be [min, max]")
    return errs


def vintage_found(sid: str, period: str, vintage: str) -> bool:
    """A vintage exclude must name a row that exists: still stored, or replaced by a later
    value (then the revision log has it as the old vintage). A typo would hide nothing."""
    data = ROOT / "data"
    series = data / "series" / f"{sid}.csv"
    revisions = data / "revisions" / f"{sid}.csv"
    def rows(path: Path) -> list[dict]:
        if not path.exists():
            return []
        with path.open() as f:
            return list(csv.DictReader(f))
    return (any(r["period"] == period and r["vintage"] == vintage for r in rows(series))
            or any(r["period"] == period and r["old_vintage"] == vintage for r in rows(revisions)))


def main() -> int:
    pages = {p.stem for p in PAGES_DIR.glob("*.md") if p.stem != "README"}
    files = sorted(f for f in SERIES_DIR.glob("*.yaml") if not f.name.startswith("_"))
    failed = 0
    for f in files:
        for e in check_series(f, pages):
            print(f"{f.relative_to(ROOT)}: {e}")
            failed += 1
    # The template itself must stay valid, so copies start valid.
    for e in check_series_template(pages):
        print(f"registry/series/_template.yaml: {e}")
        failed += 1
    print(f"registry: {len(files)} series checked, {failed} problem(s)")
    return 1 if failed else 0


def check_series_template(pages: set[str]) -> list[str]:
    """Validate the template, ignoring its id/filename mismatch."""
    errs = check_series(SERIES_DIR / "_template.yaml", pages)
    return [e for e in errs if "does not match filename" not in e]


if __name__ == "__main__":
    sys.exit(main())
