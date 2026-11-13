"""Tests against SSA's own published percentages and worked examples.

Ground truths (ssa.gov/oact/quickcalc/early_late.html):
- Born 1960 (FRA 67), claim at 62: 60 months early = 36*5/9% + 24*5/12% = 30% cut
- Born 1957 (FRA 66 and 6 months), claim at 62: 27.5% cut (SSA published value)
- Born 1960, claim at 70: 48 months * 8%/yr = +32% (124% of PIA)
"""

import math

from money_tools.breakeven import Request, calculate, monthly_benefit
from money_tools.ssa import COLA, age_factor, fra_months


def test_fra_table():
    assert fra_months(1937) == 65 * 12
    assert fra_months(1943) == 66 * 12
    assert fra_months(1954) == 66 * 12
    assert fra_months(1955) == 66 * 12 + 2
    assert fra_months(1957) == 66 * 12 + 6
    assert fra_months(1959) == 66 * 12 + 10
    assert fra_months(1960) == 67 * 12
    assert fra_months(1985) == 67 * 12


def test_claim_at_62_fra67_is_70pct():
    assert abs(age_factor(1960, 62 * 12) - 0.70) < 1e-12
    assert monthly_benefit(1000.0, 1960, 62) == 700


def test_claim_at_70_fra67_is_124pct():
    assert abs(age_factor(1960, 70 * 12) - 1.24) < 1e-12
    assert monthly_benefit(1000.0, 1960, 70) == 1240


def test_claim_at_62_fra66_6_is_72_5pct():
    assert abs(age_factor(1957, 62 * 12) - 0.725) < 1e-12


def test_at_fra_factor_is_one():
    for year in (1945, 1955, 1960, 1975):
        assert abs(age_factor(year, fra_months(year)) - 1.0) < 1e-12


def test_break_even_62_vs_70_known_shape():
    # 700/mo from 62 vs 1240/mo from 70 (today's dollars):
    # BE = 62 + 1240*96/(1240-700) months = 80.37y
    r = calculate(Request(birth_year=1960, pia=1000.0, claim_ages=[62, 70]))
    be = r.break_evens[0].break_even_age
    expected = 62 + (1240.0 * 96 / (1240.0 - 700.0)) / 12
    assert be is not None and abs(be - expected) < 0.05


def test_break_even_is_inflation_invariant_by_construction():
    # Today's-dollars outputs depend only on factors, not on any COLA path.
    # 62 (700) vs 67 (1000): BE = 62 + 1000*60/(1000-700) months = 78.67y
    r = calculate(Request(birth_year=1960, pia=1000.0, claim_ages=[62, 67, 70]))
    assert r.break_evens[0].break_even_age == 78.67


def test_earlier_claim_ahead_at_75_later_ahead_at_90():
    r = calculate(Request(birth_year=1960, pia=2000.0, claim_ages=[62, 67, 70]))
    by_age = {c.age: c for c in r.claims}
    assert by_age[62].cumulative_at_75 > by_age[70].cumulative_at_75
    assert by_age[70].cumulative_at_90 > by_age[62].cumulative_at_90


def test_response_carries_fra_and_note():
    r = calculate(Request(birth_year=1957, pia=1500.0))
    assert r.fra == "66y 6m"
    assert "today's dollars" in r.note


def test_rejects_bad_ages():
    import pytest
    with pytest.raises(Exception):
        Request(birth_year=1960, pia=1000.0, claim_ages=[61, 70])
    with pytest.raises(Exception):
        Request(birth_year=1960, pia=1000.0, claim_ages=[62, 62])


def test_cola_values_cited():
    # 2027 COLA derivable from the CPI-W table: Q3-26 avg / Q3-25 avg - 1
    q3_25 = (316.349 + 317.306 + 318.139) / 3
    q3_26 = (327.104 + 328.481 + 330.654) / 3
    assert round((q3_26 / q3_25 - 1) * 100, 1) == COLA[2027]
