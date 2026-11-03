"""Real policy rate, monthly: the repo rate in force at the end of each month minus CPI
inflation (y/y) in that month. Positive = policy is tight relative to current inflation.
Ex post (uses inflation as measured, not as expected). Site calculation.
"""
from __future__ import annotations

import pandas as pd

from pipelines.core import Raw, Source
from pipelines.core.store import load_series


def real_rate(repo: pd.DataFrame, cpi: pd.DataFrame) -> pd.DataFrame:
    """period (month), value (percentage points)."""
    r = repo[["period", "value"]].astype({"value": float}).assign(d=lambda x: pd.to_datetime(x["period"])).sort_values("d")
    c = cpi[["period", "value"]].astype({"value": float}).assign(d=lambda x: pd.to_datetime(x["period"]) + pd.offsets.MonthEnd(0))
    c = c[c["d"] >= r["d"].min()].sort_values("d")
    both = pd.merge_asof(c, r[["d", "value"]].rename(columns={"value": "repo"}), on="d", direction="backward").dropna()
    return pd.DataFrame({"period": both["period"].values, "value": (both["repo"] - both["value"]).round(2).values})


class RealRate(Source):
    name = "derived_real_rate"
    derived = True
    series_ids = ("real_repo_rate",)

    def fetch(self) -> list[Raw]:
        return []

    def parse(self, raws: list[Raw]) -> pd.DataFrame:
        out = real_rate(load_series("repo_rate"), load_series("cpi_headline_inflation"))
        return out.assign(series_id="real_repo_rate", note="site calculation: repo rate at month end minus CPI inflation (y/y)")


SOURCE = RealRate()
