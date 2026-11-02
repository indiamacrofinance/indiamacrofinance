# 02 · Conventions

Apply these everywhere: data files, charts, tables, briefings.

## Time

- **Financial year** runs April–March. 2025-26 is labelled **FY26** in charts and **2025-26** in tables and prose where space allows.
- **Quarters** are financial-year quarters: Apr–Jun 2026 = **Q1 FY27**, Jul–Sep = Q2, Oct–Dec = Q3, Jan–Mar = Q4.
- **Storage**: `period` is the ISO date of the period start (`2026-07-01` for Q2 FY27 or for July 2026). `freq` (D/W/F/M/Q/A) is recorded in meta.
- Validation requires a real calendar date written exactly as `YYYY-MM-DD` for both series and panels; invalid dates block the update before storage.
- **Fortnightly** banking data uses the reporting Friday as `period`.
- **Vintage**: every stored row carries `vintage` (the release date of that value), so revisions are traceable.
- **Times** are IST. "As of" stamps show the date and, for markets, the time.

## Units and number formatting

| Kind | Unit | Example |
|---|---|---|
| Domestic money aggregates (fiscal, credit, GST) | ₹ lakh crore (1 lakh crore = 10¹²) | ₹1.87 lakh crore |
| Smaller domestic amounts | ₹ crore | ₹4,512 crore |
| External sector (trade, reserves, FDI) | US$ billion | $702.3 bn |
| Rates, growth, shares | % to 1 decimal | 5.4% |
| Rate changes | basis points | +25 bp |
| Index levels | as published, thousands separator | 25,312 |

- Digit grouping is **international** (25,312,000), not Indian (2,53,12,000), because the audience is international economists. Prose may say "₹2.5 crore".
- A **crore ↔ billion toggle** on money charts is a Phase 2 feature: 1 crore = 10 million; 1 lakh crore = 1 trillion.
- Minus signs are the true minus `−` in display, never a hyphen.
- Missing values display as `–`, including currency amounts; they must never display as zero.

## Transforms (names used in `registry/series/*.yaml`)

| Code | Meaning |
|---|---|
| `level` | As published |
| `yoy` | % change on the same period a year earlier |
| `mom` | % change on the previous month (not annualised) |
| `mom_saar` | Month-on-month, seasonally adjusted, annualised. Only for series we seasonally adjust; document the method |
| `qoq_saar` | Quarter-on-quarter, seasonally adjusted, annualised |
| `3mma`, `12mma` | Moving averages |
| `7dma` | 7-day average for noisy daily series (calendar window, at least 5 observations) |
| `7dma_yoy` | % change of the 7-day average on the same date a year earlier |
| `diff` | First difference (used for rates, in bp) |
| `share_gdp` | % of nominal GDP (use the matching FY's GDP and note the vintage) |

**Indian headline growth is y/y.** MoSPI and RBI publish y/y, and readers expect it. Momentum measures (3m saar) are extras, clearly labelled, and seasonally adjusted by us with the method documented in `08-original-measures.md`.

## Base years

- 2026 rebasing: **GDP → 2022-23**, **CPI → 2024**, **IIP → 2022-23**. WPI as published.
- Never plot two bases on one axis without linking. A linked series has its own series id with suffix `_linked`, and its method goes in `08-original-measures.md`.
- Every chart footer shows the base year when one applies.

## Chart house style

- Title says what is measured. Subtitle gives the unit and transform ("% y/y"). The footer gives the source plus "author's calculations" when transformed, and the site name from config.
- Latest value is labelled directly on the line. Avoid legends when direct labels fit.
- Reference lines: RBI 4% target with the 2–6% band shaded on CPI charts, and zero lines on growth charts.
- Recession or shock shading: COVID (Q1 FY21) only, unless a page spec says otherwise.
- Colours come from `site.config.yaml` → `brand.colors`, plus a fixed categorical palette (Phase 1, in `site/src/styles/palette.ts`). Never use red/green as the only difference.
- Every chart has **Download CSV** (if `downloadable: true`), **Download PNG**, **Copy link** and **Cite**.
- Default window: 5 years for monthly and quarterly data, 1 year for daily, with a selector for longer.

## Language

- Plain, precise English, with no hype. "Rose 0.3 pp to 5.4%", not "surged".
- Spell out abbreviations once per page: Index of Industrial Production (IIP).
- Measures we construct are tagged **Original** and link to their method.
