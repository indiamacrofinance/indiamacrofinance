"""Underlying inflation from the 358 CPI items: RBI's MPR measures, rebuilt. Original measures.

Inputs: item indices and published item inflation (pipelines/sources/mospi/cpi_items.py) and
item weights recovered from MoSPI's index tree (registry/weights/cpi2024_items.csv, made by
scripts/estimate_cpi_item_weights.py). Definitions follow RBI's Monetary Policy Report
(October 2026, Chapter IV); every measure below matches RBI's published values for
January-August 2026 to rounding (tests/sources/test_cpi_underlying.py).

  Exclusion measures (y/y of the weighted index of the items kept; Table IV.1)
    cpi_ex_food_fuel_pm_inflation   excluding food and beverages (division 01), fuel (group
                                    04.5 and class 07.2.2: petrol, diesel, CNG) and precious
                                    metals (gold and silver jewellery)
  Trimmed means and weighted median (on published item inflation, base weights; Table IV.2)
    cpi_trimmed_mean_{5,10,25}      drop x% of the basket by weight in total (x/2 from each
                                    tail of the distribution of item inflation), average the rest
    cpi_weighted_median             inflation of the item at the 50th weighted percentile
  Diffusion indices (Box IV.1): weighted share of the basket with inflation below 2%, 2-4%,
    4-6%, 6% and above; for the whole basket and for core (CPI excluding food and fuel)
    cpi_diffusion_{headline,core}_{below2,2to4,4to6,above6}
  Goods and services (y/y of the weighted index; item code segment 5: 1 goods, 2 services)
    cpi_goods_inflation, cpi_services_inflation
  cpi_precious_metals_contribution  percentage points of headline inflation from gold and
                                    silver jewellery
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pipelines.core import Raw, Source
from pipelines.core.store import ROOT, load_panel

WEIGHTS = ROOT / "registry" / "weights" / "cpi2024_items.csv"
PRECIOUS_METALS = ("13.2.1.1.1.01", "13.2.1.1.1.02")      # gold /diamond /platinum jewellery; silver jewellery
FUEL_PREFIXES = ("04.5", "07.2.2")
BUCKETS = (("below2", -np.inf, 2), ("2to4", 2, 4), ("4to6", 4, 6), ("above6", 6, np.inf))
NOTE = "site calculation (Original); item weights in registry/weights/cpi2024_items.csv"


def load_items() -> pd.DataFrame:
    w = pd.read_csv(WEIGHTS, dtype={"code": str, "parent": str})
    return w[w.level == 5].set_index("code")


def masks(items: pd.DataFrame) -> dict[str, pd.Series]:
    code = items.index.to_series()
    food = code.str.startswith("01")
    fuel = code.str.startswith(FUEL_PREFIXES)
    pm = code.isin(PRECIOUS_METALS)
    return {"all": pd.Series(True, index=code.index), "core": ~food & ~fuel, "core_ex_pm": ~food & ~fuel & ~pm,
            "goods": items.kind.eq("good"), "services": items.kind.eq("service"), "pm": pm}


def year_ago(period: str) -> str:
    return f"{int(period[:4]) - 1}{period[4:]}"


def yoy(idx: pd.DataFrame, w: pd.Series, period: str) -> float | None:
    """y/y % of the weighted index of the items in w."""
    then = year_ago(period)
    if then not in idx.index:
        return None
    c = w.index
    return float(100 * ((w * idx.loc[period, c]).sum() / (w * idx.loc[then, c]).sum() - 1))


def trimmed_mean(rates: pd.Series, w: pd.Series, pct: float) -> float:
    """Weighted mean after dropping pct% of the weight in total, half from each tail (items
    straddling a cut-off count in part)."""
    o = rates.sort_values()
    ww = w[o.index] / w.sum()
    cum = ww.cumsum()
    lo, hi = pct / 200, 1 - pct / 200
    keep = (np.minimum(cum, hi) - np.maximum(cum - ww, lo)).clip(lower=0)
    return float((o * keep).sum() / keep.sum())


def weighted_median(rates: pd.Series, w: pd.Series) -> float:
    o = rates.sort_values()
    cum = (w[o.index] / w.sum()).cumsum()
    return float(o[cum >= 0.5].iloc[0])


def diffusion(rates: pd.Series, w: pd.Series) -> dict[str, float]:
    """Weighted share (%) of items in each inflation bucket: [lo, hi)."""
    return {name: float(100 * w[(rates >= lo) & (rates < hi)].sum() / w.sum()) for name, lo, hi in BUCKETS}


def compute(idx: pd.DataFrame, infl: pd.DataFrame, items: pd.DataFrame) -> pd.DataFrame:
    """idx, infl: period x item code. Returns long rows (series_id, period, value)."""
    m = masks(items)
    w = items["weight"]
    out = []

    def add(sid, period, value):
        if value is not None and np.isfinite(value):
            out.append({"series_id": sid, "period": period, "value": round(value, 2)})

    for period in infl.index:
        r = infl.loc[period, items.index]
        if r.isna().any():
            continue
        for pct in (5, 10, 25):
            add(f"cpi_trimmed_mean_{pct}", period, trimmed_mean(r, w, pct))
        add("cpi_weighted_median", period, weighted_median(r, w))
        for basket in ("headline", "core"):
            sel = m["all"] if basket == "headline" else m["core"]
            for name, share in diffusion(r[sel], w[sel]).items():
                add(f"cpi_diffusion_{basket}_{name}", period, share)
        if period in idx.index:
            add("cpi_ex_food_fuel_pm_inflation", period, yoy(idx, w[m["core_ex_pm"]], period))
            add("cpi_goods_inflation", period, yoy(idx, w[m["goods"]], period))
            add("cpi_services_inflation", period, yoy(idx, w[m["services"]], period))
            then = year_ago(period)
            if then in idx.index:
                pm = w[m["pm"]]
                base = (w * idx.loc[then, items.index]).sum()
                add("cpi_precious_metals_contribution", period,
                    float(100 * (pm * (idx.loc[period, pm.index] - idx.loc[then, pm.index])).sum() / base))
    return pd.DataFrame(out)


SERIES = ("cpi_trimmed_mean_5", "cpi_trimmed_mean_10", "cpi_trimmed_mean_25", "cpi_weighted_median",
          "cpi_ex_food_fuel_pm_inflation", "cpi_goods_inflation", "cpi_services_inflation",
          "cpi_precious_metals_contribution",
          *(f"cpi_diffusion_{b}_{n}" for b in ("headline", "core") for n, _, _ in BUCKETS))


class CPIUnderlying(Source):
    name = "derived_cpi_underlying"
    derived = True
    series_ids = SERIES

    def fetch(self) -> list[Raw]:
        return []

    def parse(self, raws: list[Raw]) -> pd.DataFrame:
        items = load_items()
        idx = load_panel("cpi_item_index").pivot_table(index="period", columns="entity", values="value")
        infl = load_panel("cpi_item_inflation").pivot_table(index="period", columns="entity", values="value")
        missing = set(items.index) - set(idx.columns)
        if missing:
            raise ValueError(f"{len(missing)} weighted CPI items have no stored index, e.g. {sorted(missing)[:3]}")
        out = compute(idx.astype(float), infl.astype(float), items)
        out["note"] = NOTE
        return out


SOURCE = CPIUnderlying()
