"""MoSPI Consumer Price Index (base 2024), all-India, via the eSankhyiki API.

API: GET https://api.mospi.gov.in/api/cpi/getCPIData (no key; max 100 rows/page on base 2012).
Spec: https://esankhyiki.mospi.gov.in/layout/swagger_user_cpi.yaml

Index series join MoSPI's official *back series* (2013-2024, the old series
projected onto the 2024 base by MoSPI's linking factor) to the *current series*
(2025 onwards). MoSPI does the linking; we do not splice anything ourselves.

`cpi_headline_inflation` is the y/y inflation rate **as officially published**:
2014-2024 from the back series, 2025 from the 2012-base series (the official
figure at the time; the 2024-base current series carries no 2025 inflation),
2026 onwards from the 2024-base current series. The note column says which.

Component indices (combined, all-India, 2025 onwards) feed the core CPI measure in
pipelines/sources/derived/core_cpi.py: food and beverages (division 01), electricity,
gas and other fuels (group 04.5) and fuels and lubricants for personal transport
equipment (class 07.2.2) - RBI's "food" and "fuel" in its CPI-excluding-food-and-fuel.
All 12 COICOP divisions are also stored, for the inflation detail page.
"""
from __future__ import annotations

import json

import pandas as pd

from pipelines.core import Raw, Source
from pipelines.core.store import load_series
from pipelines.sources.mospi._api import pages

MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], start=1)}

# 2024-base codes (from the MoSPI MCP get_metadata call): state 1 = All India;
# sector 1 Rural, 2 Urban, 3 Combined; division 0 = CPI (General), 1 = Food and beverages.
INDEX_SERIES = {
    ("Combined", "CPI (General)"): "cpi_headline_index",
    ("Rural", "CPI (General)"): "cpi_rural_index",
    ("Urban", "CPI (General)"): "cpi_urban_index",
}
# (division, group, class) at the combined level -> series. Divisions requested from the
# API return every lower level too, so these are fetched incrementally (see fetch()).
COMPONENT_SERIES = {
    ("Food and beverages", None, None): "cpi_food_bev_index",
    ("Housing, water, electricity, gas and other fuels", "Electricity, gas and other fuels", None):
        "cpi_elec_gas_fuels_index",
    ("Transport", "Operation of personal transport equipment",
     "Fuels and lubricants for personal transport equipment"): "cpi_vehicle_fuels_index",
}
# Every other COICOP 2018 division (combined, division level).
DIVISIONS = {
    "Paan, tobacco and intoxicants": "cpi_paan_tobacco_index",
    "Clothing and footwear": "cpi_clothing_index",
    "Housing, water, electricity, gas and other fuels": "cpi_housing_utilities_index",
    "Furnishings, household equipment and routine household maintenance": "cpi_household_goods_index",
    "Health": "cpi_health_index",
    "Transport": "cpi_transport_index",
    "Information and communication": "cpi_info_comm_index",
    "Recreation, sport and culture": "cpi_recreation_index",
    "Education services": "cpi_education_index",
    "Restaurants and accommodation services": "cpi_restaurants_index",
    "Personal care, social protection and miscellaneous goods and services": "cpi_personal_care_index",
}
COMPONENT_SERIES.update({(div, None, None): sid for div, sid in DIVISIONS.items()})
COMPONENT_DIVISIONS = ",".join(str(i) for i in range(1, 13))


def _period(year, month: str) -> str:
    return f"{int(year):04d}-{MONTHS[month]:02d}-01"


def months_since(last_period: str | float | None, back: int) -> dict[int, list[int]] | None:
    """{year: [months]} from `back` months before last_period up to today; None if no history."""
    if not isinstance(last_period, str) or not last_period:
        return None
    start = pd.Period(last_period[:7], freq="M") - back
    out: dict[int, list[int]] = {}
    for p in pd.period_range(start, pd.Period.now(freq="M"), freq="M"):
        out.setdefault(p.year, []).append(p.month)
    return out


def _float(x) -> float | None:
    return None if x in (None, "", "NA") else float(x)


class MospiCPI(Source):
    name = "mospi_cpi"
    series_ids = (*INDEX_SERIES.values(), *COMPONENT_SERIES.values(), "cpi_headline_inflation")

    def fetch(self) -> list[Raw]:
        base24 = {"base_year": "2024", "state_code": "1", "sector_code": "1,2,3"}
        raws = (pages("cpi/getCPIData", {**base24, "division_code": "0", "series": "Back"})
                + pages("cpi/getCPIData", {**base24, "division_code": "0", "series": "Current"}))
        # Component divisions return every item too (~20k rows), so after the first full
        # load fetch only the months from two before the oldest last-stored component.
        lasts = [load_series(s)["period"].max() for s in COMPONENT_SERIES.values()]
        recent = None if any(not isinstance(x, str) for x in lasts) else months_since(min(lasts), back=2)
        comp = {"base_year": "2024", "state_code": "1", "sector_code": "3",
                "division_code": COMPONENT_DIVISIONS, "series": "Current"}
        if recent is None:
            raws += pages("cpi/getCPIData", comp)
        else:
            for year, months in recent.items():
                raws += pages("cpi/getCPIData", {**comp, "year": str(year), "month_code": ",".join(map(str, months))})
        # Official 2025 headline inflation, published on the 2012 base.
        return raws + pages("cpi/getCPIData", {"base_year": "2012", "level": "Group", "series": "Current",
                                   "year": "2025", "state_code": "99", "sector_code": "3"})

    def parse(self, raws: list[Raw]) -> pd.DataFrame:
        rows, inflation = [], {}
        for raw in raws:
            for r in json.loads(raw.content)["data"]:
                period = _period(r["year"], r["month"])
                if r.get("base_year") == "2024":
                    if r.get("sub_class") is not None or r.get("item") is not None:
                        continue
                    if r.get("group") is None:
                        sid = INDEX_SERIES.get((r["sector"], r["division"]))
                    else:
                        sid = None
                    if sid is None and r["sector"] == "Combined":
                        sid = COMPONENT_SERIES.get((r["division"], r.get("group"), r.get("class")))
                    if sid is None:
                        continue
                    rows.append({"series_id": sid, "period": period, "value": float(r["index"])})
                    infl = _float(r.get("inflation"))
                    if sid == "cpi_headline_index" and infl is not None:
                        inflation[period] = (infl, f"published, base 2024 {r['series'].lower()} series")
                elif r.get("baseyear") == "2012" and r.get("group") == "General" \
                        and r.get("sector") == "Combined":
                    infl = _float(r.get("inflation"))
                    # Never overwrite a 2024-base figure with a 2012-base one.
                    if infl is not None and period not in inflation:
                        inflation[period] = (infl, "published, base 2012 series")
        rows += [{"series_id": "cpi_headline_inflation", "period": p, "value": v, "note": n}
                 for p, (v, n) in inflation.items()]
        df = pd.DataFrame(rows)
        df["note"] = df.get("note", pd.Series(dtype=str)).fillna("")
        return df


SOURCE = MospiCPI()
