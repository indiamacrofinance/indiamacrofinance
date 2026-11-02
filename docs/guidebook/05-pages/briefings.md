# Briefings and blog

**Purpose:** Short, accurate written reads on the data, with AI drafts approved by a person, plus occasional human-written posts.

**Status (2026-11-02):** taken out of the site menu at the maintainer's request (not useful for now). The pages and RSS feeds still build at `/briefings/`; put the entry back in `site/src/lib/nav.js` (`more`) only when asked.

## Must include
- [x] Daily note (weekday evenings): market closes, today's releases, what's coming (table and chart still to add)
- [x] Release notes for CPI, GDP, IIP, PLFS, trade and the MPC decision (calendar-triggered, so holds get a note too)
- [x] Weekly briefing (Saturday; markets over the week, RBI weekly data, scheduled releases, where things stand)
- [x] Monthly briefing (template `registry/briefings/monthly.md`, drafted on the 1st, reviewed via PR)
- [x] Human-written posts ("From the editor": `product: editor`, playbook `playbooks/editor-post.md`)
- [x] Each item shows how it was drafted and that a person reviewed it
- [x] RSS per product (all, release notes, daily note)
- [x] Archive page (list; search and filter still to add)
- [x] Corrections note at the bottom of any corrected item (front matter `corrections:`)

## Must NOT include
- Any number not resolved from the ledger (see `07-editorial-policy.md`)
- Unattributed commentary, market rumours, or paywalled analysis
- Anything published without a human merge

## Phase
3
