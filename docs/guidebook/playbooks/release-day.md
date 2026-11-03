# Playbook: release day

**Input:** a calendar release (e.g. CPI, 12th, 16:00 IST). **Output:** updated series and a release-note PR.

1. After the release time, run `make update SOURCE=<id>` for the release's series (or wait for the bot that owns it, see `registry/bots.yaml`; or run that bot by hand: Actions → `<name>-bot` → Run workflow).
2. Open the press release. Check the headline and 2 components against `data/series`.
3. Check the page chart renders and the home tile updated.
4. Phase 3+: `briefing.yml` opens a release-note PR. Review it with `07-editorial-policy.md`'s reviewer checklist and merge.
5. If the numbers disagree: **do not publish**. Open an issue and tag the maintainer.

## Quarterly balance of payments (RBI, about 80-90 days after the quarter)
1. The rbi bot runs `rbi_bop` (headline text) and `rbi_bop_quarterly` (Statements I and II, full detail, revisions of the last five quarters). Check `bop_bpm6_current_account` for the new quarter against the release's Table 1.
2. `make build` and open `/analysis/bop-stress/`. The current episode is `open` in `registry/analysis/bop_stress_episodes.yaml`: the build adds the new quarter if the rupee weakened and RBI was a net seller of dollars, otherwise the page says it stopped and why. Check the "Latest quarters" table agrees.
3. If the episode has clearly ended (the rupee has stabilised for two quarters or more), close it in the yaml: set `end` to its last quarter and remove `open`. If a new episode starts, add it at the top of the yaml with a fresh `id` (`current` moves to it; rename the old one to its year). Tell the maintainer: the findings text on the page changes with it.
4. Every number on the analysis pages is recomputed; past-episode totals are pinned in `tests/test_bop_stress.py`. If RBI revises old quarters enough to break a pinned value, check the revision against the Handbook or Statement before updating the test.
5. RBI's dollar dealing (Bulletin Table 4) and the Handbook (each August) arrive on their own schedule through `rbi_fx_operations`; the Handbook's arrival also refreshes the long BoP history.
