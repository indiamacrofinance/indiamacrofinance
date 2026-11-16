"""RBI WSS parsers, pinned to the WSS published 23 Oct 2026."""
from pipelines.sources.rbi.wss import SOURCE, parse_date


def at(df, sid, period):
    return df[(df.series_id == sid) & (df.period == period)].value.item()


def test_wss(raw_from):
    raws = [raw_from(f"rbi/wss/2026-10-23.s{n}.xlsx") for n in (2, 3, 4)]
    df = SOURCE.parse(raws)
    assert at(df, "fx_reserves_total", "2026-10-16") == 721.016          # US$ bn
    assert at(df, "scb_credit", "2026-10-15") == 227.42777               # ₹ lakh crore
    assert at(df, "scb_credit_growth", "2026-10-15") == 18.2
    assert at(df, "repo_rate", "2026-10-16") == 5.5
    assert at(df, "repo_rate", "2026-09-18") == 5.25
    assert at(df, "wacr", "2026-10-16") == 5.56
    assert at(df, "gsec_10y_par_fbil", "2026-10-16") == 7.4
    assert at(df, "crr", "2025-10-17") == 3.5                            # year-earlier column
    assert not df.duplicated(["series_id", "period"]).any()


def test_parse_date():
    assert parse_date("As on October 16, 2026") == "2026-10-16"
    assert parse_date("Outstanding as on Oct. 15, 2026") == "2026-10-15"
    assert parse_date("Sep. 18", 2026) == "2026-09-18"
    assert parse_date("Sept. 18", 2026) == "2026-09-18"


def test_money_and_liquidity(raw_from):
    raws = [raw_from(f"rbi/wss/2026-10-23.s{n}.xlsx") for n in (7, 8, 25)]
    df = SOURCE.parse(raws)
    assert at(df, "m3", "2026-10-15") == 333.003                          # ₹ lakh crore
    assert at(df, "m3_growth", "2026-10-15") == 16.0                      # y/y %, last column
    assert at(df, "currency_public_growth", "2026-10-15") == 14.1
    assert at(df, "reserve_money", "2026-10-15") == 53.24881
    assert at(df, "reserve_money_growth", "2026-10-15") == 10.3
    # Net injection -134,268 crore = a surplus of 1.34 lakh crore (sign flipped).
    assert at(df, "liquidity_surplus", "2026-10-18") == 1.3427
    assert len(df[df.series_id == "liquidity_surplus"]) == 7


def test_older_layouts(raw_from):
    # "May 1" stored by Excel as 2015-05-01, with the year one row lower: keep month and day.
    df = SOURCE.parse([raw_from("rbi/wss/reserve_money_excel_date.xlsx")])
    assert at(df, "reserve_money", "2026-05-01") == 52.12071
    # Liquidity dates as text ("May 25, 2026") rather than Excel dates.
    df = SOURCE.parse([raw_from("rbi/wss/liquidity_text_dates.xlsx")])
    assert at(df, "liquidity_surplus", "2026-05-25") == 0.7632


def test_liquidity_footnote_dates_are_not_days(raw_from):
    # Issue #50: footnotes below older liquidity tables carry dates ("dated April 8, 2022";
    # "for the period December 16, 2019 to February 13, 2020"), which were read as days
    # with blank values and failed the whole series.
    for name, first, value in [("liquidity_footnote_dates_2022-05.xlsx", "2022-05-09", 2.0984),
                               ("liquidity_footnote_dates_2022-01.xlsx", "2022-01-24", -0.1919)]:
        df = SOURCE.parse([raw_from(f"rbi/wss/{name}")])
        liq = df[df.series_id == "liquidity_surplus"]
        assert len(liq) == 7 and liq.value.notna().all(), name
        assert liq.period.min() == first and at(df, "liquidity_surplus", first) == value
        assert not {"2022-04-08", "2019-12-16", "2021-05-07"} & set(liq.period)


def test_paper_rates():
    # CD / CP tables: fortnight, outstanding (Rs crore), amount issued, rate range on issues.
    import pandas as pd
    from pipelines.sources.rbi.wss import parse_paper
    df = pd.DataFrame([["Fortnight ended", "Outstanding", "Issued", "Rate (%)"],
                       ["Sep. 30, 2026", 574060, 41234, "5.77 - 7.33"],
                       ["Total", 574060, None, None]])
    rows = {r["series_id"]: r for r in parse_paper(df, "cd")}
    assert rows["cd_outstanding"] == {"series_id": "cd_outstanding", "period": "2026-09-30", "value": 5.7406}
    assert rows["cd_rate_low"]["value"] == 5.77 and rows["cd_rate_high"]["value"] == 7.33


def test_trickle_picks():
    from pipelines.sources.rbi.wss import link_date, trickle_picks
    base = "https://rbidocs.rbi.org.in/rdocs/Wss/DOCs/6T_{}AB.XLSX"
    links = [base.format(d) for d in ("30102026", "23102026", "16102026", "09102026", "02102026", "25092026", "18092026")]
    assert link_date(links[0]) == "2026-10-30"
    # Skip the 2 recent files; every 2nd file by position; 2 per run.
    assert [link_date(u) for u in trickle_picks(links, 2, None, 2, 2)] == ["2026-10-16", "2026-10-02"]
    # Next run resumes below the oldest attempted.
    assert [link_date(u) for u in trickle_picks(links, 2, "2026-10-02", 2, 2)] == ["2026-09-18"]


def test_link_dates_two_digit_years_and_rbi_typos():
    from pipelines.sources.rbi.wss import link_date, link_dates, trickle_picks
    base = "https://rbidocs.rbi.org.in/rdocs/Wss/DOCs/{}.XLSX"
    # Files up to mid-2018 carry a two-digit year, straight into a hex hash: the eight-digit
    # reading gave '1860-06-15' or failed outright (which crashed the whole source).
    assert link_date(base.format("8T_150618601C36F3D9E7")) == "2018-06-15"
    assert link_date(base.format("8T_2206186AD313A3749B")) == "2018-06-22"
    assert link_date(base.format("6T_14042019AB")) == "2019-04-14"
    assert link_date(base.format("11T_1600420215AEEB6C")) is None
    # RBI's real typos, in archive order (newest first): 9 Apr 2021 named '09032021'.
    names = ["2T_16042021BC", "2T_090320219C", "2T_02042021DD", "2T_26032021D0",
             "8T_150618601C", "2T_1600420215", "8T_080618C2C2"]
    links = [base.format(n) for n in names]
    eff = link_dates(links)
    assert eff == ["2021-04-16", "2021-04-15", "2021-04-02", "2021-03-26",
                   "2018-06-15", "2018-06-14", "2018-06-08"]
    # The backfill walks the whole list without errors or repeats.
    picks, ledger, seen = None, "2021-04-17", []
    while picks != []:
        picks = trickle_picks(links, 0, ledger, 1, 2)
        seen += picks
        ledger = eff[links.index(picks[-1])] if picks else ledger
    assert seen == links
