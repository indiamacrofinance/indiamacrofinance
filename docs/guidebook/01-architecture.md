# 01 · Architecture

## Data flow

```
sources (MoSPI, RBI, CGA, Commerce, NSDL, AMFI, Grid-India, NPCI, Yahoo, …)
   │  GitHub Actions cron (IST)        +  `make india-update` from a machine in India
   ▼
pipelines/sources/<agency>/<dataset>.py
   fetch()    → raw bytes + receipt (url, fetched_at, sha256)  → data/raw/ (git-ignored) → Release asset
   parse()    → tidy frame: period, value, series_id, vintage
   validate() → schema, plausible range, no silent gaps, revision diff vs stored series
   publish()  → data/series/<id>.csv + data/meta/<id>.json + data/status.json
   ▼
pipelines/build/  → site/src/data/*.json (per page, per chart)
   ▼
site/ (Astro, static, Observable Plot) → Cloudflare Pages (private preview behind Cloudflare Access)
```

## Why this stack (details in `decisions/`)

- **Static site.** Free, fast, nothing to keep alive. All computation happens at build time.
- **Astro.** Markdown content collections handle briefings and blog posts. Components are simple enough for RAs.
- **Observable Plot.** Economist-style charts with very little code.
- **CSV per series in git.** Revisions show up as diffs in PRs and history is free. Raw files stay out of git.
- **Python 3.12 + uv** for pipelines.
- **Cloudflare Pages.** Serves a *private* repo for free, and Cloudflare Access gates the preview. GitHub Pages on a free org needs a public repo.

## The registry is the spine

Everything reads from `registry/`:

- `registry/series/<id>.yaml` holds the indicator metadata (schema: `registry/series/_schema.md`, template: `_template.yaml`).
- `registry/pages/<page>.yaml` lists a page's sections, their series and chart types.
- `registry/calendar/<publisher>.yaml` holds the expected release dates.

Pages, the calendar, the Data & Methods page, freshness checks and the briefing ledger are all generated from it. **If it isn't in the registry, it doesn't exist.**

## Panels (entity x period)

State-level data are **panels**: a source with `panel = True` returns an `entity` column. They are stored in `data/panels/<id>.csv` keyed on (entity, period), and their registry yaml sets `panel: true, entity: state`. State names are mapped to `registry/states.yaml` (aliases, plus short chart labels), and an unknown name fails loudly. The build writes `site/src/data/generated/panels/<id>.json`, with a `ref_period` (the latest period that at least twenty states have reported).

## Failure handling

A source that fails to fetch, parse or validate:

1. leaves `data/series/<id>.csv` (or `data/panels/<id>.csv`) untouched,
2. sets `stale: true` and `last_error` in `data/status.json`,
3. opens or updates one GitHub issue per series, labelled `scraper-broken`,
4. shows on the internal Status page.

Both series and panels reject missing or nonnumeric values, missing keys, duplicate
keys and values outside the registry range before publishing. Panel keys are
`(entity, period)`, so different entities can share a period. Missing parser columns
mark every series in that source stale and enter the normal failure report.

Revisions that move a past value by more than the series' `revision_alert` threshold also open an issue, labelled `large-revision`. They do not block publishing.

## Schedules (all IST; Actions cron is written in UTC)

Data is refreshed by **data bots**, modelled on econvitals' data repo: one workflow per group of publishers, each committing under its own name. The roster lives in `registry/bots.yaml`, and a test checks that every `fetch: auto` source belongs to exactly one bot.

| Workflow | When (IST) | Does |
|---|---|---|
| `bot-markets.yml` (markets-bot) | Mon–Fri 10:00, 12:00, 14:00, 16:00, 18:00 | RBI home-page rates, rupee, Nifty/Sensex/VIX, Brent, gold, Brent in ₹ |
| `bot-mospi.yml` (mospi-bot) | Mon–Sat 17:00 | CPI, core CPI, IIP, GDP, PLFS, state panels, CPI-IW |
| `bot-rbi.yml` (rbi-bot) | Mon–Sat 18:30 | WSS, BoP, services trade, surveys, IESH, MPC minutes, FBIL |
| `bot-ministries.yml` (ministries-bot) | Mon–Sat 19:30 | Trade, GST, CGA accounts and tax heads, WPI, core industries, PPAC, SIAM |
| `briefing.yml` (briefing-bot) | Mon–Sat 20:30 | Drafts release notes (review PR); auto-publishes the daily note |
| `newsletter-send.yml` (newsletter-bot) | When the maintainer pushes today's draft | Re-checks the morning email, sends it via Buttondown, archives it in `data/newsletter/morning/` |
| `newsletter-morning.yml` (newsletter-bot) | Daily 07:30 (when `writer: "api"`) | Writes the morning email with Claude Opus 5.5 through the Anthropic API, checks it, sends it via Buttondown |
| `newsletter.yml` | By hand only | Weekly digest as a provider draft |
| `deploy.yml` | On push to `main`, and when a bot or briefing-bot commits | Build + upload to Cloudflare Pages |
| `update-data.yml` | By hand only | Every auto source in one run (after an outage or a big fix) |

**How a bot works.** `bot.yml` holds the shared steps: `pipelines.run --bot <name>`, then failure issues, then `scripts/bot_commit.py <name>`. The commit script commits only when series or panels changed, and the message names the new values (e.g. "markets: USD/INR 95.23, Nifty 50 22,699"). A run that only touched timestamps makes no commit. After a commit the bot starts `deploy.yml`, because pushes made with `GITHUB_TOKEN` don't trigger other workflows. All bots share the concurrency group `data-bots`, so they take turns. If a push is still rejected, the script rebases and retries; on a clash in `data/status.json` it keeps the newer fetch.

**Adding a source:** put its name in one bot in `registry/bots.yaml`; derived measures go in the bot that fetches their inputs. **Adding a bot:** add it to `registry/bots.yaml` and copy one `bot-*.yml` with a staggered time.

**Actions minutes.** The repository has been public since 2026-10-29, so GitHub-hosted runner minutes are free and unlimited (a private repo on the free plan gets 2,000 a month). What still limits us: about 20 concurrent jobs on the free plan (the data bots share one queue, `data-bots`, on purpose, so their commits don't race), 6 hours per job, and scheduled workflows in a public repo switch off after 60 days with no repository activity (the bots' commits count; if they ever stop for two months, re-enable the schedules in the Actions tab). The real limit on how often we fetch is the sources: RBI's file server showed a captcha after heavy downloading on 2026-10-29, so the RBI bot stays at once a day. MoSPI has a 20:00 IST catch-up run and the ministries bot also runs daily at 13:00 IST.

## The foreign-IP fallback

GitHub-hosted runners are in the US. NSE, CCIL and some gov.in portals often block them. Every series yaml says `fetch: auto` or `fetch: manual`:

- `auto` runs in Actions.
- `manual` runs with `make india-update` on any machine in India. It runs all manual sources, validates them, commits on a branch, and opens a PR. Expected cadence is once per working day, about 5 minutes.

When an `auto` source starts failing with 403s or timeouts from Actions but works from India, flip it to `manual` and note it in `03-data-sources.md`. A later free upgrade is to register an always-on Mac as a **self-hosted runner**, which runs `manual` sources on a schedule.

## What makes us different from econvitals

1. **States**: a state dashboard with choropleths (GSDP, state CPI, PLFS unemployment, state finances).
2. **Base-year bridge**: properly linked long series across the 2026 rebasing (GDP 2022-23, CPI 2024, IIP 2022-23).
3. **Monsoon and food watch**: IMD rainfall vs normal, reservoir storage, vegetable prices next to CPI food.
4. **Digital pulse**: UPI, FASTag and e-way bills as high-frequency activity indicators.
5. **Indian conventions**: FY quarters, ₹ lakh crore, crore ↔ billion toggle.
6. **Citable and downloadable**: every chart has CSV download and a "cite this" line (.dta later).
7. **Built for more than one language**: no hard-coded UI strings, so a Hindi version is possible later.
