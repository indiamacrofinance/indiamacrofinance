"""Import cover of foreign exchange reserves, monthly: how many months of merchandise imports
the reserves would pay for. Site calculation.

Reserves at the end of each month (the last weekly figure in the month, RBI Weekly Statistical
Supplement) divided by average monthly merchandise imports over the twelve months to that
month (Department of Commerce, US$). Months missing from our imports data are skipped: the
average needs at least 10 of the 12 months (MIN_MONTHS), otherwise that month has no value. RBI's own measure (`reserves_import_cover`, Handbook,
annual, end-March) uses balance-of-payments imports, so the two differ a little.
"""
from __future__ import annotations

import pandas as pd

from pipelines.core import Raw, Source
from pipelines.core.store import load_series

MIN_MONTHS = 10


def import_cover(reserves: pd.DataFrame, imports: pd.DataFrame) -> pd.DataFrame:
    """period (month), value (months of imports)."""
    res = reserves.assign(month=pd.to_datetime(reserves["period"]).dt.to_period("M")).sort_values("period")
    month_end = res.groupby("month")["value"].last().astype(float)
    imp = imports.assign(month=pd.to_datetime(imports["period"]).dt.to_period("M")).set_index("month")["value"].astype(float).sort_index()
    imp = imp.reindex(pd.period_range(imp.index.min(), imp.index.max(), freq="M"))   # missing months stay NaN
    avg12 = imp.rolling(12, min_periods=MIN_MONTHS).mean()       # mean of the months present in the window
    both = pd.concat({"res": month_end, "imp": avg12}, axis=1).dropna()
    return pd.DataFrame({"period": both.index.to_timestamp().strftime("%Y-%m-%d"), "value": (both["res"] / both["imp"]).round(1)})


class ImportCover(Source):
    name = "derived_import_cover"
    derived = True
    series_ids = ("import_cover_months",)

    def fetch(self) -> list[Raw]:
        return []

    def parse(self, raws: list[Raw]) -> pd.DataFrame:
        out = import_cover(load_series("fx_reserves_total"), load_series("merch_imports"))
        return out.assign(series_id="import_cover_months",
                          note="site calculation: month-end reserves / average monthly merchandise imports, last 12 months")


SOURCE = ImportCover()
