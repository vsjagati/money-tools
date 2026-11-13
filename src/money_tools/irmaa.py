"""Roth conversion -> IRMAA calculator (2026 Medicare costs, from 2024 MAGI).

Every tier from the official fact sheet: medicare.gov/publications/11579-medicare-costs.pdf
("Fact sheet, 2026 Medicare costs", downloaded 2026-11-13).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# (upper bound single, upper bound joint, upper is inclusive?, part B monthly,
#  part D monthly add). PDF wording: "$109,000 or less" tiers 1-4 "up to"
# (inclusive); tier 5 "less than $500,000" (exclusive); tier 6 "or above".
# Married-separate: <=109k tier 1, >109k-<391k tier 5, >=391k tier 6 (PDF).
_TIERS: list[tuple[float, float, bool, float, float]] = [
    (109_000, 218_000, True, 202.90, 0.00),
    (137_000, 274_000, True, 284.10, 14.50),
    (171_000, 342_000, True, 405.80, 37.50),
    (205_000, 410_000, True, 527.50, 60.40),
    (500_000, 750_000, False, 649.20, 83.30),
    (float("inf"), float("inf"), True, 689.90, 91.00),
]

PART_D_NATIONAL_BASE = 38.99  # same fact sheet


def _tier(magi: float, status: str) -> int:
    if status == "separate":
        if magi <= 109_000:
            return 0
        return 5 if magi >= 391_000 else 4
    bound = 1 if status == "joint" else 0
    for i, t in enumerate(_TIERS):
        if magi < t[bound] or (t[2] and magi == t[bound]):
            return i
    return 5


class Request(BaseModel):
    status: str = Field(pattern="^(single|joint|separate)$")
    magi: float = Field(ge=0, description="MAGI before any conversion (AGI + tax-exempt interest)")
    roth_conversion: float = Field(default=0, ge=0, description="extra income a Roth conversion would add")


class TierView(BaseModel):
    tier: int
    part_b_monthly: float
    part_d_monthly_add: float
    annual_total: float  # 12 * (B + D add), per person


class Response(BaseModel):
    status: str
    magi: float
    roth_conversion: float
    before: TierView
    after: TierView
    extra_annual_medicare_cost: float
    room_to_next_bracket: float | None
    lookback_note: str
    note: str


def _view(magi: float, status: str) -> TierView:
    i = _tier(magi, status)
    b, d = _TIERS[i][3], _TIERS[i][4]
    return TierView(tier=i + 1, part_b_monthly=b, part_d_monthly_add=d,
                    annual_total=round(12 * (b + d), 2))


def _room(magi: float, status: str) -> float | None:
    i = _tier(magi, status)
    bound = 1 if status == "joint" else 0
    top = _TIERS[i][bound]
    return None if top == float("inf") else round(top - magi, 2)


def calculate(req: Request) -> Response:
    before = _view(req.magi, req.status)
    after = _view(req.magi + req.roth_conversion, req.status)
    return Response(
        status=req.status, magi=req.magi, roth_conversion=req.roth_conversion,
        before=before, after=after,
        extra_annual_medicare_cost=round(after.annual_total - before.annual_total, 2),
        room_to_next_bracket=_room(req.magi, req.status),
        lookback_note=("IRMAA is a 2-year lookback: 2026 costs use 2024 MAGI, "
                       "so a conversion done in 2026 raises the IRMAA charged "
                       "in 2028 (one year of surcharge, per person)."),
        note=("Tiers are cliffs: one dollar over a threshold buys the whole "
              "surcharge. Amounts per person per month. Sources: medicare.gov "
              "2026 Medicare costs fact sheet (11579), Part B and Part D "
              "IRMAA tables. Not tax advice; income tax on the conversion "
              "itself is not included."),
    )
