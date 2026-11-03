# Analysis

**Purpose:** Longer, original pieces that go beyond one indicator: a question, the official data
that answer it, how the answer was computed, and a page that recomputes itself when new data are
released. Added 2026-11-03 at the maintainer's request. Pages live under `/analysis/`; the hub is
`/analysis/` (site/src/pages/analysis/index.astro). How to add one: `playbooks/add-analysis.md`.

## Analysis 1: Forex intervention and the balance of payments

Based on Vedant Agarwal, Nirupama Kulkarni and Gautham Udupa (CAFRAL), "Forex Interventions and
Balance of Payments", June 2026; credited at the top of each page and under each table and figure
that follows it (Tables 1-4, Figures 1-3). Two pages built from one analysis (`pipelines/build/bop_stress.py` → `bop_stress.json`; method in
`08-original-measures.md`, "BoP stress episodes and forex intervention"; episodes in
`registry/analysis/bop_stress_episodes.yaml`).

### /analysis/bop-stress/ "Balance-of-payments stress: then and now"
- [x] Tiles: current episode's current account, capital and financial accounts, reserves drawn down, rupee fall
- [x] **Components of BoP flows in stress episodes** (the centre of the page; `#episodes`): goods and services, primary income, secondary income, current account; direct investment split into FDI into India and ODI; FPI; financial derivatives; other investment; capital and financial accounts; reserves drawn down; rupee fall. Current episode, 2022, 2018, 2013. Totals, with a per-quarter toggle
- [x] "What sets the current episode apart": six findings, every number computed from the JSON (no typed numbers)
- [x] Open-episode note: whether the current episode was extended or stopped by the latest quarter, and why
- [x] **Who financed the gap** (`#totals`): current account, capital and financial accounts, of which bank capital (BPM5), reserves drawn down, errors and omissions
- [x] **Build your own episode** (`#custom`): any run of quarters, same rows, computed in the browser, next to the four episodes
- [x] **Derivative-related outflows** (`#derivatives`): banking capital vs net derivatives with episodes shaded; gross receipts and payments; the BPM6 table of which derivative flows land in this line (IMF BPM6)
- [x] **Latest quarters** (`#monitor`): last 12 quarters with the episode rule (weaker rupee and net dollar sales)
- [x] **How this is built** (`#method`): data, episode rule, identity checks, limits, links to every input series

### /analysis/fx-intervention/ "Where RBI's dollar sales show up in the BoP"
- [x] **A dollar sale, step by step** (`#mechanics`): the three steps and the net BoP entries of a $1 sale
- [x] **What the data show** (`#evidence`): banking capital, current account and financial account against RBI's net dollar sales, same quarter, from 2000-01:Q1; slope, robust s.e., R², N; current episode highlighted
- [x] **How much stability a dollar buys** (`#model`): the BoP identity, ∂e/∂FXI = −1/(∂FA/∂e + ∂CA/∂e), and an interactive linear model (reader sets both slopes, a shift in financial flows, e* and the target)
- [x] **What public data cannot tell us** (`#limits`)

## Must NOT include
- Quotes from, links to, or the circulation of private reference material an analysis replicates (decision 0006). Credit the authors and institution instead, and say the numbers are our own computation of public data
- Facts from outside our series and official releases presented as findings (AGENTS.md rule 5). Published estimates used as model *assumptions* are fine if cited and labelled as such (e.g. the starting slopes of the intervention model)
- Forecasts of the rupee or of RBI's intervention
- Typed numbers in prose: every number comes from the generated JSON

## Series
bop_bpm6_current_account, bop_bpm6_goods_services, bop_bpm6_primary_income, bop_bpm6_secondary_income,
bop_bpm6_capital_account, bop_bpm6_fdi_in_india, bop_bpm6_odi, bop_bpm6_portfolio, bop_bpm6_derivatives,
bop_bpm6_derivatives_receipts, bop_bpm6_derivatives_payments, bop_bpm6_other_investment,
bop_bpm6_reserve_assets, bop_bpm6_errors_omissions, bop_bpm5_current_account, bop_bpm5_capital_account,
bop_bpm5_banking_capital, bop_bpm5_bank_assets, bop_bpm5_nri_deposits, bop_bpm5_errors_omissions,
bop_bpm5_reserves_change, rbi_fx_purchases, rbi_fx_sales, rbi_fx_net_purchase, rbi_fx_forward_book,
usdinr_monthly_avg, usdinr_ref

## Done when
- The 2013, 2018 and 2022 episode totals equal the values pinned in `tests/test_bop_stress.py`
- Both pages render at 1280 px and 375 px without console errors; charts show the episode shading
- After a quarterly BoP release, the pages show the new quarter without code changes (see `playbooks/release-day.md`, BoP)

## Phase
live (4: originals)
