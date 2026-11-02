# Data & Methods

**Purpose:** Where every number comes from, how we transform it, and how to download it.

## Must include
- [x] Shared formatting preserves missing currency values; ingestion rejects invalid ISO dates before publishing (regression tested)
- [x] Table of every series: id, title, source (with link), frequency, unit, base year, last updated, licence, download (if allowed). Generated from the registry
- [x] Per-series page `/data/<id>`: chart, metadata, revision history (vintages), CSV download, citation, verification record
- [x] Methods for every Original measure (rendered from `08-original-measures.md` at /methods/)
- [x] Base-year bridge: overlap-period comparisons for GDP (10 quarters) and CPI (2025) on the Methods page (`base_bridge.json`); no splicing
- [x] Bulk download (zip of all downloadable series), regenerated with every build (`/downloads/all-data.zip`, written by `write_bulk_zip` in site_data.py)
- [x] Citation format: "<site name> (<year>). <series title>. Retrieved <date> from <url>. Original source: <agency>."
- [x] Catalogue sorting uses a copy so production JSON caching cannot change the shared catalogue order

## Must NOT include
- Downloads for `downloadable: false` series

## Phase
2
