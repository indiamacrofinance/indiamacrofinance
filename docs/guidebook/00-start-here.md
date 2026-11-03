# 00 · Start here

## What we are building

A dashboard of the Indian economy that updates every working day. It covers macro, financial and market indicators from public sources, adds a release calendar and downloadable data, and publishes briefings and a newsletter that AI drafts and a person approves. The audience is **economists and students**, so pages are dense, with methods notes and downloadable data.

The model is econvitals.org (U.S.). We credit it and do some things differently: a states view, a base-year bridge, a monsoon and food watch, and Indian units and financial-year conventions. See `01-architecture.md` → "What makes us different".

## Roles

| Role | Does |
|---|---|
| **Maintainer** (project lead) | Sets priorities, approves briefings (merges PRs), owns the registry and the guidebook |
| **RA** | Runs `make india-update`, fixes scrapers, builds indicators and page sections from issues, verifies new series |
| **Coding agent** (Claude, Codex, …) | Same tasks as an RA, always via a playbook, always opening a PR. Never merges its own briefing PRs |

## 30-minute onboarding

1. Read `AGENTS.md` (5 min).
2. Read `01-architecture.md` and `02-conventions.md` (10 min).
3. Skim `05-pages/README.md` and the page you will work on (5 min).
4. `make setup && make check && make dev` and open the local site (10 min).
5. Pick an issue labelled `good-first-task` from the project board.

## Where we are

| Phase | Scope | Status |
|---|---|---|
| 0 | Repo, config, guidebook, skills, CI skeleton, private preview | done except the Cloudflare preview |
| 1 | Pipeline core + ~25 core series + home dashboard + calendar + logo v1 | **in progress**: 112 series from 16 sources (prices, activity, GDP, jobs, RBI WSS, markets, trade, GST, CGA accounts); 11 pages; daily workflow. Left: MGNREGA, power demand, UPI, release calendar |
| 2 | All topic pages, detail pages, Data & Methods, downloads, status page, base-year bridge | not started |
| 3 | Briefings (ledger, drafts, approval PRs), newsletter, RSS | **in progress**: ledger, checker, 7 templates (CPI, IIP, GDP, PLFS, trade, MPC, daily note), review-PR workflow, briefings pages, RSS feeds. Left: newsletter (provider), weekly/monthly briefings, optional LLM step |
| 4 | Originals and tools: surprise composites, States, monsoon watch, RBI policy rule, Budget explorer | **in progress**: Analysis section (`/analysis/`, 2026-11-03): BoP stress episodes and forex intervention (`05-pages/analysis.md`); rupee drivers; policy rule and Budget explorer tools |
| 5 | Go public: name and domain, legal pages, analytics, permission from Econvitals | not started |

Update this table when a phase closes. A phase closes only when its checklist in `10-launch-checklist.md` (for Phase 5) or the relevant page checklists (for Phases 1–4) are ticked, and the healthcheck shows zero overdue series.

## Guidebook index

- `01-architecture.md`: data flow, schedules, free-tier limits, foreign-IP fallback
- `02-conventions.md`: FY and quarter labels, units, transforms, chart house style
- `03-data-sources.md`: catalogue of every source (agency, access, licence, quirks)
- `04-adding-an-indicator.md`: step by step, with definition of done
- `05-pages/`: one checklist per page (must include / must not include / done when)
- `06-operations-runbook.md`: daily routine, release days, breakages, revisions
- `07-editorial-policy.md`: briefings, the number ledger, corrections
- `08-original-measures.md`: methods for our own constructed measures and analyses
- `decisions/`: why things are the way they are (e.g. 0006: replicating private reference material)
- `09-rebranding.md`: renaming the site or switching the domain
- `10-launch-checklist.md`: going public
- `playbooks/`: task recipes for agents and RAs
- `decisions/`: why we chose what we chose (short ADRs)
