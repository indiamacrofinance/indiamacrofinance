"""Daily closes from Yahoo Finance (via the yfinance library): Indian indices, commodities,
currencies and the US markets that move the rupee (the rupee page, pipelines/analysis/rupee.py).

Licence: show-only. Exchange index data and futures prices are shown with attribution,
never offered for download (AGENTS.md hard rule 6). Yahoo closes for the Nifty 50 and
Sensex were checked equal to the closes RBI republishes (27 Oct 2026), so this source
and pipelines/sources/rbi/home_rates.py can both write those series.

Backfills BACKFILL of history when a series is short, otherwise fetches RECENT.
Today's bar is used only when it is final: Indian indices after 16:00 IST; never for
commodity futures, which trade almost round the clock (yesterday's settle is used), or for
US markets (their day ends after midnight IST). Currencies ("fx") keep today's bar as a live
quote: Yahoo's FX day runs 05:30-05:30 IST, so it is rewritten on each run until it closes,
and pipelines/analysis/rupee.py explains only completed days.

Yahoo's FX prices carry bad ticks, in the daily close and in hourly bars alike: USD/IDR
closed ~3.5% below every hourly price on 3-5 Nov 2026 (below the bar's own low on 3-4 Nov);
USD/INR's close on 12 Oct 2026 was 1% off; IDR's hourly bars froze at 17,943 for 16-20 Oct
(issue #32). So for currencies each day has two Yahoo candidates, the daily close and the
day's last hourly price, and the ECB reference rate (official, 14:15 CET) referees: the
candidate nearer to it is stored. The stored value is always a price Yahoo reported. With
no ECB rate (TARGET holidays, or the ECB API is down) the daily close is kept, as before.
Hourly bars go back 730 days. Guard: a value still more than ECB_TOLERANCE % from the ECB
rate is left out of the run (any stored value stays) and printed.
"""
from __future__ import annotations

import hashlib
import io
import json
import warnings
from datetime import datetime, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

import pandas as pd

from pipelines.core import Raw, Source, http
from pipelines.core.store import load_series

TICKERS = {
    "^NSEI": ("nifty50_close", "index"), "^BSESN": ("sensex_close", "index"),
    "^INDIAVIX": ("indiavix_close", "index"),
    "BZ=F": ("brent_usd", "commodity"), "GC=F": ("gold_usd_oz", "commodity"),
    "INR=X": ("usdinr_close", "fx"), "CNY=X": ("usdcny_close", "fx"),
    "KRW=X": ("usdkrw_close", "fx"), "IDR=X": ("usdidr_close", "fx"),
    "DX-Y.NYB": ("dxy_close", "us"), "^TNX": ("us10y_yield", "us"), "^VIX": ("us_vix_close", "us"),
}
DECIMALS = {"fx": 4, "us": 3}
BACKFILL, RECENT, MIN_HISTORY = "10y", "1mo", 100
HOURLY_MAX = "730d"     # the longest history Yahoo serves for hourly bars
ECB_TOLERANCE = 3.0     # %; the nearer candidate was within 1% of the ECB rate every day, Aug-Nov 2026
ECB_URL = "https://data-api.ecb.europa.eu/service/data/EXR/D.{ccy}.EUR.SP00.A"
IST = ZoneInfo("Asia/Kolkata")


def hourly_period(period: str) -> str:
    """Yahoo serves hourly bars for at most 730 days."""
    return period if period in ("1mo", "3mo", "6mo", "1y") else HOURLY_MAX


@lru_cache
def ecb_per_euro(ccy: str, start: str) -> pd.Series:
    """ECB reference rate, units of `ccy` per euro by day."""
    r = http.get(ECB_URL.format(ccy=ccy), params={"startPeriod": start, "format": "csvdata"})
    return pd.read_csv(io.StringIO(r.text)).set_index("TIME_PERIOD")["OBS_VALUE"]


def ecb_usd_rates(ccy: str, start: str) -> dict[str, float]:
    """ECB reference rate, units of `ccy` per US$ by day (crossed through the euro)."""
    return (ecb_per_euro(ccy, start) / ecb_per_euro("USD", start)).dropna().round(6).to_dict()


class YahooMarkets(Source):
    name = "yahoo_markets"
    series_ids = tuple(sid for sid, _ in TICKERS.values())

    def fetch(self) -> list[Raw]:
        import yfinance as yf  # imported lazily: heavy, and only this source needs it

        raws = []
        for ticker, (sid, kind) in TICKERS.items():
            period = BACKFILL if len(load_series(sid)) < MIN_HISTORY else RECENT
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                hist = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=False)
            if hist.empty:
                raise RuntimeError(f"Yahoo returned no data for {ticker}")
            rows = [[i.strftime("%Y-%m-%d"), float(c)] for i, c in hist["Close"].dropna().items()]
            body = {"ticker": ticker, "period": period, "rows": rows}
            if kind == "fx":
                body |= self._fx_checks(yf, ticker, period, rows[0][0])
            content = json.dumps(body).encode()
            raws.append(Raw(content=content, url=f"yfinance:{ticker}?period={period}",
                            fetched_at=datetime.now(timezone.utc),
                            sha256=hashlib.sha256(content).hexdigest(), suffix=".json"))
        return raws

    @staticmethod
    def _fx_checks(yf, ticker: str, period: str, start: str) -> dict:
        """For each day: the last hourly price, and the ECB reference rate (units per US$)."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            h = yf.Ticker(ticker).history(period=hourly_period(period), interval="60m",
                                          auto_adjust=False)["Close"].dropna()
        # Bars are in the exchange's time zone, which is also how Yahoo dates its daily bars.
        last = h.groupby(h.index.strftime("%Y-%m-%d")).last()
        try:
            ecb = ecb_usd_rates(ticker.removesuffix("=X"), start)
        except Exception as e:  # noqa: BLE001 - the guard is optional; Yahoo data still flows
            print(f"  NOTE {ticker}: ECB reference rates unavailable, guard skipped ({e})")
            ecb = {}
        return {"hourly_last": [[d, float(v)] for d, v in last.items()], "ecb": ecb}

    def parse(self, raws: list[Raw]) -> pd.DataFrame:
        now_ist = raws[0].fetched_at.astimezone(IST) if raws else datetime.now(IST)
        today = now_ist.date().isoformat()
        out = []
        for raw in raws:
            body = json.loads(raw.content)
            sid, kind = TICKERS[body["ticker"]]
            dec = DECIMALS.get(kind, 2)
            if kind == "fx":
                out += self._fx_rows(sid, body, today, now_ist, dec)
                continue
            final_today = kind == "index" and now_ist.hour >= 16
            out += [{"series_id": sid, "period": d, "value": round(v, dec), "note": "Yahoo Finance close"}
                    for d, v in body["rows"] if d < today or (d == today and final_today)]
        return pd.DataFrame(out)

    @staticmethod
    def _fx_rows(sid: str, body: dict, today: str, now_ist: datetime, dec: int) -> list[dict]:
        hourly = dict(body.get("hourly_last", []))
        ecb = body.get("ecb", {})
        out = []
        for d, close in body["rows"]:
            if d > today:
                continue
            value, note = close, "Yahoo Finance close"
            ref = ecb.get(d)
            if ref and d in hourly and abs(hourly[d] - ref) < abs(close - ref):
                value, note = hourly[d], "Yahoo Finance, last hourly price (nearer the ECB rate)"
            if d == today:
                note = f"Yahoo Finance, live quote at {now_ist:%H:%M} IST"
            if ref and abs(value / ref - 1) * 100 > ECB_TOLERANCE:
                print(f"  NOTE {sid} {d}: Yahoo {value:.4f} is {abs(value / ref - 1) * 100:.1f}% from "
                      f"the ECB reference rate {ref:.4f}; left out of this run")
                continue
            out.append({"series_id": sid, "period": d, "value": round(value, dec), "note": note})
        return out


SOURCE = YahooMarkets()
