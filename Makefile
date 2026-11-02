# See AGENTS.md → Commands.
PY ?= uv run python

.PHONY: setup check test update update-auto india-update build dev archive-raw briefings morning morning-again morning-preview morning-pack morning-check

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

# Send today's morning email now (the same GitHub workflow that runs at 07:30 IST): fetches fresh
# data, writes it with AI, checks it and sends it to every subscriber. One email a day: a second
# run on the same day sends nothing.
morning:
	gh workflow run newsletter-morning.yml --ref main
	@echo "Started. The email arrives in about 2-3 minutes; progress: gh run list --workflow newsletter-morning.yml"

# Read today's email yourself without sending it: pulls the data the bots have committed, writes
# the email with Claude (needs ANTHROPIC_API_KEY in your shell; a few cents), checks it, and opens
# it in the browser. Nothing is sent or committed.
morning-preview:
	git pull --rebase --autostash -q
	$(PY) -m pipelines.newsletter.morning auto --preview newsletter/packs/preview.md
	open newsletter/packs/preview.html

# Send another one today anyway (a test): `make morning-again`.
morning-again:
	gh workflow run newsletter-morning.yml --ref main -f again=true
	@echo "Started (sends even if today's email already went out)."

# Morning newsletter by hand (runbook "Newsletter"): pull the latest data, write today's fact pack,
# then check the AI's draft in newsletter/drafts/<date>.md. Pushing the draft sends it.
morning-pack:
	git pull --rebase --autostash -q
	$(PY) -m pipelines.newsletter.morning pack

morning-check:
	$(PY) -m pipelines.newsletter.morning check
