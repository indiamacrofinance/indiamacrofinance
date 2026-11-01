"""Valuation of the BSE Sensex, monthly: average price/earnings and price/book ratios, from
RBI's Handbook of Statistics on the Indian Economy (data from BSE Ltd.).

Handbook tables, found by number on the Handbook page (see general_government.py):
  244 Average Price/Earning Ratio of BSE SENSEX
  245 Average Price/Book Value Ratio of BSE SENSEX
Layout: one row per financial year ("2025-26"), columns Apr. ... Mar. and Annual; "-" for
months not yet in. Each edition carries about five years, so the store keeps building the
history. The Handbook is updated once a year, so the latest month lags by a few months.

Series: sensex_pe, sensex_pb (monthly averages of daily ratios).
"""
from __future__ import annotations

import io
import re

import pandas as pd

from pipelines.core import Raw, Source
from pipelines.core.http import fetch_raw, get
from pipelines.sources.rbi.general_government import PAGE, table_links

TABLES = {244: "sensex_pe", 245: "sensex_pb"}
MONTHS = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
FY = re.compile(r"^(\d{4})-\d{2}$")


def parse_table(content: bytes, sid: str) -> list[dict]:
    df = pd.read_excel(io.BytesIO(content), header=None).dropna(how="all").dropna(axis=1, how="all")
    head = next(i for i in df.index if str(df.loc[i, df.columns[0]]).strip().lower().startswith("year"))
    cols = {}
    for c in df.columns[1:]:
        name = str(df.loc[head, c]).strip().rstrip(".")[:3]
        if name in MONTHS:
            cols[c] = MONTHS.index(name)
    if len(cols) != 12:
        raise ValueError(f"{sid}: expected 12 month columns, found {len(cols)}")
    rows = []
    for i in df.index[df.index > head]:
        fy = FY.match(str(df.loc[i, df.columns[0]]).strip())
        if not fy:
            continue
        start = int(fy.group(1))
        for c, k in cols.items():
            v = pd.to_numeric(df.loc[i, c], errors="coerce")
            if pd.notna(v):
                year, month = (start, k + 4) if k < 9 else (start + 1, k - 8)
                rows.append({"series_id": sid, "period": f"{year:04d}-{month:02d}-01", "value": float(v)})
    return rows


class HandbookValuation(Source):
    name = "rbi_handbook_valuation"
    series_ids = tuple(TABLES.values())

    def fetch(self) -> list[Raw]:
        links = table_links(get(PAGE).text, TABLES)
        if set(TABLES) - set(links):
            raise RuntimeError(f"Handbook tables not found: {sorted(set(TABLES) - set(links))}")
        return [fetch_raw(links[n], suffix=f".t{n}.xlsx") for n in sorted(TABLES)]

    def parse(self, raws: list[Raw]) -> pd.DataFrame:
        rows = []
        for n, raw in zip(sorted(TABLES), raws):
            rows += parse_table(raw.content, TABLES[n])
        df = pd.DataFrame(rows)
        df["note"] = "BSE Ltd., via RBI Handbook of Statistics"
        return df


SOURCE = HandbookValuation()
