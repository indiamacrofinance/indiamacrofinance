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
        raws.append(raw)
        meta = body.get("meta_data")
        if meta is None:   # "No Data Found" is an empty list with no meta_data
            if body["data"]:
                raise RuntimeError(f"MoSPI {endpoint} response has data but no meta_data")
            return raws
        if page >= meta["totalPages"]:
            return raws
        page += 1


# PLFS cuts by religion, social group and education. Until 2026-11-04 the all-categories rows
# said "all" in each; the calendar-year tables now leave a field empty when a row is not cut by
# it, so the all-India total appears once per breakdown, all with the same value.
PLFS_BREAKDOWNS = ("religion", "socialGroup", "General_Education")


def plfs_total(r: dict) -> bool:
    """True for a PLFS row covering all religions, social groups and education levels."""
    return all(r.get(k) in (None, "", "all") for k in PLFS_BREAKDOWNS)


def plfs_year(label: str) -> str:
    """'PLFS 2024' (calendar-year tables since 2026-11-04) or '2024' -> '2024'; '2023-24' -> '2023-24'."""
    m = re.search(r"\d{4}(-\d{2})?", label)
    if not m:
        raise ValueError(f"unrecognised PLFS year: {label!r}")
    return m.group(0)


def rows(raws: list[Raw]) -> list[dict]:
    return [r for raw in raws for r in json.loads(raw.content)["data"]]
