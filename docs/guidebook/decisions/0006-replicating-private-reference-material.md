# 0006: Replicating analyses from private reference material

- **Date:** 2026-11-03
- **Context:** the maintainer receives analyses (notes, decks) that are not public but are built
  from public data, and wants the site to carry the same analysis and keep it current. The repo
  and the site are public.
- **Decision:**
  1. The reference file is kept locally in `private/` (git-ignored; see `.gitignore`), with a
     `private/reference/README.md` that maps its tables and figures to site sections and records
     how closely we reproduce them. It is never committed, attached to a PR, or uploaded anywhere.
  2. The site and the public guidebook present the analysis as **our own computation from public
     data**. They do not name, quote, cite or describe the reference, its authors or its
     institution, and do not reproduce its numbers except where our own computation gives them.
  3. Only what can be rebuilt from our series and official releases goes on the site (AGENTS.md
     rule 5). Narrative, outside facts and internal matters in the reference stay out. Published
     literature may be cited for model assumptions, labelled as assumptions.
  4. Paid sources used in a reference (e.g. CEIC) are replaced with the official free source, or
     the piece is left out (rule 6).
- **First use:** the forex-intervention and BoP stress analysis (`05-pages/analysis.md`).
- **Revisit** if the maintainer gets permission to credit a reference; then add a credit line,
  agreed with its authors, on the analysis page and here.
