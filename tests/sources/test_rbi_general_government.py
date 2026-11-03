"""Combined Centre + states deficits and debt (RBI Handbook tables 239, 240)."""
from pipelines.sources.rbi.general_government import parse_table


def test_deficits_and_stage(raw_from):
    rows = {(r["series_id"], r["period"]): r for r in parse_table(raw_from("rbi/handbook/hbie239.xlsx").content, 239)}
    assert rows[("gg_gfd_pct_gdp", "2020-04-01")]["value"] == 13.1
    assert rows[("gg_gfd_pct_gdp", "2025-04-01")]["note"] == "Budget Estimates"
    assert rows[("gg_revenue_deficit_pct_gdp", "2024-04-01")]["note"] == "Revised Estimates"


def test_debt_columns(raw_from):
    rows = {(r["series_id"], r["period"]): r["value"] for r in parse_table(raw_from("rbi/handbook/hbie240.xlsx").content, 240)}
    assert rows[("gg_debt_pct_gdp", "2025-04-01")] == 81.85
    assert rows[("centre_debt_pct_gdp", "2025-04-01")] == 56.17
    assert rows[("states_debt_pct_gdp", "1985-04-01")] == 21.19


def test_centre_deficit_and_stage_on_second_sheet(raw_from):
    # Table 237: the stage footnote is on the table's second sheet.
    rows = {(r["series_id"], r["period"]): r for r in parse_table(raw_from("rbi/handbook/hbie237.xlsx").content, 237)}
    assert rows[("centre_gfd_pct_gdp", "1984-04-01")]["value"] == 6.79
    assert rows[("centre_gfd_pct_gdp", "2020-04-01")]["value"] == 9.16
    assert rows[("centre_gfd_pct_gdp", "2026-04-01")]["note"] == "Budget Estimates"
    assert {s for s, _ in rows} == {"centre_gfd_pct_gdp"}          # not net fiscal deficit etc.


def test_bop_indicators_two_header_rows(raw_from):
    # Table 241: "CAD / GDP" sits in the second header row, "Import Cover ..." in the first.
    rows = {(r["series_id"], r["period"]): r["value"] for r in parse_table(raw_from("rbi/handbook/hbie241.xlsx").content, 241)}
    assert rows[("cab_pct_gdp_fy", "2012-04-01")] == -4.81
    assert rows[("cab_pct_gdp_fy", "2020-04-01")] == 0.93
    assert rows[("reserves_import_cover", "1989-04-01")] == 1.9
    assert rows[("reserves_import_cover", "2025-04-01")] == 10.59
