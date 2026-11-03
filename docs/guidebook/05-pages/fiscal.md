# Fiscal

**Purpose:** Is the Union government on track for its budgeted deficit, and how are revenues and capex doing?

## Must include
- [x] Fiscal deficit FYTD as % of Budget Estimate, vs the same point in the previous 3 years
- [x] Revenue: net tax to Centre, non-tax, "other receipts" (CGA and the Budget have no separate disinvestment line in these tables), FYTD vs BE (gross tax is in the tax-heads section)
- [x] Spending: revenue expenditure, capital expenditure, interest payments, FYTD vs BE
- [x] GST gross collections (monthly, y/y)
- [x] Tax collections by head (CGA DTL3, from FY 2015-16): gross, direct (corporate + income), STT, customs, excise
- [x] Union Budget headline numbers (BE, RE, Actuals) for the current and last FY (panels `budget_be`, `budget_re`, `budget_actuals` from Budget at a Glance; table built into `budget.json`)
- [x] Budget record: each year's BE, RE and Actual for the fiscal deficit (% of GDP), capital expenditure and net tax, from every Budget since 2019-20 (archived PDFs, read once by `budget/glance.py`; Actuals from 2017-18). Chart and table in `#budget-record`, data in `budget.json` → `record`
- [x] Twin deficits: the Centre's gross fiscal deficit (`centre_gfd_pct_gdp`, Handbook Table 237, from 1984-85) and the current account deficit (`cab_pct_gdp_fy`, Table 241, from 1987-88), % of GDP, both drawn as deficits (`#twin-deficits`)
- [x] General government (Centre + states) deficit and debt, % of GDP (annual; RBI Handbook tables 239/240, `rbi/general_government.py`)
- [x] States: link to the States page for state fiscal ratios

## Must NOT include
- Deficit % of GDP for a partial year without stating the GDP used
- Mixing BE and RE without labelling

## Series (planned)
cga_fiscal_deficit_fytd, cga_gross_tax_fytd, cga_direct_tax_fytd, cga_corporate_tax_fytd, cga_income_tax_fytd, cga_capex_fytd, cga_revex_fytd, cga_interest_fytd, budget_fd_be, gst_gross_collections, gg_deficit_pct_gdp, gg_debt_pct_gdp

## Phase
1 (fiscal deficit, GST), 2 (page), 4 (Budget explorer tool)
