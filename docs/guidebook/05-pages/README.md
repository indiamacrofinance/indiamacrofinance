# 05 · Page checklists

One file per page. Every file uses the same sections:

- **Purpose**: the question the page answers, in one or two sentences.
- **Must include**: a checklist. Tick `[x]` when it is live and verified, and note the PR number.
- **Must NOT include**: the guard-rails.
- **Series**: ids from `registry/series/` (planned ids are in `registry/backlog.yaml`).
- **Layout and charts**: section order and chart types.
- **Done when**: the acceptance test for the page.
- **Phase**: when it is built.

The machine-readable twin of each file is `registry/pages/<page>.yaml`. When they disagree, fix the yaml to match this file, or update this file in the same PR.

| Page | File | Phase |
|---|---|---|
| Home dashboard | home.md | 1 |
| Growth | growth.md | 2 |
| Inflation | inflation.md | 2 |
| Jobs | jobs.md | 2 |
| Activity | activity.md | 2 |
| Money & banking | money-banking.md | 2 |
| Markets | markets.md | 2 |
| The rupee: what's moving it | rupee.md | live |
| Fiscal | fiscal.md | 2 |
| External | external.md | 2 |
| States | states.md | 4 |
| Calendar | calendar.md | 1 |
| Briefings | briefings.md | 3 |
| Data & Methods | data-methods.md | 2 |
| About | about.md | 1 |
| Status (internal) | status.md | 2 |
| Tools (index) | tools.md | 4 |
| Analysis (hub and pieces) | analysis.md | live |

## The menu
Every page and every `<h2>` section a reader might look for is in the header menu, defined in `site/src/lib/nav.js`. When you add a page or section, add it there. Give the `<h2>` a fixed `id` (e.g. `<h2 id="fuel">`) and link to `/page/#id`. Never link to an id derived from heading text that changes with the data (e.g. "Consumer prices, Sep 2026"). Search (Pagefind) indexes everything inside `<main>` automatically on `make build`.
