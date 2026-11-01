"""Sectoral deployment of bank credit, monthly, from RBI's press releases.

Releases are titled "Sectoral Deployment of Bank Credit – August 2026" and found through the
press-release index (_press.releases); each links an XLSX ("SIBC<ddmmyyyy>ENG.xlsx"). Sheet
"Statement 1" has one row per sector, outstanding amounts on several dates, then
"Variation (Year-on-Year)" in % for a year earlier and for the latest month. Each block of
rows has its own date header (bank credit uses fortnightly reporting dates, the sectors use
the last reporting day), e.g. "31.Aug,2026 / 22.Aug,2025": the month of the first date is
the period, and the earlier column is the same month a year before. So each release gives two growth rates per sector (the month and a year
earlier); the newest release wins.

Series (% y/y as published): credit_nonfood_growth, credit_agri_growth,
credit_industry_growth, credit_services_growth, credit_nbfc_growth, credit_personal_growth,
credit_housing_growth, credit_vehicle_growth, credit_gold_growth, credit_cards_growth.
"""
from __future__ import annotations

import io
import re
from datetime import datetime

import pandas as pd

from pipelines.core import Raw, Source
from pipelines.core.http import fetch_raw, get
from pipelines.core.store import load_series
from pipelines.sources.rbi._press import RELEASE, releases

TITLE = "Sectoral Deployment of Bank Credit"
BACKFILL_MONTHS, RECENT_MONTHS, MIN_HISTORY = 16, 3, 8
ROWS = {  # label prefix -> series
    "III. Non-food Credit": "credit_nonfood_growth",
    "1. Agriculture": "credit_agri_growth",
    "2. Industry": "credit_industry_growth",
    "3. Services": "credit_services_growth",
    "3.9. Non-Banking Financial": "credit_nbfc_growth",
    "4. Personal Loans": "credit_personal_growth",
    "4.2. Housing": "credit_housing_growth",
    "4.7. Vehicle Loans": "credit_vehicle_growth",
    "4.8. Loans against gold": "credit_gold_growth",
    "4.5. Credit Card": "credit_cards_growth",
}
# Amounts outstanding (Rs lakh crore) for credit contributions (derived/credit_contributions.py).
LEVELS = {
    "1. Agriculture": "credit_level_agri",
    "2. Industry": "credit_level_industry",
    "2.1. Micro and Small": "credit_level_mse",
    "2.2. Medium": "credit_level_medium",
    "2.3. Large": "credit_level_large",
    "3. Services": "credit_level_services",
    "3.7. Trade": "credit_level_trade",
    "3.8. Commercial Real Estate": "credit_level_cre",
    "3.9. Non-Banking Financial": "credit_level_nbfc",
    "4. Personal Loans": "credit_level_personal",
    "4.2. Housing": "credit_level_housing",
    "4.5. Credit Card": "credit_level_cards",
    "4.7. Vehicle Loans": "credit_level_vehicle",
    "4.8. Loans against gold": "credit_level_gold",
    "4.9. Other Personal Loans": "credit_level_other_personal",
}
DATE = re.compile(r"(\d{1,2})\.([A-Za-z]{3}),\s*(\d{4})")


def month_of(text: str) -> str | None:
    m = DATE.search(str(text))
    return datetime.strptime(f"{m.group(2)} {m.group(3)}", "%b %Y").strftime("%Y-%m-01") if m else None


def yoy_columns(row: pd.Series) -> dict[int, str]:
    """{column: period} for the "a / b" year-on-year headers in a date row (first two)."""
    pairs = [(c, month_of(v)) for c, v in row.items() if isinstance(v, str) and "/" in v and DATE.search(v)][:2]
    if len(pairs) < 2:                                        # year-on-year comes before the FY variation
        return {}
    # The earlier column is "a year before the latest month"; its own date can be a reporting
    # Friday in the next month (e.g. 5 Sep 2025 for August 2025), so derive it from the latest.
    latest = pairs[1][1]
    year_before = f"{int(latest[:4]) - 1}{latest[4:]}"
    return {pairs[0][0]: year_before, pairs[1][0]: latest}


def level_columns(row: pd.Series) -> dict[int, str]:
    """{column: period} for the outstanding-amount dates of a block (plain dates, not "a / b"):
    the latest month, the same month a year earlier and two years earlier. As with growth,
    an earlier date can be a reporting Friday in the next month, so periods derive from the latest."""
    dated = [(c, datetime.strptime(" ".join(DATE.search(v).groups()), "%d %b %Y"))
             for c, v in row.items() if isinstance(v, str) and "/" not in v and DATE.search(v)]
    if not dated:
        return {}
    latest_col, latest = max(dated, key=lambda x: x[1])
    out = {latest_col: latest.strftime("%Y-%m-01")}
    for years in (1, 2):
        target = latest.replace(year=latest.year - years)
        near = [(c, d) for c, d in dated if abs((d - target).days) <= 20]
        if near:
            out[min(near, key=lambda x: abs((x[1] - target).days))[0]] = target.strftime("%Y-%m-01")
    return out


def parse_statement(content: bytes) -> list[dict]:
    df = pd.read_excel(io.BytesIO(content), sheet_name="Statement 1", header=None)
    cols, lcols, rows = {}, {}, []
    for _, r in df.iterrows():
        if any(isinstance(v, str) and "/" in v and DATE.search(v) for v in r):
            cols, lcols = yoy_columns(r), level_columns(r)   # a new block of dates
            continue
        label = re.sub(r"\s+", " ", str(r[0])).strip()
        sid = next((s for k, s in ROWS.items() if label.startswith(k)), None)
        if sid and cols:
            for c, period in cols.items():
                v = pd.to_numeric(r[c], errors="coerce")
                if pd.notna(v):
                    rows.append({"series_id": sid, "period": period, "value": round(float(v), 2)})
        lid = next((s for k, s in LEVELS.items() if label.startswith(k)), None)
        if lid and lcols:
            for c, period in lcols.items():
                v = pd.to_numeric(r[c], errors="coerce")
                if pd.notna(v):
                    rows.append({"series_id": lid, "period": period, "value": round(float(v) / 1e5, 4)})
    found = {r["series_id"] for r in rows}
    wanted = set(ROWS.values()) | set(LEVELS.values())
    if wanted - found:
        raise ValueError(f"sectoral credit rows not found: {sorted(wanted - found)}")
    return rows


class SectoralCredit(Source):
    name = "rbi_sectoral_credit"
    series_ids = (*ROWS.values(), *LEVELS.values())

    def fetch(self) -> list[Raw]:
        months = BACKFILL_MONTHS if len(load_series("credit_agri_growth")) < MIN_HISTORY else RECENT_MONTHS
        found = releases(lambda t: t.startswith(TITLE), months)
        if not found:
            raise RuntimeError(f"no '{TITLE}' releases in the last {months} months")
        raws = []
        for prid in sorted(found):                            # oldest first: later releases overwrite
            page = get(RELEASE.format(prid=prid)).text
            link = re.search(r'href="([^"]+SIBC[^"]+\.xlsx)"', page, re.I)
            if link:
                raws.append(fetch_raw(link.group(1), suffix=".xlsx"))
        if not raws:
            raise RuntimeError("sectoral credit releases found, but no SIBC workbook links")
        return raws

    def parse(self, raws: list[Raw]) -> pd.DataFrame:
        rows = []
        for raw in raws:
            rows += parse_statement(raw.content)
        out = pd.DataFrame(rows).drop_duplicates(["series_id", "period"], keep="last")
        out["note"] = "RBI, as published (newest release wins)"
        return out


SOURCE = SectoralCredit()
