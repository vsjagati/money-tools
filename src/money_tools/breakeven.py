"""Social Security claiming break-even calculator.

Inputs are a worker's PIA (monthly benefit at full retirement age, as printed
on their ssa.gov statement) and claiming ages. Outputs monthly benefits,
cumulative-benefit series and pairwise break-even ages.
"""

from __future__ import annotations

import math
from pydantic import BaseModel, Field, model_validator

from money_tools.ssa import COLA, age_factor, fra_months

MAX_AGE_MONTHS = 100 * 12
EARLIEST, LATEST = 62 * 12, 70 * 12


class Request(BaseModel):
    birth_year: int = Field(ge=1938, le=2010)
    pia: float = Field(gt=0, description="monthly benefit at FRA, USD")
    claim_ages: list[int] = Field(default=[62, 67, 70], min_length=2, max_length=4)

    @model_validator(mode="after")
    def _ages(self) -> "Request":
        if not all(EARLIEST <= a * 12 <= LATEST for a in self.claim_ages):
            raise ValueError("claim ages must be whole years from 62 to 70")
        if len(set(self.claim_ages)) != len(self.claim_ages):
            raise ValueError("claim ages must be distinct")
        self.claim_ages.sort()
        return self


class ClaimResult(BaseModel):
    age: int
    monthly_benefit: int  # SSA rounds benefits down to whole dollars
    cumulative_at_75: int
    cumulative_at_80: int
    cumulative_at_85: int
    cumulative_at_90: int


class BreakEvenPair(BaseModel):
    earlier_age: int
    later_age: int
    break_even_age: float | None  # None when the earlier claim never loses within 100


class Response(BaseModel):
    birth_year: int
    fra: str
    pia: float
    claims: list[ClaimResult]
    break_evens: list[BreakEvenPair]
    note: str


def monthly_benefit(pia: float, birth_year: int, age: int) -> int:
    return math.floor(pia * age_factor(birth_year, age * 12))


def _cumulative(pia: float, birth_year: int, claim_age: int,
                to_month: int) -> int:
    """Sum of benefits from claiming to to_month (months since birth), in
    today's dollars (a uniform COLA moves totals, not comparisons)."""
    benefit = pia * age_factor(birth_year, claim_age * 12)
    return math.floor(benefit * (to_month - claim_age * 12))


def _break_even(pia: float, birth_year: int, earlier: int, later: int) -> float | None:
    """First age where the later claim's cumulative total passes the earlier
    one's, in today's dollars, scanning to 100."""
    b1 = pia * age_factor(birth_year, earlier * 12)
    b2 = pia * age_factor(birth_year, later * 12)
    gap = later * 12 - earlier * 12
    if b2 <= b1:
        return None
    months_after_earlier = b2 * gap / (b2 - b1)
    be_month = earlier * 12 + months_after_earlier
    if be_month > MAX_AGE_MONTHS:
        return None
    return round(be_month / 12, 2)


def calculate(req: Request) -> Response:
    fra = fra_months(req.birth_year)
    fra_str = f"{fra // 12}y {fra % 12}m".replace(" 0m", "")
    claims = [
        ClaimResult(
            age=a,
            monthly_benefit=monthly_benefit(req.pia, req.birth_year, a),
            cumulative_at_75=_cumulative(req.pia, req.birth_year, a, 75 * 12),
            cumulative_at_80=_cumulative(req.pia, req.birth_year, a, 80 * 12),
            cumulative_at_85=_cumulative(req.pia, req.birth_year, a, 85 * 12),
            cumulative_at_90=_cumulative(req.pia, req.birth_year, a, 90 * 12),
        )
        for a in req.claim_ages
    ]
    pairs = [
        BreakEvenPair(
            earlier_age=req.claim_ages[i],
            later_age=req.claim_ages[j],
            break_even_age=_break_even(req.pia, req.birth_year, req.claim_ages[i],
                                       req.claim_ages[j]),
        )
        for i in range(len(req.claim_ages))
        for j in range(i + 1, len(req.claim_ages))
    ]
    return Response(
        birth_year=req.birth_year, fra=fra_str, pia=req.pia,
        claims=claims, break_evens=pairs,
        note=("All figures in today's dollars; a uniform COLA raises totals but "
              "not the comparison. Estimates use SSA early/delayed factors "
              "only; taxes, the earnings test and survivor benefits are not "
              "included."),
    )
