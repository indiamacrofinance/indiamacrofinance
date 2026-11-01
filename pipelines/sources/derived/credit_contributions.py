"""Who is driving bank credit growth: contributions to y/y growth, in percentage points
(site calculations from RBI's sectoral deployment of bank credit, as in RBI's Monetary
Policy Report, Charts II.24-II.27).

    contribution_k(t) = 100 * (L_k(t) - L_k(t-12)) / L_parent(t-12)

so the contributions of a group's components sum to the parent's growth rate. Amounts
outstanding (L) come from pipelines/sources/rbi/sectoral_credit.py. Four panels (entity =
component; "Others" is the parent minus the components listed):

  credit_contrib_sectors   credit to the four main sectors (agriculture, industry, services,
                           personal loans); their sum, not RBI's non-food credit, which is
                           reported on a different date and includes unclassified credit
  credit_contrib_industry  industry by firm size
  credit_contrib_services  services: NBFCs, trade, commercial real estate, others
  credit_contrib_personal  personal loans: housing, vehicles, gold, cards, other personal, others
"""
from __future__ import annotations

import pandas as pd

from pipelines.core import Raw, Source
from pipelines.core.store import load_series

# panel -> (parent series or None for the sum of components, {label: series}, residual label)
GROUPS = {
    "credit_contrib_sectors": (None, {"Agriculture": "credit_level_agri", "Industry": "credit_level_industry",
                                      "Services": "credit_level_services", "Personal loans": "credit_level_personal"}, None),
    "credit_contrib_industry": ("credit_level_industry", {"Micro and small": "credit_level_mse", "Medium": "credit_level_medium",
                                                          "Large": "credit_level_large"}, None),
    "credit_contrib_services": ("credit_level_services", {"NBFCs": "credit_level_nbfc", "Trade": "credit_level_trade",
                                                          "Commercial real estate": "credit_level_cre"}, "Other services"),
    "credit_contrib_personal": ("credit_level_personal", {"Housing": "credit_level_housing", "Vehicles": "credit_level_vehicle",
                                                          "Gold loans": "credit_level_gold", "Credit cards": "credit_level_cards",
                                                          "Other personal loans": "credit_level_other_personal"}, "Others"),
}


def year_ago(period: str) -> str:
    return f"{int(period[:4]) - 1}{period[4:]}"


def contributions(levels: pd.DataFrame, parent: str | None, parts: dict[str, str], residual: str | None) -> list[dict]:
    """levels: period x series id (Rs lakh crore) -> rows (entity, period, value in pp)."""
    cols = list(parts.values())
    base = levels[cols].sum(axis=1, min_count=len(cols)) if parent is None else levels[parent]
    comps = {label: levels[sid] for label, sid in parts.items()}
    if residual:
        comps[residual] = base - levels[cols].sum(axis=1, min_count=len(cols))
    rows = []
    for period in levels.index:
        then = year_ago(period)
        if then not in levels.index or pd.isna(base.get(then)):
            continue
        for label, s in comps.items():
            if pd.notna(s.get(period)) and pd.notna(s.get(then)):
                rows.append({"entity": label, "period": period, "value": round(100 * (s[period] - s[then]) / base[then], 3)})
    return rows


class CreditContributions(Source):
    name = "derived_credit_contributions"
    derived = True
    panel = True
    series_ids = tuple(GROUPS)

    def fetch(self) -> list[Raw]:
        return []

    def parse(self, raws: list[Raw]) -> pd.DataFrame:
        sids = {sid for _, (parent, parts, _) in GROUPS.items() for sid in [parent, *parts.values()] if sid}
        levels = pd.concat({sid: load_series(sid).set_index("period")["value"].astype(float) for sid in sids}, axis=1)
        out = []
        for panel, (parent, parts, residual) in GROUPS.items():
            out += [{"series_id": panel, **r} for r in contributions(levels.sort_index(), parent, parts, residual)]
        df = pd.DataFrame(out)
        df["note"] = "site calculation: change in the component over a year / parent a year earlier"
        return df


SOURCE = CreditContributions()
