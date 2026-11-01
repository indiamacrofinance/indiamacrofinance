# 06 · Operations runbook

## Daily routine (about 10 minutes, one person)

1. **Morning (by 10:00 IST):** open the Status page. Triage any new `scraper-broken` issue: assign it, or fix it with `playbooks/fix-scraper.md`.
2. **Evening (after 19:00 IST):** run `make india-update` from a machine in India. It opens a PR. Check the diff (new periods only, or revisions?) and merge.
3. **If a briefing PR is open:** review and merge it (see `07-editorial-policy.md`). Unmerged drafts expire after 24 h.

## Release days

For CPI, GDP, IIP, PLFS, the MPC decision and trade, follow `playbooks/release-day.md`. In short: confirm the series updated, eyeball the chart, spot-check against the press release, then review the release-note PR.

## When a scraper breaks

- The data on the site stays at the last good value and the series shows a stale badge. **Nothing is broken publicly**, just late.
- Typical causes: the agency changed the file layout, the URL pattern changed, a foreign-IP block, or the site is down.
- If the site is just down, wait one cycle. If the layout changed, follow `playbooks/fix-scraper.md`, using the archived raw file as a new fixture.

## Revisions

Revisions are normal (GDP, IIP, EPFO revise often). The pipeline stores every vintage. Revisions above a series' `revision_alert` open a `large-revision` issue. Confirm against the press release and close it. Don't "fix" revisions by hand.

## A published value looks wrong

Sometimes a publisher's feed carries an obvious error, e.g. a value attached to the wrong period. Don't edit the CSV. Add an `exclude` entry to the series yaml: `{period, added, reason}`, with the evidence in `reason`. The value is then never published, and the series page shows it under "Values left out". Report it to the publisher if possible, and remove the entry once they fix the feed. Example: `plfs_ur_quarterly_urban`, April–June 2019.

## Base-year changes

When an agency rebases (as in 2026 for GDP, CPI and IIP):
1. Create new series ids for the new base and keep the old ones (mark them `discontinued: <date>`).
2. Build or refresh `<id>_linked` using the documented splice method.
3. Point pages at the new or linked ids, and add a note on the page.

## Manual queue etiquette

- Run it from India, on a normal residential or office connection.
- Don't run it more than twice a day (be polite to government servers).
- The shared HTTP helper waits at least one second between calls to the same host
  (`POLITE_DELAY` in `pipelines/core/http.py`). Transient failures retry with
  exponential backoff; there is no backoff sleep after the final failed attempt.

## Monthly

- Check the Actions minutes used (Status page).
- Archive `data/raw/` from the month as a GitHub Release asset (`make archive-raw`).
- Refresh `registry/calendar/` from the official calendars (MoSPI ARC, OEA ICI/WPI ARC, RBI MPC schedule, Commerce SDDS calendar). Check the coming month's dates for public holidays (the build only shifts weekends) and confirm any `estimated: true` dates you can. Extend each file so it always covers at least the next three months. At the start of each financial year, add the new ARC files and MPC schedule.

## Secrets

Kept in GitHub Actions secrets only: `LLM_API_KEY`, `NEWSLETTER_API_KEY`, `CLOUDFLARE_API_TOKEN`. Never in code, the registry, issues or chat logs.

## Newsletter

**What goes out:** one short email a day on India's economy: what is new in the data, markets, the wider picture, what is due. It is written with AI by the maintainer, so there are **no API costs**: the AI is whatever they already use (Claude Code, claude.ai or any chat). Everything around the writing is automated.

**The daily routine (about five minutes):**
1. `make morning-pack`: pulls the latest data and writes `newsletter/packs/<date>.md` (the writing rules plus every fact as a token, e.g. `{{cpi_headline_inflation.latest}} = 5.54%`) and saves those exact facts to `newsletter/drafts/<date>.facts.json`.
2. Have an AI write the email from the pack. In Claude Code, type `/morning`: it does steps 1-4, shows you the preview, and pushes only after you say yes. Elsewhere, paste the pack into the chat and save the reply as `newsletter/drafts/<date>.md`.
3. `make morning-check`: the briefing checker rejects any number typed outside a token and any unknown token, and writes a preview (`newsletter/packs/<date>.preview.md`). Fix and repeat until it passes.
4. Commit and push the draft and its `.facts.json`. The `newsletter-send` workflow re-checks it, fills in the values from the saved facts (so the email matches what you checked, even if the data moved since), sends it through Buttondown, and archives it in `data/newsletter/morning/`. `data/newsletter/sent.json` stops a second send that day; only today's draft (India time) is sent.

No draft that day means no email. Optional subject: front matter `subject: "..."` at the top of the draft (tokens allowed).

**One-time setup (maintainer):**
1. Create a free Buttondown account (free for the first 100 subscribers; the plan assumes at most one email a day). Note your username.
2. Buttondown → Settings → API: copy the key into the GitHub repo secret `BUTTONDOWN_API_KEY` (repo Settings → Secrets and variables → Actions). Never paste it into chat, issues or files.
3. In `site.config.yaml`, set `newsletter.buttondown_username` and `newsletter.enabled: true`, then push. The signup box appears on the home and About pages; sign-ups confirm by email (double opt-in).
4. Subscribe yourself, confirm, and do the routine above once.

**API mode (in use since 2026-10-29):** with `newsletter.writer: "api"` and an `ANTHROPIC_API_KEY` secret, the 07:30 IST `newsletter-morning` workflow writes and sends the email by itself (`morning auto`: one retry on checker failure, then the fixed template in `registry/newsletter/morning.md`). Measured 2026-10-29: about 12,000 input + 1,800 output tokens per email, about $0.08 a day on `claude-opus-5-5`, about $0.002 on `claude-haiku-5-5` (`newsletter.llm_model`).

**Held sign-ups:** Buttondown's spam filter ("firewall", buttondown.com/settings/firewall, set to "Accept and mark as blocked") can hold a sign-up. The reader is told it is under review and that the maintainer will take care of it. Check Buttondown → Subscribers for anyone marked **Blocked** every few days and unblock real people; Buttondown then sends their confirmation email. `.github/workflows/newsletter-status.yml` lists subscribers (masked) with their status.

**The weekly digest** (`digest.py`, `newsletter.yml`) still exists but runs only by hand, as a Buttondown draft, because the morning email uses the free plan's one-email-a-day allowance.
