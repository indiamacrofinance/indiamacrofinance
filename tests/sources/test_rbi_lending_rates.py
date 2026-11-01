"""RBI lending and deposit rates workbook (October 2026 release; full history in each table)."""
import pandas as pd

from pipelines.sources.rbi.lending_rates import TABLES, parse_book


def test_lending_rates(raw_from):
    d = pd.DataFrame(parse_book(raw_from("rbi/mldrscb_2026-10.xlsx").content))
    at = lambda sid, e, p: d[(d.series_id == sid) & (d.entity == e) & (d.period == p)].value.item()
    scb = "All scheduled commercial banks"
    assert set(d.series_id) == {p for _, p in TABLES}
    assert at("walr_outstanding", scb, "2026-09-01") == 8.96
    assert at("walr_outstanding", scb, "2012-02-01") == 12.53                 # history from 2012
    assert at("walr_fresh", "Public sector banks", "2026-09-01") == 7.93
    assert at("wadtdr_fresh", scb, "2026-09-01") == 5.61
    assert at("mclr_1y_median", scb, "2026-10-01") == 8.55                   # median column, not min/max
    assert at("loan_benchmark_share", "EBLR", "2026-06-01") == 68.24          # all-SCB block
    assert at("walr_fresh_sector", "Housing", "2026-09-01") == 7.68
    assert not d.duplicated(["series_id", "entity", "period"]).any()
