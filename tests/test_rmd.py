"""Tests against Pub 590-B (2025) Appendix B and final rule 89 FR 58886."""

from money_tools.rmd import _PERIODS, Request, applicable_age, calculate


def r(by, balance=500_000, year=2026):
    return calculate(Request(birth_year=by, balance=balance), current_year=year)


def test_uniform_lifetime_table_spots():
    # Pub 590-B (2025), Appendix B, Table III
    for age, period in [(72, 27.4), (73, 26.5), (84, 16.8), (95, 8.9),
                        (119, 2.3), (120, 2.0)]:
        assert _PERIODS[age] == period


def test_applicable_age_rule():
    # Final rule 89 FR 58886 (2024-07-19)
    assert applicable_age(1950) == 72
    assert applicable_age(1951) == 73
    assert applicable_age(1958) == 73
    assert applicable_age(1959) is None
    assert applicable_age(1960) == 75
    assert applicable_age(1965) == 75


def test_rmd_math_73_in_2026():
    # born 1953 turns 73 in 2026: 500000 / 26.5
    resp = r(1953)
    assert resp.rows[0].year == 2026 and resp.rows[0].age == 73
    assert resp.rows[0].distribution_period == 26.5
    assert resp.rows[0].rmd == 18867.92
    assert resp.rows[1].year == 2027 and resp.rows[1].rmd == 19607.84  # 25.5


def test_first_rmd_deadline_is_april_1():
    resp = r(1953)
    assert "April 1, 2027" in resp.rows[0].deadline
    assert "two RMDs" in resp.rows[0].deadline
    # born 1952 already started (2025): current row is a plain Dec 31 deadline
    resp = r(1952)
    assert resp.rows[0].deadline == "December 31, 2026"


def test_future_start_born_1960_is_75():
    # 89 FR 58886: born on/after Jan 1 1960 -> age 75
    resp = r(1960)
    assert resp.applicable_age == 75
    assert resp.first_rmd_year == 2035
    assert resp.rows[0].year == 2035 and resp.rows[0].age == 75
    assert resp.rows[0].distribution_period == 24.6
    assert resp.status.startswith("Your first RMD year is 2035")


def test_born_1959_ambiguity_is_flagged():
    resp = r(1959)
    assert resp.applicable_age is None
    assert resp.ambiguity_note and "both 73 and 75" in resp.ambiguity_note
    assert resp.first_rmd_year == 2032  # earlier reading
    assert resp.rows[0].year == 2032 and resp.rows[0].age == 73


def test_older_owner_uses_current_age():
    # born 1935 is 91 in 2026: 500000 / 11.5
    resp = r(1935)
    assert resp.rows[0].year == 2026 and resp.rows[0].age == 91
    assert resp.rows[0].rmd == 43478.26
    assert resp.first_rmd_year is None  # no sourced claim for pre-1950 starts


def test_projection_skips_to_first_rmd_year():
    # born 1965 (61 in 2026): first rows are 2040/2041/2042 at ages 75/76/77
    resp = r(1965)
    assert [x.year for x in resp.rows] == [2040, 2041, 2042]
    assert [x.distribution_period for x in resp.rows] == [24.6, 23.7, 22.9]


def test_penalty_and_note_wording():
    resp = r(1953)
    assert "25%" in resp.penalty_note and "10%" in resp.penalty_note
    assert "Uniform" in resp.note and "spouse" in resp.note
