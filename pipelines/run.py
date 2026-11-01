"""Command-line runner: fetch → archive → parse → validate → publish.

    python -m pipelines.run <source-or-series-id> [...]
    python -m pipelines.run --fetch auto      # every source whose series are fetch: auto
    python -m pipelines.run --fetch manual    # the India-only queue (make india-update)
    python -m pipelines.run --list

Exit code is 1 if any series failed; failures are listed in data/raw/last_run.json
so the workflow can open scraper-broken issues.
"""
from __future__ import annotations

import argparse
import importlib
import json
import pkgutil
import sys
import traceback
from datetime import date

import pipelines.sources
from pipelines.core import Source
from pipelines.core import registry, store
from pipelines.core.validate import revisions, validate


def discover() -> dict[str, Source]:
    """Import every module under pipelines/sources and collect their SOURCE objects."""
    found: dict[str, Source] = {}
    for mod in pkgutil.walk_packages(pipelines.sources.__path__, "pipelines.sources."):
        module = importlib.import_module(mod.name)
        src = getattr(module, "SOURCE", None)
        if isinstance(src, Source):
            if src.name in found:
                raise SystemExit(f"duplicate source name {src.name}")
            found[src.name] = src
    return found


def fetch_mode(src: Source) -> str:
    """A source is manual if any of its registered series is fetch: manual."""
    specs = registry.all_series()
    modes = {specs[s]["fetch"] for s in src.series_ids if s in specs}
    return "manual" if "manual" in modes else "auto"


def run_source(src: Source) -> list[dict]:
    """Run one source end to end; returns one failure dict per failed series."""
    specs = registry.all_series()
    unregistered = [s for s in src.series_ids if s not in specs]
    if unregistered:
        return [{"series_id": s, "source": src.name, "error": "no registry/series yaml"}
                for s in unregistered]
    try:
        raws = src.fetch()
        raw_paths = store.archive_raw(src.name, raws)
        parsed = src.parse(raws)
        required = {"series_id", "period", "value"} | ({"entity"} if src.panel else set())
        missing = required - set(parsed.columns)
        if missing:
            raise ValueError(f"parser missing columns {sorted(missing)}")
    except Exception as e:  # noqa: BLE001 - any failure must mark the series stale, not crash the run
        err = f"{type(e).__name__}: {e}"
        traceback.print_exc()
        for s in src.series_ids:
            store.update_status(s, ok=False, error=err)
        return [{"series_id": s, "source": src.name, "error": err} for s in src.series_ids]

    if src.panel:
        return run_panel(src, parsed, specs)

    failures = []
    vintage = date.today().isoformat()
    for sid in src.series_ids:
        spec = specs[sid]
        new = parsed[parsed["series_id"] == sid].drop(columns="series_id").sort_values("period")
        # Periods a person has excluded (registry `exclude`, with a reason) are never published.
        excluded = {str(e["period"]) for e in spec.get("exclude") or []}
        if excluded:
            new = new[~new["period"].isin(excluded)]
        problems = validate(sid, new, spec)
        if problems:
            err = "; ".join(problems)
            store.update_status(sid, ok=False, error=err)
            failures.append({"series_id": sid, "source": src.name, "error": err})
            print(f"  FAIL {sid}: {err}")
            continue
        old = store.load_series(sid)
        merged, revised = store.upsert(sid, new, vintage)
        big = revisions(old[["period", "value"]].astype({"value": float}),
                        new[["period", "value"]], spec["validation"]["revision_alert"])
        store.write_series(sid, merged, revised)
        urls = sorted({r.url for r in raws}) or [f"derived: {src.name}"]
        store.write_meta(sid, spec, merged, raw_paths, urls)
        store.update_status(sid, ok=True, last_period=merged["period"].iloc[-1])
        added = len(merged) - len(old)
        print(f"  ok   {sid}: {len(merged)} obs (+{added} new, {len(revised)} revised), "
              f"latest {merged['period'].iloc[-1]} = {merged['value'].iloc[-1]}")
        if not big.empty:
            print(f"  NOTE {sid}: {len(big)} revisions above {spec['validation']['revision_alert']}%")
    return failures


def run_panel(src: Source, parsed, specs: dict) -> list[dict]:
    """Validate and publish entity x period panels (data/panels/<id>.csv)."""
    failures = []
    vintage = date.today().isoformat()
    for sid in src.series_ids:
        spec = specs[sid]
        new = parsed[parsed["series_id"] == sid].drop(columns="series_id")
        problems = validate(sid, new, spec, panel=True)
        if problems:
            err = "; ".join(problems)
            store.update_status(sid, ok=False, error=err)
            failures.append({"series_id": sid, "source": src.name, "error": err})
            print(f"  FAIL {sid}: {err}")
            continue
        merged = store.upsert_panel(sid, new, vintage)
        store.write_panel(sid, merged)
        store.update_status(sid, ok=True, last_period=merged["period"].max())
        print(f"  ok   {sid}: {merged['entity'].nunique()} entities, {len(merged)} rows, "
              f"latest {merged['period'].max()}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("targets", nargs="*", help="source names or series ids")
    parser.add_argument("--fetch", choices=["auto", "manual"], help="run all sources of this fetch mode")
    parser.add_argument("--bot", help="run one data bot's sources (registry/bots.yaml)")
    parser.add_argument("--list", action="store_true", help="list sources and their series")
    args = parser.parse_args()

    sources = discover()
    if args.list:
        for name, src in sorted(sources.items()):
            print(f"{name} [{fetch_mode(src)}]: {', '.join(src.series_ids)}")
        return 0

    chosen: list[Source] = []
    if args.fetch:
        chosen = [s for s in sources.values() if fetch_mode(s) == args.fetch]
    targets = list(args.targets)
    if args.bot:
        import yaml
        bots = yaml.safe_load((store.ROOT / "registry" / "bots.yaml").read_text())["bots"]
        if args.bot not in bots:
            raise SystemExit(f"unknown bot {args.bot!r}; see registry/bots.yaml")
        targets += bots[args.bot]["sources"]
    for t in targets:
        match = sources.get(t) or next((s for s in sources.values() if t in s.series_ids), None)
        if match is None:
            raise SystemExit(f"unknown source or series id: {t}")
        if match not in chosen:
            chosen.append(match)
    if not chosen:
        parser.print_help()
        return 2
    # Downloads first, then derived measures, so they compute from fresh inputs.
    chosen.sort(key=lambda s: s.derived)

    failures = []
    for src in chosen:
        print(f"[{src.name}]")
        failures += run_source(src)

    store.RAW.mkdir(parents=True, exist_ok=True)
    (store.RAW / "last_run.json").write_text(json.dumps(
        {"at": store.now_iso(), "sources": [s.name for s in chosen], "failures": failures}, indent=2))
    print(f"done: {len(chosen)} source(s), {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
