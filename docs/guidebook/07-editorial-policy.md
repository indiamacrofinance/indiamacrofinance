# 07 · Editorial policy (briefings and newsletter)

## Principles

1. **AI drafts, a person approves.** Every briefing is opened as a PR by `briefing.yml`. Only a human merge publishes it and sends the email. Agents never merge briefing PRs.
2. **The model never types a number.** Numbers come from a **ledger** and nothing else.
3. **Only our data plus official releases.** Context comes from our series and from official press releases (RBI, MoSPI, PIB, ministries). No news scraping, rumours or paywalled research in Phase 3.
4. **Say who wrote it.** "Drafted by AI from the site's data; reviewed by <role>", or "Written by <name>".

## The ledger

Implemented in `pipelines/briefings/` (Phase 3, live).

- **Templates** live in `registry/briefings/<name>.md`: front matter (`name`, `title`, `trigger` series, `views`) and a body with **no digits**. Every number is a token: `{{<series_id>[:<transform>].<fact>}}`, e.g. `{{cpi_headline_inflation.latest}}`, `{{cpi_core_index:yoy.change_phrase}}`. Fixed facts such as RBI's target come from `registry/briefings/constants.yaml` as `{{const.<name>}}`, each with a source.
- **Facts** per view (`ledger.py`): `latest`, `latest_period`, `prev`, `prev_period`, `year_ago`, `year_ago_period`, `change`, `change_yoy`, `direction` (rose/fell/was unchanged), `change_phrase` ("up 0.71 percentage points" / "unchanged"), `change_phrase_yoy`. Precision follows the publisher's (CPI 2 decimals, GDP 1).
- **Ledger file:** each draft saves `data/briefings/<date>-<name>.json`, giving for every token the series, transform, period and source.
- **Checker (`check.py`):** fails a template or draft if any digit appears outside a token, or a token is not in the ledger. `make check` runs it on every template.
- **Direction words** come from tokens (`direction`, `change_phrase`), so they cannot contradict the numbers. Write sentences that read correctly whichever way the data moved.

## Products and triggers

| Template | Product | Drafted when |
|---|---|---|
| `cpi`, `iip`, `gdp`, `plfs`, `trade` | release-note | the trigger series records a new observation that day |
| `mpc` | release-note | the calendar has an "MPC policy decision" on that day (`trigger_calendar`), so holds get a note too |
| `daily` | daily-note | weekdays, when the day's market closes are recorded (`trigger_weekdays_only`). **Auto-published** (see below) |
| `weekly` | weekly-briefing | Saturdays (`trigger_weekday: 5`); reviewed |

Feeds: `/briefings/rss.xml` (all), `/briefings/release-notes.xml`, `/briefings/daily.xml`. The newsletter is the morning email described at the end of this page (written with AI, approved by the maintainer). The older weekly digest of published briefings is kept as a manual, draft-only option (runbook: "Newsletter").

## The one exception: the daily note is auto-published

On 2026-10-28 the maintainer approved publishing the **daily note** without human review, because it is built only from market closes and the release calendar. It still has to pass the checker, and it says on the page that it was auto-published. The template carries `auto_publish: true`. **No other template may set it without the maintainer's explicit approval**, recorded here with a date.

## Workflow

`briefing.yml` runs after each daily update. A template is drafted when its trigger series has an observation first recorded that day. The drafts are committed to a `briefing/<date>-<run>` branch and a pull request is opened with the reviewer checklist. **Merging is the approval that publishes.** If the repository does not allow Actions to open pull requests, the workflow opens an issue with a link to create one. Drafts are currently template-only (no AI). An LLM drafting step can be added later behind the same checker (`site.config.yaml → briefings.llm_model`).

## Tone

Plain and precise. Lead with what changed and why it matters. One idea per paragraph. No forecasts of our own unless they are tagged Originals. No policy advocacy.

## Reviewer checklist (on the PR)

- [ ] Checker passed (CI)
- [ ] Spot-check 3 numbers against the press release
- [ ] No claims beyond the data and official text
- [ ] Headline is accurate, not sensational
- [ ] Charts render

## Corrections

Fix the source of the error (data or prompt), not just the text. Add a dated "Correction:" line at the bottom of the published item. If it was emailed, include a correction note in the next edition.

## Cost control

The model is set in `site.config.yaml → briefings.llm_model`. Before choosing, benchmark at least two models (one cheap) on 10 past releases and compare checker pass rate, reviewer edits and cost. Log the cost per draft in the PR body.

## Morning newsletter

**Subject since 2026-11-02: the rupee.** Each morning: how the rupee moved against the dollar on the last completed trading day (and over the week, month and quarter), why, and the background, so the reader can explain any move. It is written and sent automatically by Claude Opus 5.5 through the API (`writer: "api"`); the maintainer can still write a day's email by hand with `/morning` (one email a day either way). On hold 2026-11-01 to 11-02, resumed with this focus at the maintainer's request.

Rules: it may use only the ledger's facts (the `rupee.*` facts from `pipelines/build/rupee.py`, the template's `views` and the calendar); every number must be a token and the checker must pass, or the fixed template is sent. **Causes** may be stated only as the rupee-drivers model's attribution (08-original-measures.md, "Rupee drivers") or as the facts' own readings (e.g. falling reserves "consistent with RBI selling dollars"). Drivers the model dropped may be reported but not credited. Candidates for the unexplained part come only from the facts (RBI via reserves, portfolio flows) or, in general terms, importers' and exporters' dollar demand, never as certain. No news, quotes, forecasts or outside facts. When no trading day is new since the last email (weekends, holidays), it leads with the week and month. Each email is archived with its facts in `data/newsletter/morning/`. Details: 06-operations-runbook.md ("Newsletter").

## Corrections

When a published briefing carried an error, fix the text and add to its front matter:

```yaml
corrections:
  - date: 2026-11-02
    note: "An earlier version gave the wrong month for the IIP figure."
```

The page then shows a "Correction" box at the foot of the briefing. Never silently edit a published number. Publishers' own revisions are not corrections: they are recorded in each series' revision history.
