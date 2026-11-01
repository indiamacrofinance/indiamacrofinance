"""Underlying inflation rebuilt from CPI items, pinned to RBI's Monetary Policy Report,
October 2026 (Table IV.1, Table IV.2, Box IV.1). Item data: MoSPI, Jan 2025 - Aug 2026."""
from pathlib import Path

import pandas as pd
import pytest

from pipelines.sources.derived.cpi_underlying import compute, load_items

FIXTURE = Path(__file__).parents[1] / "fixtures" / "mospi" / "cpi_items_2025-01_2026-08.csv"
MONTHS = [f"2026-0{m}-01" for m in range(1, 9)]
RBI = {  # Jan-Aug 2026
    "cpi_ex_food_fuel_pm_inflation": [2.1, 2.1, 2.1, 2.2, 2.3, 2.5, 2.7, 2.9],   # Table IV.1
    "cpi_trimmed_mean_5": [2.3, 2.4, 2.7, 2.7, 3.1, 3.7, 3.8, 4.2],             # Table IV.2
    "cpi_trimmed_mean_10": [2.2, 2.5, 2.4, 2.6, 3.0, 3.6, 3.5, 4.0],
    "cpi_trimmed_mean_25": [2.0, 2.1, 2.2, 2.3, 2.6, 3.3, 3.4, 3.7],
    "cpi_weighted_median": [2.0, 2.0, 2.0, 2.0, 2.3, 2.7, 3.1, 3.5],
}


@pytest.fixture(scope="module")
def result():
    df = pd.read_csv(FIXTURE, dtype={"code": str})
    idx = df.pivot_table(index="period", columns="code", values="index")
    infl = df.pivot_table(index="period", columns="code", values="inflation")
    out = compute(idx, infl, load_items())
    return out.pivot_table(index="period", columns="series_id", values="value")


def test_items_and_baskets():
    items = load_items()
    assert len(items) == 358 and (items.kind == "good").sum() == 308   # MoSPI: 308 goods, 50 services
    assert round(items.weight.sum(), 2) == 100
    core = items[~items.index.str.startswith("01") & ~items.index.str.startswith(("04.5", "07.2.2"))]
    assert len(core) == 198                                              # RBI Box IV.1: 198 core items


@pytest.mark.parametrize("sid", list(RBI))
def test_matches_rbi_to_rounding(result, sid):
    ours = result.loc[MONTHS, sid].round(1).tolist()
    errors = [abs(a - b) for a, b in zip(ours, RBI[sid])]
    assert max(errors) <= 0.21 and sum(errors) / len(errors) <= 0.07, (sid, ours, RBI[sid])


def test_diffusion_matches_rbi_text(result):
    # "around 37 per cent of the CPI basket registered inflation above 4 per cent [in August],
    # as compared to 23 per cent in April 2026"
    above4 = result["cpi_diffusion_headline_4to6"] + result["cpi_diffusion_headline_above6"]
    assert abs(above4["2026-08-01"] - 37) < 1 and abs(above4["2026-04-01"] - 23) < 1
    shares = result[[c for c in result if c.startswith("cpi_diffusion_core_")]].sum(axis=1)
    assert (shares - 100).abs().max() < 0.01


def test_goods_services_and_precious_metals(result):
    assert {"cpi_goods_inflation", "cpi_services_inflation"} <= set(result)
    assert result.loc["2026-08-01", "cpi_precious_metals_contribution"] > 0
