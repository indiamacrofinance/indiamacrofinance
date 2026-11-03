"""RBI balance of payments releases: three quarterly layouts and the monthly table."""
from pipelines.sources.rbi.bop import SOURCE, quarter_start


def at(df, sid, period):
    return df[(df.series_id == sid) & (df.period == period)].value.item()


def test_bop_layouts(raw_from):
    names = ["q1_2026-27", "q4_split_header", "q2_en_dash", "monthly_2026-07"]
    df = SOURCE.parse([raw_from(f"rbi/bop/{n}.html") for n in names])
    assert at(df, "bop_current_account", "2026-04-01") == -4.2       # Q1 FY27, US$ bn
    assert at(df, "bop_cab_pct_gdp", "2026-04-01") == -0.5           # deficit -> negative
    assert at(df, "bop_portfolio_net", "2026-04-01") == -9.6
    assert at(df, "bop_current_account", "2026-01-01") == 7.1        # Q4 FY26 surplus
    assert at(df, "bop_cab_pct_gdp", "2026-01-01") == 0.7
    assert at(df, "bop_current_account", "2025-07-01") == -12.3      # en-dash headers
    assert at(df, "bop_cab_monthly", "2026-07-01") == -7.0
    assert not df.duplicated(["series_id", "period"]).any()


def test_quarter_start():
    assert quarter_start("April-June 2026") == "2026-04-01"
    assert quarter_start("July – September 2025") == "2025-07-01"


def test_recent_window_spans_a_quarterly_release():
    # Quarterly releases are ~3 months apart; a 2-month window held only a monthly
    # release on 2026-11-02 and every quarterly series failed with no rows (#17).
    from pipelines.sources.rbi.bop import RECENT_MONTHS
    assert RECENT_MONTHS >= 4
