"""Validation of parsed rows before anything is written.

Any problem returned here blocks publishing for that series; the stored CSV
is left as it was (AGENTS.md hard rule 3).
"""
from __future__ import annotations

import pandas as pd


def validate(series_id: str, new: pd.DataFrame, spec: dict, *, panel: bool = False) -> list[str]:
    """Return a list of problems with the new rows for one series (empty = ok)."""
    problems = []
    if new.empty:
        return [f"{series_id}: parser returned no rows"]
    keys = ["entity", "period"] if panel else ["period"]
    missing = sorted(set(keys + ["value"]) - set(new.columns))
    if missing:
        return [f"{series_id}: parser missing columns {missing}"]
    if new.duplicated(keys).any():
        dups = new.loc[new.duplicated(keys), keys].astype(str).values.tolist()[:5]
        problems.append(f"{series_id}: duplicate {'(entity, period) rows' if panel else 'periods'} {dups}")
    for key in keys:
        if (new[key].isna() | new[key].astype(str).str.strip().eq("")).any():
            problems.append(f"{series_id}: missing {key}")
    if not pd.api.types.is_numeric_dtype(new["value"]):
        return problems + [f"{series_id}: values must be numeric"]
    if new["value"].isna().any():
        problems.append(f"{series_id}: {int(new['value'].isna().sum())} missing values")
    lo, hi = spec["validation"]["range"]
    bad = new[(new["value"] < lo) | (new["value"] > hi)]
    if not bad.empty:
        sample = bad.head(3)[["period", "value"]].astype(str).values.tolist()
        problems.append(f"{series_id}: {len(bad)} values outside plausible range [{lo}, {hi}], e.g. {sample}")
    return problems


def revisions(old: pd.DataFrame, new: pd.DataFrame, threshold_pct: float) -> pd.DataFrame:
    """Rows whose stored value changed by more than threshold_pct percent."""
    if old.empty:
        return old.iloc[0:0]
    m = old.merge(new, on="period", suffixes=("_old", "_new"))
    changed = m[m["value_old"] != m["value_new"]].copy()
    base = changed["value_old"].abs().where(changed["value_old"] != 0, 1)
    changed["pct"] = (changed["value_new"] - changed["value_old"]).abs() / base * 100
    return changed[changed["pct"] > threshold_pct]
