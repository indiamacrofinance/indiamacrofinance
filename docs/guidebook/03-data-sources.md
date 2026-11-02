# 03 · Data sources catalogue

One row per **publisher/dataset**. Each indicator built from a source also has a `registry/series/*.yaml` that points back here.

**Status key:** `to-scout` = not yet checked · `scouted` = format, URL pattern, licence and access checked (date in Notes) · `live` = a series is in production.
**Access:** `auto` = works from GitHub Actions (US IP) · `manual` = needs a machine in India · `?` = untested.
**Licence:** `GODL` = Government Open Data Licence – India (redistribute with attribution) · `show-only` = display with attribution, no bulk download · `check` = unknown.

Every entry below is **`to-scout`**. The URLs are portal home pages, not verified endpoints. The Phase 0/1 source-scout pass fills in Format, URL pattern and Notes. Use `playbooks/scout-source.md`.

## Reachability probe: 2026-10-28

`scripts/probe_sources.py` fetched each portal's home page with browser headers, from India (this Mac) and from GitHub Actions (US). Raw results: `data/probes/*.json`. Re-run with the `probe-sources` workflow. **Home pages only**: a data endpoint can behave differently, so confirm per endpoint when scouting.

| Portal | India | Actions (US) | Implication |
|---|---|---|---|
| MoSPI, eSankhyiki, Labour Bureau, NREGA, RBI (all three), CGA, PIB, indiabudget, Commerce, TradeStat, FBIL, CCIL, BSE, NSDL, AMFI, PPAC, DGCA, IMD, FCA prices, GST, World Bank API | 200 | 200 | `auto` candidates |
| EPFO | 200 | **403** | `manual` |
| Grid-India | 200 | **connection reset** | `manual` |
| CWC (reservoirs) | 200 | **401** | `manual` |
| NSE home page | 403 | 403 | Home page blocks scripts, but `nseindia.com/api/allIndices` returned 200 from both. Licensed: show-only |
| NPCI | 403 | 403 | Blocks scripts everywhere. Try a browser-like session or the PDF statistics pages; else manual entry |
| Yahoo chart API | 429 | 429 | Rate-limited without a session. Use the `yfinance` library (handles cookies) and test it |
| OEA / DPIIT (WPI, core) | SSL error | SSL error | **Fixed** 2026-10-28: missing intermediates fetched via AIA (`INCOMPLETE_CHAIN_HOSTS` in `core/http.py`) |

Small 200 responses (MoSPI 2.6 KB, eSankhyiki 1.2 KB, NREGA 0.5 KB, FBIL 1.5 KB) are JavaScript shells or redirects. Their data must come from API or file endpoints, not from parsing HTML.

## Official statistics

| Publisher | Datasets | Portal | Access | Licence | Status | Notes |
|---|---|---|---|---|---|---|
| MoSPI (NSO) | CPI (base 2024 + official back series to 2013, by state), IIP, NAS (GDP, base 2022-23; state GSDP growth, base 2011-12), PLFS (monthly/quarterly/annual, by state), WPI | REST API `https://api.mospi.gov.in/api/<product>/...` (no key). Specs: `https://esankhyiki.mospi.gov.in/layout/swagger_user_<cpi|iip|nas|plfs|wpi>.yaml`. Codes: MCP server `https://mcp.mospi.gov.in/mcp` tool `get_metadata` | auto | GODL (released under NDSAP/GSDD) | **live**: CPI, IIP, NAS quarterly, PLFS monthly | Scouted 2026-10-28. Needs TLS legacy renegotiation (handled in `core/http.py`). Max 100 rows/page (base 2012) or 200 (base 2024). CPI 2024 base uses COICOP 2018 divisions (no 'fuel and light' group). Back series covers the general index only. IIP: `iip/getIIPData` frequency=Monthly, base 2022-23 from Apr 2023, 2011-12 before; types General / Sectoral / Use-based category. NAS: `nas/getNASData` (indicators 5 GDP, 9-15 components, 21 GVA growth, 22 GDP growth; the old-base total row is called 'Total GVA Growth Rate'). PLFS: `plfs/getData` frequency_code=3 monthly from 2025, one indicator per call. CPI params: base_year, series (Current/Back), state_code (1 = All India for 2024; 99 for 2012), sector_code (1 R, 2 U, 3 C), division_code; 2012 base needs level=Group |
| Office of the Economic Adviser (DPIIT) | WPI (base 2022-23), Index of Core Industries (base 2022-23) | eaindustry.nic.in: `download_data_2223.asp` → `indx_download_2223/wpi_monthly_index_<yyyymm>.xlsx`; `ici_download_data.asp` → `eight_core_infra/Core_Industries_2022_23_<yyyymmdd>.xlsx` | auto | GODL | **live** (2026-10-28) | Monthly, around the 14th (WPI) and 20th (core). **The MoSPI API's WPI (`/api/wpi/getWpiRecords`) stops at April 2026 on the 2011-12 base (checked 2026-10-28), so WPI must come from OEA.** OEA's server sends only its leaf certificate; `core/http.py` walks the AIA chain (YR1 → Root YR cross-signed by ISRG Root X1) without partial-chain trust |
| Labour Bureau | CPI-IW (2016=100) | Latest press note linked on the home page (`uploads/public/notice/Press-Release-CPI-IW-<Month><Year>E….pdf`) | auto | GODL | **live** (2026-10-28) | No archive page, so history builds from each note (index for 2 months, inflation for the month and a year earlier). CPI-AL/RL (2019=100) press notes are linked the same way (to do) |
| EPFO | Net payroll additions | epfo.gov.in/data-hub/ (PDF per report month on pmvbry-cdn.epfindia.gov.in) | manual | GODL | **live** (`epfo/payroll.py`, Apr 2020 to Jul 2025) | epfindia.gov.in redirects to epfo.gov.in. Page 1 of each PDF has a row per month (`Jul-2025` + six age bands, total, establishments); the newest report printing a month wins. No report posted after September 2025 (checked 2026-10-29) |
| MGNREGA (MoRD) | Households demanding work, person-days | nrega.nic.in | ? | GODL | **deferred** | Report pages are slow and stateful (ASP.NET postbacks). Scout the MIS 'R1' / 'demand' reports or data.gov.in mirrors before building |

## RBI

| Dataset | Portal | Access | Licence | Status | Notes |
|---|---|---|---|---|---|
| RBI home page rates panel: repo/SDF/MSF, CRR/SLR, FBIL rates (1 pm today), benchmark G-sec yields, T-bill cut-offs, Sensex/Nifty closes | www.rbi.org.in | auto | unverified | **live** | Scouted 2026-10-28. Snapshot only (no history): we store one value per day. Footnotes give the 'as on' dates |
| DBIE time series (money, credit, rates, BoP, reserves, state finances) | data.rbi.org.in (moved from dbie.rbi.org.in, June 2024) | ? | check (RBI terms) | to-scout | No documented public API found. Scrape downloads. Note: the MoSPI API/MCP dataset `RBI` carries 39 RBI Handbook external-sector tables (trade, BoP, external debt, FX reserves monthly), but only to 2025, so it suits history, not the latest data |
| Weekly Statistical Supplement (WSS) | Archive per section: `rbi.org.in/Scripts/WSSViewDetail.aspx?TYPE=Section&PARAM1=<n>` (2 FX reserves, 3 SCB business, 4 ratios and rates, 7 money stock M3 (table 6), 8 reserve money (table 7), 25 liquidity operations (table 8), 1 RBI balance sheet; 13-23 CDs, CP, price indices, money-market turnover, T-bills, borrowings). The archive parameter is not the table number; weekly XLSX at `rbidocs.rbi.org.in/rdocs/Wss/DOCs/<n>T_<ddmmyyyy><hash>.XLSX` | auto | unverified | **live** (sections 2, 3, 4, 7, 8, 25) | Scouted 2026-10-28. Printed tables: rows matched by label, dates from headers. Earlier prints get revised (e.g. CRR for 28 Nov 2025 printed 3.00 then 3.25), so the latest print wins. The archive goes back years, so further backfill is possible. Layouts drift: older reserve-money files put the year one row lower, and Excel sometimes stores the day ("May 1") as a date with the wrong year, so only month and day are used; older liquidity files print dates as text. Fixtures for both in `tests/fixtures/rbi/wss/` |
| Handbook of Statistics on Indian States | State GSDP, fiscal deficit, revenue deficit, interest, outstanding liabilities | AnnualPublications.aspx?head=Handbook+of+Statistics+on+Indian+States (tables found by number; links single-quoted, names change each edition) | auto | unverified | **live** (`rbi/state_finances.py`) | Each column is checked against the "All States and UTs" row; Table 176 end-March 2015 fails (missing Telangana label shifts rows) and is dropped |
| Press releases: external debt | press index, titles "India's External Debt as at the end of <Month> <YYYY>" | auto | unverified | **live** (`rbi/external_debt.py`) | Highlights give the level and change vs an earlier date (previous quarter, or a year earlier in March releases) and debt/GDP for both. Wording varies ("recording an increase"). The index lists only March and June releases for 2023-26 |
| Press releases: BoP remittances | quarterly BoP release text | auto | unverified | **live** (in `rbi/bop.py`) | "Personal transfer receipts ... rose to US$ X billion in Qn:YYYY-YY from US$ Y billion in Qn:YYYY-YY", printed since Q3 2024-25 |
| Press releases: MPC minutes | rbi.org.in press index (`_press.releases`, title starts "Minutes of the Monetary Policy Committee Meeting") | auto | GODL | **live** (`rbi/mpc_minutes.py`, 62 meetings from Oct 2016) | Member titles vary ("Prof" without a dot, "Dr.Pami", no title for M. Rajeshwar Rao), so statements are matched to vote-table names, not parsed from headings. Some statements open with a section heading before paragraph 1. `rbi/mpc_decisions.py` reads the same minutes for the rate set (the "to/at N per cent" after the verb, never "from"), the stance (in the resolution; since 2025 after the outlook) and, since 2019, the size each member voted for. |
| Household Inflation Expectations Survey (IESH) | Press release 'RBI releases the results of Forward Looking Surveys' (via the index helper `pipelines/sources/rbi/_press.py`) → `PublicationsView.aspx?id=<n>` → `IESH….PDF`, Table 3 | auto | unverified | **live** (2026-10-28) | The same release links Consumer Confidence (UCCS/RCCS) and the Survey of Professional Forecasters (both **live**, `rbi_surveys`), plus OBICUS and the industrial outlook survey (candidates, same path). Older survey PDFs use other layouts; unparseable ones are skipped with a log line |
| Monetary Policy Report projections | rbi.org.in | ? | check | to-scout | Twice a year + each policy statement |

## Government finance

| Publisher | Datasets | Portal | Access | Licence | Status | Notes |
|---|---|---|---|---|---|---|
| Controller General of Accounts | Centre's monthly accounts ('Accounts at a Glance') | `cga.nic.in/writereaddata/MonthAccount/<m><yyyy>/DATA<fy>.htm` (some months .HTM) | auto | GODL | **live** (2026-10-28) | Word-exported HTML; April pages say 'for April', March pages are 'PROVISIONAL ACCOUNTS FOR yyyy-yyyy' compared with Revised Estimates. The dashboard workbook on the site stops at Feb 2026, so don't use it |
| GSTN / Ministry of Finance | GST gross/net collections; e-way bills; state-wise GST | `tutorial.gst.gov.in/offlineutilities/gst_statistics/Gross_Net_Tax_collection.xlsx` (one sheet per month) and `ewb-data-<fy>.xlsx`, listed at gst.gov.in/download/gststatistics | auto | GODL | **live** (collections; e-way bills via `gst/ewaybills.py`) | E-way bill files have one row per state and month; all-India = within-state + outgoing (incoming would double-count). Files 2018-19 to 2026-27, current year updated in place. The collections workbook lags the 1st-of-month press release by about two months. Sheet Jan-25 is malformed in the source (headers swapped), so it is skipped. Later sheets drop compensation cess |
| Union Budget | BE/RE/Actuals | indiabudget.gov.in | ? | GODL | to-scout | Budget Explorer (Phase 4) |
| CGA (tax heads) | Tax collections by head: gross, corporate, income, STT, customs, excise | cga.nic.in `MonthAccount/<m><yyyy>/DTL3<fy>.HTM` ("Monthly Trend"; one 5-column table per head, current + previous FY) | auto | GODL | **live** (`cga/tax_heads.py`, from FY 2015-16) | Supersedes an earlier note here that DTL3 had no split (it does; the earlier check looked at the wrong month). Headings changed: CORPORATION TAX→CORPORATE TAX, INCOME TAX→TAXES ON INCOME OTHER THAN CORPORATE TAX; STT has its own head from FY 2023-24. Gross = sum of heads less NCCD (verified for FY 2023-24 and 2025-26). |
| CBDT / PIB | Direct tax collections | pib.gov.in press releases (irregular) | — | GODL | **not needed** | Finance Ministry listings sampled for Dec 2023 to Oct 2026 (allRel.aspx form, ministry 15) show no CBDT collection releases after April 2024. incometaxindia.gov.in returns 403 to scripts; not pursued. CGA tax heads cover this. |
| PRS Legislative Research | State budget analyses | prsindia.org | ? | check | to-scout | Secondary. Prefer RBI State Finances |

## External sector

| Publisher | Datasets | Portal | Access | Licence | Status | Notes |
|---|---|---|---|---|---|---|
| Ministry of Commerce | Monthly merchandise trade (SDDS table); press release (merchandise + services) | JSON listing `commerce.gov.in/ministryofcommerce/api/v1/statistics-trade/current-figures-trade`; files under `commerce.gov.in/files/...` | auto | GODL | **live** (merchandise) | SDDS PDFs have three layouts (with and without spaces). The site is behind Akamai: headless browsers are blocked, plain HTTP with browser headers works. Services trade is only in the press-release PDF (to do) |
| RBI | Trade in services (monthly press release) | Listing `rbi.org.in/Scripts/Pr_DataRelease.aspx?SectionID=352` → `BS_PressReleaseDisplay.aspx?prid=<n>` | auto | unverified | **live** (2026-10-28) | Each release covers the financial year to date; earlier months revised with BoP data. Prefer this to Commerce's monthly services projection |
| RBI | Balance of payments: quarterly and (from 2026) monthly press releases | Found by POSTing the press-release index `BS_PressReleaseDisplay.aspx` with `hdnYear`/`hdnMonth` (plus the page's hidden fields) and matching titles 'Developments in India's Balance of Payments' | auto | unverified | **live** (2026-10-28) | Three quarterly table layouts (normal, split 'January-March \| 2025', en dash). % of GDP is read only from a sentence naming a quarter. Releases that can't be parsed are skipped with a log line |
| RBI | REER/NEER, ECB | data.rbi.org.in | ? | check | to-scout | |

## Markets and finance

| Publisher | Datasets | Portal | Access | Licence | Status | Notes |
|---|---|---|---|---|---|---|
| FBIL | Reference rates (USD/INR etc.), G-sec valuation, T-bill curves | fbil.org.in | ? | check | to-scout | Official benchmark for INR |
| CCIL | G-sec yields, money-market volumes | ccilindia.com | ? | check | to-scout | Often blocks foreign IPs (likely `manual`) |
| NSE / BSE | Index levels, India VIX, FII/DII provisional flows | nseindia.com, bseindia.com | ? (NSE blocks non-browser clients) | **show-only** | to-scout | Licensed. No bulk downloads |
| Yahoo Finance (via yfinance) | ^NSEI, ^BSESN, ^INDIAVIX, BZ=F (Brent), GC=F (gold) | yfinance library (handles Yahoo's session; the raw chart API returns 429) | auto | **show-only** | **live** (2026-10-28) | Nifty/Sensex closes checked equal to RBI's republished closes. Store to 2 decimals (Yahoo returns float noise). 10-year backfill on first run |
| NSDL | FPI flows (equity, debt) | fpi.nsdl.co.in | ? | check | to-scout | |
| AMFI | Mutual fund flows, SIP inflows, AUM | amfiindia.com | ? | check | to-scout | Monthly, ~10th |
| SEBI | Bulletin aggregates | sebi.gov.in | ? | check | to-scout | Later |

## High-frequency activity

| Publisher | Datasets | Portal | Access | Licence | Status | Notes |
|---|---|---|---|---|---|---|
| Grid-India | Daily all-India energy met, peak demand, solar/wind generation | File list: POST `webapi.grid-india.in/api/v1/file` `{"_source":"GRDW","_type":"DAILY_PSP_REPORT","_fileDate":"<FY>","_month":"00"}`; files at `webcdn.grid-india.in/<FilePath>` (.xls + .pdf per day) | manual | unverified | **live** (2026-10-28) | Report titled with the data date (`27.10.26_NLDC_PSP`) and published the next morning. Sheet MOP_E, section A, TOTAL column. `.xls` needs python-calamine. Backfilled from 1 Apr 2025 |
| NPCI | UPI volumes and values (monthly; daily from product statistics) | npci.org.in (page data from `/api/...`) | blocked | check | **via RBI** | Akamai bot protection: plain HTTP gets 403 even on `/api/header-menu` (checked 2026-10-28). UPI is live from RBI's Payment System Indicators instead (`rbi/payments.py`: rbi.org.in/Scripts/PSIUserView.aspx links the last 12 monthly XLSX; row "2.6 UPI", volume in lakh, value in ₹ crore, with year-earlier and previous-month columns) |
| SIAM | Domestic vehicle sales (PV, 2W, 3W) | siam.in press releases, HTML (`/news-&-updates/press-releases/<any-slug>/<id>`; slug ignored, ids sequential, monthly sales from id 482 = Apr 2021) | auto | show-only (industry body) | **live** (`siam/sales.py`) | Wholesale dispatches. PV only from Apr 2023 (Tata Motors included from then). Sentence wording varies (`Vehicles2`, `84,077units`, `were units 19,02,209`); quarter-end releases repeat sentences for the quarter and year-to-date, which the regex skips. |
| PPAC | Petroleum product consumption | ppac.gov.in (XHR POST `AjaxController/getConsumptionPetroleumProductsData`, `financialYear=YYYY-YYYY&reportBy=1&pageId=43`, JSON) | auto | GODL | **live** (`ppac/consumption.py`) | Product titles can carry HTML (`<b>TOTAL</b>`); strip tags. Older years under the Historical section, not yet pulled. |
| AAI (instead of DGCA) | Air passengers and freight, all Indian airports | aai.aero/en/business-opportunities/aai-traffic-news (monthly PDF `TR<Mon>2k<yy>.pdf`) | auto | unverified | **live** (`aai/traffic.py`) | Only the current year's reports are linked; older ones exist but names vary (TRDec2k25.pdf). Some PDFs split digits ("5 . 56"), so values are read with spaces removed and checked against the printed % change. DGCA's portal menus are JavaScript-driven and were not scraped |
| FADA | Vehicle retail registrations (2W, 3W, PV, CV, tractors, total) | fada.in/press-release-list.php (?page=2 for older), PDF per month, table "All India Vehicle Retail Data for <Mon'yy>" | auto | show-only (industry body) | **live** (`fada/retail.py`) | Month labels are "Sep'26" or "July'25". FADA restates earlier months by up to ~5% as Vahan coverage widens, so the newest release wins. Festive-only releases have no such table and are skipped. Standard browser headers needed (plain curl gets 406). |
| GSTN | E-way bills | see the GSTN row above | auto | GODL | **live** | ewaybillgst.gov.in itself has no monthly statistics |
| Indian Railways | Freight loading | pib.gov.in | manual? | GODL | blocked | Via press releases. indianrailways.gov.in has no monthly loading file that scripts can reach (checked 2026-10-29). PIB (checked 2026-10-29): the RSS feed (RssMain.aspx) holds only the latest 20 releases with no ministry feed; the all-releases page (allRel.aspx) has a ministry filter (Ministry of Railways = 23) but returns the unfiltered list when posted by a script. Options: a daily bot that watches the RSS feed and builds history going forward, or a manual entry each month. |
| S&P Global | HSBC India PMI (headline) | — | — | **show-only, cite headline only** | to-scout | Licensed. Never redistribute series |

## Monsoon, agriculture, food

| Publisher | Datasets | Portal | Access | Licence | Status | Notes |
|---|---|---|---|---|---|---|
| IMD | Rainfall vs long-period average (weekly, seasonal) | mausam.imd.gov.in | ? | check | to-scout | June–September focus |
| Central Water Commission | Reservoir storage bulletin (weekly) | cwc.gov.in | manual | GODL | to-scout | PDF |
| Dept of Consumer Affairs | Daily retail prices of essential commodities (tomato, onion, potato, pulses) | fcainfoweb.nic.in | ? | GODL | to-scout | |

## International comparisons (Phase 4)

| Publisher | Datasets | Access | Licence | Status |
|---|---|---|---|---|
| IMF (WEO, IFS via SDMX), World Bank WDI API | Peer comparisons | auto | open with attribution | to-scout |

## Never use

CMIE (paywalled), Bloomberg/Refinitiv/LSEG terminal data, any data behind a login, any source whose terms forbid redistribution.

### Budget

| Publisher | Data | URL | Fetch | Licence | Status | Notes |
|---|---|---|---|---|---|---|
| Ministry of Finance | Budget at a Glance (BE, RE, Actuals; deficits with % of GDP) | `indiabudget.gov.in/doc/Budget_at_Glance/budget_at_a_glance.xlsx` | auto | GODL | **live** (`budget/glance.py`) | Replaced each Budget, so history accumulates from 2024-25. Sheets BAAG and Deficit Statistics; % of GDP in brackets on the row below each deficit. The per-table `bag1.xls` links on the home page return 404 |
| Ministry of Finance | Spending by demand for grants (Actuals, BE, RE) | `indiabudget.gov.in/doc/eb/stat3a.xlsx` (Expenditure Profile, Statement 3) | auto | GODL | **live** (`budget/demands.py`) | Demand rows start "Demand No. N\\n<name>"; Total columns found from the header; demands must sum to Grand Total (checked) |

### International

| Publisher | Data | URL | Fetch | Licence | Status | Notes |
|---|---|---|---|---|---|---|
| BIS | Effective exchange rates (REER, NEER), broad basket | `stats.bis.org/api/v1/data/WS_EER/M.R+N.B.IN/all?format=csv` | auto | BIS terms (attribution) | **live** (`bis/eer.py`, from 2005) | Public SDMX API, no key. Used because RBI's Bulletin REER/NEER tables have no stable links |
| FBIL | G-sec par yield curve (daily) | `fbil.org.in/wasdm/gsec/fetchfiltered?fromDate&toDate&authenticated=false` lists dates; `.../gsec/downloadPublished?date=YYYY-MM-DD` serves the XLSX (sheet "Par Yield") | auto | unverified | **live** (`fbil/gsec_curve.py`, from Jan 2025) | Endpoints found in FBIL's Angular bundle (`main.*.js`). Public files lag about a week. Files don't change, so only new days are downloaded |
| NSDL | FPI net investment by month | `fpi.nsdl.co.in/web/Reports/Yearwise.aspx?RptType=6`, year via ASP.NET post-back (`ddl`) | auto | unverified | **live** (`nsdl/fpi.py`, from 2015) | Columns change by year (Debt-VRR from 2019-20, FAR and MF/AIF columns later); read with nested headers. Occasionally a post-back returns no table: retried once |
| NSDL | FPI net investment, daily (US$ mn) | `fpi.nsdl.co.in/web/Reports/Latest.aspx`: one table for the latest reporting date only | auto | unverified | **live** (`nsdl/fpi_daily.py`, from 2 Nov 2026; history builds daily) | Negatives in brackets. Equity and debt sub-totals and the all-category total |
| Yahoo Finance | Currencies and US markets for the rupee page: INR=X, CNY=X, KRW=X, IDR=X, DX-Y.NYB, ^TNX, ^VIX | yfinance | auto | show-only | **live** (`yahoo/markets.py`, ten years) | FX keeps today's bar as a live quote (Yahoo's FX day ends 05:30 IST); US series use completed days only |
| AMFI | Mutual fund flows and AUM | `portal.amfiindia.com/spages/am<mon><yyyy>repo.xls`, listed at amfiindia.com/research-information/amfi-monthly | auto | unverified | **live** (`amfi/monthly.py`, from Apr 2019) | Reports Apr 2018-Mar 2019 use another layout (skipped). SIP data not in the workbook |
| BIS | Policy rates and CPI inflation for India and 8 EM peers | `stats.bis.org/api/v1/data/WS_CBPOL/M.<areas>/all` and `WS_LONG_CPI/M.<areas>.771/all` (CSV) | auto | BIS terms | **live** (`intl/peers.py`, from 2015) | Same SDMX API as the EER |
| World Bank | Real GDP growth, annual, India and peers | `api.worldbank.org/v2/country/<iso3;...>/indicator/NY.GDP.MKTP.KD.ZG?format=json` | auto | CC BY 4.0 | **live** (`intl/peers.py`) | The IMF DataMapper API returns 403 to scripts (checked 2026-10-29) |
