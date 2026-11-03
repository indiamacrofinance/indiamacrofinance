# Playbook: QA the site

1. `make build`. Zero errors and zero broken internal links.
2. `make check`. The name check, registry validation and tests pass.
3. Screenshot every changed page at 1280 px and 375 px: `uv run --with playwright==1.55.0 python scripts/screenshot.py <paths>` (PNGs in `site/screenshots/`; prints console errors and sideways overflow). Look for overflow, overlapping labels, and empty charts.
4. Numbers: for each changed chart, compare the latest value shown against `data/series/<id>.csv`.
5. Each chart's footer has source, base year (if any) and unit. Download buttons appear only for `downloadable: true` series.
6. Attach the screenshots to the PR.
