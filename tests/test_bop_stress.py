"""The BoP stress-episode analysis (pipelines/build/bop_stress.py).

The past episodes are pinned to the totals RBI's published data give (US$ bn, one decimal):
these quarters are final, so a change means the method or the stored data broke."""
import numpy as np
import pandas as pd
import pytest

from pipelines.build import bop_stress


@pytest.fixture(scope="module")
def analysis():
    return bop_stress.analyse()


def episode(analysis, eid):
    return next(e for e in analysis["episodes"] if e["id"] == eid)


@pytest.mark.parametrize("eid, ca, kfa, bank, reserves, fall", [
    ("2013", -26.9, 15.8, 11.5, 10.7, 14.9),
    ("2018", -52.6, 35.1, 15.5, 17.5, 12.0),
    ("2022", -101.2, 73.1, 27.3, 30.3, 11.0),
])
def test_past_episodes(analysis, eid, ca, kfa, bank, reserves, fall):
    v = episode(analysis, eid)["values"]
    assert round(v["current_account"], 1) == ca
    assert round(v["kfa"], 1) == kfa
    assert round(v["bank_capital"], 1) == bank
    assert round(v["reserves_drawn"], 1) == reserves
    assert v["rupee_fall"] == fall


def test_episode_identity(analysis):
    # current account + capital and financial accounts + errors + reserves drawn down = 0
    for e in analysis["episodes"]:
        v = e["values"]
        assert abs(v["current_account"] + v["kfa"] + v["errors_omissions"] + v["reserves_drawn"]) < 0.05, e["id"]


def test_components_add_up(analysis):
    for e in analysis["episodes"]:
        v = e["values"]
        assert v["goods_services"] + v["primary_income"] + v["secondary_income"] == pytest.approx(v["current_account"], abs=0.05)
        assert v["fdi_in_india"] + v["odi"] == pytest.approx(v["direct_investment"], abs=0.01)
        assert (v["capital_account"] + v["direct_investment"] + v["portfolio"] + v["derivatives"]
                + v["other_investment"]) == pytest.approx(v["kfa"], abs=0.01)


def test_regressions_cover_the_identity(analysis):
    r = analysis["regressions"]
    assert r["start"] == "2000-04-01"
    # Current and financial accounts absorb (nearly) the whole dollar; banking capital does not.
    assert -1.1 < r["slope_sum"] < -0.85
    bank = r["panels"][0]
    assert bank["key"] == "bank_capital" and abs(bank["slope"]) < 2 * bank["se"]


def test_ols_hc1():
    rng = np.random.default_rng(0)
    x = rng.normal(size=200)
    y = 1 + 2 * x + rng.normal(size=200) * (1 + abs(x))
    fit = bop_stress.ols(y, x)
    assert fit["slope"] == pytest.approx(2, abs=0.3) and fit["n"] == 200 and 0 < fit["r2"] < 1


def test_stress_rule():
    assert bop_stress.stressed(pd.Series({"rupee_change": 1.2, "fx_net_sales": 5.0})) is True
    assert bop_stress.stressed(pd.Series({"rupee_change": -0.5, "fx_net_sales": 5.0})) is False
    assert bop_stress.stressed(pd.Series({"rupee_change": 1.2, "fx_net_sales": -3.0})) is False
    assert bop_stress.stressed(pd.Series({"rupee_change": np.nan, "fx_net_sales": 1.0})) is None
