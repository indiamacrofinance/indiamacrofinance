"""MoSPI state panels: PLFS calendar-year tables before and after MoSPI's 2026-11-04 change."""
from pipelines.sources.mospi.states import SOURCE as STATES


def ur(df):
    return df[df.series_id == "state_ur_cy"].set_index(["entity", "period"])["value"].sort_index()


def test_state_plfs_both_layouts(raw_from):
    old = STATES.parse([raw_from("mospi/states/plfs_ur_cy_p1_2026-11-04.json"),
                        raw_from("mospi/states/plfs_ur_cy_p2_2026-11-04.json")])
    new = STATES.parse([raw_from("mospi/states/plfs_ur_cy_p1_2026-11-05.json"),
                        raw_from("mospi/states/plfs_ur_cy_p2_2026-11-05.json")])
    for df in (old, new):
        assert ur(df)[("Kerala", "2022-01-01")] == 8.1
        assert ur(df)[("Kerala", "2025-01-01")] == 4.4
        assert ur(df)[("Bihar", "2023-01-01")] == 3.0
        assert not df.duplicated(["series_id", "entity", "period"]).any()
        assert "All India" not in set(df.entity)
    assert ur(old).equals(ur(new))


def test_empty_parse_is_empty():
    # No rows must reach run.py's "parser returned no rows" check, not fail on the duplicate guard.
    from pipelines.sources.mospi.plfs import SOURCE as PLFS
    assert PLFS.parse([]).empty
    assert STATES.parse([]).empty
