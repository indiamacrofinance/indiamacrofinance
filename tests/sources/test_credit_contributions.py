"""Contributions to credit growth sum to the parent's growth."""
import pandas as pd

from pipelines.sources.derived.credit_contributions import contributions


def test_contributions_sum_to_growth():
    levels = pd.DataFrame({"parent": [100.0, 120.0], "a": [60.0, 80.0], "b": [30.0, 31.0]},
                          index=["2025-08-01", "2026-08-01"])
    rows = contributions(levels, "parent", {"A": "a", "B": "b"}, "Others")
    got = {r["entity"]: r["value"] for r in rows}
    assert got == {"A": 20.0, "B": 1.0, "Others": -1.0}
    assert round(sum(got.values()), 6) == 20.0                     # = parent growth, 120 / 100 - 1
    rows = contributions(levels, None, {"A": "a", "B": "b"}, None)  # base = sum of the parts (90)
    assert round(sum(r["value"] for r in rows), 3) == round(100 * (111 / 90 - 1), 3)
