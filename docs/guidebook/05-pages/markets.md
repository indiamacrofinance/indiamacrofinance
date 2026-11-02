# Markets

**Purpose:** Where are Indian rates, equities, the rupee and commodities, and what moved today?

## Must include
- [x] Cross-asset table (as econvitals does): Latest, 1-day, 1-week, YTD for (partial: no 2y/5y/30y G-sec, sectoral indices or other currencies yet):
  - Rates: 91d T-bill, 2y, 5y, 10y, 30y G-sec, 2s10s slope (bp)
  - Equities: Nifty 50, Sensex, Nifty Bank, Nifty IT, Nifty Midcap 100, India VIX
  - FX: USD/INR (FBIL), EUR/INR, JPY/INR, GBP/INR, CNY/INR
  - Commodities: Brent ($ and ₹), gold (₹/10g), silver
- [x] "Markets updated" timestamp (IST) (the "As of" column)
- [x] G-sec yield curve: latest vs 1 month ago vs end of last FY (FBIL par yields, panel `gsec_par_yield`, from Jan 2025; `yield_curve.json`)
- [x] Chart: 10y G-sec vs repo rate (term spread) (`term_spread_10y_repo`, site calculation)
- [x] Valuation: Sensex P/E and P/B, monthly, from RBI's Handbook Tables 244-245 (BSE data, show-only; added 2026-11-01). Nifty P/E has no redistributable source.
- [x] FPI flows (equity and debt, monthly) from NSDL, from 2015. DII flows still missing: NSE blocks scripts
- [x] Mutual fund flows (AMFI monthly report, from Apr 2019: total, equity, debt, AUM). SIP inflows still missing: not in the workbook, and the AMFI SIP page returns 404
- [ ] Corporate bond spreads (AAA 5y over G-sec) if a free source exists
- [x] Footnote stating the source and closing time for each row

## Must NOT include
- Download buttons for NSE/BSE index data (licensed, show-only)
- Intraday "live" quotes (we are end-of-day only), except the rupee and Asian currencies, which feed the rupee page (`rupee.md`, since 2026-11-02)
- Stock tips, individual stocks, buy/sell language

## Series (planned)
nifty50_close, sensex_close, niftybank_close, niftyit_close, niftymid100_close, indiavix_close, gsec_2y_yield, gsec_5y_yield, gsec_10y_yield, gsec_30y_yield, usdinr_fbil, eurinr_fbil, gbpinr_fbil, jpyinr_fbil, brent_usd, gold_inr, fpi_equity_net, fpi_debt_net, dii_net, mf_sip_inflows

## Phase
1 (Nifty, Sensex, 10y, USD/INR, Brent, gold), 2 (page)
