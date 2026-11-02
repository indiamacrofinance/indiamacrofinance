"""Net investment by foreign portfolio investors (FPIs), daily, in US$ million, from NSDL.

Page: https://www.fpi.nsdl.co.in/web/Reports/Latest.aspx, "Daily Trends in FPI Investments
on <date>": one table for the latest reporting date only (custodians' confirmed trades up to
the previous trading day), so the history starts when this source was added (2 Nov 2026)
and grows by a day each business morning. Rows by category and route; we keep the
sub-totals, in NSDL's own US$ conversion:
    Equity  Sub-total                         -> fpi_daily_equity_usd
    Debt-General Limit, Debt-VRR, Debt-FAR    -> fpi_daily_debt_usd (sum of sub-totals)
    the final Total row (all categories)      -> fpi_daily_total_usd
Negative numbers are printed in brackets: (85.22).
"""
from __future__ import annotations

import hashlib
import io
from datetime import datetime, timezone

import httpx
import pandas as pd

from pipelines.core import Raw, Source
from pipelines.core.http import HEADERS

URL = "https://www.fpi.nsdl.co.in/web/Reports/Latest.aspx"


def num(v) -> float:
    s = str(v).replace(",", "").strip()
    neg = s.startswith("(") and s.endswith(")")
    return -float(s.strip("()")) if neg else float(s)


def parse_page(content: bytes) -> list[dict]:
    html = content.decode("utf-8", "ignore")
    tables = [t for t in pd.read_html(io.StringIO(html))
              if any("Daily Trends in FPI Investments" in " ".join(map(str, c if isinstance(c, tuple) else (c,)))
                     for c in t.columns)]
    if not tables:
        raise ValueError("NSDL: 'Daily Trends in FPI Investments' table not found")
    t = tables[0]
    t.columns = [str(c[-1]) if isinstance(c, tuple) else str(c) for c in t.columns]
    date_col, cat_col, route_col = t.columns[0], t.columns[1], t.columns[2]
    usd_col = next(c for c in t.columns if "US($)" in c)
    t = t[t[date_col].astype(str).str.match(r"\d{1,2}-[A-Za-z]{3}-\d{4}")]
    if t.empty:
        raise ValueError("NSDL: no dated rows in the daily table")
    day = datetime.strptime(str(t[date_col].iloc[0]), "%d-%b-%Y").strftime("%Y-%m-%d")
    sub = t[t[route_col].astype(str).str.strip() == "Sub-total"]
    cat = sub[cat_col].astype(str).str.strip()
    equity = sub[cat == "Equity"][usd_col]
    debt = sub[cat.str.startswith("Debt")][usd_col]
    total = t[t[route_col].astype(str).str.strip() == "Total"][usd_col]
    if equity.empty or debt.empty or total.empty:
        raise ValueError(f"NSDL {day}: equity/debt/total rows not found")
    note = "NSDL daily trends, US$ at NSDL's conversion rate"
    return [{"series_id": "fpi_daily_equity_usd", "period": day, "value": round(num(equity.iloc[0]), 2), "note": note},
            {"series_id": "fpi_daily_debt_usd", "period": day, "value": round(sum(num(v) for v in debt), 2), "note": note},
            {"series_id": "fpi_daily_total_usd", "period": day, "value": round(num(total.iloc[-1]), 2), "note": note}]


class NsdlFpiDaily(Source):
    name = "nsdl_fpi_daily"
    series_ids = ("fpi_daily_equity_usd", "fpi_daily_debt_usd", "fpi_daily_total_usd")

    def fetch(self) -> list[Raw]:
        r = httpx.get(URL, headers=HEADERS, timeout=60, follow_redirects=True)
        r.raise_for_status()
        return [Raw(r.content, URL, datetime.now(timezone.utc), hashlib.sha256(r.content).hexdigest(), ".html")]

    def parse(self, raws: list[Raw]) -> pd.DataFrame:
        return pd.DataFrame([row for raw in raws for row in parse_page(raw.content)])


SOURCE = NsdlFpiDaily()
