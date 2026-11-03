"""Government deficits and debt, and balance-of-payments ratios, as % of GDP, from RBI's
Handbook of Statistics on the Indian Economy (annual).

The Handbook page (AnnualPublications.aspx?head=Handbook+of+Statistics+on+Indian+Economy)
lists "Table N : <title>" with XLSX links whose names change each edition; tables are found
by number:
  239 Combined deficits of the Central and State Governments (% of GDP): Gross Fiscal
      Deficit, Gross Primary Deficit, Revenue Deficit, from 1988-89
  240 Select debt indicators (% of GDP, end-March): Centre, States, combined total liabilities
  237 Select fiscal indicators of the Central Government (% of GDP): gross fiscal deficit,
      from 1984-85
  241 Balance of payments indicators: current account balance / GDP ("CAD / GDP", negative =
      deficit) and import cover of reserves (months), from 1987-88
Columns are found by their header text, in either of the two header rows (241 has a top row
"Trade | Invisibles | Current Account | ..." over "Exports / GDP | ... | CAD / GDP"). A footnote ("Data for 2024-25 are Revised Estimates
and data for 2025-26 are Budget Estimates") gives the stage of recent years, kept in the note.
Combined liabilities net out intergovernmental holdings, so they are not Centre + States.

Series (period = 1 April of the financial year; debt is at end-March of that year):
gg_gfd_pct_gdp, gg_primary_deficit_pct_gdp, gg_revenue_deficit_pct_gdp,
gg_debt_pct_gdp, centre_debt_pct_gdp, states_debt_pct_gdp, centre_gfd_pct_gdp,
cab_pct_gdp_fy, reserves_import_cover.
"""
from __future__ import annotations

import html
import io
import re

import pandas as pd

from pipelines.core import Raw, Source
from pipelines.core.http import fetch_raw, get

PAGE = "https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook+of+Statistics+on+Indian+Economy"
COLUMNS = {
    239: {"Gross Fiscal Deficit": "gg_gfd_pct_gdp", "Gross Primary Deficit": "gg_primary_deficit_pct_gdp",
          "Revenue Deficit": "gg_revenue_deficit_pct_gdp"},
    240: {"Combined Total Liabilities": "gg_debt_pct_gdp", "Total Liabilities of the Centre": "centre_debt_pct_gdp",
          "Total Liabilities of the States": "states_debt_pct_gdp"},
    237: {"Gross Fiscal Deficit": "centre_gfd_pct_gdp"},
    241: {"CAD / GDP": "cab_pct_gdp_fy", "Import Cover": "reserves_import_cover"},
}
FY = re.compile(r"^(\d{4})-\d{2}$")


def table_links(page: str, wanted=COLUMNS) -> dict[int, str]:
    """{table number: XLSX link} for the Handbook tables in `wanted` (numbers)."""
    out = {}
    for title, url in re.findall(r"class='link2' href=PublicationsView\.aspx\?id=\d+>([^<]+)</a>.*?href='(https://rbidocs[^']+\.XLSX)'",
                                 page, re.S | re.I):
        m = re.match(r"\s*Table\s*(\d+)", html.unescape(title), re.I)
        if m and int(m.group(1)) in wanted:
            out.setdefault(int(m.group(1)), url)
    return out


def stages(df: pd.DataFrame) -> dict[str, str]:
    """{'2024-25': 'Revised Estimates', ...} from the footnote."""
    text = " ".join(str(v) for v in df.values.ravel() if isinstance(v, str))
    return {y: kind for y, kind in re.findall(r"(\d{4}-\d{2}) (?:are|is) (Revised Estimates|Budget Estimates|Accounts)", text)}


def parse_table(content: bytes, n: int) -> list[dict]:
    book = pd.read_excel(io.BytesIO(content), sheet_name=None, header=None)
    df = next(iter(book.values()))
    notes = pd.concat(list(book.values()), ignore_index=True)   # 237's footnotes are on its second sheet
    head = next(i for i in range(10) if df.loc[i].astype(str).str.contains("Year").any())
    cols = {}
    for c in df.columns:
        labels = [re.sub(r"\s+", " ", str(df.loc[r, c])).strip() for r in (head, head + 1)]
        sid = next((s for k, s in COLUMNS[n].items() if any(lb.startswith(k) for lb in labels)), None)
        if sid and sid not in cols.values():
            cols[c] = sid
    if set(cols.values()) != set(COLUMNS[n].values()):
        raise ValueError(f"Handbook table {n}: columns not found ({sorted(set(COLUMNS[n].values()) - set(cols.values()))})")
    year_col = next(c for c in df.columns if "Year" in str(df.loc[head, c]))
    stage = stages(notes)
    rows = []
    for i in range(head + 1, len(df)):
        y = FY.match(str(df.loc[i, year_col]).strip())
        if not y:
            continue
        for c, sid in cols.items():
            v = pd.to_numeric(df.loc[i, c], errors="coerce")
            if pd.notna(v):
                fy = y.group(0)
                rows.append({"series_id": sid, "period": f"{y.group(1)}-04-01", "value": round(float(v), 2),
                             "note": stage.get(fy, "")})
    return rows


class GeneralGovernment(Source):
    name = "rbi_general_government"
    series_ids = tuple(s for cols in COLUMNS.values() for s in cols.values())

    def fetch(self) -> list[Raw]:
        links = table_links(get(PAGE).text)
        if set(COLUMNS) - set(links):
            raise RuntimeError(f"Handbook tables not found: {sorted(set(COLUMNS) - set(links))}")
        return [fetch_raw(links[n], suffix=f".t{n}.xlsx") for n in sorted(COLUMNS)]

    def parse(self, raws: list[Raw]) -> pd.DataFrame:
        rows = []
        for n, raw in zip(sorted(COLUMNS), raws):
            rows += parse_table(raw.content, n)
        return pd.DataFrame(rows)


SOURCE = GeneralGovernment()
