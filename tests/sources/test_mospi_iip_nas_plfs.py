"""IIP, national accounts and PLFS parsers, pinned to values MoSPI published (API, 2026-10-28)."""
import pandas as pd

from pipelines.sources.mospi.iip import SOURCE as IIP
from pipelines.sources.mospi.nas import SOURCE as NAS
from pipelines.sources.mospi.nas import quarter_period
from pipelines.sources.mospi.plfs import SOURCE as PLFS


def at(df, sid, period):
    row = df[(df.series_id == sid) & (df.period == period)]
    assert len(row) == 1, (sid, period, len(row))
    return row.iloc[0]


def test_iip(raw_from):
    df = IIP.parse([raw_from("mospi/iip/sample.json")])
    assert at(df, "iip_general_index", "2026-09-01").value == 124.3
    assert at(df, "iip_general_growth", "2026-09-01").value == 6.7
    assert "2022-23" in at(df, "iip_general_growth", "2026-09-01").note
    assert at(df, "iip_capital_goods_index", "2026-09-01").value == 153.4
    assert not df.duplicated(["series_id", "period"]).any()


def test_nas(raw_from):
    df = NAS.parse([raw_from("mospi/nas/sample.json")])
    assert at(df, "gdp_real_growth", "2026-04-01").value == 7.8
    assert at(df, "gdp_nominal_growth", "2026-04-01").value == 10.3
    assert at(df, "gva_real_growth", "2026-04-01").value == 8.2
    assert at(df, "gva_mfg_growth", "2026-04-01").value == 9.2
    assert round(at(df, "gdp_real_level", "2026-04-01").value, 5) == 81.36153  # ₹ lakh crore
    assert not df.duplicated(["series_id", "period"]).any()


def test_quarter_period():
    assert quarter_period("2026-27", "Q1") == "2026-04-01"
    assert quarter_period("2026-27", "Q3") == "2026-10-01"
    assert quarter_period("2025-26", "Q4") == "2026-01-01"


def test_plfs(raw_from):
    df = PLFS.parse([raw_from("mospi/plfs/sample.json")])
    assert at(df, "plfs_ur_monthly", "2026-09-01").value == 5.0
    assert at(df, "plfs_ur_youth_monthly", "2026-09-01").value == 15.2
    assert at(df, "plfs_lfpr_female_monthly", "2026-09-01").value == 34.6


def test_plfs_annual_period():
    from pipelines.sources.mospi.plfs import annual_period
    assert annual_period("2023-24", "Agriculture Year") == "2023-07-01"
    assert annual_period("2025", "Calendar Year") == "2025-01-01"


def test_plfs_annual_both_layouts(raw_from):
    # MoSPI changed the calendar-year tables on 2026-11-04: years read "PLFS 2024" and the
    # all-India total repeats once per breakdown with the category fields left empty.
    old = PLFS.parse([raw_from("mospi/plfs/annual_ur_ay_2026-11-04.json"),
                      raw_from("mospi/plfs/annual_ur_cy_2026-11-04.json")])
    new = PLFS.parse([raw_from("mospi/plfs/annual_ur_cy_2026-11-05.json")])
    assert at(old, "plfs_ur_usual_ay", "2023-07-01").value == 3.2
    for df in (old, new):
        assert at(df, "plfs_ur_usual_cy", "2022-01-01").value == 3.6
        assert at(df, "plfs_ur_usual_cy", "2025-01-01").value == 3.1
        assert at(df, "plfs_ur_usual_cy", "2025-01-01").note == "usual status (PS+SS), calendar year 2025"
    cols = ["series_id", "period", "value", "note"]
    pd.testing.assert_frame_equal(old[old.series_id == "plfs_ur_usual_cy"][cols].reset_index(drop=True),
                                  new[cols].reset_index(drop=True))


def test_plfs_year():
    from pipelines.sources.mospi._api import plfs_year
    assert plfs_year("PLFS 2024") == "2024"
    assert plfs_year("2024") == "2024"
    assert plfs_year("2023-24") == "2023-24"


def test_pages_no_data(monkeypatch, raw_from):
    # "No Data Found" (no meta_data) is a clear error, not a KeyError and not a silent empty result.
    import pytest

    from pipelines.sources.mospi import _api
    monkeypatch.setattr(_api, "fetch_raw", lambda url, params: raw_from("mospi/plfs/annual_ur_cy_nodata_2026-11-05.json"))
    with pytest.raises(RuntimeError, match="No Data Found"):
        _api.pages("plfs/getData", {})


def test_plfs_total_rank():
    from pipelines.sources.mospi._api import plfs_total_rank
    row = lambda rel, soc, edu: {"religion": rel, "socialGroup": soc, "General_Education": edu}
    assert plfs_total_rank(row("all", "all", "all")) == 0        # old layout
    assert plfs_total_rank(row("all", None, None)) == 0          # new layout, religion cut
    assert plfs_total_rank(row(None, None, None)) == 1           # new layout, uncut (state rows)
    assert plfs_total_rank(row(None, "all", None)) is None       # social-group cut: a duplicate total
    assert plfs_total_rank(row("Hinduism", None, None)) is None
    assert plfs_total_rank(row("all", "scheduled caste", "all")) is None


def test_plfs_year_edge_cases():
    from pipelines.sources.mospi._api import plfs_year
    assert plfs_year("PLFS 2023-2024") == "2023"
