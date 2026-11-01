<p align="center"><img src="assets/brand/mark.svg" alt="" width="72"></p>

# IndiaTracker

**A free, daily-updated read on the Indian economy, straight from the official data.**

**Live site: [indiatracker.pages.dev](https://indiatracker.pages.dev)**

IndiaTracker brings together what India's statistical agencies, the Reserve Bank and the ministries publish. That covers growth, prices, jobs, activity, money and banking, markets, public finances, the external sector and the states. It updates as new numbers come out. Every chart names its source, and every series has its own page with its history, method and a download where the licence allows.

It is an independent project. It is not affiliated with the Reserve Bank of India, the Government of India or any data provider. It is inspired by [Econvitals](https://econvitals.org), Jason Furman's dashboard of the U.S. economy, and is not affiliated with it either.

## What's on it

| Page | Highlights |
|---|---|
| **Growth** | Quarterly and annual GDP and GVA, by sector and by spending; RBI's projections against outturns, quarter by quarter |
| **Inflation** | CPI (2024 base) by group and for all 358 items; core CPI; trimmed means, weighted median and diffusion indices; goods vs services; food watch; momentum vs base effects; uncertainty bands around RBI's path; WPI and CPI-IW |
| **Jobs** | PLFS unemployment and participation; EPFO payroll |
| **Activity** | IIP, core industries, electricity demand, GST and e-way bills, fuel, vehicle sales and registrations, air traffic, UPI |
| **Money & banking** | Policy corridor, MPC decisions and votes; transmission to bank lending and deposit rates by policy cycle; liquidity; credit by sector and what drives it; credit–deposit gap; money supply; CP and CD rates; RBI's outlook and risk scenarios |
| **Markets** | Indices, the rupee, crude and gold, the G-sec yield curve, Sensex valuation (P/E, P/B), FPI and mutual fund flows |
| **Fiscal** | Centre's monthly accounts against the Budget, tax collections, Budget explorer, general government deficits and debt |
| **External** | Trade, the balance of payments, remittances, reserves, external debt, REER/NEER, ECBs |
| **States** | GSDP, CPI, unemployment and state finances, with a profile page for every state |
| **Calendar, briefings, tools, methods, status** | Release calendar (with .ics), short data notes, a policy-rule tool, India against its peers, how each measure is built, and the freshness of every series |

As of November 2026 the site has 343 series from 56 sources and about 360 pages.

## Measures we build ourselves

Some series are calculated here rather than published by an agency. They are marked **Original** on the site, and [Methods](https://indiatracker.pages.dev/methods/) explains each one and how it was checked. Examples:

- **Underlying inflation from the 358 CPI items:** trimmed means, the weighted median, CPI excluding food, fuel and precious metals, and diffusion indices. MoSPI does not publish item weights, so they are recovered from its own index tree. The results reproduce the values in RBI's Monetary Policy Report to rounding.
- **Transmission:** how far bank lending and deposit rates moved in each easing or tightening cycle. It matches RBI's own table.
- **Contributions** to CPI inflation, GDP growth and bank credit growth.
- **Uncertainty bands** around RBI's CPI projections, built from RBI's own past forecast errors.

The main ones are pinned by tests to the published figures they reproduce (RBI's tables, MoSPI's indices), in [`tests/`](tests).

## How the data stays current

- **Data bots** are GitHub Actions workflows (`.github/workflows/bot-*.yml`, assignments in [`registry/bots.yaml`](registry/bots.yaml)). They fetch markets data several times a day and MoSPI, RBI and ministry releases every evening (IST). They commit only when something changed, and the site redeploys after every commit.
- **Validation before publishing:** each value is checked against a plausible range. A failed fetch never overwrites good data; it marks the series stale and opens a `scraper-broken` issue, which closes itself when the source recovers.
- **Sites that block servers outside India** (Grid-India, EPFO) are fetched with `make india-update` from a machine in India. The same command re-runs any automatic source that has fallen behind.
- **Raw files** are archived for every fetch, and revisions are logged in [`data/revisions/`](data/revisions).

## Repository layout

```
site.config.yaml   the site's name, colours, contacts and switches (the name lives only here)
registry/          one YAML file per series: source, licence, unit, frequency, checks, pages
pipelines/         Python: one module per source (fetch -> parse), derived measures, site build
data/              published series (CSV), metadata, status, revision log
site/              Astro + Observable Plot front end
tests/             parser tests against archived files, and checks against published figures
docs/guidebook/    how everything works: architecture, conventions, sources, page checklists, runbook
```

## Running it locally

You need Python 3.12 with [uv](https://docs.astral.sh/uv/), and Node 24.

```bash
uv sync                            # Python dependencies
(cd site && npm ci)                # front-end dependencies
make check                         # tests, registry checks, name check
make update SOURCE=mospi_cpi       # run one source end to end
make build                         # build the site into site/dist
make india-update                  # from India: manual sources + catch-up, pushed to main
```

New to the code (person or coding agent)? Start with [`AGENTS.md`](AGENTS.md), then [`docs/guidebook/00-start-here.md`](docs/guidebook/00-start-here.md).

## Data and licences

The numbers belong to their publishers. Government data are used under the [Government Open Data Licence – India](https://data.gov.in/government-open-data-license-india) or the publisher's terms, with attribution on every chart. Some series, such as exchange index levels, BSE valuation ratios and industry-body vehicle data, are shown with attribution but are not offered for download. Their registry entries carry `downloadable: false`.

## Contributing

Issues and pull requests are welcome. Report a wrong number, a broken scraper or a missing series in [Issues](../../issues). For code, read [`AGENTS.md`](AGENTS.md) and the relevant page checklist in [`docs/guidebook/05-pages/`](docs/guidebook/05-pages), and run `make check` before opening a pull request. Workflows on pull requests from forks run after a maintainer approves them.

## Maintainer

Built and maintained by Bishmay Barik. Feedback and corrections: [bishmaykbarik@gmail.com](mailto:bishmaykbarik@gmail.com).
