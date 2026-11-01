# States (India-specific)

**Purpose:** How do states compare on growth, prices, jobs and public finances?

## Must include
- [ ] (Selector done 2026-10-29; maps wait for a checked boundary file) State selector, plus choropleth maps of all-India
- [x] GSDP growth (real), latest year with at least twenty states (per-capita NSDP still to add)
- [x] State CPI y/y (monthly)
- [x] PLFS unemployment by state (annual, calendar year, with sample-size caveat)
- [x] State fiscal deficit, debt, interest (% GSDP) from RBI Handbook tables 164/170/176 over Table 21 GSDP (interest/revenue receipts still to add)
- [x] State profile page `/states/<state>` with all of the above in one place (`states/[slug].astro`, with ranks)
- [ ] Map uses official boundaries from Survey of India–consistent GeoJSON (check the licence)

## Must NOT include
- Maps with disputed or non-official boundaries
- District-level data (out of scope for now)
- Rankings presented as league tables without uncertainty notes

## Phase
4
