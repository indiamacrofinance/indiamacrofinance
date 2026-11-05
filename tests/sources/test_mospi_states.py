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


def test_keep_best_total_keeps_real_duplicates():
    # Repeated totals of lower rank are dropped; two rows of the same rank both stay, so the
    # store's validation reports the duplicate period instead of one being picked silently.
    import pandas as pd

    from pipelines.sources.mospi._api import keep_best_total
    df = pd.DataFrame([{"series_id": "a", "period": "2025-01-01", "value": 3.1, "rank": 0},
                       {"series_id": "a", "period": "2025-01-01", "value": 3.1, "rank": 1},
                       {"series_id": "b", "period": "2025-01-01", "value": 1.0, "rank": 0},
                       {"series_id": "b", "period": "2025-01-01", "value": 2.0, "rank": 0}])
    out = keep_best_total(df, ["series_id", "period"])
    assert list(out.value) == [3.1, 1.0, 2.0] and "rank" not in out
