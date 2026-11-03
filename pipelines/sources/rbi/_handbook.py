"""RBI Handbook of Statistics on the Indian Economy: find a table by its title, in the current
edition or an archived one.

The Handbook page is an ASP.NET form: GET gives the current edition; POSTing `hdnYear` (with
the page's hidden fields) gives the edition published that year (hdnYear=2026 -> 2025-26,
2016 -> 2015-16, 2013 -> 2012-13). Table numbers change between editions, so tables are found
by title. Each table row links a PDF and, from the 2009-10 edition on, an XLS/XLSX; the
2013-14 and 2014-15 editions are PDF only.

Each edition carries only the last few years of a table (the quarterly BoP tables: 16
quarters in the older presentation, 8 in BPM6), so a long history is stitched together from
successive editions; the newest edition wins where they overlap (it has the revisions).
"""
from __future__ import annotations

import html
import re

import httpx

from pipelines.core.http import HEADERS

PAGE = "https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook+of+Statistics+on+Indian+Economy"


def table_files(page: str) -> list[tuple[str, list[str]]]:
    """[(title, [file urls])] for every table on a Handbook page, files in page order."""
    out = []
    for chunk in page.split("class='link2'")[1:]:
        title = re.match(r"\s*href=PublicationsView\.aspx\?id=\d+>([^<]+)</a>", chunk)
        if not title:
            continue
        row = chunk.split("</tr>")[0]
        urls = re.findall(r"""href=['"]?(https?://rbidocs\.rbi\.org\.in/[^'" >]+\.(?:xlsx?|pdf))""", row, re.IGNORECASE)
        out.append((" ".join(html.unescape(title.group(1)).split()), [u.replace(" ", "%20") for u in urls]))
    return out


def find(page: str, pattern: str, pdf_ok: bool = False) -> str | None:
    """URL of the first table whose title matches `pattern`: its spreadsheet, else (if
    pdf_ok) its PDF."""
    for title, urls in table_files(page):
        if re.search(pattern, title, re.IGNORECASE):
            sheets = [u for u in urls if not u.lower().endswith(".pdf")]
            pdfs = [u for u in urls if u.lower().endswith(".pdf")]
            return (sheets or (pdfs if pdf_ok else []) or [None])[0]
    return None


def edition(page: str) -> str | None:
    """'2025-26' from a Handbook page."""
    m = re.search(r"Handbook of Statistics on (?:the )?Indian Economy,?\s*(\d{4}-\d{2})", page)
    return m.group(1) if m else None


def pages(years: list[int] | None = None) -> list[str]:
    """The current Handbook page, or (with `years`) the page of the edition published in each year."""
    with httpx.Client(headers=HEADERS, timeout=120, follow_redirects=True) as client:
        current = client.get(PAGE).text
        if not years:
            return [current]
        fields = dict(re.findall(r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', current))
        return [client.post(PAGE, data=dict(fields, hdnYear=str(y))).text for y in years]
