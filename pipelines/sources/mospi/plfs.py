"""MoSPI Periodic Labour Force Survey, all-India: monthly, quarterly and annual.

API: GET https://api.mospi.gov.in/api/plfs/getData; indicator_code takes ONE value per call.
- Monthly (frequency_code=3, from 2025): current weekly status (CWS), indicators 1-3.
- Quarterly bulletin (frequency_code=2, from 2018): CWS, urban (rural + urban from 2025).
- Annual (frequency_code=1): usual status (PS+SS), by agricultural year (July-June,
  2017-18 onwards; year_type_code=1) and calendar year (2022 onwards; year_type_code=2),
  narrowed to all-India headline rows by ANNUAL_FILTER.
Values are percentages as published. CWS and usual status are different concepts and
are kept in separate series.
"""
from __future__ import annotations

import pandas as pd

from pipelines.core import Raw, Source
from pipelines.sources.mospi._api import month_period, pages, plfs_total, plfs_year, rows

ENDPOINT = "plfs/getData"
INDICATORS = {1: "lfpr", 2: "wpr", 3: "ur"}
AGES = {1: "15 years and above", 2: "15-29 years"}
# (indicator, age, gender, sector) -> series id
SERIES = {
    ("ur", "15 years and above", "person", "rural + urban"): "plfs_ur_monthly",
    ("ur", "15 years and above", "person", "rural"): "plfs_ur_rural_monthly",
    ("ur", "15 years and above", "person", "urban"): "plfs_ur_urban_monthly",
    ("ur", "15 years and above", "female", "rural + urban"): "plfs_ur_female_monthly",
    ("ur", "15-29 years", "person", "rural + urban"): "plfs_ur_youth_monthly",
    ("lfpr", "15 years and above", "person", "rural + urban"): "plfs_lfpr_monthly",
    ("lfpr", "15 years and above", "female", "rural + urban"): "plfs_lfpr_female_monthly",
    ("wpr", "15 years and above", "person", "rural + urban"): "plfs_wpr_monthly",
}
NAMES = {"LFPR": "lfpr", "WPR": "wpr", "UR ": "ur"}


# Quarterly: (indicator, sector) for persons 15+ -> series id.
QUARTERLY = {("ur", "urban"): "plfs_ur_quarterly_urban", ("lfpr", "urban"): "plfs_lfpr_quarterly_urban"}
# Annual usual status (PS+SS), 15+, rural + urban: (indicator, gender, year type) -> series id.
ANNUAL = {("ur", "person", "Agriculture Year"): "plfs_ur_usual_ay",
          ("lfpr", "person", "Agriculture Year"): "plfs_lfpr_usual_ay",
          ("lfpr", "female", "Agriculture Year"): "plfs_lfpr_female_usual_ay",
          ("ur", "person", "Calendar Year"): "plfs_ur_usual_cy"}
# Annual queries return every state/religion/caste/education cut (~26k rows) unless narrowed:
# all-India, usual status (PS+SS), rural + urban, 15+. The agricultural-year tables also take
# "all categories" codes. The calendar-year tables return nothing with them since 2026-11-04
# (their total rows leave those fields empty), so they are narrowed in parse (plfs_total).
ANNUAL_FILTER = {"state_code": 99, "weekly_status_code": 1, "sector_code": 3, "age_code": 1, "gender_code": "2,3"}
ALL_CATEGORIES = {"religion_code": 1, "social_category_code": 1, "education_code": 0}
QUARTER_START = {"Jan-Mar": 1, "Apr-Jun": 4, "Jul-Sep": 7, "Oct-Dec": 10}


def annual_period(year: str, year_type: str) -> str:
    """'2023-24' (agricultural year, July-June) -> '2023-07-01'; '2025' (calendar) -> '2025-01-01'."""
    return f"{year[:4]}-07-01" if year_type == "Agriculture Year" else f"{year[:4]}-01-01"


class MospiPLFS(Source):
    name = "mospi_plfs"
    series_ids = (*SERIES.values(), *QUARTERLY.values(), *ANNUAL.values())

    def fetch(self) -> list[Raw]:
        raws = []
        for code in INDICATORS:
            for age in AGES:
                raws += pages(ENDPOINT, {"indicator_code": code, "frequency_code": 3, "age_code": age})
        for code in (1, 3):  # LFPR, UR
            raws += pages(ENDPOINT, {"indicator_code": code, "frequency_code": 2, "age_code": 1, "gender_code": 3})
            # 1 = agricultural year (July-June), 2 = calendar year
            raws += pages(ENDPOINT, {"indicator_code": code, "frequency_code": 1, "year_type_code": 1,
                                     **ANNUAL_FILTER, **ALL_CATEGORIES})
            raws += pages(ENDPOINT, {"indicator_code": code, "frequency_code": 1, "year_type_code": 2,
                                     **ANNUAL_FILTER})
        return raws

    def parse(self, raws: list[Raw]) -> pd.DataFrame:
        out = []
        for r in rows(raws):
            if r.get("state") != "All India" or r.get("value") in (None, ""):
                continue
            ind = next((v for k, v in NAMES.items() if r["indicator"].startswith(k)), None)
            freq = r.get("frequency")
            if freq == "Monthly":
                sid = SERIES.get((ind, r["AgeGroup"], r["gender"], r["sector"]))
                period, note = (month_period(r["year"], r["month"]) if sid else None), "CWS, published"
            elif freq == "Quarterly" and r["AgeGroup"] == "15 years and above" and r["gender"] == "person":
                sid = QUARTERLY.get((ind, r["sector"]))
                period = f"{int(r['year']):04d}-{QUARTER_START[r['quarter']]:02d}-01" if sid else None
                note = "CWS, quarterly bulletin"
            elif (freq == "Annually" and r["AgeGroup"] == "15 years and above" and r["sector"] == "rural + urban"
                  and r.get("weekly_status") == "PS+SS" and plfs_total(r)):
                sid = ANNUAL.get((ind, r["gender"], r.get("year_type")))
                year = plfs_year(r["year"]) if sid else None
                period = annual_period(year, r["year_type"]) if sid else None
                note = f"usual status (PS+SS), {r['year_type'].lower()} {year}"
            else:
                continue
            if sid:
                out.append({"series_id": sid, "period": period, "value": float(r["value"]), "note": note})
        # Calendar-year totals repeat once per breakdown (see plfs_total); they must agree.
        df = pd.DataFrame(out).drop_duplicates()
        clash = df[df.duplicated(["series_id", "period"], keep=False)] if not df.empty else df
        if not clash.empty:
            raise ValueError(f"conflicting PLFS totals: {clash.to_dict('records')[:4]}")
        return df


SOURCE = MospiPLFS()
