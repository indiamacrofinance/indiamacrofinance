"""Reading and writing data/: series CSVs, metadata, status, revision log, raw archive."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from pipelines.core import Raw

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
SERIES = DATA / "series"
META = DATA / "meta"
RAW = DATA / "raw"            # git-ignored; archived monthly as Release assets
REVISIONS = DATA / "revisions"
PANELS = DATA / "panels"            # entity x period data (e.g. states)
STATUS = DATA / "status.json"
COLUMNS = ["period", "value", "vintage", "note"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def archive_raw(source_name: str, raws: list[Raw]) -> list[str]:
    """Save each raw download under data/raw/<source>/ and return the relative paths."""
    paths = []
    folder = RAW / source_name
    folder.mkdir(parents=True, exist_ok=True)
    for raw in raws:
        stamp = raw.fetched_at.strftime("%Y%m%dT%H%M%S")
        path = folder / f"{stamp}-{raw.sha256[:10]}{raw.suffix}"
        if not path.exists():
            path.write_bytes(raw.content)
        paths.append(str(path.relative_to(ROOT)))
    return paths


def excluded_periods(series_id: str) -> set[str]:
    """Periods a person has left out of a series (registry `exclude`, each with a reason)."""
    from pipelines.core import registry
    spec = registry.all_series().get(series_id) or {}
    return {str(e["period"]) for e in spec.get("exclude") or []}


# Daily to fortnightly series: a row dated more than a day after it was stored (the slack is for
# IST dates on UTC runners) cannot be an observation. RBI's home page once dated the 30 October
# G-sec yields "November 30" on 3 November. Monthly and slower series are exempt: forecasts.
EARLY_CHECKED = ("D", "W", "F")


def recorded_early(series_id: str, df: pd.DataFrame) -> pd.Series:
    """Mask of rows stored before their own date (daily to fortnightly series only)."""
    from pipelines.core import registry
    if (registry.all_series().get(series_id) or {}).get("frequency") not in EARLY_CHECKED or df.empty:
        return pd.Series(False, index=df.index)
    gap = pd.to_datetime(df["period"], errors="coerce") - pd.to_datetime(df["vintage"], errors="coerce")
    return gap > pd.Timedelta(days=1)


def published(series_id: str, df: pd.DataFrame) -> pd.DataFrame:
    """The stored rows readers see: without registry-excluded periods and rows recorded early."""
    hidden = df["period"].isin(excluded_periods(series_id)) | recorded_early(series_id, df)
    return df[~hidden].reset_index(drop=True)


def load_series(series_id: str, *, stored: bool = False) -> pd.DataFrame:
    """Rows for a series (empty frame with the right columns if none yet) as readers see them
    (`published`): the site, downloads, derived measures and sources. stored=True gives the CSV
    as it is, for writing it back, since history is never deleted (AGENTS.md rule 8)."""
    path = SERIES / f"{series_id}.csv"
    if not path.exists():
        return pd.DataFrame(columns=COLUMNS)
    df = pd.read_csv(path, dtype={"period": str, "vintage": str, "note": str},
                     keep_default_na=False, na_values={"value": [""]})
    for col in COLUMNS:
        if col not in df:
            df[col] = ""
    df = df[COLUMNS]
    return df if stored else published(series_id, df)


def upsert(series_id: str, new: pd.DataFrame, vintage: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Merge new rows into the stored series. Returns (merged, revised_rows).

    New periods are added; existing periods whose value changed are updated and
    logged; stored periods absent from `new` are kept untouched.
    """
    old = load_series(series_id, stored=True)
    # A row recorded before its own date is replaced by a real value for that period, not
    # logged as a revision of it; until then it stays in the CSV as a record.
    early = old["period"][recorded_early(series_id, old)]
    old = old[~old["period"].isin(set(early) & set(new["period"]))]
    new = new.copy()
    new["vintage"] = vintage
    if "note" not in new:
        new["note"] = ""
    new["note"] = new["note"].fillna("")
    new = new[COLUMNS]

    merged = old.set_index("period")
    incoming = new.set_index("period")
    common = merged.index.intersection(incoming.index)
    changed = common[merged.loc[common, "value"].astype(float).round(10).values
                     != incoming.loc[common, "value"].astype(float).round(10).values]
    revised = pd.DataFrame({
        "period": changed,
        "old_value": merged.loc[changed, "value"].values,
        "new_value": incoming.loc[changed, "value"].values,
        "old_vintage": merged.loc[changed, "vintage"].values,
        "new_vintage": vintage,
    })
    # Unchanged periods keep their original vintage (the date the value first appeared), but
    # take the latest note (e.g. an estimate moving from "Provisional" to "Revised" at the
    # same value).
    unchanged = common.difference(changed)
    merged.loc[unchanged, "note"] = incoming.loc[unchanged, "note"].values
    incoming = incoming.drop(index=unchanged)
    merged = pd.concat([merged.drop(index=changed), incoming]).sort_index()
    return merged.reset_index()[COLUMNS], revised


def write_series(series_id: str, df: pd.DataFrame, revised: pd.DataFrame) -> None:
    SERIES.mkdir(parents=True, exist_ok=True)
    df.to_csv(SERIES / f"{series_id}.csv", index=False)
    if not revised.empty:
        REVISIONS.mkdir(parents=True, exist_ok=True)
        path = REVISIONS / f"{series_id}.csv"
        revised.to_csv(path, mode="a", header=not path.exists(), index=False)


def write_meta(series_id: str, spec: dict, df: pd.DataFrame, raw_paths: list[str],
               urls: list[str]) -> None:
    """Metadata the site build reads: registry fields + latest observation + receipt."""
    META.mkdir(parents=True, exist_ok=True)
    last = df.iloc[-1]
    meta = {
        "id": series_id,
        "title": spec["title"],
        "short_title": spec["short_title"],
        "unit": spec["unit"],
        "frequency": spec["frequency"],
        "base_year": spec.get("base_year"),
        "source": spec["source"],
        "licence": spec["licence"],
        "downloadable": spec["downloadable"],
        "first_period": df["period"].iloc[0],
        "last_period": last["period"],
        "last_value": float(last["value"]),
        "observations": len(df),
        "updated_at": now_iso(),
        "fetched_from": urls,
        "raw_files": raw_paths,
    }
    (META / f"{series_id}.json").write_text(json.dumps(meta, indent=2))


def load_status() -> dict:
    return json.loads(STATUS.read_text()) if STATUS.exists() else {}


def update_status(series_id: str, ok: bool, error: str | None = None,
                  last_period: str | None = None) -> None:
    """Record the outcome of one attempt; failures keep the last success intact."""
    status = load_status()
    entry = status.get(series_id, {})
    entry["last_attempt"] = now_iso()
    if ok:
        entry.update(last_success=entry["last_attempt"], stale=False, last_error=None,
                     last_period=last_period)
    else:
        entry.update(stale=True, last_error=error)
    status[series_id] = entry
    STATUS.write_text(json.dumps(dict(sorted(status.items())), indent=2))


PANEL_COLUMNS = ["entity", "period", "value", "vintage", "note"]


def load_panel(series_id: str) -> pd.DataFrame:
    path = PANELS / f"{series_id}.csv"
    if not path.exists():
        return pd.DataFrame(columns=PANEL_COLUMNS)
    return pd.read_csv(path, dtype={"entity": str, "period": str, "vintage": str, "note": str},
                       keep_default_na=False, na_values={"value": [""]})[PANEL_COLUMNS]


def upsert_panel(series_id: str, new: pd.DataFrame, vintage: str) -> pd.DataFrame:
    """Like upsert(), keyed on (entity, period). Unchanged rows keep their first vintage."""
    old = load_panel(series_id).set_index(["entity", "period"])
    inc = new.assign(vintage=vintage, note=new.get("note", "")).fillna({"note": ""})
    inc = inc.set_index(["entity", "period"])[["value", "vintage", "note"]]
    same = old.index.intersection(inc.index)
    same = same[old.loc[same, "value"].astype(float).round(10).values == inc.loc[same, "value"].astype(float).round(10).values]
    kept = old.loc[same].copy()
    kept["note"] = inc.loc[same, "note"].values          # latest note, first vintage
    merged = pd.concat([old.drop(index=inc.index.intersection(old.index)), inc.drop(index=same), kept])
    return merged.reset_index().sort_values(["entity", "period"])[PANEL_COLUMNS]


def write_panel(series_id: str, df: pd.DataFrame) -> None:
    PANELS.mkdir(parents=True, exist_ok=True)
    df.to_csv(PANELS / f"{series_id}.csv", index=False)
