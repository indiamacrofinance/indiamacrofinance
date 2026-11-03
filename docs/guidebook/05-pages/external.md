# External sector

**Purpose:** How are trade, the current account, capital flows, reserves and the rupee doing?

## Must include
- [x] Monthly merchandise exports, imports and trade balance (US$ bn, y/y), oil vs non-oil, gold imports
- [x] Services exports and imports (monthly, RBI actuals, not the Commerce projection)
- [x] Current account balance (quarterly, US$ bn and % GDP; monthly since 2026)
- [x] FX reserves (weekly) (import cover needs monthly imports)
- [x] REER and NEER: BIS broad indices (64 economies, 2020 = 100) as `reer_bis_broad`, `neer_bis_broad`. RBI's 40-currency Bulletin tables have no stable links (the archive form returns unrelated tables); switch if that changes
- [x] Net FDI, FPI flows, ECB registrations (`rbi/ecb.py`, monthly from Mar 2024)
- [x] Remittances: gross personal transfer receipts from the release text (`bop_remittances`, from Q3 2023-24); net secondary income stays in the BoP table
- [x] Chart: USD/INR with RBI reserve changes (weekly change bars, `reserves_change.json`)
- [x] External debt, US$ bn and % of GDP (`external_debt`, `external_debt_pct_gdp`; only the end-March and end-June releases are in RBI's index)

- [x] ECB drawdowns, repayments and net flow, quarterly from 2000 (`bop_bpm5_ecb_drawdowns`, `bop_bpm5_ecb_repayments`, `bop_bpm5_commercial_borrowings`: the BPM5 "Commercial borrowings (MT&LT)" line in `rbi/bop_quarterly.py`). Jan-Mar 2025 gross flows are as RBI last printed them, about three times normal (see the series notes)
- [x] NRI deposits, net quarterly flow from 2000 (`bop_bpm5_nri_deposits`)
- [x] Import cover of reserves: RBI's annual measure from 1987-88 (`reserves_import_cover`, Handbook Table 241) and a monthly site calculation (`import_cover_months`: month-end reserves ÷ average monthly goods imports, last 12 months; `derived/import_cover.py`)
- [x] Pointer from the BoP section to the Analysis pages on stress episodes and forex intervention (`analysis.md`); their full-history BoP series (`bop_bpm6_*`, `bop_bpm5_*`) live there

## Must NOT include
- Trade data in ₹ unless labelled (the default is US$)
- Commerce Ministry preliminary numbers presented as BoP numbers (they differ; label them)

## Series (planned)
merch_exports, merch_imports, merch_trade_balance, oil_imports, gold_imports, services_exports, services_imports, cab_quarterly, fx_reserves_total, reer_40, neer_40, fdi_net, fpi_net, ecb_net, remittances

## Phase
1 (trade, reserves), 2 (page)
