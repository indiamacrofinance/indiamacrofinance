"""RBI dollar purchases and sales (Handbook, Bulletin Table 4) and the rupee's monthly average.
Pinned values are read from the official tables (US$ million / rupees per dollar)."""
import pandas as pd
import pytest

from pipelines.sources.rbi.fx_operations import SOURCE, parse_file


def at(rows, sid, period):
    df = pd.DataFrame(rows)
    return df[(df.series_id == sid) & (df.period == period)].value.iloc[0]


def test_handbook_two_blocks(raw_from):
    rows = parse_file(raw_from("rbi/fx_operations/hbie_2025-26_fxi.xlsx"))
    assert at(rows, "rbi_fx_purchases", "2022-04-01") == 11965
    assert at(rows, "rbi_fx_sales", "2022-04-01") == 10000
    assert at(rows, "rbi_fx_forward_book", "2022-04-01") == 63826
    assert at(rows, "rbi_fx_sales", "2026-04-01") == 25169            # second block, 2026 rows
    assert at(rows, "rbi_fx_net_purchase", "2026-04-01") == 16225 - 25169


def test_handbook_long_and_date_layouts(raw_from):
    rows = parse_file(raw_from("rbi/fx_operations/hbie_2012-13_fxi.xls"))
    assert at(rows, "rbi_fx_purchases", "1997-04-01") == 641            # '1997:04 (APR)'
    assert at(rows, "rbi_fx_sales", "1997-04-01") == 0                  # '-' = no transaction
    dates = parse_file(raw_from("rbi/fx_operations/hbie_2017-18_fxi_dates.xlsx"))
    assert at(dates, "rbi_fx_purchases", "2014-04-01") == 7850          # month-end dates
    assert at(dates, "rbi_fx_forward_book", "2018-06-01") == 10689


def test_monthly_exchange_rate(raw_from):
    rows = parse_file(raw_from("rbi/fx_operations/hbie_2025-26_fxm.xlsx"))
    assert at(rows, "usdinr_monthly_avg", "2022-01-01") == pytest.approx(74.4416)
    assert at(rows, "usdinr_monthly_avg", "2026-06-01") == pytest.approx(94.9695)
    old = parse_file(raw_from("rbi/fx_operations/hbie_2017-18_fxm_dates.xlsx"))
    assert at(old, "usdinr_monthly_avg", "2014-01-01") == pytest.approx(62.07597)


def test_bulletin_table_4(raw_from):
    # October 2026 issue: August 2026, July 2026 and August 2025.
    rows = parse_file(raw_from("rbi/fx_operations/bulletin_t4_2026-10.html"))
    assert at(rows, "rbi_fx_purchases", "2026-08-01") == 74472
    assert at(rows, "rbi_fx_sales", "2026-08-01") == 31208
    assert at(rows, "rbi_fx_forward_book", "2026-08-01") == -200055
    assert at(rows, "rbi_fx_purchases", "2026-07-01") == 38417
    assert at(rows, "rbi_fx_sales", "2025-08-01") == 7695
    assert at(rows, "rbi_fx_net_purchase", "2026-08-01") == 43264


def test_parse_combines_and_converts(raw_from):
    df = SOURCE.parse([raw_from("rbi/fx_operations/hbie_2025-26_fxi.xlsx"),
                       raw_from("rbi/fx_operations/hbie_2025-26_fxm.xlsx"),
                       raw_from("rbi/fx_operations/bulletin_t4_2026-10.html")])
    s = df.set_index(["series_id", "period"]).value
    assert s["rbi_fx_net_purchase", "2026-08-01"] == pytest.approx(43.264)      # US$ bn
    assert s["usdinr_monthly_avg", "2026-06-01"] == pytest.approx(94.9695)     # not scaled
