"""The live status dashboard's map (pipelines/build/status_map.py)."""
import pandas as pd
import yaml

from pipelines.build import site_data, status_map
from pipelines.core import registry


def test_short_agency():
    f = status_map.short_agency
    assert f("Reserve Bank of India") == "RBI"
    assert f("Grid Controller of India (Grid-India)") == "Grid-India"
    assert f("FBIL (via RBI home page and fbil.org.in)") == "FBIL"
    assert f("MoSPI (NSO)") == "MoSPI"
    assert f("Department of Commerce, Ministry of Commerce & Industry") == "Commerce"
    assert f("BSE Ltd., via Reserve Bank of India") == "BSE / RBI"


def test_map_covers_every_bot_source():
    specs = registry.all_series()
    today = pd.Timestamp("2026-11-03")
    rows = [site_data.health(spec, None, {}, today) for spec in specs.values()]
    cal = [{"date": "2026-11-12", "time_ist": "16:00", "publisher": "MoSPI", "title": "CPI", "period": "Oct 2026",
            "status": "upcoming"}, {"date": "2026-10-01", "publisher": "RBI", "title": "old", "status": "released"}]
    m = status_map.build(specs, rows, cal, None)
    bots = yaml.safe_load((status_map.store.ROOT / "registry" / "bots.yaml").read_text())["bots"]
    assert [b["name"] for b in m["bots"]] == list(bots)
    for b in m["bots"]:
        assert [s["name"] for s in b["sources"]] == bots[b["name"]]["sources"]
        assert b["workflow"] == f"bot-{b['name']}.yml"
        assert all(s["agency"] for s in b["sources"])
    assert m["totals"]["series"] == sum(1 for s in specs.values() if not s.get("discontinued"))
    assert [c["title"] for c in m["upcoming"]] == ["CPI"]
