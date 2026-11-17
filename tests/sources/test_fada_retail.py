"""FADA vehicle retail parser, pinned to the July 2025, September 2026 and October 2026 releases."""
from pipelines.sources.fada.retail import SOURCE, parse_release, release_links


def at(df, sid, period):
    return df[(df.series_id == sid) & (df.period == period)].value.item()


def test_release_table(raw_from):
    rows = parse_release(raw_from("fada/2026-09.pdf").content)
    got = {(r["series_id"], r["period"]): r["value"] for r in rows}
    assert got[("vehicle_retail_total", "2026-09-01")] == 2536.92            # thousand units
    assert got[("vehicle_retail_2w", "2025-09-01")] == 1345.153              # year-ago column
    assert got[("vehicle_retail_tractor_growth", "2026-09-01")] == 13.75
    assert ("vehicle_retail_cv", "2026-08-01") in got                       # previous-month column


def test_full_month_names_and_newest_wins(raw_from):
    # "July'25" headers; the Sep 2026 release restates Sep 2025 (1,924,546 vs its own 1,827,340).
    df = SOURCE.parse([raw_from("fada/2025-07.pdf"), raw_from("fada/2026-09.pdf")])
    assert at(df, "vehicle_retail_total", "2025-07-01") == 1964.213
    assert at(df, "vehicle_retail_total_growth", "2025-07-01") == -4.31
    assert at(df, "vehicle_retail_total", "2025-09-01") == 1924.546
    assert not df.duplicated(["series_id", "period"]).any()


def test_october_2026_release_festive_table_first(raw_from):
    # From Oct 2026 the release opens with "All India Vehicle Retail Data for Navratri'26";
    # the month's table comes after it, and was missed (status page: 12 series overdue).
    rows = parse_release(raw_from("fada/2026-10.pdf").content)
    got = {(r["series_id"], r["period"]): r["value"] for r in rows}
    assert got[("vehicle_retail_2w", "2026-10-01")] == 2321.419
    assert got[("vehicle_retail_2w_growth", "2026-10-01")] == -28.35
    assert got[("vehicle_retail_pv", "2025-10-01")] == 592.032              # restated year-ago
    assert got[("vehicle_retail_total", "2026-10-01")] == 3172.466
    assert got[("vehicle_retail_total_growth", "2026-10-01")] == -23.8
    assert {p for _, p in got} == {"2026-10-01", "2026-09-01", "2025-10-01"}


def test_release_links_new_file_names():
    page = "".join(f'<a href="images/press-release/{n}">x</a>' for n in (
        "16aed49cca8e14FADA_Press_Release_Oct_26.pdf",
        "16ad896132aebfFADA_Press_Release_Navratri'26_(Provisional).pdf",
        "16acf397616dd9FADA_Press_Release_Agra Training Centre.pdf",
        "16ac46ad2e0388FADA Releases September 2026 Vehicle Retail Data.pdf"))
    assert [u.rsplit("/", 1)[-1] for u in release_links(page)] == [
        "16aed49cca8e14FADA_Press_Release_Oct_26.pdf",
        "16ac46ad2e0388FADA%20Releases%20September%202026%20Vehicle%20Retail%20Data.pdf"]
