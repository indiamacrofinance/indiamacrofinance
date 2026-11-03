"""RBI's dealing in the foreign exchange market, monthly, and the rupee's monthly average rate.

Series
  rbi_fx_purchases, rbi_fx_sales   gross US dollar purchases and sales by RBI (onshore and
                                   offshore OTC segment, spot and forward deliveries), US$ bn
  rbi_fx_net_purchase              purchases minus sales (+ = RBI bought dollars, as RBI shows it)
  rbi_fx_forward_book              outstanding net forward sales (-) / purchases (+), end-month
  usdinr_monthly_avg               rupees per US dollar, monthly average (FEDAI indicative rates
                                   to April 2012, RBI reference rate from May 2012, FBIL's from
                                   July 2018)

Where they come from
  - Handbook of Statistics tables "Sales and Purchases of US Dollar by the Reserve Bank of India"
    and "Exchange Rate of the Indian Rupee ... (Monthly Average and end-Month Rates)", found by
    title (pipelines/sources/rbi/_handbook.py). Each edition keeps a few years, so the first run
    reads every edition from 2012-13 (whose tables start in April 1997 and March 1992); later
    runs read the current edition. Layouts vary: one or two side-by-side blocks, months as
    'Apr' under a year row, as month-end dates, or as '1997:04 (APR)'.
  - The latest months of dealing, which the annual Handbook lacks, from RBI Bulletin Table 4
    "Sale/ Purchase of U.S. Dollar by the RBI" (Current Statistics). Each issue prints the
    latest month, the month before and the same month a year earlier; the last RECENT_MONTHS
    issues are read through the Bulletin page's month form (POST hdnYear/hdnMonth).
The newest file wins where they overlap. Months after the Handbook's last exchange-rate month
are not filled here: the analysis averages FBIL's daily reference rate (`usdinr_ref`) instead.
"""
from __future__ import annotations

import io
import re
from datetime import datetime

import httpx
import pandas as pd

from pipelines.core import Raw, Source
from pipelines.core.http import HEADERS, fetch_raw
from pipelines.core.store import load_series
from pipelines.sources.rbi import _handbook
from pipelines.sources.rbi.bop_quarterly import BACKFILL_YEARS, amount, norm
from pipelines.sources.rbi.services_trade import page_text

FXI_TITLE = r"Sales? and Purchases? of US Dollar"
FXM_TITLE = r"Exchange Rate of the Indian Rupee.*Monthly Average"
BULLETIN = "https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx"
MIN_HISTORY, RECENT_MONTHS = 200, 4
DATE_HEAD = re.compile(r"^(month ?/ ?year|year ?/ ?month|month)$")   # not '... at end of month'
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def month_of(v, year: int | None) -> tuple[int | None, int | None]:
    """(year, month) for a date cell, or (year, None) for a year row. Accepts month-end dates,
    '1997:04 (APR)', a bare month name (uses `year`), and a year (1990-2099)."""
    if isinstance(v, (datetime, pd.Timestamp)):
        return v.year, v.month
    s = str(v).strip()
    m = re.match(r"(\d{4})\s*:\s*(\d{2})", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    if re.fullmatch(r"(19|20)\d{2}(\.0)?", s):
        return int(float(s)), None
    if s[:3].lower() in MONTHS and re.fullmatch(r"[A-Za-z]{3,9}\.?", s) and year:
        return year, MONTHS.index(s[:3].lower()) + 1
    return year, None


def walk(df: pd.DataFrame, date_col: int, value_cols: dict[str, int], start: int) -> list[dict]:
    """Rows below `start`: track the year from year rows, read values on month rows."""
    rows, year = [], None
    for i in range(start, len(df)):
        y, m = month_of(df.iat[i, date_col], year)
        year = y or year
        if m is None:
            continue
        for sid, c in value_cols.items():
            v = amount(df.iat[i, c])
            if v is not None:
                rows.append({"series_id": sid, "period": f"{y:04d}-{m:02d}-01", "value": v})
    return rows


def parse_fxi(df: pd.DataFrame) -> list[dict]:
    """Handbook dollar purchases/sales: one or two blocks of (month, purchase, sale, forward)."""
    rows = []
    for r in range(min(len(df), 12)):
        for c in range(df.shape[1]):
            if not DATE_HEAD.match(norm(df.iat[r, c])):
                continue
            head = {k: norm(df.iat[r, k]) for k in range(c + 1, min(c + 5, df.shape[1]))}
            cols = {sid: next((k for k, h in head.items() if word in h and ("forward" in h) == fwd), None)
                    for sid, word, fwd in (("rbi_fx_purchases", "purchase", False), ("rbi_fx_sales", "sale", False),
                                           ("rbi_fx_forward_book", "forward", True))}
            if None in cols.values():
                raise ValueError(f"dollar purchase/sale columns not found next to column {c}")
            rows += walk(df, c, cols, r + 1)
        if rows:
            break
    return rows


def parse_fxm(df: pd.DataFrame) -> list[dict]:
    """Handbook monthly exchange rates: the 'Average' column under 'US Dollar'."""
    for r in range(min(len(df), 12)):
        date_col = next((c for c in range(df.shape[1]) if DATE_HEAD.match(norm(df.iat[r, c]))), None)
        usd = next((c for c in range(df.shape[1]) if norm(df.iat[r, c]) == "us dollar"), None)
        if date_col is None or usd is None:
            continue
        avg = next((c for rr in range(r + 1, min(r + 3, len(df))) for c in (usd, usd + 1)
                    if c < df.shape[1] and norm(df.iat[rr, c]) == "average"), None)
        if avg is None:
            raise ValueError("no 'Average' column under 'US Dollar'")
        return walk(df, date_col, {"usdinr_monthly_avg": avg}, r + 1)
    return []


def parse_bulletin(text: str) -> list[dict]:
    """Bulletin Table 4, OTC segment. Columns: financial year to date, the same month a year
    earlier, the previous month, the latest month. Years are not printed next to the months,
    so they follow from the issue date: the latest month is the last such month before it."""
    d = re.search(r"Date\s*:\s*([A-Z][a-z]{2})\.?\s+\d{1,2},\s*(\d{4})", text)
    seg = text[text.find("OTC segment"):text.find("currency futures segment")]
    head = re.search(r"Item\s*\|[^|]+\|[^|]+\|[^|]+\|\s*([A-Za-z]{3})[a-z]*\.?\s*\|\s*([A-Za-z]{3})[a-z]*\.?\s*\|\s*([A-Za-z]{3})[a-z]*\.?", seg)
    if not d or not head:
        raise ValueError("Bulletin Table 4: issue date or month header not found")
    issue_y, issue_m = int(d.group(2)), MONTHS.index(d.group(1).lower()) + 1
    ye, prev, cur = (MONTHS.index(g.lower()) + 1 for g in head.groups())
    cur_y = issue_y if cur < issue_m else issue_y - 1
    prev_y, want_prev = (cur_y, cur - 1) if cur > 1 else (cur_y - 1, 12)
    if prev != want_prev or ye != cur:
        raise ValueError(f"Bulletin Table 4: unexpected months {head.groups()}")
    periods = [f"{cur_y - 1:04d}-{cur:02d}-01", f"{prev_y:04d}-{prev:02d}-01", f"{cur_y:04d}-{cur:02d}-01"]
    num = r"\|\s*(-?[\d,]+)\s*"
    rows = []
    for sid, pat in (("rbi_fx_purchases", r"1\.1 Purchase \(\+\)\s*"), ("rbi_fx_sales", r"1\.2 Sale \([–-]\)\s*"),
                     ("rbi_fx_forward_book", r"4\. Outstanding Net Forward[^|]*\(US \$ Million\)\s*")):
        m = re.search(pat + num * 4, seg)
        if not m:
            raise ValueError(f"Bulletin Table 4: row for {sid} not found")
        vals = [float(x.replace(",", "")) for x in m.groups()[1:]]   # drop the financial-year column
        rows += [{"series_id": sid, "period": p, "value": v} for p, v in zip(periods, vals)]
    return rows


def with_net(rows: list[dict]) -> list[dict]:
    df = pd.DataFrame(rows).drop_duplicates(["series_id", "period"], keep="last")
    w = df.pivot(index="period", columns="series_id", values="value")
    if {"rbi_fx_purchases", "rbi_fx_sales"} <= set(w.columns):
        net = (w["rbi_fx_purchases"] - w["rbi_fx_sales"]).dropna()
        rows = rows + [{"series_id": "rbi_fx_net_purchase", "period": p, "value": v} for p, v in net.items()]
    return rows


def parse_file(raw: Raw) -> list[dict]:
    if raw.suffix == ".html":
        return with_net(parse_bulletin(page_text(raw.content)))
    xl = pd.ExcelFile(io.BytesIO(raw.content))
    rows = []
    for s in xl.sheet_names:
        df = pd.read_excel(xl, s, header=None, dtype=object).dropna(how="all").dropna(axis=1, how="all")
        df = df.reset_index(drop=True)
        df.columns = range(df.shape[1])
        title = norm(" ".join(str(v) for v in df.iloc[:3].values.ravel() if isinstance(v, str)))
        if "exchange rate" in title:
            rows += parse_fxm(df)
        elif "purchase" in title:
            rows += parse_fxi(df)
    return with_net(rows) if rows else rows


def bulletin_pages(months: int) -> list[Raw]:
    """Table 4 from the latest `months` Bulletin issues."""
    out = []
    with httpx.Client(headers=HEADERS, timeout=120, follow_redirects=True) as client:
        page = client.get(BULLETIN).text
        fields = dict(re.findall(r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', page))
        ids: list[str] = []
        for p in pd.period_range(end=pd.Period.now(freq="M"), periods=months, freq="M"):
            html = client.post(BULLETIN, data=dict(fields, hdnYear=str(p.year), hdnMonth=str(p.month))).text
            for i, title in re.findall(r"""href=['"]?BS_ViewBulletin\.aspx\?Id=(\d+)['"]?[^>]*>([^<]+)</a>""", html):
                if re.search(r"Sale\s*/\s*Purchase of U\.?S\.? Dollar", title) and i not in ids:
                    ids.append(i)
    for i in ids:
        out.append(fetch_raw(f"{BULLETIN}?Id={i}", suffix=".html"))
    return out


class RbiFxOperations(Source):
    name = "rbi_fx_operations"
    series_ids = ("rbi_fx_purchases", "rbi_fx_sales", "rbi_fx_net_purchase", "rbi_fx_forward_book", "usdinr_monthly_avg")

    def fetch(self) -> list[Raw]:
        backfill = len(load_series("rbi_fx_net_purchase")) < MIN_HISTORY
        raws = []
        for page in _handbook.pages(BACKFILL_YEARS if backfill else None):
            for pattern in (FXI_TITLE, FXM_TITLE):
                url = _handbook.find(page, pattern)
                if url:
                    raws.append(fetch_raw(url, suffix=".xlsx"))
        raws += bulletin_pages(RECENT_MONTHS)
        if not raws:
            raise RuntimeError("no Handbook tables or Bulletin pages found")
        return raws

    def parse(self, raws: list[Raw]) -> pd.DataFrame:
        frames = []
        for raw in raws:
            rows = parse_file(raw)
            if not rows:
                print(f"  FX operations: nothing parsed from {raw.url}")
                continue
            df = pd.DataFrame(rows).drop_duplicates(["series_id", "period"], keep="last")
            # Newer files win: rank by each file's latest month; a Bulletin issue beats the
            # Handbook for the months they share (it is the more recent print).
            df["rank"] = df["period"].max() + ("1" if raw.suffix == ".html" else "0")
            df["note"] = "RBI Bulletin Table 4" if raw.suffix == ".html" else "RBI Handbook of Statistics"
            frames.append(df)
        if not frames:
            raise ValueError("no FX rows parsed")
        out = pd.concat(frames).sort_values("rank", kind="stable").drop_duplicates(["series_id", "period"], keep="last")
        dollars = out["series_id"] != "usdinr_monthly_avg"
        out.loc[dollars, "value"] = (out.loc[dollars, "value"] / 1000).round(3)
        return out[["series_id", "period", "value", "note"]].sort_values(["series_id", "period"]).reset_index(drop=True)


SOURCE = RbiFxOperations()
