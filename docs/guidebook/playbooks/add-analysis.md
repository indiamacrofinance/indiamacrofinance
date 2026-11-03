# Playbook: add an analysis

**Input:** a question, or a reference analysis to replicate (often private: decision 0006).
**Output:** a PR with the data, a build module, an Analysis page and its guidebook entries.
Worked example: the forex-intervention / BoP stress analysis (`05-pages/analysis.md`).

1. **Map the reference.** List every table, figure and number in it and the data each needs. If the
   reference is private, put it in `private/reference/` (git-ignored) with a README mapping each
   table/figure to a planned site section. Drop narrative, outside facts and paid data (AGENTS.md
   rules 5 and 6).
2. **Find public sources** for every input (`03-data-sources.md`; `scout-source.md` if new). RBI's
   Handbook of Statistics has long history in successive editions (`rbi/_handbook.py` finds tables by
   title in any edition); quarterly releases and the monthly Bulletin carry the latest periods.
3. **Add the series** with `add-indicator.md` (registry yaml, source module, fixtures, tests). Prefer
   the most detailed official presentation; check accounting identities in the parser and reject
   files that fail.
4. **Reproduce before you build pages.** Recompute the reference's tables in a scratch script from
   the stored series. Every number should match to its printed rounding; write down any that do not,
   and why, in the private README (not in the public guidebook).
5. **Build module:** `pipelines/build/<analysis>.py` with `analyse() -> dict`, computing everything
   the page shows from stored series (list them in `inputs`). Choices a human makes (episode dates,
   thresholds) go in `registry/analysis/<name>.yaml`, not in code. Call it from `site_data.py` inside
   `try/except` so a failure never blocks the site.
6. **Pages** under `site/src/pages/analysis/`: lede, the headline table or chart first, findings
   written as templates over the JSON (no typed numbers), method and limits, links to every input
   series. Inline charts: `components/Figure.astro` with kinds `scatter` and `lines` (bands) in
   `scripts/charts.js`. Interactive tools compute in the browser from embedded JSON.
7. **Wire it up:** add the piece to `site/src/pages/analysis/index.astro`, the Analysis menu in
   `site/src/lib/nav.js` (page and each `<h2 id>`), and a pointer from the related topic page.
8. **Guidebook:** checklist in `05-pages/analysis.md` (+ `registry/pages/analysis.yaml`), method and
   results in `08-original-measures.md`, sources in `03-data-sources.md`, release steps in
   `release-day.md` if new data change the conclusions.
9. **Tests:** pin results that will not be revised (old periods), identities, and the helper
   functions. `make check`, then `qa-site.md` (screenshots at 1280 and 375 px).
