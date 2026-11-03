# What changed (`/updates/`)

**Purpose:** Which numbers changed on a given day? Every series with new or revised values, day by day.

## Must include
- [x] The last 30 days on which data were stored, newest first, with a chip per day to jump to it
- [x] Per day: each series (linked to its data page), its area, what changed ("2 new values (to Sep 2026)", "1 revised", or "added, with N values of history") and its latest value
- [x] Pointers to the release calendar and the live status dashboard

## How it works
`changes()` in `pipelines/build/site_data.py` writes `changes.json`. Every stored value carries a `vintage`: the date it first appeared, or the date a publisher last changed it (`pipelines/core/store.py`, `upsert`). Grouping by vintage gives each day's changes; `data/revisions/<id>.csv` (`new_vintage`) says how many of them were revisions. The page rebuilds with every deploy, so it is as fresh as the last bot run. Panels (state, item and entity tables) are included and counted by value.

## Must NOT include
- Interpretation: it is a log. Analysis belongs on the topic pages.

## Phase
live (2026-11-03)
