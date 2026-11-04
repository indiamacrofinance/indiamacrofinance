// Search quality check: runs the queries a visitor would type against the built Pagefind index
// (site/dist/pagefind) and reports where the expected page ranks. `make search-check` after
// `make build`; fails if fewer than MIN_TOP1 queries rank an expected page first or MIN_TOP3
// in the top three. Uses the ranking set in site/src/layouts/Base.astro (window.searchOptions).
// Each query is searched letter by letter first, as the search box does while typing, because
// Pagefind's scores depend on which parts of the index are already loaded.
//   node scripts/search_check.mjs [site/dist] [-v]
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const DIST = path.resolve(process.argv[2] && !process.argv[2].startsWith("-") ? process.argv[2] : "site/dist");
const VERBOSE = process.argv.includes("-v");
const MIN_TOP1 = 50, MIN_TOP3 = 60;

// The ranking the site uses, read from the built home page.
const home = fs.readFileSync(path.join(DIST, "index.html"), "utf8");
const m = home.match(/ranking: (\{[^}]+\})/);
if (!m) throw new Error("search ranking not found in index.html (window.searchOptions in Base.astro)");
const ranking = JSON.parse(m[1].replace(/(\w+):/g, '"$1":'));

// Pagefind is written for the browser: serve its fetches from site/dist.
globalThis.fetch = async (u) => {
  const buf = fs.readFileSync(path.join(DIST, String(u).replace(/^https?:\/\/[^/]+/, "").split("?")[0]));
  return { ok: true, status: 200, json: async () => JSON.parse(buf),
           arrayBuffer: async () => buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) };
};
globalThis.window = globalThis;
globalThis.location = { href: "http://localhost/", origin: "http://localhost" };
globalThis.document = { currentScript: null, querySelector: () => null };
const pf = await import(pathToFileURL(path.join(DIST, "pagefind/pagefind.js")));

const d = (s) => `/data/${s}/`;
// query -> pages that are a right answer (any of them in first place counts).
const CASES = {
  "inflation": ["/inflation/", d("cpi_headline_inflation")],
  "cpi": [d("cpi_headline_inflation"), d("cpi_headline_index"), "/inflation/"],
  "consumer price index": [d("cpi_headline_index"), d("cpi_headline_inflation"), "/inflation/"],
  "retail inflation": [d("cpi_headline_inflation"), "/inflation/"],
  "cpi inflation": [d("cpi_headline_inflation")],
  "core inflation": [d("cpi_core_index"), "/inflation/"],
  "food inflation": [d("cpi_food_bev_index"), "/inflation/"],   // item-level food inflation has no page of its own
  "wpi": [d("wpi_headline_index")],
  "wholesale inflation": [d("wpi_headline_index")],
  "gdp": [d("gdp_real_growth"), "/growth/"],
  "gdp growth": [d("gdp_real_growth"), "/growth/"],
  "economic growth": ["/growth/", d("gdp_real_growth")],
  "iip": [d("iip_general_index"), d("iip_general_growth")],
  "industrial production": [d("iip_general_index"), d("iip_general_growth")],
  "factory output": [d("iip_general_index"), d("iip_general_growth")],
  "unemployment": [d("plfs_ur_monthly"), "/jobs/"],
  "unemployment rate": [d("plfs_ur_monthly")],
  "jobs": ["/jobs/"],
  "employment": ["/jobs/", d("plfs_ur_monthly")],
  "repo rate": [d("repo_rate")],
  "policy rate": [d("repo_rate")],
  "interest rate": [d("repo_rate"), "/money/"],
  "forex reserves": [d("fx_reserves_total")],
  "foreign exchange reserves": [d("fx_reserves_total")],
  "fx reserves": [d("fx_reserves_total")],
  "rupee": ["/rupee/", d("usdinr_ref")],
  "exchange rate": [d("usdinr_ref"), "/rupee/"],
  "usd inr": [d("usdinr_ref"), d("usdinr_close")],
  "dollar": [d("usdinr_ref"), "/rupee/"],
  "fiscal deficit": [d("cga_fiscal_deficit_pct_be"), "/fiscal/", d("centre_gfd_pct_gdp")],
  "current account deficit": [d("bop_cab_pct_gdp"), d("cab_pct_gdp_fy")],
  "trade deficit": [d("merch_trade_balance")],
  "trade balance": [d("merch_trade_balance")],
  "exports": [d("merch_exports"), "/external/"],
  "gst": [d("gst_gross_collections"), d("gst_gross_growth")],
  "nifty": [d("nifty50_close")],
  "sensex": [d("sensex_close")],
  "stock market": ["/markets/", d("nifty50_close")],
  "bond yield": [d("gsec_10y_yield")],
  "10 year yield": [d("gsec_10y_yield")],
  "gsec": [d("gsec_10y_yield")],
  "bank credit": [d("scb_credit_growth")],
  "credit growth": [d("scb_credit_growth")],
  "crude oil": [d("brent_usd"), d("brent_inr")],
  "oil price": [d("brent_usd"), d("brent_inr")],
  "brent": [d("brent_usd"), d("brent_inr")],
  "gold price": [d("gold_usd_oz")],
  "fdi": [d("bop_fdi_net")],
  "foreign investment": [d("bop_fdi_net"), d("fpi_daily_total_usd")],
  "power demand": [d("power_energy_met"), d("power_peak_demand")],
  "electricity demand": [d("power_energy_met"), d("power_peak_demand")],
  "epfo": [d("epfo_net_payroll")],
  "import cover": [d("import_cover_months"), d("reserves_import_cover"), "/external/"],
  "real interest rate": [d("real_repo_rate")],
  "twin deficits": ["/fiscal/"],
  "budget": ["/tools/budget/", "/fiscal/"],
  "kerala": ["/states/kerala/"],
  "kerala inflation": ["/states/kerala/"],
  "release calendar": ["/calendar/"],
  "what changed": ["/updates/"],
  "rbi intervention": ["/analysis/fx-intervention/"],
  "balance of payments": ["/analysis/bop-stress/", "/external/", d("bop_cab_pct_gdp")],
  "mpc": [d("mpc_repo_decision"), "/money/"],
  "inflaton": ["/inflation/", d("cpi_headline_inflation")],
};

let top1 = 0, top3 = 0;
const misses = [];
for (const [q, ok] of Object.entries(CASES)) {
  await pf.destroy();
  await pf.options({ basePath: "/pagefind/", ranking });
  await pf.init();
  for (let i = 1; i < q.length; i++) await pf.search(q.slice(0, i));
  const r = await pf.search(q);
  const urls = (await Promise.all(r.results.slice(0, 10).map((x) => x.data()))).map((x) => x.url);
  const rank = urls.findIndex((u) => ok.includes(u)) + 1;
  if (rank === 1) top1++;
  if (rank >= 1 && rank <= 3) top3++;
  if (rank !== 1) misses.push(`  ${String(rank || "-").padStart(2)}  "${q}" -> ${urls.slice(0, 3).join("  ")}`);
}
const n = Object.keys(CASES).length;
console.log(`search-check: expected page first for ${top1}/${n} queries, in the top 3 for ${top3}/${n}`);
if (VERBOSE || top1 < MIN_TOP1 || top3 < MIN_TOP3) console.log(misses.join("\n"));
if (top1 < MIN_TOP1 || top3 < MIN_TOP3) {
  console.error(`search-check: below the floor (first ${MIN_TOP1}, top 3 ${MIN_TOP3})`);
  process.exit(1);
}
