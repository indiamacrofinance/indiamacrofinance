# AGENTS.md: start here

This file is the entry point for **any** agent or person working on this repo (Claude Code, Codex, Cursor, a new RA). Read it in full before changing anything.

## What this project is

A public, free, daily-updated dashboard of the Indian economy: growth, prices, jobs, activity, money and banking, markets, public finances, the external sector and states. It also has a release calendar, data downloads, and AI-drafted, human-approved briefings and a newsletter. It is inspired by econvitals.org (Jason Furman's U.S. dashboard) and credits it on the About page, but it is independent.

The site's name, tagline and colours live **only** in `site.config.yaml`. Say "the site" in prose and read the name from config in code.

## Current phase

See `docs/guidebook/00-start-here.md` → "Where we are". Phases: 0 foundations → 1 data spine + home → 2 topic pages → 3 briefings + newsletter → 4 originals and tools → 5 go public.

## Hard rules (never break these)

1. **No hard-coded site name.** Read it from `site.config.yaml`. `make check` enforces this.
2. **Every number shown traces to a series id** in `registry/series/`. No numbers typed by hand into pages or briefings.
3. **A failed fetch or validation never overwrites good data.** Mark the series stale, open or update a `scraper-broken` issue, and stop.
4. **Raw downloads are never committed.** They go to `data/raw/` (git-ignored) and are archived as GitHub Release assets.
5. **Use only the data we hold.** Briefings and analysis use our series plus official releases (RBI, MoSPI, PIB, ministries). No outside facts presented as findings.
6. **Respect licences.** Government open data (GODL-India) can be redistributed with attribution. Exchange index data (NSE/BSE) and S&P Global PMI can be **shown, not offered for download**. Never use paywalled data (CMIE etc.). Each series yaml records its `licence` and `downloadable` flag.
7. **AI writing needs human approval.** Briefings are drafted into a PR, and a human merge is the only way to publish or email.
8. **Never delete data files or history** to "clean up". Ask a maintainer.
9. **Keep the guidebook true.** If you change how something works, update the matching guidebook page in the same PR.

## Map of the repo

| Path | What lives there |
|---|---|
| `site.config.yaml` | Identity, brand, conventions, feature switches |
| `registry/series/*.yaml` | One file per indicator: the single source of truth for metadata |
| `registry/backlog.yaml` | Indicators planned but not yet built, by phase |
| `registry/pages/*.yaml` | Machine-readable page specs (sections → series → chart) |
| `registry/calendar/*.yaml` | Release calendars (MoSPI ARC, RBI MPC, CGA, Commerce) |
| `pipelines/core/` | Shared code: Source base class, HTTP, archive, validate, transforms, status |
| `pipelines/sources/<agency>/` | One module per dataset |
| `pipelines/build/` | Turns registry + data into JSON for the site |
| `pipelines/briefings/` | Number ledger, drafting, fact-checker |
| `data/series/`, `data/meta/` | Tidy CSV per series + JSON metadata (committed) |
| `data/status.json` | Freshness and health of every series |
| `site/` | Astro static site |
| `docs/guidebook/` | **The guidebook.** Conventions, page checklists, runbook, playbooks |
| `.claude/skills/`, `.claude/agents/` | Claude Code skills and subagents (wrap the playbooks) |
| `.github/` | Workflows, issue templates, PR template |

## Common tasks → which playbook

| Task | Playbook (any agent) | Claude skill |
|---|---|---|
| Add a new indicator | `docs/guidebook/playbooks/add-indicator.md` | `add-indicator` |
| A scraper broke | `docs/guidebook/playbooks/fix-scraper.md` | `fix-scraper` |
| Build or extend a page section | `docs/guidebook/playbooks/build-page-section.md` | `build-page-section` |
| Process a release day | `docs/guidebook/playbooks/release-day.md` | `release-day` |
| Draft a briefing | `docs/guidebook/playbooks/draft-briefing.md` | `draft-briefing` |
| QA the site before merging | `docs/guidebook/playbooks/qa-site.md` | `qa-site` |
| Vet a new data source | `docs/guidebook/playbooks/scout-source.md` | subagent `source-scout` |

## Commands

```bash
make setup          # uv sync (Python) + npm install (site)
make check          # registry validation + name check + tests
make update SOURCE=<series_id>   # fetch → validate → publish one series
make update-auto    # all `fetch: auto` series
make india-update   # from India: manual sources + stale automatic ones + derived; pushes to main
make build          # build site JSON + Astro site
make dev            # local preview
```

Some targets are stubs until Phase 1 lands. A stub prints `not implemented yet`.

## Conventions in one breath

Financial year runs April–March. Label FY26 for 2025-26, and Q2 FY27 for Jul–Sep 2026. Domestic money is in ₹ lakh crore and external data in US$ bn. Growth is y/y unless labelled otherwise. Store dates as ISO period-start dates. Never put two base years on one axis without linking them. Full details: `docs/guidebook/02-conventions.md`.

## Definition of done (any PR)

- [ ] `make check` passes
- [ ] New and changed series have registry yaml, tests and a `verified_against` entry (official release checked by a person or the `data-validator` agent)
- [ ] Page checklist in `docs/guidebook/05-pages/` updated (tick what you delivered)
- [ ] Guidebook updated if behaviour changed
- [ ] PR description says what was verified and how
