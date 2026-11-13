# Sources

Every constant in this project comes from a public SSA page, fetched live on
2026-11-13. Nothing is from memory.

| What | Value | Source |
|---|---|---|
| Full retirement age by birth year | 65 (≤1937) stepping to 67 (1960+) | https://www.ssa.gov/oact/progdata/nra.html |
| Early claiming reduction | 5/9 of 1% per month for the first 36 months before FRA, then 5/12 of 1% per month | https://www.ssa.gov/oact/quickcalc/early_late.html |
| SSA's own worked example | 60 months early (62 when FRA 67) = 30% reduction → 70% of PIA | same page |
| Delayed retirement credit | 8% per year for births 1943+, no credit after 69 | same page |
| COLA 2027 (3.6%) cross-check | computed from the page's CPI-W table: Q3-2026 avg 328.746 vs Q3-2025 avg 317.265 = +3.618% | https://www.ssa.gov/oact/STATS/cpiw.html |

Tests encode these ground truths: `tests/test_money_tools.py` asserts the 70%,
72.5% (born 1957 at 62) and 124% (born 1960 at 70) factors, the FRA table, and
recomputes the 2027 COLA from the CPI-W table.

Model notes:
- Benefits are rounded down to whole dollars, as SSA pays them.
- All outputs are in today's dollars: a uniform COLA raises both streams'
  totals but not their comparison (crossing is preserved under a common
  price index). Break-evens are therefore inflation-invariant.
- Not included: taxes on benefits, the earnings test before FRA, survivor
  benefits, spousal benefits. Estimates only, not financial advice.
