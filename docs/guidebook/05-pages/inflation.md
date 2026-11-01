# Inflation

**Purpose:** Is inflation close to RBI's 4% target, what is driving it, and what is the underlying trend?

## Must include
- [x] Table: CPI headline, food and beverages, fuel (RBI definition), core (Original), rural, urban (housing still to add). Columns: 1-month, 3-month avg y/y, 12-month y/y, and m/m momentum
- [x] Chart: CPI headline and core y/y, with the 4% target line and the shaded 2–6% band
- [x] Chart: contributions to headline CPI by group (weights from the 2024 base)
- [x] Chart: momentum vs base effect decomposition of the change in y/y inflation (Original; method in 08-original-measures.md)
- [x] WPI headline, WPI food, WPI manufactured products
- [x] CPI-IW (Labour Bureau; history builds from monthly press notes)
- [x] RBI household inflation expectations (3-month and 1-year ahead, plus current perception)
- [x] RBI's CPI projections (each MPC, from 2023-24) vs outturn (`mpc_cpi_projection`, `rbi_projections.json`)
- [x] Food watch: CPI inflation for 15 food classes/items (`cpi_food_inflation`). Monsoon and reservoir data still missing: IMD publishes rainfall as images/PDFs, CWC blocks US runners, DCA daily prices sit behind a captcha
- [ ] State-wise CPI y/y map (links to States, Phase 4)
- [x] Clear definition of core: CPI excluding food and beverages, and fuel and light (and the variant also excluding petrol, diesel and gold, if we publish it). Weights and method in `08-original-measures.md`
- [x] Detail page `/inflation/detail`: all 12 COICOP divisions with weights and contributions (groups and items still to add)

## Must NOT include
- Unlinked 2012-base and 2024-base CPI on one axis
- "Core" without saying which exclusion definition it is
- Seasonally adjusted momentum unless labelled Original with the method linked

## Series (planned)
cpi_headline_index, cpi_food_index, cpi_fuel_index, cpi_core_index, cpi_rural_index, cpi_urban_index, cpi_housing_index, wpi_headline_index, wpi_food_index, wpi_mfg_index, cpi_iw_index, rbi_hh_infl_exp_3m, rbi_hh_infl_exp_1y, rbi_cpi_projection

## Done when
Headline, food and the rural/urban y/y figures match the MoSPI press release. The core computation reproduces published third-party core figures within 0.1 pp for the last 12 months (sanity check, not a source).

## Phase
1 (headline, core, WPI), 2 (page)
- [x] Underlying inflation (trimmed means, weighted median, core ex precious metals), diffusion indices and goods/services from the 358 CPI items, matching RBI's MPR (added 2026-11-01)
