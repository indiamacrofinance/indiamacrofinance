# 0006: Replicating analyses from private reference material

- **Date:** 2026-11-03
- **Context:** the maintainer receives analyses (notes, decks) that are not public but are built
  from public data, and wants the site to carry the same analysis and keep it current. The repo
  and the site are public.
- **Decision:**
  1. The reference file is kept locally in `private/` (git-ignored; see `.gitignore`), with a
     `private/reference/README.md` that maps its tables and figures to site sections and records
     how closely we reproduce them. It is never committed, attached to a PR, or uploaded anywhere.
  2. The site **credits the authors and their institution** (author names, institution, title and
     date of the reference) at the top of each page and under each table or figure it follows,
     and says plainly that the numbers shown are our own computation from public data. It does
     not quote the reference's text, link to it, or describe where it was circulated.
     (Amended 2026-11-03: the maintainer asked for CAFRAL and the authors to be cited.)
  3. Only what can be rebuilt from our series and official releases goes on the site (AGENTS.md
     rule 5). Narrative, outside facts and internal matters in the reference stay out. Published
     literature may be cited for model assumptions, labelled as assumptions.
  4. Paid sources used in a reference (e.g. CEIC) are replaced with the official free source, or
     the piece is left out (rule 6).
- **First use:** the forex-intervention and BoP stress analysis (`05-pages/analysis.md`), credited
  to Vedant Agarwal, Nirupama Kulkarni and Gautham Udupa (CAFRAL), "Forex Interventions and
  Balance of Payments", June 2026.
- **Ask the maintainer** how to credit each new reference before publishing (names, institution,
  whether to credit at all).
