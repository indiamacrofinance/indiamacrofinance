"""Sensex P/E and P/B from RBI Handbook Tables 244-245 (financial-year rows, month columns)."""
from pipelines.sources.rbi.handbook_valuation import parse_table


def test_valuation(raw_from):
    pe = {r["period"]: r["value"] for r in parse_table(raw_from("rbi/hbie_244.xlsx").content, "sensex_pe")}
    pb = {r["period"]: r["value"] for r in parse_table(raw_from("rbi/hbie_245.xlsx").content, "sensex_pb")}
    assert pe["2021-04-01"] == 33.5 and pe["2026-06-01"] == 20.47      # Apr of FY 2021-22; Jun 2026
    assert pb["2026-03-01"] == 4.08                                     # March belongs to the next calendar year
    assert "2026-07-01" not in pe                                       # "-" = not yet published
    assert len(pb) == 63
