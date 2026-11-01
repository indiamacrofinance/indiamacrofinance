"""RBI's quarter-by-quarter projections of CPI inflation and real GDP growth, from each MPC
resolution (the same minutes as mpc_decisions.py). RBI's Monetary Policy Report compares these
with outturns (Charts III.2 and IV.3); we keep every meeting's path.

Sentences that project (contain "project") and name CPI inflation or GDP growth are read for
quarter figures, in the wordings used since 2016:
  "CPI inflation ... for 2026-27 ... with Q2 at 4.9 per cent; Q3 at 6.0 per cent"
  "... with Q1:2023-24 at 7.8 per cent; Q2 at 6.2 per cent"
  "... with Q1 at 6.7 per cent; Q2 at 7.0 per cent; and Q3 and Q4 at 6.5 per cent each"
  "CPI inflation for Q1:2026-27 and Q2 are projected at 3.9 per cent and 4.0 per cent, respectively"
  "CPI inflation for Q1:2025-26 is projected at 4.4 per cent"
A bare "Q2" belongs to the last financial year named before it in the sentence.

Panels (entity = target quarter "2026-27 Q3", period = month of the meeting, value = %):
  mpc_cpi_projection_q, mpc_gdp_projection_q
"""
from __future__ import annotations

import re

import pandas as pd

from pipelines.core import Raw, Source
from pipelines.core.http import fetch_raw
from pipelines.core.store import load_panel
from pipelines.sources.rbi._minutes import FIRST_MEETING, TITLE, meeting_period, text_of
from pipelines.sources.rbi._press import RELEASE, releases
from pipelines.sources.rbi.mpc_decisions import SENTENCE

QUARTER = re.compile(r"Q([1-4])(?:\s*:\s*(20\d\d-\d\d))?")
FY = re.compile(r"\b(20\d\d-\d\d)\b")
VALUE = r"(-?\d{1,2}(?:\.\d{1,2})?)\s*per\s*cent"
SUBJECTS = {"mpc_cpi_projection_q": r"\b(CPI|[Hh]eadline) inflation", "mpc_gdp_projection_q": r"GDP growth"}


def quarter_values(sentence: str) -> dict[str, float]:
    """{"2026-27 Q3": 6.0, ...} from one projection sentence."""
    s = re.sub(r"\s+", " ", sentence)
    out: dict[str, float] = {}
    fy = None

    def label(m) -> str | None:
        nonlocal fy
        if m.group(2):
            fy = m.group(2)
        else:
            before = FY.findall(s[:m.start()])
            fy = before[-1] if before else fy
        return f"{fy} Q{m.group(1)}" if fy else None

    # "Q1:2026-27 and Q2 are projected at 3.9 per cent and 4.0 per cent, respectively"
    resp = re.search(r"((?:Q[1-4](?:\s*:\s*20\d\d-\d\d)?(?:,\s*|\s+and\s+)?)+)[^.]*?(?:at|to|be)\s+((?:" + VALUE
                     + r"(?:,\s*|\s+and\s+)?)+),?\s+respectively", s)
    if resp:
        qs = [label(m) for m in QUARTER.finditer(resp.group(1))]
        vs = [float(v) for v in re.findall(VALUE, resp.group(2))]
        if len(qs) == len(vs):
            out.update({q: v for q, v in zip(qs, vs) if q})
        return out
    # "Q3 and Q4 at 6.5 per cent each"
    for m in re.finditer(r"Q([1-4])(?:\s*:\s*(20\d\d-\d\d))?\s+and\s+Q([1-4])\s+at\s+" + VALUE + r"\s+each", s):
        first = label(m)
        if first:
            out[first] = float(m.group(4))
            out[f"{fy} Q{m.group(3)}"] = float(m.group(4))
    # "Q2 at 4.9 per cent", "Q1:2023-24 at 7.8 per cent", "for Q1:2025-26 is projected at 4.4 per cent"
    for m in re.finditer(r"Q([1-4])(?:\s*:\s*(20\d\d-\d\d))?(?:\s+is\s+projected)?\s+(?:at|to be)\s+" + VALUE, s):
        q = label(m)
        if q and q not in out:
            out[q] = float(m.group(3))
    return out


def parse_minutes(text: str) -> list[dict]:
    period = meeting_period(text)
    stop = text.find("Statement by")
    head = text[:stop if stop > 0 else None]
    rows = []
    for sentence in SENTENCE.split(head):
        if "project" not in sentence:
            continue
        for sid, subject in SUBJECTS.items():
            if re.search(subject, sentence) and not ("core" in sentence.lower() and sid == "mpc_cpi_projection_q"):
                rows += [{"series_id": sid, "entity": q, "period": period, "value": v}
                         for q, v in quarter_values(sentence).items()]
    return rows


class MpcProjectionsQ(Source):
    name = "rbi_mpc_projections_q"
    panel = True
    series_ids = tuple(SUBJECTS)

    def fetch(self) -> list[Raw]:
        rescan = load_panel("mpc_cpi_projection_q")["period"].nunique() < 10
        months = (pd.Period.now(freq="M") - FIRST_MEETING).n + 1 if rescan else 4
        found = releases(lambda t: t.startswith(TITLE), months)
        if not found:
            raise RuntimeError(f"no MPC minutes in the last {months} months of the RBI press index")
        return [fetch_raw(RELEASE.format(prid=p), suffix=".html") for p in sorted(found)]

    def parse(self, raws: list[Raw]) -> pd.DataFrame:
        rows = []
        for raw in raws:
            rows += parse_minutes(text_of(raw.content))
        df = pd.DataFrame(rows)
        df["note"] = "MPC resolution"
        return df.drop_duplicates(["series_id", "entity", "period"], keep="last")


SOURCE = MpcProjectionsQ()
