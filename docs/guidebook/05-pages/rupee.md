# The rupee: what's moving it

**Purpose:** Every day, why did the rupee move? Split each move (day, week, month, quarter) into
its usual drivers, show what is left unexplained, and give the background a reader needs to
answer "why is the rupee falling / rising?" Added 2026-11-02 at the maintainer's request; the
morning newsletter is built on the same analysis.

## Must include
- [x] Latest close, today's live quote (time-stamped, IST), FBIL reference rate, weakest close in the data
- [x] Decomposition table: the rupee's % change and each driver's share, plus drift and "not explained", for the last day, week, month and three months
- [x] What the drivers did over the same periods, and whether each is used in the model
- [x] Weekly stacked bars of the decomposition (26 weeks)
- [x] Trend charts: USD/INR (1y, 10y), Brent, Nifty, yuan, DXY, US 10-year, weekly change in reserves
- [x] Background: daily and monthly FPI flows, reserves, India-US yield gap, REER, trade balance
- [x] Method and fit (share of daily, weekly, monthly moves explained), with the caveat that it is an attribution, not proof of cause

## Must NOT include
- Forecasts or trading calls on the rupee
- Downloads of Yahoo market data (show-only)

## Notes
- This page is the exception to "end-of-day only" on Markets: the rupee and the other currencies
  keep today's bar as a live quote, refreshed by the markets bot (hourly on weekdays).
- Method: pipelines/build/rupee.py and 08-original-measures.md ("Rupee drivers").

## Series
usdinr_close, usdcny_close, usdkrw_close, usdidr_close, dxy_close, us10y_yield, us_vix_close,
brent_usd, nifty50_close, fpi_daily_equity_usd, fpi_daily_debt_usd, fpi_daily_total_usd,
fx_reserves_total, gsec_10y_yield, reer_bis_broad, merch_trade_balance, usdinr_ref

## Phase
live
