"""CPI (base 2024) for every item in the basket, all-India combined, monthly.

Same API as cpi.py (cpi/getCPIData, current series). Each month has 668 records: 12
divisions, then groups, classes, sub-classes and 358 items. Codes nest (an item's code
extends its parent's, e.g. 13.2.1.1.1.01 "Gold /diamond /platinum jewellery" under
13.2.1.1), and the fifth segment of an item code is 1 for goods and 2 for services (308 and
50 items, matching MoSPI's count). Published y/y inflation per item starts January 2026;
indices start January 2025.

Two panels, entity = item code (names, parents and weights: registry/weights/cpi2024_items.csv):
  cpi_item_index      index, 2024 = 100
  cpi_item_inflation  % on a year earlier, as published
The first run fetches every month (~140 pages); later runs fetch the last three months only.
Feeds pipelines/sources/derived/cpi_underlying.py.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from pipelines.core import Raw, Source
from pipelines.core.store import load_panel
from pipelines.sources.mospi._api import pages, rows
from pipelines.sources.mospi.cpi import _float, _period

ENDPOINT = "cpi/getCPIData"
BASE = {"base_year": "2024", "state_code": "1", "sector_code": "3", "series": "Current"}
DIVISIONS = range(1, 13)           # API division codes 1-12 (published codes 01-11 and 13)
RECENT_MONTHS, MIN_HISTORY = 3, 20


def recent_months(today: date, n: int = RECENT_MONTHS) -> list[tuple[int, int]]:
    """(year, month) for the n months before today's month, newest first."""
    y, m, out = today.year, today.month, []
    for _ in range(n):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        out.append((y, m))
    return out


class MospiCPIItems(Source):
    name = "mospi_cpi_items"
    panel = True
    series_ids = ("cpi_item_index", "cpi_item_inflation")

    def fetch(self) -> list[Raw]:
        if load_panel("cpi_item_index")["period"].nunique() < MIN_HISTORY:
            return [r for d in DIVISIONS for r in pages(ENDPOINT, {**BASE, "division_code": str(d)})]
        return [r for y, m in recent_months(date.today())
                for r in pages(ENDPOINT, {**BASE, "year": str(y), "month_code": str(m)})]

    def parse(self, raws: list[Raw]) -> pd.DataFrame:
        out = []
        for r in rows(raws):
            if r.get("sector") != "Combined" or not r.get("item") or not r.get("code"):
                continue
            period = _period(r["year"], r["month"])
            for sid, key in (("cpi_item_index", "index"), ("cpi_item_inflation", "inflation")):
                v = _float(r.get(key))
                if v is not None:
                    out.append({"series_id": sid, "entity": r["code"], "period": period, "value": v,
                                "note": ""})
        if not out:
            raise ValueError("no CPI item rows in the response")
        return pd.DataFrame(out).drop_duplicates(["series_id", "entity", "period"], keep="last")


SOURCE = MospiCPIItems()
