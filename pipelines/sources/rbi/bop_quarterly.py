"""India's balance of payments, quarterly, with the full detail and history the press-release
text lacks: RBI's two standard presentations, from the Handbook of Statistics and each
quarterly release's statements.

BPM6 ("Standard Presentation of India's Balance of Payments as per BPM6"): current account and
its parts, capital account, direct investment split into investment in India (item 3.1.A) and
by India (ODI, 3.1.B), portfolio investment, financial derivatives (3.3, with gross receipts
and payments), other investment, reserve assets and errors and omissions. From Apr-Jun 2013.

BPM5 (RBI's older "Overall Balance of Payments" presentation, still published as Statement II):
the only place with banking capital (commercial banks' foreign assets and liabilities,
including non-resident deposits), and commercial borrowings (ECBs, medium and long term) with
their gross drawdowns (credit) and repayments (debit). From Apr-Jun 2000.

Where the files come from (pipelines/sources/rbi/_handbook.py):
  - Handbook tables "... BPM6 - Quarterly - US Dollar" and "Overall Balance of Payments -
    Quarterly - US Dollar(s)". Each edition holds 8 (BPM6) or 16 (BPM5) quarters, so the first
    run reads every edition from 2012-13 (BPM5 back to 2000-01:Q1, in a long one-row-per-quarter
    layout) and 2014-15 (BPM6 from Apr-Jun 2013; that edition is PDF only). Later runs read the
    current edition.
  - Each quarterly BoP press release links Statement I (BPM6) and Statement II (BPM5) as XLSX
    (rdocs/content/docs/BOPS<ddmmyyyy>_1.xlsx and _2.xlsx), covering the latest five quarters.
The newest file wins for any quarter printed more than once (it carries the revisions).

Values are net (credit minus debit), US$ billion (files are in US$ million). + = inflow. Reserve
assets keep RBI's sign: negative = reserves rose, positive = reserves were drawn down. Every
quarter is checked against the BoP identity before anything is kept.
"""
from __future__ import annotations

import io
import re

import pandas as pd
import pdfplumber

from pipelines.core import Raw, Source
from pipelines.core.http import fetch_raw, get
from pipelines.core.store import load_series
from pipelines.sources.rbi import _handbook
from pipelines.sources.rbi._press import RELEASE, releases

BPM6_TITLE = r"BPM6\s*-?\s*Quarterly"
BPM5_TITLE = r"Overall Balance of Payments\s*-\s*Quarterly\s*-\s*US"
# Editions published in these years hold, between them, every quarter from 2000-01:Q1.
BACKFILL_YEARS = [2013, *range(2015, 2027)]
MIN_HISTORY, RECENT_MONTHS = 60, 4

# BPM6 item code -> series id (net).
BPM6 = {
    "1": "bop_bpm6_current_account", "1.A": "bop_bpm6_goods_services", "1.B": "bop_bpm6_primary_income",
    "1.C": "bop_bpm6_secondary_income", "2": "bop_bpm6_capital_account", "3.1.A": "bop_bpm6_fdi_in_india",
    "3.1.B": "bop_bpm6_odi", "3.2": "bop_bpm6_portfolio", "3.3": "bop_bpm6_derivatives",
    "3.4": "bop_bpm6_other_investment", "3.5": "bop_bpm6_reserve_assets", "5": "bop_bpm6_errors_omissions",
}
DERIVATIVES_GROSS = ("bop_bpm6_derivatives_receipts", "bop_bpm6_derivatives_payments")  # 3.3 credit, debit
ECB_GROSS = ("bop_bpm5_ecb_drawdowns", "bop_bpm5_ecb_repayments")  # BPM5 commercial borrowings credit, debit
# BPM5 series id -> label pattern (normalised label: lower case, single spaces), first match wins.
# Block layout ("3. Banking capital (a+b)") and long layout ("B.3) Banking Capital") both covered.
BPM5 = {
    "bop_bpm5_current_account": r"^total current account|^a\) current account$",
    "bop_bpm5_capital_account": r"^total capital account|^b\) capital account$",
    "bop_bpm5_banking_capital": r"^3\. ?banking capital|^b\.3\) banking capital",
    "bop_bpm5_bank_assets": r"^i\) ?assets$|^b\.3\.a\.1\) assets of commercial banks",
    "bop_bpm5_nri_deposits": r"non-resident deposits",
    "bop_bpm5_commercial_borrowings": r"^b\) commercial borrowings|^b\.2\.b\) commercial borrowings",
    "bop_bpm5_errors_omissions": r"^c\. ?errors|^c\) errors and omissions",
    "bop_bpm5_reserves_change": r"^ii\) ?foreign exchange reserves|^e\.2\) foreign exchange reserves",
    # Not published as a series: reserves plus IMF transactions, for the identity check.
    "_bpm5_monetary_movements": r"^e\. ?monetary movements|^e\) monetary movements",
}
QPAIRS = {"jan": ("mar", 1), "apr": ("jun", 4), "jul": ("sep", 7), "oct": ("dec", 10)}
QLABEL = re.compile(r"(jan|apr|jul|oct)[a-z]*\.?\s*[-–]\s*(mar|jun|sep|dec)[a-z]*\.?,?\s*(?:\|\s*)?(\d{4})", re.IGNORECASE)
CODE = re.compile(r"^\s*(\d(?:\.[0-9A-Za-z]+)*)\s+[A-Za-z]")   # '3.1.A Direct ...', not '1 2 3 4'



def quarter(label: str) -> str | None:
    """'April-June 2026 P' or 'Apr-Jun 2016' -> '2026-04-01' / '2016-04-01'; None for anything
    else, including annual columns such as 'April-March 2025-26'."""
    m = QLABEL.search(str(label))
    if not m:
        return None
    start, end, year = m.group(1).lower(), m.group(2).lower(), int(m.group(3))
    if QPAIRS[start][0] != end:
        return None
    return f"{year:04d}-{QPAIRS[start][1]:02d}-01"


def fy_quarter(label: str) -> str | None:
    """'2000-01:Q1' -> '2000-04-01'; '2012-13:Q4' -> '2013-01-01'."""
    m = re.match(r"\s*(\d{4})-\d{2}\s*:\s*Q([1-4])", str(label))
    if not m:
        return None
    fy, q = int(m.group(1)), int(m.group(2))
    month = 3 * q + 1
    return f"{fy + (month > 12):04d}-{(month - 1) % 12 + 1:02d}-01"


def amount(v) -> float | None:
    """A table cell in US$ million -> float; '-' or '–' (nil) -> 0; blank or text -> None."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return None if pd.isna(v) else float(v)
    s = str(v).strip().replace(",", "").replace("–", "-").replace("−", "-")
    if s in {"-", "--"}:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return None


def norm(label) -> str:
    return " ".join(str(label).replace("\n", " ").split()).lower()


def bpm6_item(label: str) -> tuple[str | None, str | None]:
    """(item code, series id) for a BPM6 row label, or (None, None). Errors and omissions are
    item 5 in the Handbook but item 4 in Statement I, so they are matched by name; item 3 is
    kept (for the identity check) only when it is the financial account."""
    m = CODE.match(label)
    code = m.group(1).rstrip(".") if m else None
    low = label.lower()
    if "errors and omissions" in low:
        return code, BPM6["5"]
    if code == "3":
        return code, "_bpm6_financial_account" if "financial account" in low else None
    if code in {"4", "5"}:
        return code, None
    return code, BPM6.get(code)


def headers(df: pd.DataFrame) -> list[tuple[int, list[tuple[str, int, int, int]]]]:
    """Every quarter header in a sheet (some editions stack two blocks of quarters one above
    the other): [(header row, [(period, credit col, debit col, net col)])]."""
    out = []
    for r in range(len(df)):
        cols = [(c, quarter(v)) for c, v in enumerate(df.iloc[r]) if isinstance(v, str) and quarter(v)]
        if not cols:
            continue
        qs = []
        for i, (c, period) in enumerate(cols):
            stop = cols[i + 1][0] if i + 1 < len(cols) else df.shape[1]
            found = {}
            for rr in range(r + 1, min(r + 5, len(df))):
                for cc in range(c, stop):
                    v = norm(df.iat[rr, cc])
                    if v in {"credit", "debit", "net"}:
                        found.setdefault(v, cc)
            if set(found) != {"credit", "debit", "net"}:
                raise ValueError(f"no Credit/Debit/Net columns under {period}")
            qs.append((period, found["credit"], found["debit"], found["net"]))
        if out and r - out[-1][0] <= 2:      # one header split over adjacent rows (2015-16)
            out[-1] = (r, out[-1][1] + qs)
        else:
            out.append((r, qs))
    return out


def label_of(row: pd.Series, before: int) -> str | None:
    """The item label: the text left of the first quarter column. Statement I keeps the item
    code ('1.A') in its own column, so the cells are joined ('1.A Goods and Services ...')."""
    cells = [str(v).strip() for v in row.iloc[:before] if pd.notna(v) and str(v).strip()]
    label = " ".join(cells)
    return label if re.search(r"[A-Za-z]", label) else None


def is_bpm6(df: pd.DataFrame) -> bool:
    head = " ".join(str(v) for v in df.iloc[:6].values.ravel() if isinstance(v, str))
    return "BPM6" in head.upper()


def parse_blocks(df: pd.DataFrame) -> list[dict]:
    """Sheets with quarters across (Handbook tables from 2015-16, release statements)."""
    bpm6, rows = is_bpm6(df), []
    found = headers(df)
    for k, (r, qs) in enumerate(found):
        stop = found[k + 1][0] if k + 1 < len(found) else len(df)
        first_col = min(q[1] for q in qs)
        seen5: set[str] = set()
        for i in range(r + 1, stop):
            label = label_of(df.iloc[i], first_col)
            if label is None:
                continue
            if bpm6:
                code, sid = bpm6_item(label)
            else:
                lab = norm(label)
                sid = next((s for s, pat in BPM5.items() if s not in seen5 and re.search(pat, lab)), None)
                seen5.add(sid)
            if sid is None:
                continue
            for period, cc, dc, nc in qs:
                credit, debit, net = (amount(df.iat[i, c]) for c in (cc, dc, nc))
                if net is None and credit is None and debit is None:
                    continue
                rows.append({"series_id": sid, "period": period,
                             "value": net if net is not None else (credit or 0) - (debit or 0)})
                gross = DERIVATIVES_GROSS if bpm6 and code == "3.3" else ECB_GROSS if sid == "bop_bpm5_commercial_borrowings" else None
                if gross:
                    rows += [{"series_id": gross[0], "period": period, "value": credit or 0.0},
                             {"series_id": gross[1], "period": period, "value": debit or 0.0}]
    return rows


def parse_long(df: pd.DataFrame) -> list[dict]:
    """The BPM5 table in the 2009-10 to 2012-13 editions: one Credit/Debit/Net row triplet per
    quarter ('2000-01:Q1'), items across the columns."""
    head = next((i for i in range(min(len(df), 15)) if norm(df.iat[i, 0]).startswith("year/quarter")), None)
    if head is None:
        return []
    cols = {}
    for sid, pat in BPM5.items():
        c = next((c for c, v in enumerate(df.iloc[head]) if isinstance(v, str) and re.search(pat, norm(v))), None)
        if c is None:
            raise ValueError(f"long BoP table: no column for {sid}")
        cols[sid] = c
    rows, period = [], None
    for i in range(head + 1, len(df)):
        period = fy_quarter(df.iat[i, 0]) or period
        kind = norm(df.iat[i, 1])
        if period and kind == "net":
            for sid, c in cols.items():
                v = amount(df.iat[i, c])
                if v is not None:
                    rows.append({"series_id": sid, "period": period, "value": v})
        elif period and kind in ("credit", "debit"):
            v = amount(df.iat[i, cols["bop_bpm5_commercial_borrowings"]])
            rows.append({"series_id": ECB_GROSS[kind == "debit"], "period": period, "value": v or 0.0})
    return rows


def parse_pdf(content: bytes) -> list[dict]:
    """The 2014-15 edition's BPM6 table (PDF only): pages of two quarters, each item line ending
    in six numbers (credit, debit, net for each quarter); '–' is nil and '–21,772' negative."""
    rows = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    qs: list[str] = []
    for line in text.splitlines():
        found = [quarter(m.group(0)) for m in QLABEL.finditer(line)]
        if len(found) == 2 and all(found):
            qs = found
            continue
        m = CODE.match(line)
        if not m or not qs:
            continue
        code, sid = bpm6_item(line)
        if sid is None:
            continue
        nums = re.findall(r"(?<![\w.])[–-]?[\d,]+(?:\.\d+)?(?![\w.])|(?<!\S)[–-](?!\S)", line[m.end() - 1:])
        if len(nums) < 6:
            raise ValueError(f"BPM6 PDF: expected 6 numbers on line {line!r}")
        vals = [amount(n) for n in nums[-6:]]
        for k, period in enumerate(qs):
            credit, debit, net = vals[3 * k: 3 * k + 3]
            rows.append({"series_id": sid, "period": period, "value": net})
            if code == "3.3":
                rows += [{"series_id": DERIVATIVES_GROSS[0], "period": period, "value": credit},
                         {"series_id": DERIVATIVES_GROSS[1], "period": period, "value": debit}]
    return rows


def parse_file(raw: Raw) -> list[dict]:
    if raw.suffix == ".pdf" or raw.content[:4] == b"%PDF":
        return parse_pdf(raw.content)
    xl = pd.ExcelFile(io.BytesIO(raw.content))
    rows: list[dict] = []
    # Release statements have a US$ sheet and a rupee sheet; keep US$ only.
    sheets = [s for s in xl.sheet_names if not re.search(r"\bINR\b|rupee", s, re.IGNORECASE)]
    for s in sheets:
        df = pd.read_excel(xl, s, header=None, dtype=object).dropna(how="all").dropna(axis=1, how="all")
        df = df.reset_index(drop=True)
        df.columns = range(df.shape[1])
        rows += parse_long(df) or parse_blocks(df)
    return rows


def complete(df: pd.DataFrame) -> bool:
    """Every core item covers the same quarters. Some sheets (the 2015-16 edition's BPM5 table)
    print part of a column one row off its label; such a file has gaps and is not used (other
    editions cover the same quarters)."""
    core = df[df["series_id"].isin([*BPM6.values(), *BPM5])]
    spans = core.groupby("series_id")["period"].apply(frozenset)
    return spans.nunique() == 1


def check_identity(df: pd.DataFrame, where: str) -> None:
    """BPM6: current + capital + financial account + errors = 0. BPM5: current + capital account
    + errors + monetary movements (reserves and IMF) = 0. Tolerance: rounding to the million."""
    wide = df.pivot_table(index="period", columns="series_id", values="value", aggfunc="last")
    checks = {
        "BPM6": ["bop_bpm6_current_account", "bop_bpm6_capital_account", "_bpm6_financial_account", "bop_bpm6_errors_omissions"],
        "BPM5": ["bop_bpm5_current_account", "bop_bpm5_capital_account", "bop_bpm5_errors_omissions", "_bpm5_monetary_movements"],
    }
    for name, cols in checks.items():
        if not set(cols) <= set(wide.columns):
            continue
        sub = wide[cols].dropna()
        gap = sub.sum(axis=1).abs()
        bad = gap[gap > 6]          # US$ million; files round each item to the million
        if not bad.empty:
            raise ValueError(f"{where}: {name} identity fails for {bad.index.tolist()[:4]} (gap {bad.max():.0f} mn)")


class RbiBopQuarterly(Source):
    name = "rbi_bop_quarterly"
    series_ids = (*BPM6.values(), *DERIVATIVES_GROSS, *(s for s in BPM5 if not s.startswith("_")), *ECB_GROSS)

    def fetch(self) -> list[Raw]:
        backfill = min(len(load_series(s)) for s in ("bop_bpm5_banking_capital", "bop_bpm5_commercial_borrowings")) < MIN_HISTORY
        raws = []
        for page in _handbook.pages(BACKFILL_YEARS if backfill else None):
            for pattern in (BPM5_TITLE, BPM6_TITLE):
                url = _handbook.find(page, pattern, pdf_ok=pattern == BPM6_TITLE)
                if url:
                    raws.append(fetch_raw(url, suffix=".pdf" if url.lower().endswith(".pdf") else ".xlsx"))
        quarterly = releases(lambda t: t.startswith("Developments") and "Balance of Payments" in t
                             and "Quarter" in t, RECENT_MONTHS)
        for prid in sorted(quarterly, key=int):
            page = get(RELEASE.format(prid=prid)).text
            for url in sorted(set(re.findall(r"https://rbidocs\.rbi\.org\.in/rdocs/content/docs/BOPS\d+_[12]\.xlsx", page, re.IGNORECASE))):
                raws.append(fetch_raw(url, suffix=".xlsx"))
        if not raws:
            raise RuntimeError("no Handbook BoP tables or release statements found")
        return raws

    def parse(self, raws: list[Raw]) -> pd.DataFrame:
        frames = []
        for raw in raws:
            rows = parse_file(raw)
            if not rows:
                print(f"  BoP quarterly: nothing parsed from {raw.url}")
                continue
            df = pd.DataFrame(rows).drop_duplicates(["series_id", "period"], keep="first")
            if not complete(df):
                print(f"  BoP quarterly: skipped {raw.url} (items cover different quarters; misaligned sheet)")
                continue
            check_identity(df, raw.url)
            # Newer files carry revisions. Rank a file by its latest quarter; on a tie the
            # Handbook (published after the release with the same latest quarter) wins.
            df["rank"] = df["period"].max() + ("1" if "/Publications/" in raw.url else "0")
            df["note"] = "RBI BoP release statement" if "/content/docs/BOPS" in raw.url else "RBI Handbook of Statistics"
            frames.append(df)
        if not frames:
            raise ValueError("no BoP rows parsed")
        out = pd.concat(frames).sort_values("rank", kind="stable")
        out = out.drop_duplicates(["series_id", "period"], keep="last")
        out = out[~out["series_id"].str.startswith("_")].copy()
        out["value"] = (out["value"] / 1000).round(3)
        return out[["series_id", "period", "value", "note"]].sort_values(["series_id", "period"]).reset_index(drop=True)


SOURCE = RbiBopQuarterly()
