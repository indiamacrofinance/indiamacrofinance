# Search (header overlay and `/search/`)

**Purpose:** Type what you are looking for, in your own words ("forex reserves", "jobs", "car sales"), and land on the right page first.

## Must include
- [x] Pagefind index of every page's `<main>`, built by `make build`; the briefings archive is left out (`search={false}`, it is off the menu)
- [x] Other names people use for each series ("forex reserves" for FX reserves, "factory output" for IIP), and the topic words for each topic page, so the main page for a topic comes first (`site/src/lib/search.js`)
- [x] Each result shows its page's summary (the first `.lede`), not a raw excerpt
- [x] A quality check on common queries: `make search-check`

## How it works
- **Terms.** `Base.astro` puts hidden text at the top of `<main>`, which Pagefind indexes: the page title, its topic words (`pageTerms`, by path) and, for data pages, the series' main words at weight 10 and its other names at weight 5 (`seriesTerms`). Main words are listed by id in `HEADLINE` (the home page's key indicators) and `ALSO_MAIN`. Other names come from `ALIASES`, patterns matched on the series title and id. Keep a pattern narrow: a broad one (e.g. every series with "repo" in it) pulls minor series above the main one.
- **Left out of the index** (`data-pagefind-ignore`): tables of numbers and citations on data pages, and the lists of every series on Data, Status and What changed, which otherwise outrank the series pages themselves.
- **Ranking** is set once in `window.searchOptions` (`Base.astro`) and used by both search boxes: less weight on repeated words and on short pages, more on exact matches.
- **Result text.** Pagefind's excerpt could show the hidden terms, so `processResult` swaps in the page's summary (`data-pagefind-meta="summary"` on the first `.lede`). Give a new page a `.lede`, and tag it.

## Checking it
`make build && make search-check` runs 64 common queries against the built index, typing each one letter by letter as the search box does (Pagefind's scores depend on which parts of the index are already loaded), and reports where the expected page ranks. It fails below 50 first-place hits or 60 in the top three. On 2026-11-04 it scored 55 and 62, up from 20 and 34 before this work. Add a query to `CASES` in `scripts/search_check.mjs` when a search goes wrong, then fix the terms rather than the expected answer.

## Adding a page or series
- A new topic page: add its path and words to `PAGES` in `search.js`.
- A new main series for a topic: add it to `HEADLINE` or `ALSO_MAIN`.
- A new kind of series people call by another name: add a narrow `ALIASES` pattern.

## Must NOT include
- Words that are not true of the page. Terms are for other names of the same thing, not for related topics.

## Phase
live (2026-11-04)
