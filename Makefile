# See AGENTS.md → Commands.
PY ?= uv run python

.PHONY: setup check test update update-auto india-update build dev archive-raw briefings morning-pack morning-check

setup:
	uv sync
	cd site && npm install

check:
	$(PY) scripts/validate_registry.py
	$(PY) scripts/check_name.py
	$(PY) -m pipelines.briefings.draft --check-only
	uv run pytest -q

test:
	uv run pytest -q

# make update SOURCE=<source name or series id>
update:
	@test -n "$(SOURCE)" || (echo "usage: make update SOURCE=<source-or-series-id>" && exit 2)
	$(PY) -m pipelines.run $(SOURCE)

update-auto:
	$(PY) -m pipelines.run --fetch auto

# Run from a machine in India: fetches every `fetch: manual` series and opens a PR.
india-update:
	git pull -q --rebase origin main
	-$(PY) -m pipelines.run --catch-up
	git add data
	@if git diff --cached --quiet; then echo "india-update: no data changes"; else \
	  git commit -q -m "data: india-update $$(date +%F)" && \
	  git pull -q --rebase -X theirs origin main && git push -q origin main && \
	  echo "india-update: pushed to main; the site redeploys in a few minutes"; fi

build:
	$(PY) -m pipelines.build.site_data
	cd site && npx astro build && npx pagefind --site dist

dev:
	$(PY) -m pipelines.build.site_data
	cd site && npx astro dev

archive-raw:
	@echo "not implemented yet: monthly bundle of data/raw/ as a GitHub Release asset"

# Draft release notes for today's releases (the briefing workflow does this on GitHub).
briefings:
	$(PY) -m pipelines.briefings.draft

# Morning newsletter (runbook "Newsletter"): pull the latest data, write today's fact pack,
# then check the AI's draft in newsletter/drafts/<date>.md. Pushing the draft sends it.
morning-pack:
	git pull --rebase --autostash -q
	$(PY) -m pipelines.newsletter.morning pack

morning-check:
	$(PY) -m pipelines.newsletter.morning check
