"""Required minimum distribution (RMD) calculator.

Sources (all fetched 2026-11-14; nothing from memory):
- Uniform Lifetime Table III (ages 72-120+): Pub 590-B (2025), Appendix B,
  https://www.irs.gov/pub/irs-pdf/p590b.pdf (p. 67)
- Applicable RMD age by birth year: Treasury/IRS final rule 89 FR 58886
  (2024-07-19): born Jul 1 1949 - Dec 31 1950 -> 72; born 1951-1958 -> 73;
  born on/after Jan 1 1960 -> 75. Born 1959: the statute reads both 73 and 75;
  the final rule reserves the question (calculated here at 73, the earlier
  reading).
- RMD = prior-year (Dec 31) balance divided by the distribution period for the
  age attained that year; first RMD due April 1 of the following year, later
  RMDs by Dec 31 (irs.gov RMD FAQs + retirement topics: RMDs).
- Missed-RMD excise tax 25%, 10% if corrected within two years (Form 5329);
  RMD FAQs updated Dec 10 2024.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

# Uniform Lifetime Table III, Pub 590-B (2025) Appendix B. "120 and over" = 2.0.
_PERIODS: dict[int, float] = {
    72: 27.4, 73: 26.5, 74: 25.5, 75: 24.6, 76: 23.7, 77: 22.9, 78: 22.0,
    79: 21.1, 80: 20.2, 81: 19.4, 82: 18.5, 83: 17.7, 84: 16.8, 85: 16.0,
    86: 15.2, 87: 14.4, 88: 13.7, 89: 12.9, 90: 12.2, 91: 11.5, 92: 10.8,
    93: 10.1, 94: 9.5, 95: 8.9, 96: 8.4, 97: 7.8, 98: 7.3, 99: 6.8,
    100: 6.4, 101: 6.0, 102: 5.6, 103: 5.2, 104: 4.9, 105: 4.6, 106: 4.3,
    107: 4.1, 108: 3.9, 109: 3.7, 110: 3.5, 111: 3.4, 112: 3.3, 113: 3.1,
    114: 3.0, 115: 2.9, 116: 2.8, 117: 2.7, 118: 2.5, 119: 2.3, 120: 2.0,
}

_1959_NOTE = ("Born in 1959: the law sets your RMD age as both 73 and 75, and "
              "final IRS rules have not resolved it yet (reserved in 89 FR "
              "58886). Calculated here at 73, the earlier reading - plan for "
              "money leaving sooner rather than later.")


def _period(age: int) -> float:
    return _PERIODS.get(age, 2.0)  # "120 and over"


def applicable_age(birth_year: int) -> int | None:
    """RMD start age, or None for 1959 births (statute is ambiguous)."""
    if 1951 <= birth_year <= 1958:
        return 73
    if birth_year == 1959:
        return None
    if birth_year >= 1960:
        return 75
    return 72  # born 1949-1950 (and anyone older, already past their start)


class Request(BaseModel):
    birth_year: int = Field(ge=1935, le=1965,
                            description="owner's year of birth (1935-1965)")
    balance: float = Field(gt=0,
                           description="total balance of all traditional/SEP/SIMPLE IRAs as of last Dec 31, USD")


class YearRow(BaseModel):
    year: int
    age: int
    distribution_period: float
    rmd: float
    deadline: str


class Response(BaseModel):
    birth_year: int
    balance: float
    applicable_age: int | None
    first_rmd_year: int | None
    rows: list[YearRow]
    status: str
    ambiguity_note: str | None = None
    penalty_note: str
    note: str


def _row(year: int, birth_year: int, balance: float, first: bool) -> YearRow:
    age = year - birth_year
    deadline = (f"April 1, {year + 1} (first RMD; deferring means two RMDs in {year + 1})"
                if first else f"December 31, {year}")
    return YearRow(year=year, age=age, distribution_period=_period(age),
                   rmd=round(balance / _period(age), 2), deadline=deadline)


def calculate(req: Request, current_year: int | None = None) -> Response:
    today = current_year or date.today().year
    age_now = applicable_age(req.birth_year)
    if req.birth_year == 1959:
        first_year = req.birth_year + 73  # earlier reading; see ambiguity_note
    else:
        first_year = req.birth_year + age_now if age_now else None
    # Births before 1950 started long ago under pre-SECURE 2.0 ages; no
    # sourced first-year claim is made for them - current RMDs are what matter.
    if req.birth_year < 1950:
        first_year = None
    start = max(today, first_year or today)
    rows = [_row(start + i, req.birth_year, req.balance, first=(start + i == first_year))
            for i in range(3)]
    if first_year and first_year >= today:
        status = (f"Your first RMD year is {first_year} "
                  f"(the year you turn {first_year - req.birth_year}).")
    elif req.birth_year == 1959 and today <= req.birth_year + 73:
        status = f"Your first RMD year is {first_year} (calculated at age 73 - see note)."
    else:
        status = ("RMDs are already due every year you stay in the account - "
                  "these are your next three.")
    return Response(
        birth_year=req.birth_year, balance=req.balance,
        applicable_age=age_now, first_rmd_year=first_year,
        rows=rows, status=status,
        ambiguity_note=_1959_NOTE if req.birth_year == 1959 else None,
        penalty_note=("A missed or short RMD faces a 25% excise tax, cut to 10% "
                      "if corrected within two years (file Form 5329)."),
        note=("RMD = last year's Dec 31 balance divided by the IRS Uniform "
              "Lifetime Table period for the age you reach that year. Compute "
              "it for each IRA you own, but you can withdraw the total from "
              "one or more of them; 401(k)-type plans are separate. If your "
              "sole beneficiary is a spouse 10+ years younger, Table II gives "
              "you smaller RMDs (not shown). Future years assume the balance "
              "stays as entered. Not tax advice."),
    )
