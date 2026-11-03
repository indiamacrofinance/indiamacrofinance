"""India's balance of payments: quarterly and (from 2026) monthly RBI press releases.

Releases are found by scanning RBI's press-release index month by month (an ASP.NET
form: POST hdnYear/hdnMonth with the page's hidden fields) for titles starting
"Developments in India's Balance of Payments". The first run scans BACKFILL_MONTHS;
later runs scan the last RECENT_MONTHS. Quarterly releases come about three months
apart (early Sep, Dec, late Mar, late Jun), so RECENT_MONTHS must reach back past the
latest one; with only monthly releases in the window every quarterly series parses
to no rows and the source is flagged broken.

Quarterly releases ("... during the First Quarter (April-June) of 2026-27"): Table 1 has
Credit/Debit/Net for the same quarter a year earlier and the latest quarter; we keep Net.
The current account as % of GDP comes from the release's first sentence.
Monthly releases ("... for the Month of July 2026"): net values for the month a year
earlier, the month, and the two financial-year-to-date totals; we keep the two months.
The newest release wins for any period printed more than once. US$ billion.
"""
from __future__ import annotations

import re

import pandas as pd

from pipelines.core import Raw, Source
from pipelines.core.http import fetch_raw
from pipelines.core.store import load_series
from pipelines.sources.rbi._press import RELEASE, releases
from pipelines.sources.rbi.services_trade import page_text
BACKFILL_MONTHS, RECENT_MONTHS, MIN_HISTORY = 26, 4, 4
MONTHS = ("January February March April May June July August September October "
          "November December").split()
NUM = r"(-?\d+(?:\.\d+)?)"
# Quarterly Table 1 rows (label prefix) -> series id; each row has 6 numbers (C, D, N x 2).
QUARTERLY_ROWS = {
    "A. Current Account": "bop_current_account", "1. Goods": "bop_goods_net",
    "2. Services": "bop_services_net", "3. Primary Income": "bop_primary_income_net",
    "4. Secondary Income": "bop_secondary_income_net", "1. Direct Investment": "bop_fdi_net",
    "2. Portfolio Investment": "bop_portfolio_net",
}
MONTHLY_ROW = "A. Current Account (Net)"


def quarter_start(label: str) -> str:
    """'April-June 2026' -> '2026-04-01'; 'January-March 2026' -> '2026-01-01'."""
    m = re.match(r"([A-Za-z]+)\s*[-–]\s*[A-Za-z]+\s+(\d{4})", label.strip())
    return f"{int(m.group(2)):04d}-{MONTHS.index(m.group(1)) + 1:02d}-01"


def parse_quarterly(text: str) -> list[dict]:
    # Anchor on the table's own heading; earlier "Table 1" mentions are cross-references.
    start = text.find("Table 1: Major Items")
    table = text[start:] if start >= 0 else text[text.rfind("Table 1"):]
    # Headers read "April-June 2026 P", "January-March | 2025 PR" or "July – September 2025 P".
    heads = re.findall(r"((?:" + "|".join(MONTHS) + r")\s*[-–]\s*(?:" + "|".join(MONTHS) + r"))\s*\|?\s*(\d{4})\s+P", table)
    if len(heads) < 2:
        raise ValueError("quarterly BoP table headers not found")
    prev_q, cur_q = (quarter_start(f"{rng} {yr}") for rng, yr in heads[:2])
    rows = []
    for label, sid in QUARTERLY_ROWS.items():
        m = re.search(re.escape(label) + r"[^|]*\|\s*" + r"\s*\|?\s*".join([NUM] * 6), table)
        if not m:
            raise ValueError(f"BoP row {label!r} not found")
        vals = [float(x) for x in m.groups()]
        rows += [{"series_id": sid, "period": prev_q, "value": vals[2]},
                 {"series_id": sid, "period": cur_q, "value": vals[5]}]
    # "current account deficit stood at US$ 4.2 billion (0.5 per cent of GDP) in Q1:2026-27
    #  as compared to US$ 3.4 billion (0.4 per cent of GDP) in Q1:2025-26"
    # Only a sentence about the quarter ("... in Q1:2026-27"), not the full year.
    g = re.search(r"current account (deficit|surplus)[^(|]*\((" + NUM[1:-1] + r") per cent of GDP\) in Q\d:[^(|]*"
                  r"\((" + NUM[1:-1] + r") per cent of GDP\)", text)
    if g:
        sign = -1 if g.group(1) == "deficit" else 1
        rows += [{"series_id": "bop_cab_pct_gdp", "period": cur_q, "value": sign * float(g.group(2))}]
        # The year-earlier figure can be a deficit or surplus; only keep it when the
        # sentence says it is the same kind (otherwise the sign is ambiguous).
        if not re.search(r"as compared to (a )?(surplus|deficit)", text[g.start():g.end()]):
            rows += [{"series_id": "bop_cab_pct_gdp", "period": prev_q, "value": sign * float(g.group(3))}]
    # "Personal transfer receipts ..., mainly representing remittances by Indians employed
    #  overseas, rose to US$ 42.9 billion in Q1:2026-27 from US$ 33.2 billion in Q1:2025-26"
    # (printed since Q3 2024-25; absent from older releases, so optional).
    r = re.search(r"Personal transfer receipts[^|]*?US\$\s*" + NUM + r" billion in Q(\d):\s*(\d{4})-\d{2}"
                  r"[^|]*?US\$\s*" + NUM + r" billion in Q(\d):\s*(\d{4})-\d{2}", text)
    if r:
        for value, q, fy in [(r.group(1), r.group(2), r.group(3)), (r.group(4), r.group(5), r.group(6))]:
            rows.append({"series_id": "bop_remittances", "period": fy_quarter_start(int(q), int(fy)),
                         "value": float(value)})
    return rows


def fy_quarter_start(q: int, fy_start: int) -> str:
    """Q1 of 2026-27 -> '2026-04-01'; Q4 of 2025-26 -> '2026-01-01'."""
    month = 3 * q + 1
    return f"{fy_start + (month > 12):04d}-{(month - 1) % 12 + 1:02d}-01"


def parse_monthly(text: str) -> list[dict]:
    m = re.search(r"Item \|\s*(" + "|".join(MONTHS) + r")\s+(\d{4})\s+P?R?\s*\|\s*(" + "|".join(MONTHS)
                  + r")\s+(\d{4})", text)
    if not m:
        raise ValueError("monthly BoP table header not found")
    prev_m = f"{int(m.group(2)):04d}-{MONTHS.index(m.group(1)) + 1:02d}-01"
    cur_m = f"{int(m.group(4)):04d}-{MONTHS.index(m.group(3)) + 1:02d}-01"
    r = re.search(re.escape(MONTHLY_ROW) + r"[^|]*\|\s*" + NUM + r"\s*\|\s*" + NUM, text)
    if not r:
        raise ValueError("monthly current account row not found")
    return [{"series_id": "bop_cab_monthly", "period": prev_m, "value": float(r.group(1))},
            {"series_id": "bop_cab_monthly", "period": cur_m, "value": float(r.group(2))}]


class RbiBoP(Source):
    name = "rbi_bop"
    series_ids = (*QUARTERLY_ROWS.values(), "bop_cab_pct_gdp", "bop_cab_monthly", "bop_remittances")

    def fetch(self) -> list[Raw]:
        months = BACKFILL_MONTHS if len(load_series("bop_current_account")) < MIN_HISTORY else RECENT_MONTHS
        found = releases(lambda t: t.startswith("Developments") and "Balance of Payments" in t, months)
        if not found:
            raise RuntimeError("no balance of payments releases found in the press-release index")
        # Newest release first (prids increase over time).
        return [fetch_raw(RELEASE.format(prid=p), suffix=".html") for p in sorted(found, key=int, reverse=True)]

    def parse(self, raws: list[Raw]) -> pd.DataFrame:
        rows = []
        for raw in raws:
            text = page_text(raw.content)
            title = re.search(r"Developments in India.s Balance of Payments[^|]*", text)
            if not title:
                continue
            try:
                rows += parse_monthly(text) if "for the Month of" in title.group(0) else parse_quarterly(text)
            except ValueError as e:
                # Older releases can use another layout; skip loudly, keep the rest.
                print(f"  BoP: skipped {raw.url} ({title.group(0).strip()[:70]}): {e}")
        df = pd.DataFrame(rows)
        df["note"] = "RBI BoP release (newest release wins)"
        return df.drop_duplicates(subset=["series_id", "period"], keep="first")


SOURCE = RbiBoP()
