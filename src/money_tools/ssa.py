"""Social Security rules and constants, every value cited to its SSA source.

Sources (fetched 2026-11-13):
- FRA table: https://www.ssa.gov/oact/progdata/nra.html
- Early reduction / DRC rules: https://www.ssa.gov/oact/quickcalc/early_late.html
- CPI-W (COLA derivation): https://www.ssa.gov/oact/STATS/cpiw.html
"""

from __future__ import annotations

# Year of birth -> full retirement age in months (relative to 65y).
_FRA_MONTHS_AFTER_65: list[tuple[int, int]] = [
    # (birth year from, months after age 65); last entry applies to all later years
    (1938, 2), (1939, 4), (1940, 6), (1941, 8), (1942, 10),
    (1943, 12),  # 1943-1954: 66
    (1955, 14), (1956, 16), (1957, 18), (1958, 20), (1959, 22),
    (1960, 24),  # 1960+: 67
]

EARLY_FIRST_36 = 5 / 9 / 100   # per month, first 36 months before FRA
EARY_BEYOND_36 = 5 / 12 / 100  # per month, months beyond the first 36
DRC_PER_MONTH_1943_LATER = 8 / 12 / 100  # 8%/yr, births 1943+

# Announced COLAs (ssa.gov/OACT latest COLA; derivable from the CPI-W table).
COLA = {2025: 2.5, 2026: 2.8, 2027: 3.6}


def fra_months(birth_year: int) -> int:
    """Full retirement age in whole years*12 (65*12 + extra months)."""
    if birth_year <= 1937:
        return 65 * 12
    extra = 24
    for start, m in _FRA_MONTHS_AFTER_65:
        if birth_year >= start:
            extra = m
    return 65 * 12 + extra


def age_factor(birth_year: int, claim_age_months: int) -> float:
    """Benefit as a share of PIA for claiming at claim_age_months (months since
    birth). Early: 5/9%/mo for first 36 months before FRA, 5/12%/mo beyond.
    Late: 8%/yr DRC to 70, all credits applied (as SSA's quickcalc shows)."""
    fra = fra_months(birth_year)
    diff = claim_age_months - fra
    if diff >= 0:
        drc_months = min(diff, (70 * 12) - fra)
        return 1.0 + drc_months * DRC_PER_MONTH_1943_LATER
    before = -diff
    first36 = min(before, 36)
    rest = before - first36
    return 1.0 - first36 * EARLY_FIRST_36 - rest * EARY_BEYOND_36
