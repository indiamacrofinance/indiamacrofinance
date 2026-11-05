"""State-level panels from MoSPI's API: CPI, PLFS and GSDP growth.

- CPI (base 2024, current series, combined, general index): index and published y/y
  inflation by state, monthly from 2025 (inflation from 2026).
- PLFS annual, calendar year, usual status (PS+SS), 15+, persons, rural + urban, all
  categories: unemployment rate and LFPR by state (2022 onwards).
- NAS indicator 26 (GSDP growth rate), base 2011-12, constant prices, by financial year.
  The 2022-23 national base has no state series yet.
State names are mapped to registry/states.yaml; all-India rows are dropped.
"""
from __future__ import annotations

import pandas as pd

from pipelines.core import Raw, Source
from pipelines.core.states import canonical
from pipelines.sources.mospi._api import month_period, pages, plfs_total, plfs_year, rows

# No "all categories" codes: since 2026-11-04 the calendar-year tables return nothing with them
# (their total rows leave those fields empty); parse keeps the totals (plfs_total).
PLFS_STATE = {"weekly_status_code": 1, "sector_code": 3, "age_code": 1, "gender_code": 3,
              "frequency_code": 1, "year_type_code": 2}


class MospiStates(Source):
    name = "mospi_states"
    panel = True
    series_ids = ("state_cpi_index", "state_cpi_inflation", "state_ur_cy", "state_lfpr_cy", "state_gsdp_growth")

    def fetch(self) -> list[Raw]:
        return (pages("cpi/getCPIData", {"base_year": "2024", "series": "Current", "sector_code": "3", "division_code": "0"})
                + pages("plfs/getData", {**PLFS_STATE, "indicator_code": 3})
                + pages("plfs/getData", {**PLFS_STATE, "indicator_code": 1})
                + pages("nas/getNASData", {"base_year": "2011-12", "series": "Current", "frequency_code": "Annually",
                                           "indicator_code": 26}))

    def parse(self, raws: list[Raw]) -> pd.DataFrame:
        out = []
        for r in rows(raws):
            state = r.get("state")
            if not state or canonical(state) is None:
                continue
            entity = canonical(state)
            if r.get("base_year") == "2024" and r.get("division") == "CPI (General)" and r.get("sector") == "Combined":
                period = month_period(r["year"], r["month"])
                out.append({"series_id": "state_cpi_index", "entity": entity, "period": period, "value": float(r["index"])})
                if r.get("inflation") not in (None, ""):
                    out.append({"series_id": "state_cpi_inflation", "entity": entity, "period": period,
                                "value": float(r["inflation"])})
            elif (r.get("frequency") == "Annually" and r.get("year_type") == "Calendar Year"
                  and r.get("value") not in (None, "") and plfs_total(r)):
                sid = "state_ur_cy" if r["indicator"].startswith("UR") else "state_lfpr_cy" if r["indicator"].startswith("LFPR") else None
                if sid:
                    out.append({"series_id": sid, "entity": entity, "period": f"{plfs_year(r['year'])}-01-01",
                                "value": float(r["value"])})
            elif r.get("indicator") == "GSDP Growth Rate" and r.get("constant_price") not in (None, ""):
                out.append({"series_id": "state_gsdp_growth", "entity": entity, "period": f"{r['year'][:4]}-04-01",
                            "value": float(r["constant_price"])})
        df = pd.DataFrame(out).drop_duplicates()
        clash = df[df.duplicated(["series_id", "entity", "period"], keep=False)] if not df.empty else df
        if not clash.empty:
            raise ValueError(f"conflicting state values: {clash.to_dict('records')[:4]}")
        df["note"] = "MoSPI"
        return df


SOURCE = MospiStates()
