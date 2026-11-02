"""Rupee drivers (pipelines/build/rupee.py) and NSDL daily FPI flows."""
import numpy as np
import pandas as pd

from pipelines.build import rupee
from pipelines.sources.nsdl import fpi_daily


def synthetic(monkeypatch, n=700, seed=0):
    """Rupee driven by oil (-0.05 per 1%) and Asian currencies (+0.3 per 1%); the dollar is noise."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2023-01-02", periods=n)
    oil = rng.normal(0, 2, n)
    asia = rng.normal(0, 0.3, n)
    noise = {k: rng.normal(0, s, n) for k, s in [("dxy", 0.4), ("nifty", 1.0), ("us10", 0.05), ("vix", 1.0)]}
    rupee_ret = -0.05 * oil + 0.3 * asia + rng.normal(0, 0.05, n)
    lvl = lambda r, start: start * np.exp(np.cumsum(r) / 100)
    data = {
        "usdinr_close": lvl(-rupee_ret, 80), "brent_usd": lvl(oil, 80), "dxy_close": lvl(noise["dxy"], 100),
        "usdcny_close": lvl(-asia, 7), "usdkrw_close": lvl(-asia, 1300), "usdidr_close": lvl(-asia, 15000),
        "nifty50_close": lvl(noise["nifty"], 20000), "us10y_yield": 4 + np.cumsum(noise["us10"]),
        "us_vix_close": 15 + np.cumsum(noise["vix"]) * 0.01,
    }
    frames = {k: pd.DataFrame({"period": days.strftime("%Y-%m-%d"), "value": v, "note": "test"}) for k, v in data.items()}
    empty = pd.DataFrame(columns=["period", "value", "note"])
    monkeypatch.setattr(rupee.store, "load_series", lambda sid: frames.get(sid, empty).copy())
    return days


def test_model_recovers_drivers_and_parts_add_up(monkeypatch):
    synthetic(monkeypatch)
    a = rupee.analyse()
    kept = a["model"]["kept"]
    assert "oil" in kept and "asia" in kept and "dollar" not in kept
    assert abs(a["model"]["effects"]["oil"] + 0.05) < 0.01 and abs(a["model"]["effects"]["asia"] - 0.3) < 0.05
    assert a["model"]["r2"]["daily"] > 0.8
    for h in a["horizons"].values():
        assert abs(sum(h["parts"].values()) - h["actual"]) < 1e-9          # parts add up exactly
    facts, _ = rupee.rupee_facts(a)
    assert facts["rupee.day.direction"] in ("strengthened", "weakened", "was unchanged")
    assert not any(ch.isdigit() for k in facts for ch in k.split(".", 1)[1].replace("rupee", ""))


def test_live_quote_is_shown_not_explained(monkeypatch):
    days = synthetic(monkeypatch)
    real = rupee.store.load_series

    def with_live(sid):
        df = real(sid)
        if sid == "usdinr_close":
            df.loc[len(df)] = [(days[-1] + pd.Timedelta(days=3)).strftime("%Y-%m-%d"), 81.0, "Yahoo Finance, live quote at 10:30 IST"]
        return df
    monkeypatch.setattr(rupee.store, "load_series", with_live)
    a = rupee.analyse()
    assert a["live"]["value"] == 81.0 and a["as_of"] == days[-1].strftime("%Y-%m-%d")


NSDL = """<html><body><table>
<tr><th colspan="9">Daily Trends in FPI Investments on 30-Oct-2026</th></tr>
<tr><th>Reporting Date</th><th>Debt/Debt-VRR/Equity/Hybrid</th><th>Investment Route</th><th>Gross Purchases(Rs. Crore)</th>
<th>Gross Sales (Rs. Crore)</th><th>Net Investment (Rs. Crore)</th><th>Net Investment US($) million</th><th>Conversion (1 USD TO INR)*</th></tr>
<tr><td>30-Oct-2026</td><td>Equity</td><td>Stock Exchange</td><td>1</td><td>2</td><td>(812.73)</td><td>(85.22)</td><td>Rs.95.3688</td></tr>
<tr><td>30-Oct-2026</td><td>Equity</td><td>Sub-total</td><td>1</td><td>2</td><td>(802.91)</td><td>(84.19)</td><td>Rs.95.3688</td></tr>
<tr><td>30-Oct-2026</td><td>Debt-General Limit</td><td>Sub-total</td><td>1</td><td>2</td><td>(24.55)</td><td>(2.58)</td><td>Rs.95.3688</td></tr>
<tr><td>30-Oct-2026</td><td>Debt-VRR</td><td>Sub-total</td><td>1</td><td>2</td><td>162.09</td><td>17.00</td><td>Rs.95.3688</td></tr>
<tr><td>30-Oct-2026</td><td>Debt-FAR</td><td>Sub-total</td><td>1</td><td>2</td><td>518.16</td><td>54.33</td><td>Rs.95.3688</td></tr>
<tr><td>30-Oct-2026</td><td>AIFs</td><td>Total</td><td>1</td><td>2</td><td>(123.33)</td><td>(12.94)</td><td>Rs.95.3688</td></tr>
</table></body></html>"""


def test_nsdl_daily_parses_subtotals_and_brackets():
    rows = {r["series_id"]: r for r in fpi_daily.parse_page(NSDL.encode())}
    assert rows["fpi_daily_equity_usd"]["value"] == -84.19
    assert rows["fpi_daily_debt_usd"]["value"] == 68.75                     # -2.58 + 17.00 + 54.33
    assert rows["fpi_daily_total_usd"]["value"] == -12.94
    assert rows["fpi_daily_total_usd"]["period"] == "2026-10-30"
