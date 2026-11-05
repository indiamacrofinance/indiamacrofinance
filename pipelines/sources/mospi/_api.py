"""Shared helpers for MoSPI's eSankhyiki REST API (https://api.mospi.gov.in/api/<product>/...).

No key is needed. Page size limits differ by dataset (100 is safe everywhere).
Specs: https://esankhyiki.mospi.gov.in/layout/swagger_user_<product>.yaml
Filter codes: MCP server https://mcp.mospi.gov.in/mcp, tool get_metadata.
"""
from __future__ import annotations

import json
import re

from pipelines.core import Raw
from pipelines.core.http import fetch_raw

BASE = "https://api.mospi.gov.in/api"
PAGE = 100
MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], start=1)}


def month_period(year, month: str) -> str:
    """(2026, "September") -> "2026-09-01"."""
    return f"{int(year):04d}-{MONTHS[month]:02d}-01"


def pages(endpoint: str, params: dict) -> list[Raw]:
    """Fetch every page of one query; raises if the API returns an error body."""
    raws, page = [], 1
    while True:
        raw = fetch_raw(f"{BASE}/{endpoint}",
                        params={**params, "limit": PAGE, "page": page, "Format": "JSON"})
        body = json.loads(raw.content)
        if "data" not in body:
            raise RuntimeError(f"unexpected MoSPI {endpoint} response: {str(body)[:200]}")
        if "meta_data" not in body:   # "No Data Found": an empty list and no page count
            raise RuntimeError(f"MoSPI {endpoint} returned no data for {params}: {body.get('msg')!r}")
        raws.append(raw)
        if page >= body["meta_data"]["totalPages"]:
            return raws
        page += 1


# PLFS cuts by religion, social group and education. Until 2026-11-04 every row filled all
# three, the all-categories total saying "all" in each. The calendar-year tables now fill only
# the field a row is cut by: the national total appears once per breakdown (religion "all",
# social group "all", ...) plus once with all three empty, and state rows have all three empty.
PLFS_BREAKDOWNS = ("religion", "socialGroup", "General_Education")


def plfs_total_rank(r: dict) -> int | None:
    """Which PLFS rows are all-categories totals, best first: 0 = religion "all" and the others
    "all" or empty (both layouts); 1 = all three empty (state rows now); None = a breakdown.
    Parsers keep one row per period, the best-ranked, so repeated totals never conflict."""
    rel, soc, edu = (r.get(k) or None for k in PLFS_BREAKDOWNS)
    if rel == "all" and soc in ("all", None) and edu in ("all", None):
        return 0
    if rel is soc is edu is None:
        return 1
    return None


def keep_best_total(df, keys: list[str]):
    """Per keys, the rows with the lowest plfs_total_rank (column 'rank', dropped). Repeated
    totals of lower rank go; real duplicates (same rank) stay for validation to report."""
    if df.empty:
        return df
    return df[df["rank"] == df.groupby(keys)["rank"].transform("min")].drop(columns="rank")


def plfs_year(label: str) -> str:
    """'PLFS 2024' (calendar-year tables since 2026-11-04) or '2024' -> '2024'; '2023-24' -> '2023-24'."""
    m = re.search(r"\d{4}(?:-\d{2}(?!\d))?", label)
    if not m:
        raise ValueError(f"unrecognised PLFS year: {label!r}")
    return m.group(0)


def rows(raws: list[Raw]) -> list[dict]:
    return [r for raw in raws for r in json.loads(raw.content)["data"]]
