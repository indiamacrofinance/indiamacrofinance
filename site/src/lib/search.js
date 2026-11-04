// Search terms for the Pagefind index (rendered by Base.astro as hidden, weighted text).
// Pagefind only matches words that are on a page, so a visitor typing "forex reserves" never
// finds the page titled "FX reserves". These lists add the other names people use, and tell
// the ranking which page is the main one for a topic.

// Other names for words in series titles and ids: [pattern tested on "title short_title id", names].
const ALIASES = [
  [/\bCPI\b(?!-IW)|cpi_(?!iw)/, "consumer price index, consumer prices, retail inflation, prices"],
  [/CPI-IW|cpi_iw/, "consumer price index for industrial workers, Labour Bureau"],
  [/\bWPI\b|wpi_/, "wholesale price index, wholesale prices, wholesale inflation"],
  [/\bIIP\b|iip_/, "index of industrial production, industrial production, industrial output, factory output"],
  [/\bGDP\b|\bGVA\b|gdp_|gva_/, "gross domestic product, economic growth, national accounts, output"],
  [/\bPLFS\b|unemployment|plfs_/i, "unemployment, employment, labour force survey, labour market"],
  [/\bEPFO\b|epfo_/, "employees' provident fund, formal jobs, payroll, employment"],
  [/\bFX\b|forex|foreign exchange|fx_/i, "forex, foreign exchange"],
  [/fx_reserves|reserves_total/, "forex reserves, foreign exchange reserves, RBI reserves"],
  [/^(?!.*\breal\b).*(repo rate|repo_rate)/is, "policy rate, interest rate, RBI rate"],
  [/real_repo/, "real interest rate, real policy rate"],
  [/\bMPC\b|mpc_/, "monetary policy committee, monetary policy, RBI policy"],
  [/G-sec|gsec_/, "government bond yield, bond yield, ten-year yield, 10 year yield, gilt, g-sec, gsec"],
  [/USD\/INR|usdinr/, "rupee, dollar, rupee-dollar, exchange rate, INR, USD INR"],
  [/\bREER\b|\bNEER\b|reer_|neer_/, "effective exchange rate, rupee"],
  [/Brent|brent_/, "crude oil, oil price, crude price"],
  [/\bGold\b/, "gold price, gold"],
  [/Nifty|Sensex|nifty|sensex/, "stock market, shares, equities, stock index"],
  [/\bGST\b|gst_/, "goods and services tax, tax collections, indirect tax"],
  [/Trade balance|trade_balance/, "trade deficit, trade gap, merchandise trade"],
  [/Current account|bop_cab|cab_/, "current account deficit, CAD, balance of payments"],
  [/Fiscal deficit|\bGFD\b|fiscal_deficit|gfd_/, "fiscal deficit, government deficit, budget deficit"],
  [/\bFDI\b|fdi_/, "foreign direct investment, foreign investment, capital flows"],
  [/\bFPI\b|fpi_/, "foreign portfolio investment, foreign investment, foreign investors, capital flows"],
  [/\bECB\b|commercial borrowings|ecb_/i, "external commercial borrowings, foreign borrowing"],
  [/credit/i, "bank lending, loans, bank credit"],
  [/Power|energy met|power_/i, "electricity, electricity demand, power demand, power consumption"],
  [/Import cover|import_cover/, "import cover, months of imports, reserve adequacy"],
  [/auto_[0-9a-z]+_sales|vehicle_retail/, "vehicle sales, auto sales, automobiles"],
  [/\bM3\b|m3/, "money supply, broad money"],
];

// The main series for a topic (shown on the home page) also take the topic's own words, at the
// highest weight, so a one-word search lands on the headline rather than on a sub-index.
const HEADLINE = {
  cpi_headline_inflation: "CPI, inflation, consumer price index, retail inflation, headline inflation",
  cpi_headline_index: "CPI, consumer price index",
  cpi_core_index: "core inflation, core CPI",
  gdp_real_growth: "GDP, GDP growth, economic growth, real GDP growth",
  iip_general_index: "IIP, industrial production, factory output",
  iip_general_growth: "IIP growth, industrial production growth",
  plfs_ur_monthly: "unemployment, unemployment rate",
  repo_rate: "repo rate, policy rate, interest rate",
  fx_reserves_total: "forex reserves, foreign exchange reserves, FX reserves, reserves",
  usdinr_ref: "rupee, exchange rate, dollar, USD INR, rupee-dollar rate",
  gsec_10y_yield: "bond yield, 10 year yield, government bond yield, G-sec",
  scb_credit_growth: "bank credit, credit growth, bank lending growth",
  merch_trade_balance: "trade deficit, trade balance",
  bop_cab_pct_gdp: "current account deficit, current account",
  cga_fiscal_deficit_pct_be: "fiscal deficit",
  gst_gross_growth: "GST, GST growth",
  nifty50_close: "Nifty, stock market",
  sensex_close: "Sensex, stock market",
  power_energy_met: "power demand, electricity demand",
  brent_inr: "crude oil, Brent",
};

// Main series that are not on the home page, by the same rule.
const ALSO_MAIN = {
  wpi_headline_index: "WPI, wholesale inflation, wholesale prices",
  cpi_food_inflation: "food inflation, food prices",
  brent_usd: "crude oil, oil price, Brent",
  gold_usd_oz: "gold price",
  gst_gross_collections: "GST, GST collections",
  bop_fdi_net: "FDI, foreign direct investment",
  merch_exports: "exports",
  merch_imports: "imports",
  epfo_net_payroll: "EPFO, payroll, formal jobs",
  import_cover_months: "import cover",
  real_repo_rate: "real interest rate, real repo rate",
  auto_pv_sales: "car sales, passenger vehicle sales",
};

/** Search terms for one series: [main words (weight 10) or "", other names (weight 5)]. */
export function seriesTerms(s) {
  const text = `${s.title} ${s.short_title} ${s.id}`;
  const names = [...new Set(ALIASES.filter(([re]) => re.test(text)).flatMap(([, t]) => t.split(", ")))];
  return [HEADLINE[s.id] ?? ALSO_MAIN[s.id] ?? "", names.join(", ")];
}

// Topic pages: the words a visitor types for the whole topic, so "jobs" finds the Jobs page
// before the state pages that also have a Jobs section.
const PAGES = {
  "/inflation/": "inflation, prices, CPI, consumer price index, WPI, food inflation, core inflation, price rise",
  "/growth/": "growth, GDP, economic growth, gross domestic product, national accounts, GVA, economy",
  "/jobs/": "jobs, employment, unemployment, labour market, PLFS, EPFO, payroll, wages",
  "/activity/": "activity, economic activity, high-frequency indicators, IIP, industrial production, GST, power, fuel, autos",
  "/money/": "money, banking, banks, credit, deposits, liquidity, interest rates, monetary policy, RBI",
  "/markets/": "markets, stock market, bonds, bond yields, rupee, Nifty, Sensex, commodities",
  "/fiscal/": "fiscal, budget, government finances, fiscal deficit, public debt, taxes, spending, twin deficits",
  "/external/": "external sector, balance of payments, trade, exports, imports, current account, forex reserves, capital flows",
  "/rupee/": "rupee, exchange rate, dollar, USD INR, currency, depreciation",
  "/states/": "states, state data, state finances, state inflation, state economies",
  "/calendar/": "release calendar, calendar, release dates, upcoming releases, schedule",
  "/updates/": "what changed, updates, new data, latest data, revisions, changelog",
  "/status/": "status, data status, freshness, stale series",
  "/data/": "data, all series, download, catalogue, sources",
  "/methods/": "methods, methodology, definitions, how we calculate",
  "/analysis/": "analysis, research",
  "/analysis/fx-intervention/": "RBI intervention, forex intervention, dollar sales, CAFRAL",
  "/analysis/bop-stress/": "balance of payments stress, BoP crisis, 1991, external vulnerability",
  "/tools/budget/": "budget, union budget, budget explorer, ministry spending, demands for grants",
  "/tools/policy-rule/": "Taylor rule, policy rule, repo rate rule",
  "/tools/peers/": "peers, India and its peers, emerging markets, comparison",
};

/** Search terms for a page path ("/jobs/"), or "". */
export const pageTerms = (path) => PAGES[path] ?? "";
