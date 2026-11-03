"""Union Budget headline numbers, from "Budget at a Glance" (indiabudget.gov.in).

File: https://www.indiabudget.gov.in/doc/Budget_at_Glance/budget_at_a_glance.xlsx, replaced
each Budget. Sheet "BAAG" has the headline table and "Deficit Statistics" the deficits with
% of GDP in brackets on the row below each figure. Both have four columns, read from the two
header rows: Actuals (two years back), Budget Estimates and Revised Estimates (last year),
Budget Estimates (the Budget year), e.g. 2024-2025 Actuals | 2025-2026 BE | 2025-2026 RE |
2026-2027 BE. Rows are matched by their English label ("17. Fiscal Deficit [9-(1+5+6)]").

Three panels, one per stage, entity = budget item, period = first day of the financial
year (2026-27 -> 2026-04-01). Amounts in Rs lakh crore (Rs crore in the file), deficit
ratios in % of GDP.

History: earlier Budgets are archived only as PDF, at
https://www.indiabudget.gov.in/budget<YYYY-YY>/doc/Budget_at_Glance/budget_at_a_glance.pdf
(2019-20 to 2025-26; older editions are not at that address). Page "Budget at a Glance" has
the same four columns and English labels beside the Hindi ones, % of GDP in brackets on the
line below. They are read once (when the panels lack 2017-18) and give Actuals from 2017-18.
Where editions overlap (a year's BE appears in its own Budget and the next), the newer wins.
"""
from __future__ import annotations

import io
import re

import pandas as pd
import pdfplumber

from pipelines.core import Raw, Source
from pipelines.core.http import fetch_raw
from pipelines.core.store import load_panel

URL = "https://www.indiabudget.gov.in/doc/Budget_at_Glance/budget_at_a_glance.xlsx"
ARCHIVE = "https://www.indiabudget.gov.in/budget{fy}/doc/Budget_at_Glance/budget_at_a_glance.pdf"
ARCHIVE_YEARS = range(2019, 2026)        # Budget 2019-20 ... 2025-26
FIRST_ACTUALS = "2017-04-01"
STAGES = {"Actuals": "budget_actuals", "Budget": "budget_be", "Revised": "budget_re"}
# English label in the file -> entity name on the site (amounts, Rs lakh crore).
AMOUNTS = {
    "Revenue Receipts": "Revenue receipts", "Tax Revenue (Net to Centre)": "Tax revenue (net to Centre)",
    "Non Tax Revenue": "Non-tax revenue", "Total Expenditure": "Total expenditure",
    "On Revenue Account": "Revenue expenditure", "Interest Payments": "Interest payments",
    "On Capital Account": "Capital expenditure", "Effective Capital Expenditure": "Effective capital expenditure",
    "Fiscal Deficit": "Fiscal deficit", "Revenue Deficit": "Revenue deficit", "Primary Deficit": "Primary deficit",
}
RATIOS = {"Fiscal Deficit": "Fiscal deficit, % of GDP", "Revenue Deficit": "Revenue deficit, % of GDP",
          "Primary Deficit": "Primary deficit, % of GDP"}
ORDER = [*AMOUNTS.values(), *RATIOS.values()]


def english(cell) -> str | None:
    """'17. Fiscal Deficit [9-(1+5+6)]' -> 'Fiscal Deficit [9-(1+5+6)]'."""
    m = re.match(r"^\s*\d+\.\s+([A-Za-z].*)", str(cell).replace("\n", " "))
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else None


def columns(df: pd.DataFrame) -> dict[int, tuple[str, str]]:
    """{column: (panel id, 'YYYY-04-01')} from the year row and the stage row below it."""
    year_row = next(i for i in df.index if sum(bool(re.fullmatch(r"\d{4}-\d{4}", str(v).strip())) for v in df.loc[i]) >= 3)
    out = {}
    for c in df.columns:
        y = str(df.loc[year_row, c]).strip()
        stage = next((sid for word, sid in STAGES.items() if word in str(df.loc[year_row + 1, c])), None)
        if re.fullmatch(r"\d{4}-\d{4}", y) and stage:
            out[c] = (stage, f"{y[:4]}-04-01")
    if len(out) < 3:
        raise ValueError("Budget at a Glance: year/stage header not found")
    return out


def parse_sheet(df: pd.DataFrame, wanted: dict[str, str], ratio: bool) -> list[dict]:
    cols = columns(df)
    rows = []
    for i in df.index:
        label = next((english(v) for v in df.loc[i] if english(v)), None)
        entity = next((name for key, name in wanted.items() if label and label.startswith(key)), None)
        if not entity:
            continue
        source = df.loc[i + 1] if ratio else df.loc[i]
        for c, (sid, period) in cols.items():
            v = str(source[c]).strip().strip("()")
            if re.fullmatch(r"-?\d+(\.\d+)?", v):
                value = float(v) if ratio else round(float(v) / 1e5, 4)
                rows.append({"series_id": sid, "entity": entity, "period": period, "value": value})
    return rows


# English label at the start of a PDF line (after the item number) -> key in AMOUNTS/RATIOS.
# Regex on the label's start, longer labels first ("Effective Revenue Deficit" is not "Revenue
# Deficit"); Budget 2025-26 shortens some ("13. On Capital", "14. Effective Capital").
PDF_LABELS = [(r"Effective Capital", "Effective Capital Expenditure"), (r"Effective Revenue", None),
              (r"Non[- ]?Tax Revenue", "Non Tax Revenue"), (r"Tax Revenue", "Tax Revenue (Net to Centre)"),
              (r"Revenue Receipts", "Revenue Receipts"), (r"Total Expenditure", "Total Expenditure"),
              (r"On Revenue", "On Revenue Account"), (r"Interest Payments", "Interest Payments"),
              (r"On Capital", "On Capital Account"), (r"Fiscal Deficit", "Fiscal Deficit"),
              (r"Revenue Deficit", "Revenue Deficit"), (r"Primary Deficit", "Primary Deficit")]
NUM, RATIO = r"(-?\d{4,})", r"\((-?\d+\.\d)\)"
HEADER = re.compile(r"^\s*((?:\d{4}-\d{4}\s+){3,4}\d{4}-\d{4})\s*$", re.MULTILINE)


def trailing(pattern: str, n: int) -> re.Pattern:
    """n values of `pattern` at the end of a line."""
    return re.compile(r"\s+".join([pattern] * n) + r"\s*$")


def pdf_label(line: str) -> tuple[bool, str | None] | None:
    """(True, key) for the English item label on a line ('16. Fiscal Deficit ...'); key is None
    for an item we do not keep ('4. Capital Receipts'). None if the line has no item label
    (a wrapped label, '(Net to Centre) 1242488 ...', whose item is on the line above)."""
    labels = [m.group(1) for m in re.finditer(r"(?<![\d.])\d{1,2}\.\s*([A-Z][a-z][A-Za-z ()-]*)", line)]
    for text in labels:
        for label, key in PDF_LABELS:
            if re.match(label, text):
                return True, key
    return (True, None) if labels else None


def parse_pdf(content: bytes) -> list[dict]:
    """The headline table of an archived Budget at a Glance (PDF). Four columns (Actuals, BE, RE,
    BE); Budget 2024-25, presented after the election, adds Provisional Actuals for 2023-24 before
    the last column, which is skipped (final actuals come with the next Budget)."""
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        page = next((t for t in (p.extract_text() or "" for p in pdf.pages)
                     if "Fiscal Deficit" in t and "Revenue Receipts" in t and HEADER.search(t)), None)
    if page is None:
        raise ValueError("Budget at a Glance PDF: headline table not found")
    years = re.findall(r"(\d{4})-\d{4}", HEADER.search(page).group(1))
    if len(years) == 5 and "Provisional" not in page:
        raise ValueError("Budget at a Glance PDF: five columns but no Provisional Actuals")
    stages = ("budget_actuals", "budget_be", "budget_re", None, "budget_be")[:len(years)] if len(years) == 5 \
        else ("budget_actuals", "budget_be", "budget_re", "budget_be")
    cols = list(zip(stages, (f"{y}-04-01" for y in years)))
    four, ratio4 = trailing(NUM, len(years)), trailing(RATIO, len(years))
    lines = page.splitlines()
    rows, last_key = [], None
    for i, line in enumerate(lines):
        r = ratio4.search(line)
        if r and last_key in RATIOS:
            rows += [{"series_id": sid, "entity": RATIOS[last_key], "period": per, "value": float(v)}
                     for (sid, per), v in zip(cols, r.groups()) if sid]
            last_key = None
            continue
        m = four.search(line)
        if not m:
            continue
        hit = pdf_label(line) or (pdf_label(lines[i - 1]) if i else None)
        last_key = hit[1] if hit else None
        if last_key in AMOUNTS:
            rows += [{"series_id": sid, "entity": AMOUNTS[last_key], "period": per, "value": round(float(v) / 1e5, 4)}
                     for (sid, per), v in zip(cols, m.groups()) if sid]
    # Effective capital expenditure is in the table only from Budget 2022-23.
    missing = set(ORDER) - {"Effective capital expenditure"} - {r["entity"] for r in rows}
    if missing:
        raise ValueError(f"Budget at a Glance PDF: rows not found: {sorted(missing)}")
    if len(rows) != len({(r["series_id"], r["entity"], r["period"]) for r in rows}):
        raise ValueError("Budget at a Glance PDF: an item was read twice")
    return rows


class BudgetGlance(Source):
    name = "budget_glance"
    panel = True
    series_ids = tuple(STAGES.values())

    def fetch(self) -> list[Raw]:
        raws = []
        actuals = load_panel("budget_actuals")
        if actuals.empty or actuals["period"].min() > FIRST_ACTUALS:      # backfill once from the PDFs
            raws += [fetch_raw(ARCHIVE.format(fy=f"{y}-{str(y + 1)[2:]}"), suffix=".pdf") for y in ARCHIVE_YEARS]
        return [*raws, fetch_raw(URL, suffix=".xlsx")]       # current Budget last: it wins

    def parse(self, raws: list[Raw]) -> pd.DataFrame:
        frames = []
        for raw in raws:
            if raw.suffix == ".pdf" or raw.content[:4] == b"%PDF":
                rows = parse_pdf(raw.content)
                edition = re.search(r"budget(\d{4}-\d{2})", raw.url)
                note = f"Budget at a Glance {edition.group(1)}" if edition else "Budget at a Glance (archive)"
            else:
                book = pd.ExcelFile(io.BytesIO(raw.content))
                rows = parse_sheet(pd.read_excel(book, "BAAG", header=None), AMOUNTS, ratio=False)
                rows += parse_sheet(pd.read_excel(book, "Deficit Statistics", header=None), RATIOS, ratio=True)
                missing = set(ORDER) - {r["entity"] for r in rows}
                if missing:
                    raise ValueError(f"Budget at a Glance rows not found: {sorted(missing)}")
                note = ""
            df = pd.DataFrame(rows)
            df["note"] = note
            frames.append(df)
        # Later files (newer editions, then the current xlsx) win where they overlap.
        out = pd.concat(frames).drop_duplicates(["series_id", "entity", "period"], keep="last")
        return out.reset_index(drop=True)


SOURCE = BudgetGlance()
