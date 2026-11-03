"""Budget at a Glance (Budget 2026-27)."""
import pytest

from pipelines.sources.budget.glance import ORDER, SOURCE


def at(df, sid, entity, period):
    return df[(df.series_id == sid) & (df.entity == entity) & (df.period == period)].value.item()


def test_budget_at_a_glance(raw_from):
    df = SOURCE.parse([raw_from("budget/budget_at_a_glance_2026-27.xlsx")])
    assert at(df, "budget_be", "Fiscal deficit", "2026-04-01") == 16.9577        # Rs 16,95,768 crore
    assert at(df, "budget_re", "Fiscal deficit", "2025-04-01") == 15.5849
    assert at(df, "budget_actuals", "Fiscal deficit", "2024-04-01") == 15.7443
    assert at(df, "budget_be", "Fiscal deficit, % of GDP", "2026-04-01") == 4.3  # "(4.3)" on the row below
    assert at(df, "budget_actuals", "Revenue deficit, % of GDP", "2024-04-01") == 1.7
    # "Revenue Deficit" must not pick up "Effective Revenue Deficit".
    assert at(df, "budget_be", "Revenue deficit", "2026-04-01") == 5.9234
    assert set(df.entity) == set(ORDER)
    assert len(df) == len(ORDER) * 4


def test_demands_add_up(raw_from):
    from pipelines.sources.budget.demands import SOURCE as DEMANDS
    df = DEMANDS.parse([raw_from("budget/stat3a_2026-27.xlsx")])
    be = df[(df.series_id == "budget_demand_be") & (df.period == "2026-04-01")]
    assert be.entity.nunique() == 102
    assert round(be.value.sum(), 3) == 53.473                       # Grand Total, Rs 53,47,315 crore
    rail = be[be.entity == "Ministry of Railways"].iloc[0]
    assert (rail.value, rail.note) == (2.81377, "Demand No. 85")


def test_archived_pdf_editions(raw_from):
    """Archived Budgets (PDF, headline page only). 2019-20: a row whose label we do not keep
    ('Capital Receipts') must not inherit the label above it; no Effective capex yet."""
    old = SOURCE.parse([raw_from("budget/budget_at_a_glance_2019-20.pdf")])
    assert at(old, "budget_actuals", "Non-tax revenue", "2017-04-01") == 1.9275      # Rs 1,92,745 crore
    assert at(old, "budget_actuals", "Interest payments", "2017-04-01") == 5.2895
    assert at(old, "budget_actuals", "Fiscal deficit, % of GDP", "2017-04-01") == 3.5
    assert "Effective capital expenditure" not in set(old.entity)
    # 2024-25 (full Budget after the election): five columns; Provisional Actuals 2023-24 skipped.
    mid = SOURCE.parse([raw_from("budget/budget_at_a_glance_2024-25.pdf")])
    assert at(mid, "budget_actuals", "Fiscal deficit", "2022-04-01") == pytest.approx(17.37755, abs=1e-4)
    assert at(mid, "budget_re", "Fiscal deficit", "2023-04-01") == pytest.approx(17.34773, abs=1e-4)
    assert at(mid, "budget_be", "Fiscal deficit", "2024-04-01") == pytest.approx(16.13312, abs=1e-4)
    assert at(mid, "budget_be", "Fiscal deficit, % of GDP", "2024-04-01") == 4.9
    assert not ((mid.series_id == "budget_actuals") & (mid.period == "2023-04-01")).any()
    # 2025-26 shortens labels ("13. On Capital", "14. Effective Capital", "Non-Tax Revenue").
    new = SOURCE.parse([raw_from("budget/budget_at_a_glance_2025-26.pdf")])
    assert at(new, "budget_be", "Capital expenditure", "2025-04-01") == pytest.approx(11.2109, abs=1e-4)
    assert at(new, "budget_be", "Effective capital expenditure", "2025-04-01") == pytest.approx(15.48282, abs=1e-4)
    assert at(new, "budget_be", "Non-tax revenue", "2025-04-01") == 5.83
    assert at(new, "budget_actuals", "Tax revenue (net to Centre)", "2023-04-01") == pytest.approx(23.27251, abs=1e-4)
    assert set(new.entity) == set(ORDER)
