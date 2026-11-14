# Sources

Every constant in this project comes from a public official page, fetched live.
Nothing is from memory.

| What | Value | Source |
|---|---|---|
| Full retirement age by birth year | 65 (≤1937) stepping to 67 (1960+) | https://www.ssa.gov/oact/progdata/nra.html |
| Early claiming reduction | 5/9 of 1% per month for the first 36 months before FRA, then 5/12 of 1% per month | https://www.ssa.gov/oact/quickcalc/early_late.html |
| SSA's own worked example | 60 months early (62 when FRA 67) = 30% reduction → 70% of PIA | same page |
| Delayed retirement credit | 8% per year for births 1943+, no credit after 69 | same page |
| COLA 2027 (3.6%) cross-check | computed from the page's CPI-W table: Q3-2026 avg 328.746 vs Q3-2025 avg 317.265 = +3.618% | https://www.ssa.gov/oact/STATS/cpiw.html |
| IRMAA tiers, 2026 Part B/D premiums | tiers 1-6 with cliffs; $202.90 base | https://www.medicare.gov/publications/11579-medicare-costs.pdf (fact sheet, downloaded 2026-11-13) |
| Uniform Lifetime Table III (RMD divisors, ages 72-120+) | 72→27.4 ... 119→2.3, 120+→2.0 | https://www.irs.gov/pub/irs-pdf/p590b.pdf (Pub 590-B 2025, Appendix B, p. 67, downloaded 2026-11-14) |
| RMD start age by birth year | born Jul 1 1949-Dec 31 1950→72; 1951-1958→73; 1960+→75; 1959 reserved (statute reads both 73 and 75) | https://www.federalregister.gov/documents/2024/07/19/2024-14542/required-minimum-distributions (final rule 89 FR 58886, fetched 2026-11-14) |
| First RMD deadline | April 1 of the year after reaching RMD age; later RMDs Dec 31 | https://www.irs.gov/retirement-plans/retirement-plan-and-ira-required-minimum-distributions-faqs |
| Missed-RMD excise tax | 25%, or 10% if corrected within two years (Form 5329) | same IRS FAQs page (updated 2024-12-10) |

Tests encode these ground truths: `tests/test_money_tools.py` asserts the 70%,
72.5% (born 1957 at 62) and 124% (born 1960 at 70) factors, the FRA table, and
recomputes the 2027 COLA from the CPI-W table. `tests/test_irmaa.py` asserts
the official tier premiums. `tests/test_rmd.py` asserts table divisors
straight from the Pub 590-B page, the birth-year → RMD age rule, the April-1
first deadline, and the 25%/10% excise text.

Model notes:
- Benefits are rounded down to whole dollars, as SSA pays them.
- All outputs are in today's dollars: a uniform COLA raises both streams'
  totals but not their comparison (crossing is preserved under a common
  price index). Break-evens are therefore inflation-invariant.
- Not included: taxes on benefits, the earnings test before FRA, survivor
  benefits, spousal benefits. Estimates only, not financial advice.
