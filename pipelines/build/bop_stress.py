"""Forex intervention and the balance of payments: stress episodes compared, and where RBI's
dollar sales show up in the BoP.

Used by the Analysis pages /analysis/bop-stress/ and /analysis/fx-intervention/ (via
site_data.py -> bop_stress.json). Method: docs/guidebook/08-original-measures.md, "BoP stress
episodes and forex intervention". Every number is computed from stored series (INPUTS).

  1. Quarterly panel (calendar quarters, US$ bn, + = inflow): RBI's BPM6 presentation for the
     current account and its parts, direct investment in India and by India (ODI), portfolio,
     financial derivatives, other investment, reserve assets and errors and omissions; RBI's
     older BPM5 presentation for banking capital (the only place it is published); RBI's net
     dollar sales (monthly purchases minus sales, summed over the quarter, sign flipped so + =
     RBI sold dollars); the rupee's quarterly average rate (Handbook monthly averages, then FBIL's
     daily reference rate for months the Handbook does not reach yet).
  2. Episodes (registry/analysis/bop_stress_episodes.yaml): each component summed over the
     episode's quarters. Capital and financial accounts = capital account + financial account
     excluding reserve assets. Reserves drawn down = BPM6 reserve assets (RBI prints a fall as +).
     Rupee fall = % change in the quarterly average rate from the quarter before the episode to
     its last quarter. An `open` episode is extended while each new quarter still has a weaker
     rupee and net dollar sales.
  3. Where intervention shows up: OLS of banking capital, the current account and the financial
     account (BPM5 capital account, i.e. excluding reserves) on RBI's net dollar sales in the
     same quarter, from 2000-01:Q1; heteroskedasticity-robust (HC1) standard errors.
  4. The stress monitor: the same items quarter by quarter for recent quarters.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import yaml

from pipelines.core import store

EPISODES = store.ROOT / "registry" / "analysis" / "bop_stress_episodes.yaml"
REG_START = "2000-04-01"
MONITOR_QUARTERS = 12
# column -> series id (all US$ bn, quarterly).
BOP = {
    "goods_services": "bop_bpm6_goods_services", "primary_income": "bop_bpm6_primary_income",
    "secondary_income": "bop_bpm6_secondary_income", "current_account": "bop_bpm6_current_account",
    "capital_account": "bop_bpm6_capital_account", "fdi_in_india": "bop_bpm6_fdi_in_india", "odi": "bop_bpm6_odi",
    "portfolio": "bop_bpm6_portfolio", "derivatives": "bop_bpm6_derivatives",
    "derivatives_receipts": "bop_bpm6_derivatives_receipts", "derivatives_payments": "bop_bpm6_derivatives_payments",
    "other_investment": "bop_bpm6_other_investment", "reserve_assets": "bop_bpm6_reserve_assets",
    "errors_omissions": "bop_bpm6_errors_omissions",
    "bank_capital": "bop_bpm5_banking_capital", "bank_assets": "bop_bpm5_bank_assets", "nri_deposits": "bop_bpm5_nri_deposits",
    "ca_bpm5": "bop_bpm5_current_account", "fa_bpm5": "bop_bpm5_capital_account",
}
INPUTS = [*BOP.values(), "rbi_fx_net_purchase", "usdinr_monthly_avg", "usdinr_ref"]
# Table 3 rows: (key, label, kind). kind: item | total | sub (indented) | memo
TABLE3 = [
    ("goods_services", "Goods and services", "item"),
    ("primary_income", "Primary income", "item"),
    ("secondary_income", "Secondary income (mostly remittances)", "item"),
    ("current_account", "Current account", "total"),
    ("direct_investment", "Direct investment, net", "item"),
    ("fdi_in_india", "FDI into India (net)", "sub"),
    ("odi", "Investment abroad by Indian residents (ODI, net)", "sub"),
    ("portfolio", "Portfolio investment (FPI), net", "item"),
    ("derivatives", "Financial derivatives, net", "item"),
    ("other_investment", "Other investment (loans, deposits, trade credit)", "item"),
    ("kfa", "Capital and financial accounts", "total"),
    ("reserves_drawn", "Reserves drawn down", "memo"),
    ("rupee_fall", "Rupee fall against the US dollar, %", "memo"),
]


def _series(sid: str) -> pd.Series:
    df = store.load_series(sid)
    if df.empty:
        return pd.Series(dtype=float)
    return pd.Series(df["value"].astype(float).values, index=pd.to_datetime(df["period"]))


def rupee_monthly() -> pd.Series:
    """Monthly average rupees per dollar: the Handbook's averages, then complete months of FBIL's
    daily reference rate (at least 10 fixings) after the Handbook's last month."""
    hb = _series("usdinr_monthly_avg")
    ref = _series("usdinr_ref")
    if not ref.empty:
        this_month = pd.Timestamp.now().to_period("M")
        by_month = ref.groupby(ref.index.to_period("M")).agg(["mean", "count"])
        by_month = by_month[(by_month["count"] >= 10) & (by_month.index < this_month)]
        later = by_month.loc[by_month.index.to_timestamp() > (hb.index.max() if not hb.empty else pd.Timestamp(0)), "mean"]
        hb = pd.concat([hb, pd.Series(later.values, index=later.index.to_timestamp())])
    return hb.sort_index()


def panel() -> pd.DataFrame:
    """Calendar quarters (index = quarter start) x components; NaN where not published."""
    q = pd.DataFrame({k: _series(sid) for k, sid in BOP.items()})
    q.index = pd.to_datetime(q.index)
    q["direct_investment"] = q["fdi_in_india"] + q["odi"]
    q["kfa"] = q[["capital_account", "fdi_in_india", "odi", "portfolio", "derivatives", "other_investment"]].sum(axis=1, min_count=6)
    q["reserves_drawn"] = q["reserve_assets"]          # RBI prints a fall in reserves as +
    fx = _series("rbi_fx_net_purchase")
    by_q = fx.groupby(fx.index.to_period("Q")).agg(["sum", "count"])
    sales = (-by_q.loc[by_q["count"] == 3, "sum"]).rename("fx_net_sales")
    sales.index = sales.index.to_timestamp()
    rupee = rupee_monthly()
    rq = rupee.groupby(rupee.index.to_period("Q")).agg(["mean", "count"])
    avg = rq.loc[rq["count"] == 3, "mean"].rename("usdinr_avg")
    avg.index = avg.index.to_timestamp()
    q = q.join(sales, how="outer").join(avg, how="outer").sort_index()
    q["rupee_change"] = 100 * (q["usdinr_avg"] / q["usdinr_avg"].shift(1) - 1)
    # The shift is only valid between consecutive quarters (the index has no gaps after 2000).
    return q[q.index >= pd.Timestamp("1997-04-01")]


def stressed(row: pd.Series) -> bool | None:
    """The episode rule for one quarter: a weaker rupee and net dollar sales by RBI."""
    if pd.isna(row.get("rupee_change")) or pd.isna(row.get("fx_net_sales")):
        return None
    return bool(row["rupee_change"] > 0 and row["fx_net_sales"] > 0)


def episodes(q: pd.DataFrame) -> list[dict]:
    spec = yaml.safe_load(EPISODES.read_text())["episodes"]
    have_bop = q["current_account"].dropna().index
    out = []
    for e in spec:
        start, end = pd.Timestamp(e["start"]), pd.Timestamp(e["end"])
        extended, stopped = [], None
        if e.get("open"):
            for t in [t for t in have_bop if t > end]:
                flag = stressed(q.loc[t])
                if flag:
                    extended.append(t)
                    end = t
                else:
                    stopped = {"period": t.strftime("%Y-%m-%d"), "reason": None if flag is None else
                               ("the rupee strengthened" if q.loc[t, "rupee_change"] <= 0 else "RBI was a net buyer of dollars")}
                    break
        span = q.loc[start:end]
        before = start - pd.offsets.QuarterBegin(1, startingMonth=1)
        sums = {k: _round(span[k].sum(min_count=len(span))) for k, _, _ in TABLE3 if k != "rupee_fall"}
        for k in ("bank_capital", "bank_assets", "nri_deposits", "errors_omissions", "capital_account", "fx_net_sales"):
            sums[k] = _round(span[k].sum(min_count=len(span)))
        fall = None
        if before in q.index and not pd.isna(q.loc[before, "usdinr_avg"]) and not pd.isna(q.loc[end, "usdinr_avg"]):
            fall = round(100 * (q.loc[end, "usdinr_avg"] / q.loc[before, "usdinr_avg"] - 1), 1)
        sums["rupee_fall"] = fall
        out.append({
            "id": str(e["id"]), "label": e["label"], "short": str(e["short"]), "note": e.get("note"),
            "start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d"), "quarters": len(span),
            "open": bool(e.get("open")), "extended": [t.strftime("%Y-%m-%d") for t in extended], "stopped": stopped,
            "values": sums, "shares": shares(sums),
            "rupee": {"before": _round(q.loc[before, "usdinr_avg"], 2) if before in q.index else None,
                      "end": _round(q.loc[end, "usdinr_avg"], 2)},
        })
    return out


def shares(v: dict) -> dict:
    """Ratios used in the text, in %; None where the ratio has no meaning (wrong signs)."""
    def pct(a, b, need_pos=True):
        if a is None or b is None or b == 0 or (need_pos and (a <= 0 or b <= 0)):
            return None
        return round(100 * a / b)
    ca, kfa, bank, res = v["current_account"], v["kfa"], v["bank_capital"], v["reserves_drawn"]
    return {
        # How much of the current-account deficit net capital inflows paid for.
        "kfa_financing_ca": pct(kfa, -ca) if ca is not None else None,
        # Banking capital as a share of net capital flows (same sign: both inflows or both outflows).
        "bank_of_kfa": pct(abs(bank), abs(kfa)) if bank is not None and kfa and bank * kfa > 0 else None,
        # Share of reserve drawdown that paid for capital outflows rather than the current account.
        "reserves_for_capital": pct(res + ca, res) if (res and ca is not None and kfa is not None and kfa < 0) else None,
        # Remittances etc. as a share of the goods-and-services deficit plus primary income outflow.
        "secondary_covers": pct(v["secondary_income"], -(v["goods_services"] + v["primary_income"])),
    }


def ols(y: np.ndarray, x: np.ndarray) -> dict:
    """y = a + b x by least squares; HC1 robust standard error of b; R squared."""
    X = np.column_stack([np.ones(len(x)), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ beta
    n, k = X.shape
    xtx = np.linalg.inv(X.T @ X)
    v = xtx @ (X.T * e ** 2) @ X @ xtx * n / (n - k)
    r2 = 1 - (e @ e) / ((y - y.mean()) @ (y - y.mean()))
    return {"slope": round(float(beta[1]), 3), "intercept": round(float(beta[0]), 3),
            "se": round(float(math.sqrt(v[1, 1])), 3), "r2": round(float(r2), 3), "n": int(n)}


def regressions(q: pd.DataFrame, highlight: tuple[str, str]) -> dict:
    """Banking capital, current account and financial account on RBI's net dollar sales, same quarter."""
    cols = {"bank_capital": "Banking capital", "ca_bpm5": "Current account", "fa_bpm5": "Financial account (excluding reserves)"}
    d = q.loc[q.index >= pd.Timestamp(REG_START), ["fx_net_sales", *cols]].dropna()
    lo, hi = (pd.Timestamp(t) for t in highlight)
    panels = []
    for k, label in cols.items():
        fit = ols(d[k].values, d["fx_net_sales"].values)
        pts = [[round(float(x), 2), round(float(y), 2), bool(lo <= t <= hi), t.strftime("%Y-%m-%d")]
               for t, x, y in zip(d.index, d["fx_net_sales"], d[k])]
        panels.append({"key": k, "label": label, **fit, "points": pts})
    return {"start": d.index.min().strftime("%Y-%m-%d"), "end": d.index.max().strftime("%Y-%m-%d"),
            "highlight": [lo.strftime("%Y-%m-%d"), hi.strftime("%Y-%m-%d")], "panels": panels,
            "slope_sum": round(panels[1]["slope"] + panels[2]["slope"], 2)}


def _round(v, digits: int = 3):
    return None if v is None or pd.isna(v) else round(float(v), digits)


def quarter_rows(q: pd.DataFrame) -> list[dict]:
    """Every quarter from 2000 with the components, for the custom-episode tool and the charts."""
    keep = ["goods_services", "primary_income", "secondary_income", "current_account", "capital_account",
            "direct_investment", "fdi_in_india", "odi", "portfolio", "derivatives", "derivatives_receipts",
            "derivatives_payments", "other_investment", "kfa", "reserves_drawn", "errors_omissions",
            "bank_capital", "bank_assets", "nri_deposits", "ca_bpm5", "fa_bpm5", "fx_net_sales", "usdinr_avg", "rupee_change"]
    rows = []
    for t, r in q.loc[q.index >= pd.Timestamp(REG_START)].iterrows():
        if pd.isna(r["ca_bpm5"]) and pd.isna(r["current_account"]):
            continue
        rows.append({"period": t.strftime("%Y-%m-%d"), **{k: _round(r[k], 2 if k in ("usdinr_avg", "rupee_change") else 3) for k in keep},
                     "stressed": stressed(r)})
    return rows


def analyse() -> dict:
    q = panel()
    eps = episodes(q)
    cur = next(e for e in eps if e["id"] == "current")
    rows = quarter_rows(q)
    bop_last = q["current_account"].dropna().index.max()
    fx = _series("rbi_fx_net_purchase")
    return {
        "as_of": {"bop": bop_last.strftime("%Y-%m-%d"), "fx": fx.index.max().strftime("%Y-%m-%d"),
                  "rupee": rupee_monthly().index.max().strftime("%Y-%m-%d"),
                  "bpm6_from": q["current_account"].dropna().index.min().strftime("%Y-%m-%d")},
        "table3": [{"key": k, "label": label, "kind": kind} for k, label, kind in TABLE3],
        "episodes": eps,
        "regressions": regressions(q, (cur["start"], cur["end"])),
        "quarters": rows,
        "monitor": rows[-MONITOR_QUARTERS:],
        "inputs": INPUTS,
    }


if __name__ == "__main__":
    import json
    print(json.dumps({k: v for k, v in analyse().items() if k not in ("quarters", "regressions")}, indent=1)[:6000])
