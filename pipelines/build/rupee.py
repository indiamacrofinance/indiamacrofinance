"""Why did the rupee move? A daily decomposition of the rupee's moves into its usual drivers.

Used by the rupee page (site/src/pages/rupee.astro, via site_data.py -> rupee.json) and the
morning newsletter (pipelines/newsletter/morning.py, as `rupee.*` ledger tokens).
Method (docs/guidebook/08-original-measures.md, "Rupee drivers"):

  1. The rupee is the market rate (usdinr_close, Yahoo INR=X), completed days only (today's
     live quote is shown but not explained). Its daily % change is expressed as the rupee's
     own value: positive = the rupee strengthened against the dollar.
  2. Drivers, as daily changes: the dollar index (DXY, %), Asian currencies against the dollar
     (average of the yuan, won and rupiah, %), Brent crude (%), the Nifty 50 (%), the US
     10-year yield (basis points) and the US VIX (points). Global drivers enter on the same
     day and the day before (US markets close after India's), and their effect is the sum.
  3. One regression of the rupee's daily change on all drivers, over the last WINDOW trading
     days. A driver is kept only if its total effect has the sign economics expects (PRIOR)
     and a t-statistic of at least T_MIN; the rest are dropped and the regression re-run.
  4. A move over any horizon = sum over its days of (coefficient x driver change) for each
     driver, plus the intercept (the rupee's average drift), plus what is left over: the part
     these drivers do not explain (RBI's dealing, importers' and exporters' dollar demand,
     flows not visible in the Nifty, news).
The fit is reported (share of daily, weekly and monthly moves explained) so readers can see
how much of a move the model can account for.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd

from pipelines.core import store

WINDOW, T_MIN = 500, 1.5
# name: (series ids, how the daily change is measured, same day + previous day?, label)
DRIVERS = {
    "dollar":   (["dxy_close"], "pct", True, "the US dollar (against major currencies)"),
    "asia":     (["usdcny_close", "usdkrw_close", "usdidr_close"], "asia", True, "other Asian currencies"),
    "oil":      (["brent_usd"], "pct", True, "oil prices (Brent)"),
    "equities": (["nifty50_close"], "pct", False, "Indian shares (Nifty 50)"),
    "us_yields": (["us10y_yield"], "bp", True, "US bond yields (ten-year)"),
    "risk":     (["us_vix_close"], "diff", True, "global risk aversion (US VIX)"),
}
# Expected sign of each driver's effect on the rupee's value.
PRIOR = {"dollar": -1, "asia": 1, "oil": -1, "equities": 1, "us_yields": -1, "risk": -1}
HORIZONS = {"d1": 1, "w1": 5, "m1": 21, "m3": 63}
COMPONENT_LABELS = {"drift": "Usual drift", "other": "Not explained by these factors"}


def _series(sid: str) -> pd.Series:
    df = store.load_series(sid)
    if df.empty:
        return pd.Series(dtype=float)
    s = pd.Series(df["value"].astype(float).values, index=pd.to_datetime(df["period"]))
    return s[~s.index.duplicated(keep="last")].sort_index()


def rupee_levels() -> tuple[pd.Series, dict | None]:
    """Completed daily closes of USD/INR, and today's live quote if there is one."""
    df = store.load_series("usdinr_close").sort_values("period")
    live = None
    if not df.empty and "live" in str(df["note"].iloc[-1]):
        last = df.iloc[-1]
        live = {"period": str(last["period"]), "value": float(last["value"]), "note": str(last["note"])}
        df = df.iloc[:-1]
    s = pd.Series(df["value"].astype(float).values, index=pd.to_datetime(df["period"]))
    return s, live


def driver_changes(days: pd.DatetimeIndex) -> pd.DataFrame:
    """Daily change of each driver on the rupee's trading days (missing days: no change)."""
    out = {}
    for name, (sids, how, _, _) in DRIVERS.items():
        levels = pd.concat([_series(s) for s in sids], axis=1)
        levels = levels.reindex(levels.index.union(days)).ffill().reindex(days)
        if how == "pct":
            ch = np.log(levels.iloc[:, 0]).diff() * 100
        elif how == "asia":      # Asian currencies' value against the dollar: minus USD/xxx
            ch = (-np.log(levels).diff() * 100).mean(axis=1)
        elif how == "bp":
            ch = levels.iloc[:, 0].diff() * 100
        else:
            ch = levels.iloc[:, 0].diff()
        out[name] = ch
    return pd.DataFrame(out, index=days)


def design(x: pd.DataFrame, names: list[str]) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    cols, groups = {}, {}
    for n in names:
        cols[n] = x[n]
        groups[n] = [n]
        if DRIVERS[n][2]:
            cols[n + "_lag"] = x[n].shift(1)
            groups[n].append(n + "_lag")
    return pd.DataFrame(cols), groups


def fit(y: pd.Series, x: pd.DataFrame) -> dict:
    """OLS with driver selection by sign and t-statistic (module docstring, step 3)."""
    names = list(DRIVERS)
    dropped = {}
    while True:
        X, groups = design(x, names)
        data = pd.concat([y.rename("y"), X], axis=1).dropna().tail(WINDOW)
        A = np.column_stack([np.ones(len(data)), data[X.columns].values])
        b, *_ = np.linalg.lstsq(A, data["y"].values, rcond=None)
        resid = data["y"].values - A @ b
        dof = max(len(data) - A.shape[1], 1)
        cov = np.linalg.pinv(A.T @ A) * (resid @ resid / dof)
        coef = dict(zip(["const", *X.columns], b))
        idx = {c: i for i, c in enumerate(["const", *X.columns])}
        worst = None
        for n, cs in groups.items():
            total = sum(coef[c] for c in cs)
            var = sum(cov[idx[a], idx[c]] for a in cs for c in cs)
            t = total / np.sqrt(var) if var > 0 else 0.0
            bad = np.sign(total) != PRIOR[n] or abs(t) < T_MIN
            if bad and (worst is None or abs(t) < worst[1]):
                worst = (n, abs(t), "wrong sign" if np.sign(total) != PRIOR[n] else "weak")
        if worst is None or not names:
            break
        names.remove(worst[0])
        dropped[worst[0]] = worst[2]
    sst = ((data["y"] - data["y"].mean()) ** 2).sum()
    return {"coef": coef, "groups": groups, "kept": names, "dropped": dropped, "n": len(data),
            "start": data.index[0], "end": data.index[-1],
            "r2": float(1 - (resid @ resid) / sst) if sst > 0 else 0.0}


def contributions(x: pd.DataFrame, model: dict) -> pd.DataFrame:
    """Daily contribution of each kept driver (and the drift) to the rupee's change."""
    X, _ = design(x, model["kept"])
    out = pd.DataFrame(index=x.index)
    for n, cs in model["groups"].items():
        out[n] = sum(X[c].fillna(0) * model["coef"][c] for c in cs)
    out["drift"] = model["coef"]["const"]
    return out


def horizon_r2(y: pd.Series, fitted: pd.Series, k: int) -> float:
    """Share of non-overlapping k-day moves explained, over the estimation window."""
    df = pd.concat([y, fitted], axis=1).dropna().tail(WINDOW)
    g = np.arange(len(df))[::-1] // k
    s = df.groupby(g).sum()
    s = s[df.groupby(g).size() == k]
    e = s.iloc[:, 0] - s.iloc[:, 1]
    sst = ((s.iloc[:, 0] - s.iloc[:, 0].mean()) ** 2).sum()
    return float(1 - (e ** 2).sum() / sst) if sst > 0 else 0.0


def analyse() -> dict:
    """Everything the rupee page and the newsletter need. Changes in % of the rupee's value."""
    lv, live = rupee_levels()
    days = lv.index
    y = -np.log(lv).diff() * 100                     # rupee strengthened = positive
    x = driver_changes(days)
    model = fit(y, x)
    contrib = contributions(x, model)
    fitted = contrib.sum(axis=1)
    raw_levels = {n: pd.concat([_series(s) for s in DRIVERS[n][0]], axis=1) for n in DRIVERS}

    horizons = {}
    for h, k in HORIZONS.items():
        if len(lv) <= k:
            continue
        end, start = days[-1], days[-1 - k]
        window = slice(days[-k], end)
        actual = (lv.iloc[-1 - k] / lv.iloc[-1] - 1) * 100       # % change in the rupee's value
        parts = {n: float(contrib.loc[window, n].sum()) for n in model["kept"]}
        parts["drift"] = float(contrib.loc[window, "drift"].sum())
        parts["other"] = float(actual - sum(parts.values()))
        moves = {n: float(x.loc[window, n].sum()) for n in DRIVERS}
        horizons[h] = {"days": k, "start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d"),
                       "from": float(lv.iloc[-1 - k]), "to": float(lv.iloc[-1]),
                       "actual": float(actual), "parts": parts, "driver_moves": moves}

    # Weekly decomposition for the chart: last 26 weeks, Friday-ended.
    wk = pd.concat([contrib, y.rename("actual")], axis=1).dropna(subset=["actual"])
    wk["other"] = wk["actual"] - wk[model["kept"] + ["drift"]].sum(axis=1)
    weekly = wk.resample("W-FRI").sum().tail(26)
    rows, total = [], []
    for p, r in weekly.iterrows():
        monday = (p - pd.Timedelta(days=4)).strftime("%Y-%m-%d")      # the chart's weeks: Monday to Friday
        for n in model["kept"] + ["drift", "other"]:
            rows.append({"period": monday, "component": label(n), "pp": round(float(r[n]), 3)})
        total.append([monday, round(float(r["actual"]), 3)])

    lvl_1y = lv[lv.index > days[-1] - pd.Timedelta(days=365)]
    return {
        "as_of": days[-1].strftime("%Y-%m-%d"), "latest": float(lv.iloc[-1]), "live": live,
        "weakest": {"value": float(lv.max()), "period": lv.idxmax().strftime("%Y-%m-%d"),
                    "since": days[0].strftime("%Y-%m-%d")},
        "range_1y": {"high": float(lvl_1y.max()), "high_period": lvl_1y.idxmax().strftime("%Y-%m-%d"),
                     "low": float(lvl_1y.min()), "low_period": lvl_1y.idxmin().strftime("%Y-%m-%d")},
        "horizons": horizons,
        "model": {"kept": model["kept"], "dropped": model["dropped"], "n": model["n"],
                  "start": model["start"].strftime("%Y-%m-%d"), "end": model["end"].strftime("%Y-%m-%d"),
                  "r2": {"daily": model["r2"], "weekly": horizon_r2(y, fitted, 5),
                         "monthly": horizon_r2(y, fitted, 21)},
                  "effects": {n: float(sum(model["coef"][c] for c in model["groups"][n])) for n in model["kept"]},
                  "drift_monthly": float(model["coef"]["const"] * 21)},
        "labels": {n: DRIVERS[n][3] for n in DRIVERS} | COMPONENT_LABELS,
        "units": {n: DRIVERS[n][1] for n in DRIVERS},
        "driver_latest": {n: {"value": float(raw_levels[n].dropna().iloc[-1].mean()) if n != "asia" else None,
                              "period": raw_levels[n].dropna().index[-1].strftime("%Y-%m-%d")} for n in DRIVERS},
        "weekly": {"rows": rows, "total": total},
        "context": context(days[-1]),
    }


def label(n: str) -> str:
    return COMPONENT_LABELS.get(n) or DRIVERS[n][3][0].upper() + DRIVERS[n][3][1:]


def _last(sid: str, before: pd.Timestamp | None = None) -> tuple[pd.Timestamp, float] | None:
    s = _series(sid).dropna()
    if before is not None:
        s = s[s.index <= before]
    return (s.index[-1], float(s.iloc[-1])) if len(s) else None


def context(as_of: pd.Timestamp) -> dict:
    """Slower-moving background: flows, reserves, carry, valuation, trade."""
    out = {}
    for key, sid in (("fpi_day_total", "fpi_daily_total_usd"), ("fpi_day_equity", "fpi_daily_equity_usd"),
                     ("fpi_day_debt", "fpi_daily_debt_usd"), ("fpi_month_total", "fpi_total_net"),
                     ("fbil_ref", "usdinr_ref"), ("reer", "reer_bis_broad"),
                     ("trade_balance", "merch_trade_balance")):
        got = _last(sid)
        if got:
            out[key] = {"period": got[0].strftime("%Y-%m-%d"), "value": got[1]}
    fpi = _series("fpi_daily_total_usd")
    if len(fpi):
        month = fpi[fpi.index >= fpi.index[-1].replace(day=1)]
        out["fpi_daily_mtd"] = {"period": fpi.index[-1].strftime("%Y-%m-%d"), "value": float(month.sum()),
                                "days": int(len(month)), "from": month.index[0].strftime("%Y-%m-%d")}
    res = _series("fx_reserves_total").dropna()
    if len(res) > 4:
        out["reserves"] = {"period": res.index[-1].strftime("%Y-%m-%d"), "value": float(res.iloc[-1]),
                           "week_change": float(res.iloc[-1] - res.iloc[-2]),
                           "four_week_change": float(res.iloc[-1] - res.iloc[-5])}
    ind, us = _series("gsec_10y_yield").dropna(), _series("us10y_yield").dropna()
    if len(ind) and len(us):
        spread = (ind - us.reindex(ind.index, method="ffill")).dropna()
        a_month = spread[spread.index <= spread.index[-1] - pd.Timedelta(days=28)]
        out["spread_10y"] = {"period": spread.index[-1].strftime("%Y-%m-%d"), "value": float(spread.iloc[-1]),
                             "month_change": float(spread.iloc[-1] - a_month.iloc[-1]) if len(a_month) else None}
    reer = _series("reer_bis_broad").dropna()
    if len(reer) > 12:
        out["reer"]["yoy"] = float((reer.iloc[-1] / reer.iloc[-13] - 1) * 100)
        out["reer"]["avg_5y"] = float(reer.tail(60).mean())
    return out


def today_ist() -> date:
    return (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)).date()


# --- Facts for the newsletter ledger (tokens `rupee.*`; every number the writer may use) ------

HORIZON_NAMES = {"d1": "day", "w1": "week", "m1": "month", "m3": "quarter"}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
FULL_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December"]


def _d(iso: str) -> str:
    y, m, d = (int(v) for v in iso[:10].split("-"))
    return f"{d} {MONTHS[m - 1]} {y}"


def _month(iso: str) -> str:
    y, m, _ = (int(v) for v in iso[:10].split("-"))
    return f"{FULL_MONTHS[m - 1]} {y}"


def _pct(v: float) -> str:
    return f"{abs(v):.2f}%"


def _move(v: float, unit: str) -> str:
    """A driver's own change, in words: 'up 0.45%', 'down 5 basis points', 'up 1.20 points'."""
    if unit == "bp":
        n = round(v)
        return "unchanged" if n == 0 else f"{'up' if n > 0 else 'down'} {abs(n)} basis points"
    if unit == "diff":
        return "unchanged" if round(v, 2) == 0 else f"{'up' if v > 0 else 'down'} {abs(v):.2f} points"
    return "unchanged" if round(v, 2) == 0 else f"{'up' if v > 0 else 'down'} {abs(v):.2f}%"


def _effect_word(v: float) -> str:
    if abs(v) < 0.005:
        return "made almost no difference to the rupee"
    return "supported the rupee" if v > 0 else "weighed on the rupee"


def rupee_facts(a: dict) -> tuple[dict[str, str], dict[str, dict]]:
    f: dict[str, str] = {}
    units = {"dollar": "pct", "asia": "pct", "oil": "pct", "equities": "pct", "us_yields": "bp", "risk": "diff"}
    f["rupee.latest"] = f"₹{a['latest']:.2f} per US dollar"
    f["rupee.latest_date"] = _d(a["as_of"])
    lv = a.get("live")
    f["rupee.live"] = (f"₹{lv['value']:.2f} per US dollar ({lv['note'].split('quote at ')[-1]} on {_d(lv['period'])})"
                       if lv else "no live quote yet today")
    f["rupee.weakest"] = f"₹{a['weakest']['value']:.2f} per US dollar"
    f["rupee.weakest_date"] = _d(a["weakest"]["period"])
    f["rupee.weakest_since"] = _d(a["weakest"]["since"])
    gap = (a["weakest"]["value"] / a["latest"] - 1) * 100
    f["rupee.from_weakest"] = _pct(gap)
    f["rupee.at_weakest"] = "yes" if gap < 0.005 else "no"
    r = a["range_1y"]
    f["rupee.year_weakest"] = f"₹{r['high']:.2f} on {_d(r['high_period'])}"
    f["rupee.year_strongest"] = f"₹{r['low']:.2f} on {_d(r['low_period'])}"
    for h, name in HORIZON_NAMES.items():
        v = a["horizons"].get(h)
        if not v:
            continue
        p = f"rupee.{name}"
        f[f"{p}.from"] = f"₹{v['from']:.2f}"
        f[f"{p}.to"] = f"₹{v['to']:.2f}"
        f[f"{p}.start_date"], f[f"{p}.end_date"] = _d(v["start"]), _d(v["end"])
        f[f"{p}.change"] = _pct(v["actual"])
        f[f"{p}.direction"] = ("was unchanged" if abs(v["actual"]) < 0.005
                               else "strengthened" if v["actual"] > 0 else "weakened")
        for n, c in v["parts"].items():
            f[f"{p}.{n}.effect"] = _pct(c)
            f[f"{p}.{n}.effect_word"] = _effect_word(c)
        for n, m in v["driver_moves"].items():
            f[f"{p}.{n}.move"] = _move(m, units[n])
            words = _move(m, units[n])
            f[f"{p}.{n}.move_abs"] = "nothing" if words == "unchanged" else words.split(" ", 1)[1]
            f[f"{p}.{n}.move_direction"] = ("was unchanged" if words == "unchanged"
                                            else "rose" if words.startswith("up") else "fell")
    m = a["model"]
    lab = a["labels"]
    f["rupee.model.share_daily"] = f"{max(m['r2']['daily'], 0) * 100:.0f}%"
    f["rupee.model.share_weekly"] = f"{max(m['r2']['weekly'], 0) * 100:.0f}%"
    f["rupee.model.share_monthly"] = f"{max(m['r2']['monthly'], 0) * 100:.0f}%"
    f["rupee.model.window"] = f"{_d(m['start'])} to {_d(m['end'])}"
    f["rupee.model.drivers_used"] = ", ".join(lab[n] for n in m["kept"]) or "none"
    f["rupee.model.drivers_dropped"] = ", ".join(lab[n] for n in m["dropped"]) or "none"
    f["rupee.model.drift_month"] = _pct(m["drift_monthly"])
    f["rupee.model.drift_direction"] = "weakened" if m["drift_monthly"] < 0 else "strengthened"
    for n in m["kept"]:
        f[f"rupee.model.{n}.effect_per_move"] = (f"{abs(m['effects'][n]):.2f}% per basis point" if units[n] == "bp"
                                                 else f"{abs(m['effects'][n]):.2f}% per point" if units[n] == "diff"
                                                 else f"{abs(m['effects'][n]):.2f}% for each 1% move")
    c = a["context"]
    if "fbil_ref" in c:
        f["rupee.fbil"] = f"₹{c['fbil_ref']['value']:.4f} per US dollar"
        f["rupee.fbil_date"] = _d(c["fbil_ref"]["period"])
    for key, name in (("fpi_day_total", "total"), ("fpi_day_equity", "equity"), ("fpi_day_debt", "debt")):
        if key in c:
            v = c[key]["value"]
            f[f"rupee.fpi.day_{name}"] = f"${abs(v):,.1f} million"
            f[f"rupee.fpi.day_{name}_word"] = ("net buying" if v > 0 else "net selling" if v < 0 else "no net trade")
            f["rupee.fpi.day_date"] = _d(c[key]["period"])
    if "fpi_month_total" in c:
        v = c["fpi_month_total"]["value"]
        f["rupee.fpi.month_total"] = f"₹{abs(v):,.0f} crore"
        f["rupee.fpi.month_word"] = "net buying" if v > 0 else "net selling"
        f["rupee.fpi.month"] = _month(c["fpi_month_total"]["period"])
    if "reserves" in c:
        rs = c["reserves"]
        f["rupee.reserves.level"] = f"${rs['value']:,.1f} billion"
        f["rupee.reserves.date"] = _d(rs["period"])
        f["rupee.reserves.week_change"] = f"${abs(rs['week_change']):,.1f} billion"
        f["rupee.reserves.week_direction"] = "rose" if rs["week_change"] > 0 else "fell"
        f["rupee.reserves.four_week_change"] = f"${abs(rs['four_week_change']):,.1f} billion"
        f["rupee.reserves.four_week_direction"] = "rose" if rs["four_week_change"] > 0 else "fell"
        f["rupee.reserves.reading"] = (
            "consistent with RBI selling dollars, which cushions the rupee when it is under pressure"
            if rs["four_week_change"] < 0 else
            "consistent with RBI buying dollars, which adds to reserves and keeps the rupee from rising as fast")
    if "spread_10y" in c:
        f["rupee.spread_ten_year"] = f"{c['spread_10y']['value']:.2f} percentage points"
    if "reer" in c and "yoy" in c["reer"]:
        rr = c["reer"]
        f["rupee.reer.month"] = _month(rr["period"])
        f["rupee.reer.yoy"] = _move(rr["yoy"], "pct")
        f["rupee.reer.vs_average"] = ("below" if rr["value"] < rr["avg_5y"] else "above")
    if "trade_balance" in c:
        v = c["trade_balance"]["value"]
        f["rupee.trade.balance"] = f"${abs(v):,.1f} billion"
        f["rupee.trade.word"] = "deficit" if v < 0 else "surplus"
        f["rupee.trade.month"] = _month(c["trade_balance"]["period"])
    dl = a["driver_latest"]
    f["rupee.level.dollar"] = f"{dl['dollar']['value']:.2f}"
    f["rupee.level.oil"] = f"${dl['oil']['value']:.2f} a barrel"
    f["rupee.level.us_yields"] = f"{dl['us_yields']['value']:.2f}%"
    f["rupee.level.equities"] = f"{dl['equities']['value']:,.2f}"
    f["rupee.level.risk"] = f"{dl['risk']['value']:.2f}"
    receipts = {t: {"series": "usdinr_close (rupee drivers model, pipelines/build/rupee.py)",
                    "transform": "rupee_drivers", "period": a["as_of"], "source": "https://finance.yahoo.com/",
                    "text": v} for t, v in f.items()}
    return f, receipts
