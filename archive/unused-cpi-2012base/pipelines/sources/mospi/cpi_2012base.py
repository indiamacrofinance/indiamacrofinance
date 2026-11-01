"""CPI headline inflation as originally published on the 2012 base (2013-2025): the numbers
RBI was forecasting at the time. Closed series: MoSPI moved to the 2024 base in January 2026.

cpi_headline_inflation (cpi.py) uses MoSPI's 2024-base *back series* for 2014-2024, which
re-estimates those years; RBI's projections of that period targeted the 2012-base figures, so
judging RBI's forecast errors (site_data.cpi_fan) needs these.

API: cpi/getCPIData, base_year 2012, level Group, all-India (state 99), combined; group
"General". About 44 pages; fetched once, then the stored series is re-emitted unchanged.

Series: cpi_inflation_2012base (% y/y as published).
"""
from __future__ import annotations

import pandas as pd

from pipelines.core import Raw, Source
from pipelines.core.store import load_series
from pipelines.sources.mospi._api import pages, rows
from pipelines.sources.mospi.cpi import _float, _period

LAST_PERIOD = "2025-12-01"


class MospiCPI2012(Source):
    name = "mospi_cpi_2012base"
    series_ids = ("cpi_inflation_2012base",)

    def fetch(self) -> list[Raw]:
        stored = load_series("cpi_inflation_2012base")
        if len(stored) and stored["period"].max() >= LAST_PERIOD:
            return []                                   # closed series, already complete
        return pages("cpi/getCPIData", {"base_year": "2012", "level": "Group", "series": "Current",
                                        "state_code": "99", "sector_code": "3"})

    def parse(self, raws: list[Raw]) -> pd.DataFrame:
        if not raws:
            stored = load_series("cpi_inflation_2012base")
            return stored.assign(series_id="cpi_inflation_2012base")[["series_id", "period", "value", "note"]]
        out = []
        for r in rows(raws):
            if r.get("group") == "General" and r.get("sector") == "Combined":
                v = _float(r.get("inflation"))
                if v is not None:
                    out.append({"series_id": "cpi_inflation_2012base", "period": _period(r["year"], r["month"]),
                                "value": v, "note": "published, base 2012"})
        return pd.DataFrame(out).drop_duplicates(["period"], keep="last")


SOURCE = MospiCPI2012()
