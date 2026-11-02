# 08 · Original measures (methods)

Every measure we construct, rather than copy from an agency, is listed here and tagged **Original** on the site. Each entry covers: what it is, why it matters, inputs (series ids), method, limitations, and validation.

## Live

### Core CPI and the "fuel" index
- **What:** CPI excluding food and fuel, using **RBI's definition** so it matches what the MPC looks at. "Fuel" = electricity, gas and other fuels (group 04.5) + fuels and lubricants for personal transport equipment (class 07.2.2: petrol, diesel, CNG). Source of the definition: RBI Bulletin Table 19(c), footnote #, which points to Box IV.2 of the April 2026 Monetary Policy Report.
- **Series:** `cpi_core_index`, `cpi_fuel_index` (`pipelines/sources/derived/core_cpi.py`).
- **Weights** (`registry/weights/cpi2024_core.yaml`): food and beverages 36.75 (MoSPI), core 53.04 (RBI), fuel 10.21 = the remainder. MoSPI does not publish the split of fuel between its two parts in machine-readable form, so `scripts/estimate_core_cpi_weights.py` recovers it. CPI 2024 is fixed-weight, so each parent index is an exact weighted average of its children, and constrained least squares over 21 months gives the shares (max residual 0.007 index points). The estimates are 5.372 + 4.848 = 10.220, scaled to sum to 10.21.
- **Formula:** core = (100·general − 36.75·food − 5.367·elec_gas_fuels − 4.843·vehicle_fuels) / 53.04.
- **Validation (2026-10-28):** vs RBI's published core index for Jun-25, Jul-25, Jun-26 and Jul-26, within 0.01 index points; FY26 average 104.31 = 104.31; y/y Jun-26 3.90 = 3.90, Jul-26 3.87 vs 3.86. Pinned in `tests/sources/test_core_cpi.py`.
- **Limitations:** starts January 2025 (MoSPI's back series exists only for the general index), so y/y starts January 2026. Re-run the weight script if MoSPI revises weights. Weights are fixed until the next base revision.
- **Contributions:** the inflation page shows the percentage-point contributions of food, fuel and core: w·(I_t − I_t−12)/General_t−12. They sum to the published headline rate (checked: Jun–Sep 2026 within 0.01 pp).

### Brent crude in rupees
- **What:** Brent (US$ per barrel, front-month future, Yahoo Finance) × FBIL's USD/INR reference rate. Series `brent_inr` (`pipelines/sources/derived/brent_inr.py`).
- **Method:** each Brent close is converted at the reference rate of the same date, or the latest earlier one within 5 days. Days with no rate that recent are left out, not filled with a stale rate.

### Growth rates "as published" across base years
- **What:** the headline growth series for CPI (`cpi_headline_inflation`), IIP (`iip_general_growth`) and GDP/GVA (`gdp_real_growth`, `gva_*_growth`) show each period's rate **as the agency published it**.
- **Method:** where the new base (CPI 2024, IIP 2022-23, GDP 2022-23) has a rate, it is used. Earlier periods use the old base's published rate. Nothing is recomputed or spliced, and the note column on every row says which base it comes from.
- **Limitations:** rates from two bases differ in basket and weights, so a long chart joins two definitions. Charts say so in their notes.

### Year-on-year changes and other transforms
- **What:** growth rates computed from published index levels (e.g. CPI components, IIP categories, trade) are labelled "computed from the indices" on the site.
- **Method:** % change against the same calendar period a year earlier (matched on the date, not the row position). Because published indices are rounded, a computed rate can differ from the published one by about 0.01–0.1 points. Where an agency publishes the rate itself, we show that and label it "as published".
- **7-day averages** (`7dma`, `7dma_yoy`): for noisy daily series such as electricity demand, a 7-day calendar-window mean (at least 5 observations), and its % change on the same date a year earlier. Moving festivals and weather still distort the year-on-year comparison.

### GST growth on a consistent definition
- **What:** `gst_gross_growth`, `gst_net_growth`.
- **Method:** each month's growth compares that month with the year-earlier column **in the same sheet** of the GST portal's workbook, so both sides use one definition (later sheets exclude the compensation cess). Levels are taken only from each month's own sheet.

### Momentum and base effect in CPI inflation
- **What:** the month's change in 12-month headline CPI inflation, split into momentum and base effect (Inflation page, `cpi_momentum_base.json`, built in `pipelines/build/site_data.py`).
- **Formula (log points):** ln(I_t/I_t−12) − ln(I_t−1/I_t−13) = ln(I_t/I_t−1) − ln(I_t−12/I_t−13). Momentum = 100·ln(I_t/I_t−1); base effect = −100·ln(I_t−12/I_t−13). The two add up exactly to the change in the log 12-month rate.
- **Data:** `cpi_headline_index`, MoSPI's linked back series to 2024 = 100, not seasonally adjusted.
- **Limitations:** log points differ slightly from percentage-point changes in the published rate (which also rounds); indices are published to two decimals, so a month with an unchanged index shows zero.

### Term spread
- **What:** `term_spread_10y_repo` = FBIL 10-year par yield minus the policy repo rate in force that day (`pipelines/sources/derived/term_spread.py`).

### Policy rule for RBI (tool)
- **What:** `/tools/policy-rule/`: rule rate = r* + π + a(π − π*) + b(g − g*), against the repo rate set at each MPC meeting. Computed in the reader's browser; inputs in `policy_rule.json` (`policy_rule_inputs` in site_data.py).
- **Data:** π = headline CPI inflation as published (monthly); g = real GDP growth of the quarter the month falls in, as published (the latest quarter carried forward, flagged); repo = `mpc_repo_decision`, in force from the month of each meeting, from October 2016.
- **Defaults:** r* = 1.5, π* = 4, a = 0.5, g* = 6.5, b = 0.5. They are placeholders the reader changes, not estimates, and the page says so.
- **Why a growth gap:** the 2022-23-base national accounts start in 2022-23, too short for a trend or HP-filter output gap; revisit when a linked long series exists.

### Underlying inflation from the 358 CPI items
- **What:** RBI's measures of underlying inflation from its Monetary Policy Report (October 2026, Chapter IV), rebuilt from MoSPI's item-level CPI (`pipelines/sources/derived/cpi_underlying.py`): 5%, 10% and 25% trimmed means and the weighted median (Table IV.2); CPI excluding food, fuel and precious metals (Table IV.1); diffusion indices for the whole basket and for core (Box IV.1); goods and services inflation; and the contribution of gold and silver jewellery to headline inflation. From January 2026, when MoSPI's item-level inflation starts.
- **Item weights:** MoSPI publishes division weights but not item weights. CPI 2024 is a fixed-weight index, so each published parent index is an exact weighted average of its children. Non-negative least squares on 21 months of indices (January 2025 to September 2026) recovers each child's share for all 309 parents; item weight = official division weight × shares down the tree (`scripts/estimate_cpi_item_weights.py` → `registry/weights/cpi2024_items.csv`). Every parent is reproduced to within 0.0104 index points, the rounding of the published indices. Four small items in large, near-identical sibling groups (other wheat products, snuff, weighing machines, other hair products) come out at zero weight: the data cannot separate them. Totals are unaffected.
- **Goods and services:** the fifth segment of MoSPI's item code is 1 for goods and 2 for services, which gives MoSPI's own count of 308 goods and 50 services.
- **Definitions (checked against RBI's numbers):** trimmed means use published item inflation and base weights, dropping x% of the basket by weight *in total*, half from each tail, with items straddling a cut-off counted in part. The weighted median is the item at the 50th weighted percentile. Exclusion measures and goods and services are y/y changes of the weighted index of the items kept. Food = division 01; fuel = group 04.5 (electricity, gas and other fuels) and class 07.2.2 (petrol, diesel, CNG); precious metals = gold/diamond/platinum jewellery and silver jewellery. Diffusion buckets are below 2%, 2–4%, 4–6% and 6% and above, by weight.
- **Checks (October 2026 MPR, January–August 2026):** CPI excluding food and fuel matches RBI in all 8 months; excluding food, fuel and precious metals matches in all 8 (Table IV.1); weighted median matches (mean error 0.01 pp); 5%, 10% and 25% trimmed means are within 0.02–0.06 pp on average (Table IV.2); the share of the basket above 4% is 22.4% in April and 36.8% in August against RBI's "23 per cent" and "around 37 per cent"; the core basket has 198 items, as in RBI's box; core sub-group shares match Chart IV.15 within 0.4 pp. Pinned in `tests/sources/test_cpi_underlying.py`.
- **Limits:** recovered weights are estimates, so a single small item's weight is less certain than any aggregate. RBI's own series before 2026 use the old 2012 base; ours start in 2026 and are not spliced to it.

### How uncertain is RBI's CPI path (forecast bands from RBI's own errors)
- **What:** bands around RBI's latest quarter-by-quarter CPI projection path (`cpi_fan` in `pipelines/build/site_data.py`), shown with a table of RBI's past misses by horizon. Not RBI's fan chart, which comes from its own models.
- **Data:** every quarterly projection in MPC resolutions since 2018 (`pipelines/sources/rbi/mpc_projections_q.py`, which skips recaps of earlier projections, HRA-excluded variants and outturns), against the outturn = average of the quarter's three monthly y/y rates as published. For 2014-2024 these are MoSPI's 2024-base back-series rates, which we checked are identical to the rates originally published on the 2012 base (difference 0.00 in every month), i.e. the numbers RBI was forecasting.
- **Method:** horizon h = quarters from the meeting's quarter to the target quarter (0 = the quarter under way). For each h, the root-mean-square miss (which includes any bias) sets bands of projection ± 0.674, 1.036 and 1.645 × RMSE (50%, 70%, 90%, assuming roughly normal errors). Horizons with fewer than 12 past errors borrow the nearest shorter horizon. Quarters already complete get no band.
- **Numbers (November 2026):** RMSE 0.44 pp for the current quarter, 1.04 one quarter ahead, 1.41 two ahead, 1.44 three ahead, from 25-27 errors each; average misses are small (-0.14 to +0.08 pp).
- **Limits:** about 25 errors per horizon, so the band edges are approximate; errors from the 2020 pandemic quarters are included. GDP is not done: RBI's pre-2026 GDP projections were on the old 2011-12 base while the outturns are now on the 2022-23 base, so the errors would mix forecasting and rebasing.

### Rupee drivers: why the rupee moved
- **What:** each move of the rupee against the US dollar (last day, week, month, three months) split into the part its usual drivers account for, the rupee's average drift, and what is left unexplained. Shown on the rupee page (`/rupee/`) and used by the morning newsletter. Code: `pipelines/build/rupee.py`.
- **Inputs:** the market rate `usdinr_close` (Yahoo INR=X, completed days; today's live quote is shown but not explained), `dxy_close`, the yuan, won and rupiah (`usdcny_close`, `usdkrw_close`, `usdidr_close`, averaged as Asian currencies' value against the dollar), `brent_usd`, `nifty50_close`, `us10y_yield`, `us_vix_close`.
- **Method:** OLS of the rupee's daily % change in value (+ = stronger) on the daily changes in the drivers (%, except US yields in basis points and the VIX in points) over the last 500 trading days, with an intercept (the drift). Global drivers enter on the same day and the day before, since US markets close after India's; their effect is the sum of the two coefficients. A driver is kept only if its effect has the expected sign (stronger dollar, dearer oil, higher US yields or VIX: weaker rupee; stronger Asian currencies or Indian shares: stronger rupee) and its t-statistic is at least 1.5; otherwise it is dropped and the regression re-run. A period's attribution for each driver = the sum over its days of coefficient × driver change; "not explained" = the actual change minus all attributed parts and the drift, so the parts add up exactly.
- **Fit (2 Nov 2026):** the kept drivers were Asian currencies, oil and Indian shares; the dollar index, US yields and the VIX showed no reliable link over the window. The model explained about 11% of daily, 19% of weekly and 9% of monthly moves. Over the same years the rupee's monthly moves were most closely tied to oil (correlation 0.73) and Indian shares (−0.64).
- **RBI:** reserves are not a driver in the regression: they move with the rupee (RBI buys dollars when the rupee is strong and sells when it is weak, correlation of weekly changes +0.28), so they show RBI leaning against moves rather than causing them. They are shown as background, with the caveat that they also move with valuation.
- **Limits:** a statistical attribution, not proof of cause. The large unexplained share is typical of a managed currency. Daily FPI flows (NSDL) only exist from 2 Nov 2026, so they are background, not a driver, until there is enough history.

## Planned

### Linked series across base years (Phase 2)
- **What:** long series for GDP, CPI and IIP across the 2026 rebasing.
- **Method (default):** ratio splice at the overlap period (back-cast the old series by the ratio of new to old in the overlap year or month). Document the overlap used per series. Do not splice growth rates.
- **Limitations:** composition changes between bases. Show the overlap comparison on the Data & Methods page.

### Seasonally adjusted momentum (Phase 2)
- **What:** 3-month saar for CPI and IIP.
- **Method:** X-13ARIMA-SEATS (statsmodels wrapper) with Indian festival adjustments (Diwali moving holiday) where significant. Parameters stored in the registry.

### Activity and inflation surprise composites (Phase 4)
- **What:** z-scores of each indicator's latest reading vs its own history (rolling 10y), averaged into an activity composite and an inflation composite. India's version of econvitals' "relative to past performance".


### RBI policy rule (Phase 4)
- To be specified.
