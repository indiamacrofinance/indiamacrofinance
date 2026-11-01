# 09 · Rebranding (changing the site name or domain)

The name is defined **only** in `site.config.yaml`.

## Rename

1. Edit `site.name`, `site.short_name`, `site.tagline` in `site.config.yaml`.
2. Replace `assets/brand/` wordmark files if they contain text (the mark itself is name-independent).
3. `make check` (the name check now looks for the *new* name outside config, so it catches nothing old). Also run `scripts/check_name.py --also "<old name>"` to catch leftovers.
4. Rebuild and deploy.
5. Optional: rename the GitHub repo or org. GitHub keeps redirects.

## New domain

1. Add the domain in Cloudflare Pages → Custom domains.
2. Set `site.url` in `site.config.yaml` (used for canonical URLs, RSS, sitemaps, OG tags).
3. Update the newsletter provider's sender domain (SPF/DKIM) if emailing from the domain.

## Rename of 2026-11-01

The site was first called "Econvitals India". It was renamed to the current name (site.name) by editing
`site.config.yaml` alone; `scripts/check_name.py --also "Econvitals India"` found no leftovers.
Still carrying the old spelling, on purpose or until the maintainer changes them:
- the GitHub org/repo (`econvitalsindia/econvitalsindia`; GitHub redirects after a rename),
- the Cloudflare Pages project and its `econvitalsindia.pages.dev` address (Pages projects
  cannot be renamed; connect the custom domain instead, or create a new project and set the
  repository variable `CF_PAGES_PROJECT`, which deploy.yml reads),
- the Buttondown username `econvitalsindia` (config `newsletter.buttondown_username`) and the
  newsletter's display name, set in Buttondown's settings,
- archived emails in `data/newsletter/morning/` (a record of what was sent),
- credits to econvitals.org, the inspiration, which stay.

## Newsletter visibility

`newsletter.enabled` sends the morning email; `newsletter.public` shows the sign-up box, the
About section and the privacy note. Since 2026-11-01: enabled, not public (existing
subscribers still get the email; no new sign-ups from the site).
