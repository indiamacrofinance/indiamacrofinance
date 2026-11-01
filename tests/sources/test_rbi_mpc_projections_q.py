"""Quarter-by-quarter projections in MPC resolutions: wordings, recaps and outturns."""
import pytest

from pipelines.sources.rbi.mpc_projections_q import RETRO, SENTENCE, quarter_values


@pytest.mark.parametrize("sentence,want", [
    ("CPI inflation is projected to be 5.2 per cent for 2026-27 with Q2 at 4.9 per cent; Q3 at 6.0 per cent; and Q4 at 5.7 per cent",
     {"2026-27 Q2": 4.9, "2026-27 Q3": 6.0, "2026-27 Q4": 5.7}),
    ("real GDP growth for 2025-26 is projected at 6.7 per cent with Q1 at 6.7 per cent; Q2 at 7.0 per cent; and Q3 and Q4 at 6.5 per cent each",
     {"2025-26 Q1": 6.7, "2025-26 Q2": 7.0, "2025-26 Q3": 6.5, "2025-26 Q4": 6.5}),
    ("CPI inflation for Q1:2026-27 and Q2 are projected at 3.9 per cent and 4.0 per cent, respectively", {"2026-27 Q1": 3.9, "2026-27 Q2": 4.0}),
    ("CPI inflation for Q1:2025-26 is projected at 4.4 per cent", {"2025-26 Q1": 4.4}),
    ("CPI inflation is projected at 5.3 per cent during 2021-22: 5.1 per cent in Q2, 4.5 per cent in Q3; and 5.8 per cent in Q4",
     {"2021-22 Q2": 5.1, "2021-22 Q3": 4.5, "2021-22 Q4": 5.8}),
])
def test_wordings(sentence, want):
    assert quarter_values(sentence) == want


def test_recaps_and_paragraph_numbers():
    assert RETRO.search("Excluding the HRA impact, CPI inflation was projected at 3.7 per cent in Q2:2018-19")
    assert RETRO.search("The 6th bi-monthly resolution of 2017-18 in February projected CPI inflation at 5.1 per cent in Q4:2017-18")
    # A numbered paragraph must not glue a projection to the next paragraph's GDP outturn.
    text = ("CPI inflation is projected at 4.6 per cent in H1 and 4.7 per cent in H2. 21. Turning to the growth outlook, "
            "the CSO's provisional estimates have placed GDP growth for Q4:2017-18 at 7.7 per cent")
    projecting = [s for s in SENTENCE.split(text) if "project" in s]
    assert all(quarter_values(s) == {} for s in projecting)
