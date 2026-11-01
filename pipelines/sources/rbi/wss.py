"""RBI Weekly Statistical Supplement (WSS): FX reserves, bank business, ratios and rates.

Archive pages list every week's table as XLSX:
  https://www.rbi.org.in/Scripts/WSSViewDetail.aspx?TYPE=Section&PARAM1=<n>
  n=2 Foreign Exchange Reserves (weekly, "As on <Friday>")
  n=3 Scheduled Commercial Banks - Business in India (fortnightly "Outstanding as on <date>")
  n=4 Ratios and Rates (six "week ended" columns, the first a year earlier)
  n=7 Money Stock: Components and Sources (fortnightly; "Outstanding as on" Mar. 31 and the
      latest date, then variations, the last column year-on-year %)
  n=8 Reserve Money: Components and Sources (weekly; same layout)
  n=13 Certificates of Deposit, n=14 Commercial Paper (fortnightly rows: amount outstanding,
      amount issued in the fortnight, rate of interest as a range "5.50 - 6.92")
  n=25 Liquidity Operations by RBI (one row per day; the last column is net injection (+) /
      absorption (-), in Rs crore; "-" means none)
Files are printed tables, so rows are found by their label and dates by their header.
The first run backfills BACKFILL_WEEKS files per section; later runs take RECENT_WEEKS.
Overlapping weeks are harmless: publishing upserts by period.
"""
from __future__ import annotations

import io
import re
from datetime import date, datetime

import pandas as pd

from pipelines.core import Raw, Source
from pipelines.core.http import fetch_raw, get
from pipelines.core.store import load_series

ARCHIVE = "https://www.rbi.org.in/Scripts/WSSViewDetail.aspx?TYPE=Section&PARAM1={n}"
BACKFILL_WEEKS, RECENT_WEEKS = 60, 6
SECTION = {2: "fx", 3: "banks", 4: "rates", 7: "money", 8: "reserve_money", 25: "liquidity", 13: "cd", 14: "cp"}

FX_ROWS = {"Total Reserves": "fx_reserves_total", "Foreign Currency Assets": "fx_reserves_fca",
           "Gold": "fx_reserves_gold"}
BANK_LEVELS = {"2.1 Aggregate Deposits": "scb_deposits", "7 Bank Credit": "scb_credit",
               "7a.2 Non-food credit": "scb_nonfood_credit"}
BANK_GROWTH = {"2.1a Growth": "scb_deposits_growth", "7.1a Growth": "scb_credit_growth"}
# Last column of the level rows: the year-on-year change in Rs crore, current year.
BANK_YOY_CHANGE = {"2.1 Aggregate Deposits": "scb_deposits_yoy_change", "7 Bank Credit": "scb_credit_yoy_change"}
RATE_ROWS = {
    "Cash Reserve Ratio": "crr", "Statutory Liquidity Ratio": "slr", "Policy Repo Rate": "repo_rate",
    "Standing Deposit Facility": "sdf_rate", "Marginal Standing Facility": "msf_rate",
    "Call Money Rate": "wacr", "91-Day Treasury Bill": "tbill_91d_weekly",
    "182-Day Treasury Bill": "tbill_182d_weekly", "364-Day Treasury Bill": "tbill_364d_weekly",
    "10-Year G-Sec Par Yield": "gsec_10y_par_fbil",
}
MONEY_ROWS = {"M3": ("m3", "m3_growth"), "1.1 Currency with the Public": (None, "currency_public_growth")}
RESERVE_ROWS = {"Reserve Money": ("reserve_money", "reserve_money_growth")}
MONTH = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"


def parse_date(text: str, year: int | None = None) -> str | None:
    """'October 16, 2026' / 'Oct. 15, 2026' / ('Sep. 18', 2026) -> ISO date."""
    m = re.search(MONTH + r"\s*(\d{1,2})(?:,\s*(\d{4}))?", str(text))
    if not m:
        return None
    y = int(m.group(3)) if m.group(3) else year
    if y is None:
        return None
    return datetime.strptime(f"{m.group(1)} {m.group(2)} {y}", "%b %d %Y").date().isoformat()


def label(row) -> str:
    return " ".join(str(v) for v in row if isinstance(v, str)).strip()


def numbers(row) -> list[float]:
    out = []
    for v in row:
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return [x for x in out if pd.notna(x)]


def parse_fx(df: pd.DataFrame) -> list[dict]:
    as_on = next(d for d in (parse_date(v) for v in df.values.ravel() if isinstance(v, str)
                             and "As on" in v) if d)
    usd_col = next(c for c in df.columns if (df[c].astype(str).str.strip() == "US$ Mn.").any())
    rows = []
    for _, r in df.iterrows():
        text = label(r)
        sid = next((s for k, s in FX_ROWS.items() if re.match(r"^1(\.\d)?\s+" + k, text)), None)
        if sid and pd.notna(r[usd_col]):
            rows.append({"series_id": sid, "period": as_on, "value": float(r[usd_col]) / 1000})
    return rows


def parse_banks(df: pd.DataFrame) -> list[dict]:
    as_on = next(d for d in (parse_date(v) for v in df.values.ravel() if isinstance(v, str)
                             and "as on" in v.lower()) if d)
    rows = []
    for _, r in df.iterrows():
        text, nums = label(r), numbers(r)
        for key, sid in BANK_LEVELS.items():
            if text.startswith(key) and nums:
                rows.append({"series_id": sid, "period": as_on, "value": nums[0] / 1e5})
        for key, sid in BANK_YOY_CHANGE.items():
            if text.startswith(key) and len(nums) >= 6:
                rows.append({"series_id": sid, "period": as_on, "value": nums[-1] / 1e5})
        for key, sid in BANK_GROWTH.items():
            if text.startswith(key) and nums:
                # Last column is year-on-year growth for the current year, as published.
                rows.append({"series_id": sid, "period": as_on, "value": nums[-1]})
    return rows


def parse_rates(df: pd.DataFrame) -> list[dict]:
    header = df.index[df.apply(lambda r: label(r).startswith("Item/Week Ended"), axis=1)][0]
    years, dates = df.loc[header], df.loc[header + 1]
    col_date, year = {}, None
    for c in df.columns:
        if pd.notna(years[c]) and str(years[c]).strip().isdigit():
            year = int(str(years[c]).strip())
        d = parse_date(dates[c], year) if pd.notna(dates[c]) else None
        if d:
            col_date[c] = d
    rows = []
    for _, r in df.loc[header + 2:].iterrows():
        text = label(r)
        sid = next((s for k, s in RATE_ROWS.items() if text.startswith(k)), None)
        if not sid:
            continue
        for c, d in col_date.items():
            try:
                rows.append({"series_id": sid, "period": d, "value": float(r[c])})
            except (TypeError, ValueError):
                continue
    return rows


def parse_outstanding(df: pd.DataFrame, wanted: dict[str, tuple[str | None, str]]) -> list[dict]:
    """Money stock / reserve money: the level on the latest "Outstanding as on" date
    (Rs crore -> lakh crore) and RBI's year-on-year growth (the last column)."""
    head = df.index[df.apply(lambda r: "Outstanding as on" in label(r), axis=1)][0]
    level_col = next(c for c in df.columns if "Outstanding as on" in str(df.loc[head, c]))
    # The two "Outstanding as on" columns are Mar. 31 and the latest date. Below the header:
    # a row with the year (sometimes one row lower), and the "Mar. 31" row with the dates. Excel sometimes
    # stores the day as a date with the wrong year ("May 1" -> 2015-05-01): keep its month
    # and day only.
    last_col = level_col + 1
    year_row = next(i for i in range(head + 1, head + 4)
                    if any(str(df.loc[i, c]).strip()[:4].isdigit() for c in (level_col, last_col)))
    year = int(next(str(df.loc[year_row, c]).strip()[:4] for c in (last_col, level_col)
                    if str(df.loc[year_row, c]).strip()[:4].isdigit()))
    date_row = next(i for i in range(head + 1, head + 6) if str(df.loc[i, level_col]).startswith("Mar"))
    cell = df.loc[date_row, last_col]
    if isinstance(cell, (datetime, pd.Timestamp)):
        as_on = date(year, cell.month, cell.day).isoformat()
    else:
        as_on = parse_date(cell, year)
    if as_on is None:
        raise ValueError(f"no 'Outstanding as on' date in {cell!r}")
    rows = []
    for _, r in df.loc[date_row + 1:].iterrows():
        text = label(r)
        for key, (level_id, growth_id) in wanted.items():
            if text == key or text.startswith(key + " ") and key[0].isdigit():
                nums = numbers(r)
                if level_id and pd.notna(r[last_col]):
                    rows.append({"series_id": level_id, "period": as_on, "value": float(r[last_col]) / 1e5})
                if growth_id and nums:
                    rows.append({"series_id": growth_id, "period": as_on, "value": nums[-1]})
    return rows


def parse_money(df: pd.DataFrame) -> list[dict]:
    return parse_outstanding(df, MONEY_ROWS)


def parse_reserve_money(df: pd.DataFrame) -> list[dict]:
    return parse_outstanding(df, RESERVE_ROWS)


def parse_liquidity(df: pd.DataFrame) -> list[dict]:
    """Daily net liquidity. Published as net injection (+) / absorption (-); stored with the
    sign flipped, as the system's surplus (+) or deficit (-), in Rs lakh crore."""
    head = df.index[df.apply(lambda r: "Net Injection" in label(r), axis=1)][0]
    net_col = next(c for c in df.columns if "Net Injection" in str(df.loc[head, c]))
    rows = []
    for _, r in df.loc[head + 1:].iterrows():
        # The date is an Excel date in recent files and text ("May 25, 2026") in older ones.
        day = next((pd.Timestamp(v).date().isoformat() if isinstance(v, (datetime, pd.Timestamp))
                    else parse_date(v) for v in r if isinstance(v, (datetime, pd.Timestamp))
                    or isinstance(v, str) and parse_date(v)), None)
        if day is None:
            continue
        v = r[net_col]
        v = 0.0 if isinstance(v, str) and v.strip() in {"-", "–"} else float(v)
        rows.append({"series_id": "liquidity_surplus", "period": day,
                     "value": round(-v / 1e5, 4)})
    return rows


def parse_paper(df: pd.DataFrame, prefix: str) -> list[dict]:
    """CD / CP: per fortnight, outstanding (Rs lakh crore) and the low and high of the rate
    range on issues during the fortnight."""
    rows = []
    for _, r in df.iterrows():
        cells = [v for v in r if pd.notna(v)]
        if len(cells) < 4 or not isinstance(cells[0], str):
            continue
        day = parse_date(cells[0])
        rate = re.match(r"\s*(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)", str(cells[-1]))
        out = pd.to_numeric(cells[1], errors="coerce")
        if not (day and rate) or pd.isna(out):
            continue
        rows += [{"series_id": f"{prefix}_outstanding", "period": day, "value": round(float(out) / 1e5, 4)},
                 {"series_id": f"{prefix}_rate_low", "period": day, "value": float(rate.group(1))},
                 {"series_id": f"{prefix}_rate_high", "period": day, "value": float(rate.group(2))}]
    return rows


PARSERS = {2: parse_fx, 3: parse_banks, 4: parse_rates, 7: parse_money, 8: parse_reserve_money,
           25: parse_liquidity, 13: lambda df: parse_paper(df, "cd"), 14: lambda df: parse_paper(df, "cp")}
# Table titles printed in each file (the section is read from the file, not its name).
TITLES = {"Foreign Exchange Reserves": 2, "Scheduled Commercial Banks - Business in India": 3,
          "Ratios and Rates": 4, "Money Stock: Components and Sources": 7,
          "Reserve Money: Components and Sources": 8, "Liquidity Operations by RBI": 25,
          "Certificates of Deposit": 13, "Commercial Paper": 14}


def section_of(df: pd.DataFrame) -> int:
    text = " ".join(str(v) for v in df.head(4).values.ravel() if isinstance(v, str))
    for title, n in TITLES.items():
        if title in text:
            return n
    raise ValueError(f"unrecognised WSS table: {text[:80]!r}")
# Series per section: if any has little history yet, that section backfills.
MIN_HISTORY = 20
SECTION_SERIES = {2: list(FX_ROWS.values()),
                  3: [*BANK_LEVELS.values(), *BANK_GROWTH.values(), *BANK_YOY_CHANGE.values()],
                  4: list(dict.fromkeys(RATE_ROWS.values())),
                  7: ["m3", "m3_growth", "currency_public_growth"],
                  8: ["reserve_money", "reserve_money_growth"],
                  25: ["liquidity_surplus"],
                  13: ["cd_outstanding", "cd_rate_low", "cd_rate_high"],
                  14: ["cp_outstanding", "cp_rate_low", "cp_rate_high"]}


class RbiWSS(Source):
    name = "rbi_wss"
    series_ids = (*FX_ROWS.values(), *BANK_LEVELS.values(), *BANK_GROWTH.values(), *BANK_YOY_CHANGE.values(),
                  *dict.fromkeys(RATE_ROWS.values()), *SECTION_SERIES[7], *SECTION_SERIES[8],
                  *SECTION_SERIES[25], *SECTION_SERIES[13], *SECTION_SERIES[14])

    def fetch(self) -> list[Raw]:
        raws = []
        for n in SECTION:
            page = get(ARCHIVE.format(n=n)).text
            links = list(dict.fromkeys(re.findall(
                r'https://rbidocs\.rbi\.org\.in/rdocs/Wss/DOCs/\d+T_[0-9A-F]+\.XLSX', page)))
            if not links:
                raise RuntimeError(f"no WSS XLSX links on section {n} archive page")
            short = any(len(load_series(s)) < MIN_HISTORY for s in SECTION_SERIES[n])
            take = BACKFILL_WEEKS if short else RECENT_WEEKS
            for url in links[:take]:
                raws.append(fetch_raw(url, suffix=".xlsx"))
        return raws

    def parse(self, raws: list[Raw]) -> pd.DataFrame:
        rows = []
        for raw in raws:
            df = pd.read_excel(io.BytesIO(raw.content), header=None).dropna(how="all").dropna(axis=1, how="all")
            df = df.reset_index(drop=True)
            df.columns = range(df.shape[1])
            rows += PARSERS[section_of(df)](df)
        out = pd.DataFrame(rows)
        # Several files cover the same week (the rates table repeats recent weeks), and RBI
        # revises earlier prints. Raws arrive newest publication first, so keep the first
        # value seen for each week: the latest published one.
        conflicts = out.groupby(["series_id", "period"])["value"].nunique()
        conflicts = conflicts[conflicts > 1]
        if len(conflicts):
            print(f"  WSS: {len(conflicts)} week(s) revised between prints; keeping the latest print: "
                  f"{[f'{s} {p}' for s, p in conflicts.index[:5]]}")
        out = out.drop_duplicates(subset=["series_id", "period"], keep="first")
        out["note"] = "RBI WSS"
        return out[out["period"] <= date.today().isoformat()]


SOURCE = RbiWSS()
