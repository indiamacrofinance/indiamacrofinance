"""Lending and deposit rates of scheduled commercial banks, monthly: how policy rate changes
reach borrowers and savers (transmission). RBI's Monetary Policy Report uses these tables
(Table II.7-II.8, Charts II.28-II.32).

RBI's monthly press release "Lending and Deposit Rates of Scheduled Commercial Banks – <Month>
<YYYY>" links one workbook (MLDRSCB<ddmmyyyy>ENG.xlsx) that carries the whole history in
each table, so only the latest release is read. Tables are found by their printed titles:

  walr_outstanding        weighted average lending rate, outstanding rupee loans (from 2012)
  walr_fresh              WALR on fresh rupee loans sanctioned in the month (from 2014)
  wadtdr_outstanding      weighted average domestic term deposit rate, outstanding (from 2013)
  wadtdr_fresh            WADTDR on fresh term deposits (from 2020, monthly from 2021)
  mclr_1y_median          median one-year MCLR across banks in the group, month end
  loan_benchmark_share    share of outstanding floating-rate loans (all SCBs) linked to each
                          benchmark: EBLR (external, e.g. repo), MCLR, base rate, others; quarterly
  walr_outstanding_sector / walr_fresh_sector   WALR by borrowing sector (from April 2020)

All are panels: entity = bank group (public sector, private sector, foreign, all SCBs) or
sector or benchmark; value in per cent.
"""
from __future__ import annotations

import io
import re

import pandas as pd

from pipelines.core import Raw, Source
from pipelines.core.http import fetch_raw, get
from pipelines.sources.rbi._press import RELEASE, releases

TITLE = "Lending and Deposit Rates of Scheduled Commercial Banks"
GROUPS = {"public sector banks": "Public sector banks", "private sector banks": "Private sector banks",
          "foreign banks": "Foreign banks", "scheduled commercial banks": "All scheduled commercial banks"}
# (words that must all appear in the table's title block) -> panel
TABLES = [
    (("bank group", "lending rates", "outstanding rupee loans"), "walr_outstanding"),
    (("bank group", "lending rates", "fresh rupee loans"), "walr_fresh"),
    (("bank group", "deposit rates", "outstanding rupee term deposits"), "wadtdr_outstanding"),
    (("bank group", "deposit rates", "fresh rupee term deposits"), "wadtdr_fresh"),
    (("bank group", "mclr"), "mclr_1y_median"),
    (("share", "benchmarks"), "loan_benchmark_share"),
    (("sector-wise", "outstanding rupee loans"), "walr_outstanding_sector"),
    (("sector-wise", "fresh rupee loans"), "walr_fresh_sector"),
]


def title_of(df: pd.DataFrame) -> str:
    return " ".join(str(v) for v in df.iloc[:4].values.ravel() if isinstance(v, str)).lower()


def panel_of(df: pd.DataFrame) -> str | None:
    t = re.sub(r"\s+", " ", title_of(df)).replace("group-wise", "group wise").replace("groupwise", "group wise")
    if not re.match(r"table \d+\s*:", t):                    # skip the contents sheet, which lists every title
        return None
    return next((p for words, p in TABLES if all(w in t for w in words)), None)


def period_of(v) -> str | None:
    if isinstance(v, pd.Timestamp) or hasattr(v, "year"):
        return f"{v.year:04d}-{v.month:02d}-01"
    return None


def parse_table(df: pd.DataFrame, panel: str) -> list[dict]:
    """Header row = the row whose first cell mentions "Month". Two-row headers come two ways:
    group names on that row with sub-headings below (MCLR: Min/Max/Median), or group names on the
    row above with sub-headings on it (benchmark shares: Base Rate/MCLR/EBLR). Group names are
    carried right across their merged cells."""
    head = next(i for i in df.index if "month" in str(df.loc[i, df.columns[0]]).lower())
    names = df.loc[head].tolist()
    groups = pd.Series(df.loc[head - 1].tolist()).ffill().tolist() if head - 1 in df.index else [None] * len(names)
    below = df.index[df.index > head]
    if len(below) and period_of(df.loc[below[0], df.columns[0]]) is None:
        groups, names = pd.Series(names).ffill().tolist(), df.loc[below[0]].tolist()
        head = below[0]
    cols = {}
    for k, c in enumerate(df.columns[1:], start=1):
        name, group = str(names[k]).strip(), str(groups[k]).strip().lower()
        if panel == "mclr_1y_median":
            if name.lower() == "median" and group in GROUPS:
                cols[c] = GROUPS[group]
        elif panel == "loan_benchmark_share":
            if group == "scheduled commercial banks" and name.lower() != "total":
                cols[c] = name
        elif panel.endswith("_sector"):
            if name and name.lower() != "nan":
                cols[c] = name
        elif name.lower() in GROUPS:
            cols[c] = GROUPS[name.lower()]
    if not cols:
        raise ValueError(f"{panel}: no columns recognised")
    rows = []
    for i in df.index[df.index > head]:
        period = period_of(df.loc[i, df.columns[0]])
        if not period:
            continue
        for c, entity in cols.items():
            v = pd.to_numeric(df.loc[i, c], errors="coerce")
            if pd.notna(v):
                rows.append({"series_id": panel, "entity": entity, "period": period, "value": round(float(v), 3)})
    return rows


def parse_book(content: bytes) -> list[dict]:
    book = pd.ExcelFile(io.BytesIO(content))
    rows, seen = [], set()
    for sheet in book.sheet_names:
        df = pd.read_excel(book, sheet, header=None).dropna(how="all").dropna(axis=1, how="all")
        if df.empty:
            continue
        panel = panel_of(df)
        if panel and panel not in seen:
            seen.add(panel)
            rows += parse_table(df, panel)
    missing = {p for _, p in TABLES} - seen
    if missing:
        raise ValueError(f"lending/deposit rate tables not found: {sorted(missing)}")
    return rows


class RbiLendingRates(Source):
    name = "rbi_lending_rates"
    panel = True
    series_ids = tuple(p for _, p in TABLES)

    def fetch(self) -> list[Raw]:
        found = releases(lambda t: t.startswith(TITLE), 3)
        for prid in sorted(found, reverse=True):              # newest release with a workbook
            link = re.search(r'href="([^"]+MLDRSCB[^"]+\.xlsx)"', get(RELEASE.format(prid=prid)).text, re.I)
            if link:
                return [fetch_raw(link.group(1), suffix=".xlsx")]
        raise RuntimeError(f"no '{TITLE}' workbook in the last 3 months of releases")

    def parse(self, raws: list[Raw]) -> pd.DataFrame:
        df = pd.DataFrame(parse_book(raws[0].content))
        df["note"] = ""
        return df.drop_duplicates(["series_id", "entity", "period"], keep="last")


SOURCE = RbiLendingRates()
