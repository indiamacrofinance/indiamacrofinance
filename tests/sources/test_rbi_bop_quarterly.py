"""RBI quarterly BoP (BPM6 and BPM5) from the Handbook and the release statements.
Pinned values are read from the official tables (US$ million in the files)."""
import pandas as pd
import pytest

from pipelines.sources.rbi.bop_quarterly import (
    SOURCE,
    check_identity,
    complete,
    parse_file,
    quarter,
)


def at(rows, sid, period):
    df = pd.DataFrame(rows)
    return df[(df.series_id == sid) & (df.period == period)].value.iloc[0]


def test_quarter_labels():
    assert quarter("April-June 2026 P") == "2026-04-01"
    assert quarter("Apr-Jun 2016") == "2016-04-01"
    assert quarter("January-March 2026 PR") == "2026-01-01"
    assert quarter("April-March 2025-26 PR") is None          # annual column, not a quarter


def test_bpm6_handbook_blocks(raw_from):
    rows = parse_file(raw_from("rbi/bop_quarterly/hbie_2025-26_bpm6.xlsx"))
    assert at(rows, "bop_bpm6_current_account", "2024-04-01") == pytest.approx(-4454, abs=1)
    assert at(rows, "bop_bpm6_goods_services", "2024-04-01") == pytest.approx(-19943, abs=1)
    assert at(rows, "bop_bpm6_odi", "2024-04-01") == pytest.approx(-4382, abs=1)
    assert at(rows, "bop_bpm6_derivatives", "2024-04-01") == pytest.approx(-3613, abs=1)
    assert at(rows, "bop_bpm6_derivatives_payments", "2024-04-01") == pytest.approx(9666, abs=1)
    assert at(rows, "bop_bpm6_reserve_assets", "2024-04-01") == pytest.approx(-5226, abs=1)
    assert at(rows, "bop_bpm6_errors_omissions", "2024-04-01") == pytest.approx(773, abs=1)
    assert {r["period"] for r in rows} >= {"2024-04-01", "2026-01-01"}   # all four sheets


def test_bpm6_pdf_edition(raw_from):
    # 2014-15 edition, PDF only: Apr-Jun 2013 ('–' is nil, '–21,772' negative).
    rows = parse_file(raw_from("rbi/bop_quarterly/hbie_2014-15_bpm6.pdf"))
    assert at(rows, "bop_bpm6_current_account", "2013-04-01") == -21772
    assert at(rows, "bop_bpm6_fdi_in_india", "2013-04-01") == 6476
    assert at(rows, "bop_bpm6_derivatives_receipts", "2013-04-01") == 1735
    assert at(rows, "bop_bpm6_derivatives_payments", "2013-04-01") == 2280
    assert at(rows, "bop_bpm6_reserve_assets", "2013-07-01") == 10355
    assert at(rows, "bop_bpm6_errors_omissions", "2013-07-01") == -434


def test_statement_one_code_column_and_item_4(raw_from):
    # Statement I keeps the code in its own column; errors and omissions are item 4 there.
    rows = parse_file(raw_from("rbi/bop_quarterly/statement1_2026-09-01.xlsx"))
    assert at(rows, "bop_bpm6_current_account", "2025-04-01") == pytest.approx(-3360.2, abs=0.1)
    assert at(rows, "bop_bpm6_errors_omissions", "2025-04-01") == pytest.approx(-1364.8, abs=0.1)
    assert "2026-04-01" in {r["period"] for r in rows}
    assert "2025-26" not in str({r["period"] for r in rows})       # annual column skipped


def test_bpm5_blocks_long_and_split_header(raw_from):
    rows = parse_file(raw_from("rbi/bop_quarterly/hbie_2025-26_bpm5.xlsx"))
    assert at(rows, "bop_bpm5_banking_capital", "2022-04-01") == pytest.approx(19041, abs=1)
    assert at(rows, "bop_bpm5_bank_assets", "2022-04-01") == pytest.approx(19458, abs=1)
    assert at(rows, "bop_bpm5_nri_deposits", "2022-04-01") == pytest.approx(349, abs=1)
    assert at(rows, "bop_bpm5_capital_account", "2022-04-01") == pytest.approx(22055, abs=1)
    assert at(rows, "bop_bpm5_reserves_change", "2022-04-01") == pytest.approx(-4595, abs=1)
    long = parse_file(raw_from("rbi/bop_quarterly/hbie_2012-13_bpm5_long.xls"))
    assert at(long, "bop_bpm5_current_account", "2000-04-01") == -2563          # 2000-01:Q1
    assert {r["period"] for r in long} >= {"2000-04-01", "2013-01-01"}
    assert complete(pd.DataFrame(rows)) and complete(pd.DataFrame(long))


def test_misaligned_sheet_is_skipped(raw_from):
    # 2015-16 edition: part of some columns printed a row above its label, leaving gaps.
    split = pd.DataFrame(parse_file(raw_from("rbi/bop_quarterly/hbie_2015-16_bpm5_split_header.xlsx")))
    assert not complete(split)
    df = SOURCE.parse([raw_from("rbi/bop_quarterly/hbie_2015-16_bpm5_split_header.xlsx"),
                       raw_from("rbi/bop_quarterly/hbie_2025-26_bpm5.xlsx")])
    assert df.period.min() == "2022-04-01"          # nothing taken from the misaligned file


def test_identity_check_rejects_a_bad_file():
    rows = pd.DataFrame([
        {"series_id": "bop_bpm6_current_account", "period": "2024-04-01", "value": -4454},
        {"series_id": "bop_bpm6_capital_account", "period": "2024-04-01", "value": 35},
        {"series_id": "_bpm6_financial_account", "period": "2024-04-01", "value": 3646},
        {"series_id": "bop_bpm6_errors_omissions", "period": "2024-04-01", "value": 773},
    ])
    check_identity(rows, "ok")
    rows.loc[0, "value"] = -5454
    with pytest.raises(ValueError, match="identity"):
        check_identity(rows, "bad")


def test_newest_file_wins_and_units(raw_from):
    # The release statement (to Apr-Jun 2026) revises the Handbook's 2025 quarters.
    df = SOURCE.parse([raw_from("rbi/bop_quarterly/hbie_2025-26_bpm6.xlsx"),
                       raw_from("rbi/bop_quarterly/statement1_2026-09-01.xlsx")])
    ca = df[(df.series_id == "bop_bpm6_current_account")].set_index("period").value
    assert ca["2025-04-01"] == pytest.approx(-3.360, abs=0.001)           # US$ bn, statement value
    assert ca["2026-04-01"] == pytest.approx(-4.219, abs=0.001)
    assert not df.series_id.str.startswith("_").any()
