"""Yahoo source: only final daily bars are kept."""
import json
from datetime import datetime, timezone

from pipelines.core import Raw
from pipelines.sources.yahoo.markets import SOURCE


def raw(ticker, rows, fetched_utc):
    body = json.dumps({"ticker": ticker, "period": "1mo", "rows": rows}).encode()
    return Raw(body, f"yfinance:{ticker}", fetched_utc, "x", ".json")


def test_today_bar_rules():
    # 2026-10-28 11:00 UTC = 16:30 IST: Indian close is final; futures are still trading.
    t = datetime(2026, 10, 28, 11, 0, tzinfo=timezone.utc)
    rows = [["2026-10-27", 100.123], ["2026-10-28", 101.0]]
    df = SOURCE.parse([raw("^NSEI", rows, t), raw("BZ=F", rows, t)])
    assert set(df[df.series_id == "nifty50_close"].period) == {"2026-10-27", "2026-10-28"}
    assert set(df[df.series_id == "brent_usd"].period) == {"2026-10-27"}
    assert df[df.period == "2026-10-27"].value.iloc[0] == 100.12


def test_before_indian_close():
    t = datetime(2026, 10, 28, 6, 0, tzinfo=timezone.utc)  # 11:30 IST, market open
    df = SOURCE.parse([raw("^NSEI", [["2026-10-27", 1.0], ["2026-10-28", 2.0]], t)])
    assert list(df.period) == ["2026-10-27"]


def fx_raw(rows, hourly, ecb, fetched_utc):
    body = json.dumps({"ticker": "IDR=X", "period": "1mo", "rows": rows,
                       "hourly_last": hourly, "ecb": ecb}).encode()
    return Raw(body, "yfinance:IDR=X", fetched_utc, "x", ".json")


def test_fx_picks_the_candidate_nearer_the_ecb_rate():
    t = datetime(2026, 11, 6, 6, 0, tzinfo=timezone.utc)  # 11:30 IST
    rows = [["2026-10-16", 18020.1], ["2026-11-02", 18113.9], ["2026-11-03", 17472.2], ["2026-11-06", 18132.0]]
    hourly = [["2026-10-16", 17943.0], ["2026-11-03", 18148.0], ["2026-11-06", 18130.0]]
    ecb = {"2026-10-16": 18031.0, "2026-11-03": 18136.7}
    df = SOURCE.parse([fx_raw(rows, hourly, ecb, t)]).set_index("period")
    # 3 Nov: Yahoo's daily close was a bad tick ~3.5% below every hourly price.
    assert df.loc["2026-11-03", "value"] == 18148.0
    assert df.loc["2026-11-03", "note"].startswith("Yahoo Finance, last hourly price")
    # 16 Oct: the hourly bars were frozen at 17,943; the close is nearer the ECB rate.
    assert df.loc["2026-10-16", "value"] == 18020.1
    assert df.loc["2026-10-16", "note"] == "Yahoo Finance close"
    # No ECB rate (2 Nov here; today, before the ECB publishes): the daily close, as before.
    assert df.loc["2026-11-02", "value"] == 18113.9
    assert df.loc["2026-11-06", "value"] == 18132.0
    assert df.loc["2026-11-06", "note"].startswith("Yahoo Finance, live quote at 11:30")


def test_fx_ecb_guard_leaves_out_far_values():
    t = datetime(2026, 11, 6, 6, 0, tzinfo=timezone.utc)
    rows = [["2026-11-04", 17536.1], ["2026-11-05", 17509.2]]
    hourly = [["2026-11-04", 18140.0], ["2026-11-05", 17509.2]]   # 5 Nov: both candidates bad
    ecb = {"2026-11-04": 18129.0, "2026-11-05": 18069.0}
    df = SOURCE.parse([fx_raw(rows, hourly, ecb, t)])
    assert list(df.period) == ["2026-11-04"]    # 5 Nov is 3.1% from the ECB rate: left out
    assert df.value.iloc[0] == 18140.0
