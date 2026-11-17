"""Vehicle retail sales (registrations), monthly, from FADA's press releases.

The Federation of Automobile Dealers Associations compiles retail registrations from the
Vahan portal each month. https://fada.in/press-release-list.php (and ?page=2, ...) links
PDFs named like "FADA Releases September 2026 Vehicle Retail Data.pdf" (from Oct 2026,
"FADA_Press_Release_Oct_26.pdf"). A page near the end has the table
    All India Vehicle Retail Data for Sep'26
    CATEGORY Sep'26 Aug'26 Sep'25 MoM% YoY%
    2W 17,90,188 17,14,610 13,45,153 4.41% 33.08%
    ...
    Total 25,36,920 24,23,201 19,24,546 4.69% 31.82%
From Oct 2026 a festive table ("... for Navratri'26") can come before it; only a table
headed by a month is read. Columns are read from the month labels in the header, so a table
without the previous month still parses; labels are "Sep'26" or "July'25". Sub-rows
(E-RICKSHAW, LCV, ...) are skipped. Counts use Indian digit grouping. FADA restates earlier
months (more registration offices are covered over time; year-ago columns differ from the month's own release by up
to about 5%), so the newest release wins, which keeps the levels consistent with FADA's
printed y/y growth (its own figure for the release month).

Series (thousand units): vehicle_retail_total, vehicle_retail_2w, vehicle_retail_3w,
vehicle_retail_pv, vehicle_retail_cv, vehicle_retail_tractor; and the same with _growth
(% y/y as published).
"""
from __future__ import annotations

import io
import re
import urllib.parse
from datetime import datetime

import pandas as pd
import pdfplumber

from pipelines.core import Raw, Source
from pipelines.core.http import fetch_raw, get
from pipelines.core.store import load_series

LIST = "https://fada.in/press-release-list.php"
BACKFILL_PAGES, RECENT_PAGES, MIN_HISTORY = 2, 1, 12
ROWS = {"2W": "2w", "3W": "3w", "PV": "pv", "CV": "cv", "TRAC": "tractor", "Total": "total"}
HEAD = re.compile(r"All India Vehicle Retail Data for ([A-Za-z]{3,9})[’'`]\s?(\d{2})\b")
MON = re.compile(r"([A-Za-z]{3,9})[’'`](\d{2})")
NUM = r"(-?[\d,]+)"


def month(mon: str, yy: str) -> str:
    return datetime.strptime(f"{mon[:3].title()} 20{yy}", "%b %Y").strftime("%Y-%m-01")


MONTHS = {datetime(2026, m, 1).strftime(f).lower() for m in range(1, 13) for f in ("%b", "%B")} | {"sept"}


def is_month(name: str) -> bool:
    """'Oct', 'Sept', 'October' -> True; 'Navratri' -> False."""
    return name.lower() in MONTHS


def release_links(page: str) -> list[str]:
    """Monthly retail releases: 'FADA Releases September 2026 Vehicle Retail Data.pdf', and from
    Oct 2026 'FADA_Press_Release_Oct_26.pdf'. Festive-period releases ('..._Navratri'26_...')
    and other press releases are left out."""
    def monthly(name: str) -> bool:
        if re.search(r"vehicle retail data", name, re.I):
            return True
        m = re.search(r"Press[_ ]Release[_ ]([A-Za-z]{3,9})[_ ]'?(\d{2})\.pdf$", name, re.I)
        return bool(m) and is_month(m.group(1))
    links = re.findall(r'href="(images/press-release/[^"]+\.pdf)"', page, re.I)
    return ["https://fada.in/" + urllib.parse.quote(l) for l in links if monthly(l)]


def parse_release(content: bytes) -> list[dict]:
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    lines = text.splitlines()
    # The month's table; from Oct 2026 a festive table ("... for Navratri'26") can come first.
    start = next((i for i, l in enumerate(lines) if (h := HEAD.search(l)) and is_month(h.group(1))), None)
    if start is None:
        raise ValueError("no 'All India Vehicle Retail Data for <Mon'yy>' table")
    header = next(l for l in lines[start + 1:start + 4] if l.startswith("CATEGORY"))
    periods = [month(*m) for m in MON.findall(header)]
    if not periods or periods[0] != month(*HEAD.search(lines[start]).groups()):
        raise ValueError(f"unexpected header: {header!r}")
    rows = []
    for line in lines[start + 2:start + 40]:
        m = re.match(rf"^(2W|3W|PV|CV|TRAC|Total)\s+{' '.join([NUM] * len(periods))}(.*)$", line)
        if not m:
            if line.startswith("Source"):
                break
            continue
        key = ROWS[m.group(1)]
        for i, period in enumerate(periods):
            rows.append({"series_id": f"vehicle_retail_{key}", "period": period,
                         "value": round(int(m.group(i + 2).replace(",", "")) / 1000, 3), "own": i == 0})
        pct = re.findall(r"(-?\d+(?:\.\d+)?)%", m.group(len(periods) + 2))
        if pct and "YoY" in header:
            rows.append({"series_id": f"vehicle_retail_{key}_growth", "period": periods[0],
                         "value": float(pct[-1]), "own": True})
    if {r["series_id"] for r in rows} < {f"vehicle_retail_{k}" for k in ROWS.values()}:
        raise ValueError("FADA table: some categories missing")
    return rows


class FadaRetail(Source):
    name = "fada_retail"
    series_ids = tuple(f"vehicle_retail_{k}{s}" for k in ROWS.values() for s in ("", "_growth"))

    def fetch(self) -> list[Raw]:
        pages = BACKFILL_PAGES if len(load_series("vehicle_retail_total")) < MIN_HISTORY else RECENT_PAGES
        links = []
        for n in range(1, pages + 1):
            links += release_links(get(LIST if n == 1 else f"{LIST}?page={n}").text)
        if not links:
            raise RuntimeError("no FADA vehicle retail releases linked")
        return [fetch_raw(u, suffix=".pdf") for u in links]

    def parse(self, raws: list[Raw]) -> pd.DataFrame:
        releases = []
        for raw in raws:
            try:
                rows = parse_release(raw.content)
            except ValueError:
                continue                                   # e.g. a festive-only release
            releases.append((next(r["period"] for r in rows if r["own"]), rows))
        if not releases:
            raise ValueError("no FADA retail tables parsed")
        out = []
        for release, rows in sorted(releases, key=lambda x: x[0]):   # oldest first: newest wins
            out += [dict(r, note=f"FADA, {release[:7]} release") for r in rows]
        out = pd.DataFrame(out).drop_duplicates(["series_id", "period"], keep="last")
        return out.drop(columns="own").reset_index(drop=True)


SOURCE = FadaRetail()
