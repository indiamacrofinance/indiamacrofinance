"""Import cover and the real policy rate (pipelines/sources/derived/import_cover.py, real_rate.py)."""
import pandas as pd

from pipelines.sources.derived.import_cover import import_cover
from pipelines.sources.derived.real_rate import real_rate


def test_import_cover_uses_month_end_reserves_and_12_month_average():
    months = pd.date_range("2025-01-01", periods=13, freq="MS").strftime("%Y-%m-%d")
    imports = pd.DataFrame({"period": months, "value": [50.0] * 12 + [74.0]})
    reserves = pd.DataFrame({"period": ["2025-12-05", "2025-12-26", "2026-01-30"], "value": [590.0, 600.0, 612.0]})
    out = import_cover(reserves, imports).set_index("period").value
    assert out["2025-12-01"] == 12.0                          # 600 (last week of Dec) / 50
    assert out["2026-01-01"] == 11.8                          # 612 / ((11 x 50 + 74) / 12) = 612 / 52
    assert "2025-11-01" not in out                            # no reserves that month


def test_import_cover_skips_a_missing_month_but_not_three():
    one_gap = [f"2025-{m:02d}-01" for m in range(1, 13) if m != 6] + ["2026-01-01"]
    imports = pd.DataFrame({"period": one_gap, "value": 50.0})
    reserves = pd.DataFrame({"period": ["2026-01-30"], "value": [600.0]})
    assert import_cover(reserves, imports).value.tolist() == [12.0]   # 11 months present, mean 50
    three_gaps = [p for p in one_gap if p not in ("2025-07-01", "2025-08-01")]
    assert import_cover(reserves, pd.DataFrame({"period": three_gaps, "value": 50.0})).empty


def test_real_rate_uses_repo_in_force_at_month_end():
    repo = pd.DataFrame({"period": ["2026-08-28", "2026-10-09"], "value": [5.25, 5.5]})
    cpi = pd.DataFrame({"period": ["2026-07-01", "2026-09-01", "2026-10-01"], "value": [4.0, 5.54, 5.0]})
    out = real_rate(repo, cpi).set_index("period").value
    assert out["2026-09-01"] == -0.29                         # 5.25 in force on 30 Sep
    assert out["2026-10-01"] == 0.5
    assert "2026-07-01" not in out                            # before the repo history starts
