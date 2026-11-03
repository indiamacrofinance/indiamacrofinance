# Money & banking

**Purpose:** What is the RBI's policy stance, how tight is liquidity, and how fast are credit and deposits growing?

## Must include
- [x] Real policy rate: repo rate at month end minus CPI inflation (`real_repo_rate`, `derived/real_rate.py`, from Sep 2022), with the repo rate and CPI alongside (`#real-rate`)
- [x] Policy corridor chart: repo, SDF, MSF, with WACR overlaid (weekly from WSS; daily snapshots since 28 Oct 2026)
- [x] Table of MPC decisions: date, decision, vote split, stance wording (from the resolution in the minutes; `mpc_repo_decision`, built into `mpc_decisions.json`). Size splits ("1 member voted for 25 bp") are shown where the minutes record them
- [x] Next MPC date and countdown (from `registry/calendar/rbi.yaml`; the countdown is fixed at build time)
- [x] Net liquidity (₹ lakh crore, + = surplus), daily, from WSS table 8 (`liquidity_surplus`; RBI's sign flipped). It covers all RBI operations, not LAF alone
- [x] CRR and SLR with change dates
- [x] Scheduled commercial bank credit and deposit growth y/y (fortnightly), plus the credit–deposit ratio (site calculation)
- [x] Sectoral deployment of credit (monthly): industry, services, personal loans, agriculture (`rbi/sectoral_credit.py`, growth as published)
- [x] Money supply M3 growth, reserve money (WSS tables 6 and 7, fortnightly)
- [x] T-bill yields (91d, 182d, 364d) plus CP and CD rate ranges and amounts outstanding (WSS tables 10–11, from Aug 2025)

## Must NOT include
- Fed-style "market-implied path" unless we have a free, redistributable OIS source (we probably don't; leave it out)
- Bank-level data (out of scope)

## Series (planned)
repo_rate, sdf_rate, msf_rate, wacr, liquidity_surplus, mpc_repo_decision, crr, slr, scb_credit, scb_deposits, credit_<sector>, m3, m3_growth, currency_public_growth, reserve_money, reserve_money_growth, tbill_91d, tbill_182d, tbill_364d

## Phase
1 (repo, WACR, credit), 2 (page)
- [x] Transmission to lending and deposit rates by policy cycle (RBI MPR Table II.7; matches RBI), WALR/WADTDR by bank group and sector, loan benchmark shares (2026-11-01)
- [x] Credit-deposit gap; contributions to credit growth by sector, firm size, services and personal-loan type (2026-11-01)
- [x] RBI's outlook: MPR assumptions, projections and risk scenarios (registry/mpr/, hand-entered twice a year)
- [ ] Liquidity drivers (MPR Table II.1). Deferred 2026-11-01: the largest driver, RBI's net forex purchases, is published monthly in the Bulletin with a two-month lag; weekly RBI forex assets include revaluation, so they cannot stand in. A table without it would mislead.
