"""Recover the weight of every CPI 2024 item (all-India combined) from MoSPI's index tree.

MoSPI publishes division weights but not item weights. CPI 2024 is a fixed-weight
(Laspeyres) index, so every parent index is an exact weighted average of its children:

    I_parent(t) = sum_k s_k * I_k(t),   s_k >= 0,   sum_k s_k = 1

For each of the ~309 parents, non-negative least squares on 20+ months of published
indices (the sum constraint as a heavily weighted extra row) recovers the shares s_k. Item
weights are the official division weight (registry/weights/cpi2024_divisions.yaml) times the
shares down the tree. Validation against RBI's published measures:
docs/guidebook/08-original-measures.md ("Underlying inflation").

    uv run python scripts/estimate_cpi_item_weights.py    # rewrites registry/weights/cpi2024_items.csv

Re-run when MoSPI revises indices or after a few more months of data (more months pin down
small items better); the weights themselves are fixed for the life of the 2024 base.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipelines.sources.mospi._api import month_period, pages, rows  # noqa: E402

OUT = ROOT / "registry" / "weights" / "cpi2024_items.csv"
DIVISION_SERIES = {  # published division code -> series id in cpi2024_divisions.yaml
    "01": "cpi_food_bev_index", "02": "cpi_paan_tobacco_index", "03": "cpi_clothing_index",
    "04": "cpi_housing_utilities_index", "05": "cpi_household_goods_index", "06": "cpi_health_index",
    "07": "cpi_transport_index", "08": "cpi_info_comm_index", "09": "cpi_recreation_index",
    "10": "cpi_education_index", "11": "cpi_restaurants_index",
    "13": "cpi_personal_care_index",   # COICOP 2018 division 12 (insurance, financial services) is not in India's CPI
}


def nnls(A: np.ndarray, b: np.ndarray, iters: int = 500) -> np.ndarray:
    """Lawson-Hanson non-negative least squares (numpy only)."""
    n = A.shape[1]
    x, P = np.zeros(n), np.zeros(n, bool)
    w = A.T @ (b - A @ x)
    for _ in range(iters):
        if P.all() or w[~P].max(initial=-np.inf) <= 1e-12:
            break
        P[np.argmax(np.where(P, -np.inf, w))] = True
        while True:
            z = np.zeros(n)
            z[P] = np.linalg.lstsq(A[:, P], b, rcond=None)[0]
            if (z[P] > 0).all():
                x = z
                break
            neg = P & (z <= 0)
            x = x + np.min(x[neg] / (x[neg] - z[neg])) * (z - x)
            P &= x > 1e-12
        w = A.T @ (b - A @ x)
    return x


def shares(parent: pd.Series, children: pd.DataFrame, lam: float = 1000.0) -> tuple[np.ndarray, float]:
    X = children.loc[parent.index].values
    s = nnls(np.vstack([X, lam * np.ones(X.shape[1])]), np.append(parent.values, lam))
    s = s / s.sum()
    return s, float(np.abs(X @ s - parent.values).max())


def estimate(df: pd.DataFrame, division_weight: dict[str, float]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """df: one row per (code, period) with index and the name columns -> (weights, residuals)."""
    idx = df.pivot_table(index="period", columns="code", values="index", aggfunc="first")
    codes = list(idx.columns)
    level = {c: c.count(".") for c in codes}
    parent = {c: max((p for p in codes if level[p] < level[c] and c.startswith(p + ".")),
                     key=lambda p: level[p], default=None) for c in codes}
    kids: dict[str, list[str]] = {}
    for c, p in parent.items():
        if p:
            kids.setdefault(p, []).append(c)
    weight = dict(division_weight)
    report = []
    for p in sorted(kids, key=lambda c: level[c]):
        ch = sorted(kids[p])
        s, res = (np.array([1.0]), float((idx[ch[0]] - idx[p]).abs().max())) if len(ch) == 1 \
            else shares(idx[p].dropna(), idx[ch])
        for c, sk in zip(ch, s):
            weight[c] = weight[p] * sk
        report.append({"parent": p, "children": len(ch), "max_abs_residual": round(res, 4)})
    names = df.drop_duplicates("code").set_index("code")
    label = (names["item"].fillna(names["sub_class"]).fillna(names["class"])
             .fillna(names["group"]).fillna(names["division"]))
    out = pd.DataFrame({"code": list(weight), "weight": [round(v, 5) for v in weight.values()]})
    out["level"] = out.code.map(level)
    out["parent"] = out.code.map(parent)
    out["kind"] = np.where(out.level == 5, np.where(out.code.str.split(".").str[4] == "2", "service", "good"), "")
    out["name"] = out.code.map(label)
    return out.sort_values("code")[["code", "parent", "level", "kind", "weight", "name"]], pd.DataFrame(report)


def main() -> None:
    division = yaml.safe_load((ROOT / "registry/weights/cpi2024_divisions.yaml").read_text())["weights"]
    division_weight = {code: division[sid] for code, sid in DIVISION_SERIES.items()}
    recs = []
    for d in range(1, 13):
        recs += rows(pages("cpi/getCPIData", {"base_year": "2024", "state_code": "1", "sector_code": "3",
                                              "series": "Current", "division_code": str(d)}))
    df = pd.DataFrame(recs)
    df = df[df.code.notna() & (df.sector == "Combined")]
    df["period"] = [month_period(y, m) for y, m in zip(df.year, df.month)]
    df["index"] = df["index"].astype(float)
    weights, report = estimate(df, division_weight)
    weights.to_csv(OUT, index=False)
    items = weights[weights.level == 5]
    print(f"{len(items)} items ({(items.kind == 'good').sum()} goods, {(items.kind == 'service').sum()} services), "
          f"weights sum {items.weight.sum():.3f}; months {df.period.min()}..{df.period.max()}")
    print(f"{len(report)} parents; max abs residual {report.max_abs_residual.max():.4f} index points; "
          f"zero-weight items: {(items.weight < 1e-6).sum()}")


if __name__ == "__main__":
    main()
