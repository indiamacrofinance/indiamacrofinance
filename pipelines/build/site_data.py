"""Turn registry + data/ into the JSON the Astro site reads (site/src/data/generated/).

    python -m pipelines.build.site_data

Everything numeric on the site comes from here (AGENTS.md hard rule 2). Pages
never compute values themselves; they read these files. Files are only ever
overwritten, never deleted (project rule); the site reads series listed in
catalogue.json, so a leftover file for a removed series is simply ignored.
"""
from __future__ import annotations

import json
import sys
from datetime import date

import pandas as pd
import yaml

from pipelines.build import bop_stress, calendar, rupee, status_map
from pipelines.core import registry, store

OUT = store.ROOT / "site" / "src" / "data" / "generated"
PUBLIC = store.ROOT / "site" / "public" / "data"
PAGES = store.ROOT / "registry" / "pages"


def load(series_id: str) -> pd.DataFrame:
    """Stored series with period as Timestamp, sorted."""
    df = store.load_series(series_id)
    df["period"] = pd.to_datetime(df["period"])
    df["value"] = df["value"].astype(float)
    return df.sort_values("period").reset_index(drop=True)


def transform(df: pd.DataFrame, how: str) -> pd.DataFrame:
    """Apply a transform from 02-conventions.md. Changes match calendar periods, not row offsets."""
    s = df.set_index("period")["value"]
    if how == "level":
        out = s
    elif how in ("yoy", "mom"):
        offset = pd.DateOffset(years=1) if how == "yoy" else pd.DateOffset(months=1)
        prior = s.reindex(s.index - offset)
        out = pd.Series((s.values / prior.values - 1) * 100, index=s.index).dropna()
    elif how == "diff":
        out = s.diff().dropna() * 100  # percentage points -> basis points
    elif how in ("7dma", "7dma_yoy"):
        # 7-day calendar-window average (needs at least 5 observations in the window).
        ma = s.rolling("7D", min_periods=5).mean().dropna()
        if how == "7dma":
            out = ma
        else:
            prior = ma.reindex(ma.index - pd.DateOffset(years=1))
            out = pd.Series((ma.values / prior.values - 1) * 100, index=ma.index).dropna()
    else:
        raise ValueError(f"transform {how!r} not implemented in site build")
    return out.rename("value").reset_index()


def value_on_or_before(df: pd.DataFrame, when: pd.Timestamp, max_gap_days: int) -> float | None:
    """Last value on or before `when`, if it is no more than max_gap_days older than `when`.

    The gap limit stops a "1-day change" being computed against a week-old value
    when the series has holes (e.g. FBIL's delayed public feed).
    """
    prior = df[(df["period"] <= when) & (df["period"] >= when - pd.Timedelta(days=max_gap_days))]
    return None if prior.empty else float(prior["value"].iloc[-1])


# Largest gap (days) between a reference date and the observation used for it, by
# frequency: (1-day, 1-week, year-start). None = change not shown for that frequency.
GAP_LIMITS = {"D": (4, 3, 7), "W": (None, 9, 21), "F": (None, None, 30)}
STEP_GAP = 60  # step series (policy rates) hold their value until changed


def changes(df: pd.DataFrame, unit: str, freq: str, step: bool) -> dict | None:
    """1-day, 1-week and calendar-YTD changes (bp for rates, % otherwise).

    Step series (registry `step: true`, e.g. the repo rate) carry their last value
    forward, so any observation within STEP_GAP days is a valid reference.
    """
    limits = (STEP_GAP,) * 3 if step else GAP_LIMITS.get(freq)
    if limits is None:
        return None
    last_p, last_v = df["period"].iloc[-1], float(df["value"].iloc[-1])
    targets = (last_p - pd.Timedelta(days=1), last_p - pd.Timedelta(days=7),
               pd.Timestamp(year=last_p.year - 1, month=12, day=31))
    out = {}
    for key, target, gap in zip(("d1", "w1", "ytd"), targets, limits):
        ref = None if gap is None else value_on_or_before(df, target, max_gap_days=gap)
        if ref is None:
            out[key] = None
        elif unit == "percent":
            out[key] = round((last_v - ref) * 100, 1)       # basis points
        else:
            out[key] = round((last_v / ref - 1) * 100, 2)   # percent change
    out["kind"] = "bp" if unit == "percent" else "pct"
    return out


def revisions_of(series_id: str, limit: int = 50) -> list[dict]:
    """Most recent logged revisions for a series (data/revisions/<id>.csv), newest first."""
    path = store.REVISIONS / f"{series_id}.csv"
    if not path.exists():
        return []
    rv = pd.read_csv(path, dtype=str).fillna("")
    return rv.iloc[::-1].head(limit).to_dict("records")


def series_payload(series_id: str, spec: dict, df: pd.DataFrame) -> dict:
    transforms = {t: [[p.strftime("%Y-%m-%d"), round(v, 4)]
                      for p, v in transform(df, t).itertuples(index=False)]
                  for t in spec["transforms"] if t != "level"}
    return {
        "id": series_id,
        "title": spec["title"],
        "short_title": spec["short_title"],
        "area": spec["area"],
        "unit": spec["unit"],
        "frequency": spec["frequency"],
        "base_year": spec.get("base_year"),
        "source": spec["source"],
        "licence": spec["licence"],
        "downloadable": spec["downloadable"],
        "notes": spec.get("notes", ""),
        "original": bool(spec.get("original")),
        "fetch": spec["fetch"],
        "release_rule": spec.get("release", {}).get("rule", ""),
        "verified_against": spec.get("verified_against") or [],
        "exclude": spec.get("exclude") or [],
        "revisions": revisions_of(series_id),
        "data": [[p.strftime("%Y-%m-%d"), v, n] for p, v, n in
                 zip(df["period"], df["value"], df["note"].fillna(""))],
        "transforms": transforms,
        # `changes: none` for balances that cross zero (a % change would mean nothing).
        "changes": None if spec.get("changes") == "none" else changes(df, spec["unit"], spec["frequency"], bool(spec.get("step"))),
    }


def tile(spec: dict, payload: dict) -> dict:
    """One home-page tile: latest value of the requested transform plus its period."""
    how = spec.get("transform", "level")
    points = payload["data"] if how == "level" else payload["transforms"][how]
    period, value = points[-1][0], points[-1][1]
    # Same period a year earlier, matched on the date (not on row position).
    lag = {"M": pd.DateOffset(years=1), "Q": pd.DateOffset(years=1)}.get(payload["frequency"])
    year_ago = None
    if lag is not None:
        target = (pd.Timestamp(period) - lag).strftime("%Y-%m-%d")
        year_ago = next((v for p, v, *_ in points if p == target), None)
    return {**spec, "period": period, "value": value, "year_ago": year_ago,
            "unit": "percent" if how in ("yoy", "mom") else payload["unit"],
            "frequency": payload["frequency"], "changes": payload["changes"],
            "title": spec.get("label") or payload["short_title"],
            "note": payload["data"][-1][2] if how == "level" else ""}


def contributions(parts: dict[str, tuple[str, float]]) -> list[dict]:
    """Percentage-point contributions to headline CPI inflation.

    parts: label -> (series id, weight). contribution_k(t) = w_k * (I_k(t) - I_k(t-12)) /
    I_general(t-12); these sum to the headline y/y rate because CPI 2024 is fixed-weight.
    """
    general = load("cpi_headline_index").set_index("period")["value"]
    rows = []
    for label, (sid, weight) in parts.items():
        s = load(sid).set_index("period")["value"]
        prior = s.reindex(s.index - pd.DateOffset(years=1)).values
        base = general.reindex(s.index - pd.DateOffset(years=1)).values
        contrib = pd.Series(weight * (s.values - prior) / base, index=s.index).dropna()
        rows += [{"period": p.strftime("%Y-%m-%d"), "component": label, "series": sid, "pp": round(v, 3)}
                 for p, v in contrib.items()]
    return rows


def cpi_contributions() -> list[dict]:
    """Food, fuel and core (weights: registry/weights/cpi2024_core.yaml)."""
    w = yaml.safe_load((store.ROOT / "registry" / "weights" / "cpi2024_core.yaml").read_text())
    return contributions({"Food and beverages": ("cpi_food_bev_index", w["food_and_beverages"]),
                          "Fuel": ("cpi_fuel_index", w["electricity_gas_fuels"] + w["vehicle_fuels"]),
                          "Core": ("cpi_core_index", w["core"])})


def credit_contribution_charts() -> dict[str, dict]:
    """Stacked contributions to credit growth by panel: {panel: {"rows": [...], "total": [[period, %]]}}."""
    out = {}
    for panel in ("credit_contrib_sectors", "credit_contrib_industry", "credit_contrib_services", "credit_contrib_personal"):
        df = store.load_panel(panel)
        if df.empty:
            continue
        df["value"] = df["value"].astype(float)
        rows = [{"period": r.period, "component": r.entity, "series": panel, "pp": round(r.value, 3)}
                for r in df.sort_values(["period", "entity"]).itertuples()]
        total = df.groupby("period")["value"].sum().round(2)
        out[panel] = {"rows": rows, "total": [[p, v] for p, v in total.items()]}
    return out


def policy_cycles(decisions: pd.Series) -> list[dict]:
    """Easing/tightening cycles from MPC decisions (period -> repo after the meeting): maximal
    runs of rate moves of the same sign, with holds in between allowed. Each cycle runs from its
    first move to the month before the first opposite move (or open, if none yet)."""
    moves = decisions.diff().dropna()
    moves = moves[moves != 0]
    cycles = []
    for period, change in moves.items():
        sign = 1 if change > 0 else -1
        if cycles and cycles[-1]["sign"] == sign:
            cycles[-1]["last_move"] = period
        else:
            cycles.append({"sign": sign, "start": period, "last_move": period})
    for k, c in enumerate(cycles):
        nxt = cycles[k + 1]["start"] if k + 1 < len(cycles) else None
        c["end"] = (nxt - pd.DateOffset(months=1)) if nxt is not None else None
        before = decisions[decisions.index < c["start"]]
        c["repo_before"] = float(before.iloc[-1]) if len(before) else None
        c["repo_after"] = float(decisions[decisions.index <= c["last_move"]].iloc[-1])
    return cycles


def transmission() -> dict:
    """Table II.7-style transmission: for each policy cycle, the change (basis points) in the
    repo rate and in banks' lending and deposit rates (all SCBs), from the month before the
    first move to the cycle's end or the latest month with data."""
    decisions = load("mpc_repo_decision").set_index("period")["value"]
    scb = "All scheduled commercial banks"
    rates = {}
    for sid in ("walr_fresh", "walr_outstanding", "wadtdr_fresh", "wadtdr_outstanding", "mclr_1y_median"):
        df = store.load_panel(sid)
        df = df[df["entity"] == scb]
        rates[sid] = pd.Series(df["value"].astype(float).values, index=pd.to_datetime(df["period"])).sort_index()
    rows = []
    for c in policy_cycles(decisions):
        base = c["start"] - pd.DateOffset(months=1)
        row = {"kind": "Tightening" if c["sign"] > 0 else "Easing", "start": c["start"].strftime("%Y-%m-%d"),
               "end": c["end"].strftime("%Y-%m-%d") if c["end"] is not None else None,
               "repo_bp": None if c["repo_before"] is None else round(100 * (c["repo_after"] - c["repo_before"]))}
        last = None
        for sid, s in rates.items():
            at_base = s[s.index <= base]
            upto = s[s.index <= c["end"]] if c["end"] is not None else s
            if at_base.empty or upto.empty or at_base.index[-1] < base - pd.DateOffset(months=2) or upto.index[-1] <= base:
                row[sid] = None
                continue
            row[sid] = round(100 * (upto.iloc[-1] - at_base.iloc[-1]))
            last = max(last, upto.index[-1]) if last is not None else upto.index[-1]
        row["data_to"] = last.strftime("%Y-%m-%d") if last is not None else None
        if row["repo_bp"] is not None:
            rows.append(row)
    return {"cycles": rows[::-1]}


def quarter_start(label: str) -> pd.Timestamp:
    """"2026-27 Q3" -> 2026-10-01 (financial year April-March)."""
    fy, q = label.split(" Q")
    return pd.Timestamp(int(fy[:4]), 4, 1) + pd.DateOffset(months=3 * (int(q) - 1))


def quarterly_projections(n: int = 10) -> dict[str, list[dict]]:
    """RBI's quarter projections against outturns (MPR Charts III.2, IV.3): for the latest n
    target quarters, the first and latest projection, and the outturn once published (CPI:
    average of the three monthly y/y rates as published; GDP: y/y growth as published)."""
    cpi = load("cpi_headline_inflation").set_index("period")["value"]
    gdp = load("gdp_real_growth").set_index("period")["value"]
    out = {}
    for key, sid in (("cpi", "mpc_cpi_projection_q"), ("gdp", "mpc_gdp_projection_q")):
        df = store.load_panel(sid)
        rows = []
        for q, g in df.groupby("entity"):
            g = g.sort_values("period")
            start = quarter_start(q)
            if key == "cpi":
                months = [start + pd.DateOffset(months=k) for k in range(3)]
                actual = round(float(cpi.reindex(months).mean()), 1) if cpi.reindex(months).notna().all() else None
            else:
                actual = float(gdp[start]) if start in gdp.index else None
            first, last = g.iloc[0], g.iloc[-1]
            rows.append({"quarter": q, "start": start.strftime("%Y-%m-%d"), "projections": len(g),
                         "first": float(first["value"]), "first_meeting": first["period"],
                         "latest": float(last["value"]), "latest_meeting": last["period"], "actual": actual,
                         "error": None if actual is None else round(float(last["value"]) - actual, 1)})
        out[key] = sorted(rows, key=lambda r: r["start"])[-n:][::-1]
    return out


def fiscal_quarter_start(month: pd.Timestamp) -> pd.Timestamp:
    """First month of the financial-year quarter containing `month` (Apr-Jun, Jul-Sep, ...)."""
    return pd.Timestamp(month.year, month.month - (month.month - 1) % 3, 1)


def cpi_fan(min_errors: int = 12) -> dict | None:
    """Uncertainty bands around RBI's latest CPI projection path, from RBI's own past errors.

    Every past quarterly projection with an outturn gives an error (outturn - projection) at a
    horizon h = quarters from the meeting's quarter to the target quarter (h <= 0: the quarter
    under way, -1: the quarter just ended). For each horizon, the root-mean-square error (RMSE, which includes
    any bias) sets bands of +/- z x RMSE, z = 0.674, 1.036 and 1.645 for 50%, 70% and 90%,
    assuming errors are roughly normal. Horizons with fewer than min_errors errors are pooled
    with the nearest shorter horizon."""
    cpi = load("cpi_headline_inflation").set_index("period")["value"]
    d = store.load_panel("mpc_cpi_projection_q")
    if d.empty:
        return None
    d["value"] = d["value"].astype(float)

    def horizon(q, meeting):
        qs, mq = quarter_start(q), fiscal_quarter_start(pd.Timestamp(meeting))
        return (qs.year - mq.year) * 4 + (qs.month - mq.month) // 3

    def outturn(q):
        months = [quarter_start(q) + pd.DateOffset(months=k) for k in range(3)]
        a = cpi.reindex(months)
        return float(a.mean()) if a.notna().all() else None

    errs = []
    for r in d.itertuples():
        a = outturn(r.entity)
        if a is not None:
            errs.append({"h": horizon(r.entity, r.period), "err": a - r.value})
    e = pd.DataFrame(errs)
    stats = {int(h): {"n": len(g), "rmse": float((g.err ** 2).mean() ** 0.5), "bias": float(g.err.mean())}
             for h, g in e.groupby("h")}
    usable = sorted(h for h, st in stats.items() if st["n"] >= min_errors)
    latest = d[d["period"] == d["period"].max()]
    path = []
    for r in latest.sort_values("entity").itertuples():
        if outturn(r.entity) is not None:                  # quarter over: no band needed
            continue
        h = max(horizon(r.entity, r.period), 0)
        hh = max([u for u in usable if 0 <= u <= h], default=None)
        if hh is None:
            continue
        rmse = stats[hh]["rmse"]
        point = {"label": r.entity.replace(" Q", ", Q"), "date": (quarter_start(r.entity) + pd.DateOffset(months=1)).strftime("%Y-%m-%d"),
                 "mid": r.value, "h": h, "rmse": round(rmse, 2), "n": stats[hh]["n"]}
        for k, z in (("50", 0.674), ("70", 1.036), ("90", 1.645)):
            point[f"lo{k}"], point[f"hi{k}"] = round(r.value - z * rmse, 2), round(r.value + z * rmse, 2)
        path.append(point)
    hist = []
    # Quarterly outturns for the last three years, dated mid-quarter.
    qcpi = cpi[cpi.index >= cpi.index.max() - pd.DateOffset(years=3)]
    for qs, g in qcpi.groupby(qcpi.index.map(fiscal_quarter_start)):
        if len(g) == 3:
            hist.append([(qs + pd.DateOffset(months=1)).strftime("%Y-%m-%d"), round(float(g.mean()), 2)])
    if path and hist:                                     # start the fan at the last outturn
        d0, v0 = hist[-1]
        path.insert(0, {"label": "Latest outturn", "date": d0, "mid": v0, "anchor": True,
                        **{f"{b}{k}": v0 for k in ("50", "70", "90") for b in ("lo", "hi")}})
    return {"meeting": latest["period"].iloc[0], "path": path, "history": hist,
            "errors": [{"h": h, **{k: round(v, 2) if isinstance(v, float) else v for k, v in st.items()}} for h, st in sorted(stats.items())]}


def cpi_diffusion() -> dict[str, list[dict]]:
    """Diffusion indices as stacked shares: {"headline": rows, "core": rows}, rows like the
    contribution charts (component = inflation bucket, pp = % of the basket)."""
    labels = {"below2": "Below 2%", "2to4": "2-4%", "4to6": "4-6%", "above6": "6% and above"}
    out = {}
    for basket in ("headline", "core"):
        rows = []
        for key, label in labels.items():
            sid = f"cpi_diffusion_{basket}_{key}"
            for _, r in load(sid).iterrows():
                rows.append({"period": pd.Timestamp(r["period"]).strftime("%Y-%m-%d"), "component": label,
                             "series": sid, "pp": round(float(r["value"]), 2)})
        out[basket] = rows
    return out


def cpi_division_contributions(specs: dict) -> list[dict]:
    """All 12 COICOP divisions (weights: registry/weights/cpi2024_divisions.yaml)."""
    w = yaml.safe_load((store.ROOT / "registry" / "weights" / "cpi2024_divisions.yaml").read_text())["weights"]
    return contributions({division_label(specs[sid]): (sid, wt) for sid, wt in w.items()})


def gdp_contributions() -> list[dict]:
    """Percentage-point contributions to real GDP growth (y/y) by spending component.

    contribution_k = 100 * (X_k(t) - X_k(t-4q)) / GDP(t-4q), with imports entering
    negatively. "Other" is the residual (change in stocks, valuables, discrepancies),
    so the bars add up to GDP growth computed from the same levels.
    """
    parts = {"Private consumption": "pfce_real_level", "Government consumption": "gfce_real_level",
             "Fixed investment": "gfcf_real_level", "Exports": "exports_real_level",
             "Imports (negative)": "imports_real_level"}
    gdp = load("gdp_real_level").set_index("period")["value"]
    gdp_prior = gdp.reindex(gdp.index - pd.DateOffset(years=1)).values
    total = pd.Series(100 * (gdp.values - gdp_prior) / gdp_prior, index=gdp.index).dropna()
    rows, explained = [], pd.Series(0.0, index=total.index)
    for label, sid in parts.items():
        s = load(sid).set_index("period")["value"].reindex(gdp.index)
        sign = -1 if sid.startswith("imports") else 1
        c = (sign * 100 * (s.values - s.reindex(gdp.index - pd.DateOffset(years=1)).values) / gdp_prior)
        c = pd.Series(c, index=gdp.index).reindex(total.index)
        explained = explained + c.fillna(0)
        rows += [{"period": p.strftime("%Y-%m-%d"), "component": label, "pp": round(v, 3)}
                 for p, v in c.dropna().items()]
    rows += [{"period": p.strftime("%Y-%m-%d"), "component": "Other (stocks, valuables, discrepancies)",
              "pp": round(v, 3)} for p, v in (total - explained).items()]
    totals = [[p.strftime("%Y-%m-%d"), round(v, 2)] for p, v in total.items()]
    return {"rows": rows, "total": totals}


def mpc_decisions(cal: list[dict]) -> dict:
    """One row per MPC meeting, newest first: rate set, change in basis points, stance and
    vote split on the rate resolution; plus the next scheduled decision from the calendar."""
    df = store.load_series("mpc_repo_decision")
    if df.empty:
        return {"rows": [], "next": None}
    df["value"] = df["value"].astype(float)
    df["change_bp"] = (df["value"].diff() * 100).round()
    rows = []
    for _, r in df.iterrows():
        rest, _, votes = r["note"].partition("; votes: ")
        dates, _, rest = rest.partition("; stance: ")
        stance, _, size = rest.partition("; size: ")
        yes, _, no = votes.partition("-")
        rows.append({"period": r["period"], "dates": dates, "rate": r["value"],
                     "change_bp": None if pd.isna(r["change_bp"]) else int(r["change_bp"]),
                     "stance": stance, "size_split": size, "votes_for": int(yes) if votes else None,
                     "votes_against": int(no) if votes else None})
    today = date.today().isoformat()
    upcoming = [c for c in cal if c["date"] > today and "repo_rate" in c["series"]
                and "MPC" in c["title"]]
    nxt = min(upcoming, key=lambda c: c["date"]) if upcoming else None
    return {"rows": rows[::-1], "next": nxt and {"date": nxt["date"], "title": nxt["title"],
                                                  "days": (date.fromisoformat(nxt["date"]) - date.today()).days}}


def budget_table() -> dict:
    """Union Budget at a glance, as the Budget prints it: for the latest Budget year Y,
    Actuals Y-2, Budget and Revised Estimates Y-1, Budget Estimates Y, plus the change
    from Y-1 RE to Y BE. Rows in the order of pipelines/sources/budget/glance.py."""
    from pipelines.sources.budget.glance import ORDER
    stages = {sid: store.load_panel(sid) for sid in ("budget_actuals", "budget_be", "budget_re")}
    if stages["budget_be"].empty:
        return {"columns": [], "rows": []}
    year = int(stages["budget_be"]["period"].max()[:4])
    fy = lambda y: f"{y}-{str(y + 1)[2:]}"
    cols = [("budget_actuals", year - 2, f"{fy(year - 2)} Actuals"), ("budget_be", year - 1, f"{fy(year - 1)} BE"),
            ("budget_re", year - 1, f"{fy(year - 1)} RE"), ("budget_be", year, f"{fy(year)} BE")]
    look = {sid: {(r.entity, r.period): float(r.value) for r in df.itertuples()} for sid, df in stages.items()}
    rows = []
    for item in ORDER:
        vals = [look[sid].get((item, f"{y}-04-01")) for sid, y, _ in cols]
        re_, be = vals[2], vals[3]
        change = None if "% of GDP" in item or not re_ or be is None else round(100 * (be / re_ - 1), 1)
        rows.append({"item": item, "ratio": "% of GDP" in item, "values": vals, "change_pct": change})
    # The record: each year's Budget Estimate, Revised Estimate and Actual, from every Budget we
    # hold (archived editions from 2019-20 give Actuals from 2017-18).
    record = {}
    for item in ("Fiscal deficit, % of GDP", "Capital expenditure", "Tax revenue (net to Centre)", "Total expenditure"):
        years = sorted({p for sid in look for (e, p) in look[sid] if e == item})
        record[item] = [{"fy": fy(int(p[:4])), "period": p, "be": look["budget_be"].get((item, p)),
                         "re": look["budget_re"].get((item, p)), "actual": look["budget_actuals"].get((item, p))}
                        for p in years]
    return {"year": fy(year), "columns": [c[2] for c in cols], "rows": rows, "record": record}


def what_changed(specs: dict, days: int = 30) -> dict:
    """What changed, day by day: for each of the last `days` days on which data were stored,
    every series and panel with values that first appeared that day (new periods, or a whole
    history when the series was added) or were revised that day. Read from the `vintage` each
    stored value carries (the date it first appeared or last changed) and data/revisions."""
    by_day: dict[str, list[dict]] = {}
    for sid, spec in specs.items():
        panel = spec.get("panel")
        df = store.load_panel(sid) if panel else store.load_series(sid)
        if df.empty:
            continue
        rev_path = store.REVISIONS / f"{sid}.csv"
        revised = pd.read_csv(rev_path, dtype=str)["new_vintage"].value_counts().to_dict() if rev_path.exists() else {}
        first_day = df["vintage"].min()
        last = df.sort_values("period").iloc[-1]
        for day, rows in df.groupby("vintage"):
            n_rev = min(int(revised.get(day, 0)), len(rows))
            by_day.setdefault(day, []).append({
                "id": sid, "title": spec["short_title"], "area": spec["area"], "frequency": spec["frequency"],
                "panel": bool(panel), "added": day == first_day, "new": len(rows) - n_rev, "revised": n_rev,
                "to": rows["period"].max(), "latest_period": last["period"],
                "latest_value": None if panel else float(last["value"]), "unit": spec["unit"],
            })
    recent = sorted(by_day, reverse=True)[:days]
    return {"days": [{"date": d, "series": sorted(by_day[d], key=lambda r: (r["area"], r["title"]))} for d in recent]}


def yield_curve() -> dict:
    """FBIL par yield curve on the latest date, about a month earlier, and the last date of
    the previous financial year (31 March or the last business day before it)."""
    from pipelines.sources.fbil.gsec_curve import TENORS
    df = store.load_panel("gsec_par_yield")
    if df.empty:
        return {"curves": []}
    df["value"] = df["value"].astype(float)
    days = sorted(df["period"].unique())
    last = days[-1]
    month_ago = max(d for d in days if d <= (pd.Timestamp(last) - pd.DateOffset(months=1)).date().isoformat())
    fy_end = f"{int(last[:4]) - (1 if last[5:7] <= '03' else 0)}-03-31"
    year_end = max((d for d in days if d <= fy_end), default=None)
    years = {label: t for t, label in TENORS.items()}
    curves = []
    for day, name, main in [(last, "Latest", True), (month_ago, "A month earlier", False), (year_end, "End of last FY", False)]:
        if day is None:
            continue
        sub = df[df["period"] == day]
        pts = sorted([[years[e], v] for e, v in zip(sub["entity"], sub["value"]) if e in years])
        curves.append({"label": f"{name} ({pd.Timestamp(day):%d %b %Y})", "date": day, "main": main, "points": pts})
    return {"curves": curves}


def cpi_momentum_base(months: int = 24) -> dict:
    """Change in headline CPI inflation split into momentum and base effect (Original).

    In log points, ln(I_t/I_t-12) - ln(I_t-1/I_t-13) = ln(I_t/I_t-1) - ln(I_t-12/I_t-13):
    this month's price change (momentum) minus the price change in the same month a year
    earlier (base effect, entered with a minus sign). The two bars add up exactly to the
    dot, the change in the 12-month rate (log points, close to percentage points)."""
    import numpy as np
    s = load("cpi_headline_index").set_index("period")["value"]
    s = s.asfreq("MS")
    lg = 100 * np.log(s)
    momentum = lg.diff()
    base = -momentum.shift(12)
    total = (lg - lg.shift(12)).diff()
    frame = pd.DataFrame({"m": momentum, "b": base, "t": total}).dropna().tail(months)
    rows = []
    for p, r in frame.iterrows():
        d = p.strftime("%Y-%m-%d")
        rows += [{"period": d, "component": "Momentum (this month's price change)", "pp": round(r["m"], 3) + 0.0},
                 {"period": d, "component": "Base effect (minus last year's change)", "pp": round(r["b"], 3) + 0.0}]
    return {"rows": rows, "total": [[p.strftime("%Y-%m-%d"), round(v, 2)] for p, v in frame["t"].items()]}


def write_bulk_zip(specs: dict) -> None:
    """site/public/downloads/all-data.zip: every downloadable CSV (as in site/public/data)
    plus catalogue.csv describing them. Overwritten on every build."""
    import io
    import zipfile
    files = sorted(f for f in PUBLIC.glob("*.csv") if f.stem in specs and specs[f.stem]["downloadable"])
    cat = pd.DataFrame([{"id": f.stem, "title": specs[f.stem]["title"], "unit": specs[f.stem]["unit"],
                         "frequency": specs[f.stem]["frequency"], "source": specs[f.stem]["source"]["agency"],
                         "licence": specs[f.stem]["licence"], "panel": bool(specs[f.stem].get("panel"))}
                        for f in files])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("catalogue.csv", cat.to_csv(index=False))
        for f in files:
            z.write(f, f"series/{f.name}")
    out = PUBLIC.parent / "downloads"
    out.mkdir(parents=True, exist_ok=True)
    (out / "all-data.zip").write_bytes(buf.getvalue())


def policy_rule_inputs() -> dict:
    """Monthly inputs for the policy-rule tool (the rule itself is computed in the reader's
    browser from parameters they choose): headline CPI inflation as published, real GDP
    growth of the quarter the month falls in (as published), and the repo rate set at the
    latest MPC meeting (mpc_repo_decision, in force from the month of the meeting)."""
    cpi = load("cpi_headline_inflation").set_index("period")["value"]
    gdp = load("gdp_real_growth").set_index("period")["value"]
    repo = load("mpc_repo_decision").set_index("period")["value"]
    if cpi.empty or gdp.empty or repo.empty:
        return {"rows": []}
    months = pd.date_range(max(repo.index.min(), cpi.index.min()), cpi.index.max(), freq="MS")
    # Financial-year quarters start in Jan/Apr/Jul/Oct, as do calendar quarters.
    quarter = months.to_period("Q").start_time
    rows = []
    for m, q in zip(months, quarter):
        g = gdp.get(q)
        r = repo[repo.index <= m]
        if m not in cpi.index or r.empty:
            continue
        rows.append({"month": m.strftime("%Y-%m-%d"), "cpi": round(float(cpi[m]), 2),
                     "growth": None if g is None or pd.isna(g) else round(float(g), 2), "repo": float(r.iloc[-1])})
    # Months whose quarter has no GDP yet use the latest published quarter (flagged).
    last = None
    for row in rows:
        if row["growth"] is None and last is not None:
            row["growth"], row["growth_carried"] = last, True
        last = row["growth"]
    return {"rows": rows}


def budget_demands() -> dict:
    """Budget explorer: every demand for grants with Actuals Y-2, BE and RE Y-1, BE Y, the
    planned change on last year's RE and the share of total spending (site calculations)."""
    stages = {sid: store.load_panel(sid) for sid in ("budget_demand_actuals", "budget_demand_be", "budget_demand_re")}
    be = stages["budget_demand_be"]
    if be.empty:
        return {"rows": []}
    year = int(be["period"].max()[:4])
    fy = lambda y: f"{y}-{str(y + 1)[2:]}"
    cols = [("budget_demand_actuals", year - 2, f"{fy(year - 2)} Actuals"), ("budget_demand_be", year - 1, f"{fy(year - 1)} BE"),
            ("budget_demand_re", year - 1, f"{fy(year - 1)} RE"), ("budget_demand_be", year, f"{fy(year)} BE")]
    look = {sid: {(r.entity, r.period): float(r.value) for r in df.itertuples()} for sid, df in stages.items()}
    notes = {r.entity: r.note for r in be.itertuples()}
    total = sum(v for (e, p), v in look["budget_demand_be"].items() if p == f"{year}-04-01")
    rows = []
    for e in sorted({e for e, p in look["budget_demand_be"] if p == f"{year}-04-01"}):
        vals = [look[sid].get((e, f"{y}-04-01")) for sid, y, _ in cols]
        re_, now = vals[2], vals[3]
        rows.append({"name": e, "demand": notes.get(e, ""), "values": vals,
                     "change_pct": None if not re_ or now is None else round(100 * (now / re_ - 1), 1),
                     "share": round(100 * now / total, 2)})
    rows.sort(key=lambda r: -r["values"][3])
    return {"year": fy(year), "columns": [c[2] for c in cols], "total": round(total, 3), "rows": rows}


def reserves_change(weeks: int = 60) -> dict:
    """Week-on-week change in total FX reserves (US$ bn), for bars beside USD/INR. Site
    calculation from the weekly WSS series; includes valuation changes, as RBI's data do."""
    s = load("fx_reserves_total").set_index("period")["value"]
    d = s.diff().dropna().tail(weeks)
    return {"rows": [{"period": p.strftime("%Y-%m-%d"), "component": "Weekly change in reserves", "pp": round(v, 2)}
                     for p, v in d.items()]}


def rbi_projections() -> dict:
    """RBI's whole-year projections at each MPC meeting against the outturn, by financial year.
    Outturn: real GDP growth = MoSPI's latest annual estimate (with its stage); CPI inflation =
    mean of the twelve monthly published rates, April to March (site calculation)."""
    out = {}
    cpi = load("cpi_headline_inflation").set_index("period")["value"]
    gdp_fy = store.load_series("gdp_real_growth_fy")
    for key, sid in (("cpi", "mpc_cpi_projection"), ("gdp", "mpc_gdp_projection")):
        df = store.load_series(sid)
        years = {}
        for r in df.itertuples():
            fy = str(r.note).replace("for ", "")
            years.setdefault(fy, []).append({"meeting": r.period, "value": float(r.value)})
        rows = []
        for fy, proj in sorted(years.items()):
            if fy < "2023-24":        # older statements project half-years; pairings unreliable
                continue
            start = pd.Timestamp(f"{fy[:4]}-04-01")
            outturn, basis = None, ""
            if key == "cpi":
                months = cpi[(cpi.index >= start) & (cpi.index < start + pd.DateOffset(years=1))]
                if len(months) == 12:
                    outturn, basis = round(float(months.mean()), 1), "average of monthly rates"
            else:
                hit = gdp_fy[gdp_fy["period"] == f"{fy[:4]}-04-01"]
                if len(hit):
                    outturn, basis = float(hit["value"].iloc[0]), str(hit["note"].iloc[0])
            proj = sorted(proj, key=lambda p: p["meeting"])
            rows.append({"fy": fy, "first": proj[0], "last": proj[-1], "path": proj, "outturn": outturn, "basis": basis,
                         "miss": None if outturn is None else round(outturn - proj[0]["value"], 1)})
        out[key] = rows
    return out


def base_bridge() -> dict:
    """Old vs new base where both exist (the 2026 rebasing).
    CPI: 2025 inflation as officially published on the 2012 base vs the same months computed
    from MoSPI's linked 2024-base index. GDP: quarterly real growth on the 2011-12 base vs the
    2022-23 base, in the quarters MoSPI published on both."""
    pub = store.load_series("cpi_headline_inflation")
    old_cpi = pub[pub["note"].str.contains("2012", na=False)].set_index("period")["value"].astype(float)
    new_cpi = transform(load("cpi_headline_index"), "yoy").set_index("period")["value"]
    cpi = []
    for p, v in old_cpi.items():
        n = new_cpi.get(pd.Timestamp(p))
        if n is not None and not pd.isna(n):
            cpi.append({"period": p, "old": round(v, 2), "new": round(float(n), 2), "diff": round(float(n) - v, 2)})
    old_gdp = store.load_series("gdp_real_growth_2011base").set_index("period")["value"].astype(float)
    new_all = store.load_series("gdp_real_growth")
    new_gdp = new_all[~new_all["note"].str.contains("2011", na=False)].set_index("period")["value"].astype(float)
    gdp = [{"period": p, "old": v, "new": float(new_gdp[p]), "diff": round(float(new_gdp[p]) - v, 1)}
           for p, v in old_gdp.items() if p in new_gdp.index]
    return {"cpi": cpi, "gdp": gdp}


def division_label(spec: dict) -> str:
    """'CPI food & beverages' -> 'Food & beverages'."""
    s = spec["short_title"].removeprefix("CPI ")
    return s[:1].upper() + s[1:]


def question_metric(spec: dict, payload: dict) -> dict:
    """One number on a home-page question card: latest, year-ago or 4-period average."""
    how = spec.get("transform", "level")
    points = payload["data"] if how == "level" else payload["transforms"][how]
    period, value = points[-1][0], points[-1][1]
    if spec["stat"] == "year_ago":
        target = (pd.Timestamp(period) - pd.DateOffset(years=1)).strftime("%Y-%m-%d")
        period, value = target, next((v for p, v, *_ in points if p == target), None)
    elif spec["stat"] == "avg4":
        last4 = points[-4:]
        period, value = f"{last4[0][0]}/{last4[-1][0]}", round(sum(p[1] for p in last4) / len(last4), 2)
    return {**spec, "period": period, "value": value, "frequency": payload["frequency"]}


PERIOD_LENGTH = {"D": pd.DateOffset(days=1), "W": pd.DateOffset(days=7), "F": pd.DateOffset(days=14),
                 "M": pd.DateOffset(months=1), "Q": pd.DateOffset(months=3), "A": pd.DateOffset(years=1)}


def health(spec: dict, payload: dict | None, status: dict, today: pd.Timestamp) -> dict:
    """Is a series overdue? The next period after the latest one ends one period-length
    later; it is due release.lag_days after that end. Overdue = today is past that date."""
    entry = {"id": spec["id"], "title": spec["short_title"], "fetch": spec["fetch"],
             "frequency": spec["frequency"], "lag_days": spec["release"]["lag_days"],
             "stale": bool(status.get("stale")), "last_error": status.get("last_error"),
             "last_success": status.get("last_success"), "last_period": None, "due": None, "overdue_days": None,
             "discontinued": spec.get("discontinued")}
    if payload and spec.get("discontinued"):
        entry["last_period"] = payload["data"][-1][0]
    elif payload:
        last = pd.Timestamp(payload["data"][-1][0])
        step = PERIOD_LENGTH[spec["frequency"]]
        next_period_end = last + step + step - pd.Timedelta(days=1)
        due = next_period_end + pd.Timedelta(days=spec["release"]["lag_days"])
        entry.update(last_period=last.strftime("%Y-%m-%d"), due=due.strftime("%Y-%m-%d"),
                     overdue_days=max(0, (today - due).days))
    return entry


def open_issues() -> list[dict] | None:
    """Open scraper-broken / large-revision issues via the gh CLI, if available (None otherwise)."""
    import shutil
    import subprocess
    if not shutil.which("gh"):
        return None
    try:
        out = subprocess.run(["gh", "issue", "list", "--state", "open", "--limit", "100", "--json",
                              "number,title,labels,url,updatedAt"], cwd=store.ROOT,
                             capture_output=True, text=True, timeout=30, check=True).stdout
    except (subprocess.SubprocessError, OSError):
        return None
    issues = json.loads(out)
    keep = {"scraper-broken", "large-revision"}
    return [{"number": i["number"], "title": i["title"], "url": i["url"], "updated": i["updatedAt"][:10],
             "labels": [lb["name"] for lb in i["labels"]]} for i in issues
            if keep & {lb["name"] for lb in i["labels"]}]


def actions_minutes() -> dict | None:
    """Estimated GitHub Actions minutes this calendar month (UTC), from the workflow runs'
    start and end times, each rounded up to a whole minute as GitHub bills jobs. An estimate:
    the exact figure (Settings -> Billing) needs organisation-admin access the build lacks."""
    import math
    import shutil
    import subprocess
    if not shutil.which("gh"):
        return None
    start = date.today().replace(day=1).isoformat()
    try:
        out = subprocess.run(["gh", "api", "--paginate", f"repos/{{owner}}/{{repo}}/actions/runs?created=>={start}&per_page=100",
                              "--jq", ".workflow_runs[] | [.name, .run_started_at, .updated_at, .status] | @tsv"],
                             cwd=store.ROOT, capture_output=True, text=True, timeout=120, check=True).stdout
    except (subprocess.SubprocessError, OSError):
        return None
    try:                                                    # public repositories have no limit
        private = subprocess.run(["gh", "api", "repos/{owner}/{repo}", "--jq", ".private"], cwd=store.ROOT,
                                 capture_output=True, text=True, timeout=60, check=True).stdout.strip() != "false"
    except (subprocess.SubprocessError, OSError):
        private = True
    total, runs, by_workflow = 0, 0, {}
    for line in out.splitlines():
        name, began, ended, status = (line.split("\t") + ["", "", "", ""])[:4]
        if status != "completed" or not began or not ended:
            continue
        secs = (pd.Timestamp(ended) - pd.Timestamp(began)).total_seconds()
        mins = max(1, math.ceil(secs / 60))
        total, runs = total + mins, runs + 1
        by_workflow[name] = by_workflow.get(name, 0) + mins
    top = sorted(by_workflow.items(), key=lambda kv: -kv[1])[:6]
    return {"month": start[:7], "minutes": total, "runs": runs, "limit": 2000 if private else None, "by_workflow": top}


def panel_payload(series_id: str, spec: dict, min_entities: int = 20) -> dict | None:
    """Entity x period panel for the site. `ref_period` is the latest period that at least
    `min_entities` entities have reported (late reporters otherwise skew rankings)."""
    df = store.load_panel(series_id)
    if df.empty:
        return None
    df["value"] = df["value"].astype(float)
    counts = df.groupby("period")["entity"].nunique()
    ref = counts[counts >= min(min_entities, counts.max())].index.max()
    wide = df.pivot_table(index="entity", columns="period", values="value")
    noted = df[df["note"].fillna("") != ""]
    cell_notes = {e: dict(zip(g["period"], g["note"])) for e, g in noted.groupby("entity")}
    return {"id": series_id, "title": spec["title"], "short_title": spec["short_title"], "unit": spec["unit"],
            "frequency": spec["frequency"], "source": spec["source"], "notes": spec.get("notes", ""),
            "periods": sorted(df["period"].unique().tolist()), "ref_period": ref,
            "rows": [{"entity": e, "values": {p: (None if pd.isna(v) else round(float(v), 3)) for p, v in r.items()}}
                     for e, r in wide.iterrows()],
            "cell_notes": cell_notes}


def first_last(sid: str, payloads: dict, panels: dict) -> tuple[str | None, str | None]:
    if sid in payloads:
        return payloads[sid]["data"][0][0], payloads[sid]["data"][-1][0]
    if panels.get(sid):
        return panels[sid]["periods"][0], panels[sid]["periods"][-1]
    return None, None


def observations(sid: str, payloads: dict, panels: dict) -> int:
    if sid in payloads:
        return len(payloads[sid]["data"])
    if panels.get(sid):
        return sum(v is not None for r in panels[sid]["rows"] for v in r["values"].values())
    return 0


def write_json(path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1))


def main() -> int:
    specs = registry.all_series()
    payloads = {}
    for sid, spec in specs.items():
        df = load(sid)
        if df.empty:
            continue
        payloads[sid] = series_payload(sid, spec, df)
        write_json(OUT / "series" / f"{sid}.json", payloads[sid])

    panels = {}
    for sid, spec in specs.items():
        if spec.get("panel"):
            panels[sid] = panel_payload(sid, spec)
            if panels[sid]:
                write_json(OUT / "panels" / f"{sid}.json", panels[sid])
    write_json(OUT / "state_short_names.json",
               yaml.safe_load((store.ROOT / "registry" / "states.yaml").read_text()).get("short", {}))

    pages = {f.stem: yaml.safe_load(f.read_text()) for f in sorted(PAGES.glob("*.yaml"))}
    tiles = [tile(t, payloads[t["series"]]) for t in pages.get("home", {}).get("tiles", [])
             if t["series"] in payloads]
    questions = [{**q, "metrics": [question_metric(m, payloads[m["series"]]) for m in q["metrics"]
                                   if m["series"] in payloads]}
                 for q in pages.get("home", {}).get("questions", [])]
    write_json(OUT / "home.json", {"tiles": tiles, "questions": questions})
    write_json(OUT / "cpi_contributions.json", cpi_contributions())
    write_json(OUT / "cpi_diffusion.json", cpi_diffusion())
    write_json(OUT / "transmission.json", transmission())
    write_json(OUT / "quarterly_projections.json", quarterly_projections())
    write_json(OUT / "cpi_fan.json", cpi_fan())
    write_json(OUT / "credit_contributions.json", credit_contribution_charts())
    write_json(OUT / "cpi_division_contributions.json", cpi_division_contributions(specs))
    write_json(OUT / "gdp_contributions.json", gdp_contributions())

    catalogue = [{"id": sid, "title": spec["title"], "short_title": spec["short_title"],
                  "area": spec["area"], "agency": spec["source"]["agency"],
                  "source_url": spec["source"].get("url", ""), "frequency": spec["frequency"],
                  "unit": spec["unit"], "base_year": spec.get("base_year"),
                  "licence": spec["licence"], "downloadable": spec["downloadable"],
                  "fetch": spec["fetch"], "notes": spec.get("notes", ""),
                  "panel": bool(spec.get("panel")),
                  "first_period": first_last(sid, payloads, panels)[0],
                  "last_period": first_last(sid, payloads, panels)[1],
                  "observations": observations(sid, payloads, panels)}
                 for sid, spec in specs.items()]
    write_json(OUT / "catalogue.json", catalogue)

    # Release calendar, with each release's latest published value attached.
    today = date.today().isoformat()
    cal = calendar.load(set(specs))
    for r in cal:
        r["status"] = "released" if r["date"] <= today else "upcoming"
        sid = r["series"][0] if r["series"] else None
        if sid in payloads:
            pts = payloads[sid]["data"] if r["show"] == "level" else payloads[sid]["transforms"][r["show"]]
            unit = "percent" if r["show"] in ("yoy", "mom") else payloads[sid]["unit"]
            r["latest"] = {"series": sid, "period": pts[-1][0], "value": pts[-1][1], "unit": unit,
                           "frequency": payloads[sid]["frequency"], "title": payloads[sid]["short_title"],
                           "show": r["show"]}
    write_json(OUT / "calendar.json", cal)
    write_json(OUT / "mpc_decisions.json", mpc_decisions(cal))
    write_json(OUT / "budget.json", budget_table())
    write_json(OUT / "changes.json", what_changed(specs))
    write_json(OUT / "budget_demands.json", budget_demands())
    write_json(OUT / "yield_curve.json", yield_curve())
    write_json(OUT / "cpi_momentum_base.json", cpi_momentum_base())
    write_json(OUT / "policy_rule.json", policy_rule_inputs())
    write_json(OUT / "reserves_change.json", reserves_change())
    try:                       # the rupee page explains the latest move; never block the rest of the site
        write_json(OUT / "rupee.json", rupee.analyse())
    except Exception as e:     # noqa: BLE001
        print(f"  rupee drivers: skipped ({type(e).__name__}: {e})")
        write_json(OUT / "rupee.json", {"error": f"{type(e).__name__}: {e}"})
    try:                       # Analysis: BoP stress episodes and forex intervention (same rule)
        write_json(OUT / "bop_stress.json", bop_stress.analyse())
    except Exception as e:     # noqa: BLE001
        print(f"  BoP stress analysis: skipped ({type(e).__name__}: {e})")
        write_json(OUT / "bop_stress.json", {"error": f"{type(e).__name__}: {e}"})
    write_json(OUT / "rbi_projections.json", rbi_projections())
    write_json(OUT / "base_bridge.json", base_bridge())
    PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    (PUBLIC.parent / "calendar.ics").write_text(calendar.ics(cal, registry.site_config()["site"]["name"]))

    as_of = max((p["data"][-1][0] for p in payloads.values()), default=None)
    status = store.load_status()
    today = pd.Timestamp(date.today())
    write_json(OUT / "site.json", {"built_on": date.today().isoformat(), "as_of": as_of, "status": status})
    health_rows = [health(spec, payloads.get(sid), status.get(sid, {}), today) for sid, spec in specs.items()]
    actions = actions_minutes()
    write_json(OUT / "health.json", {"series": health_rows, "issues": open_issues(), "actions": actions})
    try:                       # the live status dashboard's map (scheduler/dashboard.js); never block the site
        write_json(PUBLIC.parent / "status-map.json", status_map.build(specs, health_rows, cal, actions))
    except Exception as e:     # noqa: BLE001
        print(f"  status map: skipped ({type(e).__name__}: {e})")

    # Downloadable CSVs (licence permitting) are copied into the site's public folder.
    PUBLIC.mkdir(parents=True, exist_ok=True)
    for sid, spec in specs.items():
        if spec["downloadable"] and sid in payloads:
            # The stored file, less any rows readers don't see (store.published, e.g. `exclude`).
            path = store.SERIES / f"{sid}.csv"
            if not spec.get("exclude"):
                (PUBLIC / f"{sid}.csv").write_bytes(path.read_bytes())
            else:
                raw = pd.read_csv(path, dtype=str, keep_default_na=False)
                raw[~store.excluded_rows(sid, raw)].to_csv(PUBLIC / f"{sid}.csv", index=False)
        elif spec["downloadable"] and panels.get(sid):
            (PUBLIC / f"{sid}.csv").write_bytes((store.PANELS / f"{sid}.csv").read_bytes())
    leaked = [f.name for f in PUBLIC.glob("*.csv")
              if f.stem not in specs or not specs[f.stem]["downloadable"]]
    if leaked:
        print(f"ERROR: public CSVs for non-downloadable or unregistered series: {leaked}. "
              f"A maintainer must remove them from site/public/data/.")
        return 1

    write_bulk_zip(specs)
    print(f"built {len(payloads)} series, {len(tiles)} tiles -> {OUT.relative_to(store.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
