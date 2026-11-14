"""MCP server exposing the Social Security break-even calculator over stdio.

Run: python -m money_tools.mcp_server
"""

from __future__ import annotations

import json

from mcp.server.mcpserver import MCPServer

from money_tools.breakeven import Request, calculate
from money_tools.irmaa import Request as IrmaaRequest, calculate as irmaa_calculate
from money_tools.rmd import Request as RmdRequest, calculate as rmd_calculate

mcp = MCPServer(name="money-tools", version="0.2.0")


@mcp.tool()
def ss_break_even(birth_year: int, pia: float, claim_ages: list[int] | None = None) -> str:
    """Social Security claiming break-even analysis for a US worker.

    Args:
        birth_year: worker's year of birth (1938-2010).
        pia: monthly retirement benefit at full retirement age in USD, as
            printed on the worker's ssa.gov statement.
        claim_ages: whole claiming ages to compare, each 62-70 (default 62, 67, 70).

    Returns JSON with each age's monthly benefit, cumulative totals to 75/80/85/90
    (today's dollars), and the break-even age for each pair. Rules and factors
    from ssa.gov/OACT (nra.html, early_late.html).
    """
    r = calculate(Request(birth_year=birth_year, pia=pia,
                          claim_ages=claim_ages or [62, 67, 70]))
    return json.dumps(r.model_dump(), indent=1)


@mcp.tool()
def roth_irmaa(status: str, magi: float, roth_conversion: float = 0.0) -> str:
    """What a Roth conversion does to Medicare costs (2026 IRMAA tiers).

    Args:
        status: filing status: "single", "joint" (married filing jointly) or
            "separate" (married filing separately).
        magi: modified adjusted gross income before the conversion, USD.
        roth_conversion: extra income the Roth conversion would add, USD.

    Returns JSON with the IRMAA tier before and after, Part B monthly premium,
    Part D surcharge, the extra annual Medicare cost per person, and the MAGI
    room left before the next bracket cliff. Tiers from the official Medicare
    2026 costs fact sheet; IRMAA is a two-year lookback.
    """
    r = irmaa_calculate(IrmaaRequest(status=status, magi=magi,
                                     roth_conversion=roth_conversion))
    return json.dumps(r.model_dump(), indent=1)


@mcp.tool()
def rmd(birth_year: int, balance: float) -> str:
    """Required minimum distributions (RMDs) for a US traditional IRA owner.

    Args:
        birth_year: account owner's year of birth (1935-1965).
        balance: total balance of all traditional/SEP/SIMPLE IRAs as of last
            December 31, USD.

    Returns JSON with the next three RMD years: age attained, IRS Uniform
    Lifetime Table divisor, the RMD amount, and each deadline (first RMD due
    April 1 of the following year). RMD ages from Treasury/IRS final rule
    89 FR 58886: 73 for births 1951-1958, 75 for 1960+; 1959 births are
    flagged (statute is ambiguous, calculated at 73). Missed-RMD excise tax
    is 25%, 10% if corrected within two years.
    """
    r = rmd_calculate(RmdRequest(birth_year=birth_year, balance=balance))
    return json.dumps(r.model_dump(), indent=1)


if __name__ == "__main__":
    mcp.run()
