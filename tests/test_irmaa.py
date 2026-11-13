"""Tests against the official 2026 fact sheet tiers."""

from money_tools.irmaa import Request, calculate


def t(status, magi, conv=0.0):
    return calculate(Request(status=status, magi=magi, roth_conversion=conv))


def test_standard_tier():
    r = t("single", 109_000)
    assert r.before.tier == 1 and r.before.part_b_monthly == 202.90
    assert r.before.part_d_monthly_add == 0.0


def test_one_dollar_over_the_cliff():
    r = t("single", 109_001)
    assert r.before.tier == 2 and r.before.part_b_monthly == 284.10
    assert r.before.part_d_monthly_add == 14.50


def test_top_tier_and_boundaries():
    assert t("single", 500_000).before.tier == 6
    assert t("single", 499_999).before.tier == 5
    assert t("joint", 750_000).before.tier == 6
    assert t("joint", 749_999).before.tier == 5
    assert t("single", 136_999).before.tier == 2
    assert t("single", 137_001).before.tier == 3


def test_married_separate_special_tiers():
    assert t("separate", 100_000).before.tier == 1
    assert t("separate", 150_000).before.tier == 5  # jumps straight to tier 5
    assert t("separate", 400_000).before.tier == 6


def test_roth_conversion_pushes_a_tier():
    r = t("single", 105_000, conv=10_000)
    assert r.before.tier == 1 and r.after.tier == 2
    # 12 * ((284.10-202.90) + 14.50) = 12 * 95.70 = 1148.40
    assert r.extra_annual_medicare_cost == 1148.40


def test_conversion_within_same_tier_costs_nothing():
    r = t("single", 90_000, conv=5_000)
    assert r.after.tier == 1
    assert r.extra_annual_medicare_cost == 0.0


def test_room_to_next_bracket():
    assert t("single", 100_000).room_to_next_bracket == 9_000
    assert t("joint", 210_000).room_to_next_bracket == 8_000
    assert t("single", 600_000).room_to_next_bracket is None


def test_annual_total_maths():
    r = t("joint", 300_000)
    # tier 3: 12 * (405.80 + 37.50) = 5319.60
    assert r.before.annual_total == 5319.60
