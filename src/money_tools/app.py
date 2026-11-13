"""Web + JSON API for the Social Security break-even calculator."""

from __future__ import annotations

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import ValidationError

from contextlib import asynccontextmanager

from money_tools.breakeven import Request as CalcRequest, calculate
from money_tools.irmaa import Request as IrmaaRequest, calculate as irmaa_calculate
from money_tools import __version__

# MCP streamable HTTP app; mounted below. Starlette does not run a mounted
# app's lifespan, so its task group is started through the parent lifespan.
# DNS-rebinding protection is off: we are a public API behind Cloud Run's own
# host routing, not a local server.
from mcp.server.transport_security import TransportSecuritySettings  # noqa: E402
from money_tools.mcp_server import mcp as mcp_server  # noqa: E402
mcp_app = mcp_server.streamable_http_app(
    stateless_http=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))


@asynccontextmanager
async def _lifespan(app):
    async with mcp_app.router.lifespan_context(mcp_app):
        yield


app = FastAPI(title="Money Tools", version=__version__, lifespan=_lifespan)

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Social Security Break-Even Calculator - claim at 62, 67 or 70?</title>
<meta name="description" content="Compare claiming Social Security at 62, 67 and 70:
monthly benefit, total collected and the break-even age, using SSA's own rules.">
<style>
 body{font-family:system-ui,sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem;line-height:1.5}
 h1{font-size:1.5rem} form{display:grid;gap:.8rem;max-width:24rem}
 label{font-size:.9rem;display:grid;gap:.2rem}
 input{font:inherit;padding:.4rem}
 button{font:inherit;padding:.5rem;width:fit-content}
 table{border-collapse:collapse;margin:1rem 0}
 th,td{border:1px solid #ccc;padding:.4rem .7rem;text-align:right;font-variant-numeric:tabular-nums}
 th:first-child,td:first-child{text-align:left}
 .be{background:#f0f7f0;padding:.6rem .8rem;margin:.4rem 0}
 .note{font-size:.8rem;color:#555}
 code{background:#f4f4f4;padding:0 .3rem}
</style></head><body>
<h1>Social Security break-even calculator</h1>
<p><a href="/irmaa">Roth conversion &middot; IRMAA calculator &rarr;</a></p>
<p>Claim at 62, 67 or 70? Enter what your statement calls your benefit at full
retirement age, and see what each claiming age pays and when waiting pays off.</p>
<form method="get" action="/">
 <label>Birth year <input name="birth_year" type="number" min="1938" max="2010" required value="{by}"></label>
 <label>Monthly benefit at full retirement age (USD) <input name="pia" type="number" min="1" step="0.01" required value="{pia}"></label>
 <button type="submit">Calculate</button>
</form>
{results}
</body></html>"""

RESULT_BLOCK = """
<h2>Full retirement age: {fra}</h2>
<table><tr><th>Claim at</th><th>Monthly</th><th>Total by 75</th><th>by 80</th><th>by 85</th><th>by 90</th></tr>
{rows}</table>
{be_lines}
<p class="note">{note}</p>
<p class="note">Sources:
<a href="https://www.ssa.gov/oact/progdata/nra.html">SSA retirement age</a> ·
<a href="https://www.ssa.gov/oact/quickcalc/early_late.html">SSA early/late factors</a>.
Estimates only, not financial advice.</p>"""


def _money(n: int) -> str:
    return f"${n:,}"


def _echo(v: float) -> str:
    return str(int(v)) if v == int(v) else str(v)


def _render(by: str, pia: str, result_html: str) -> HTMLResponse:
    page = (PAGE
            .replace("{by}", by or "1965")
            .replace("{pia}", pia or "2500")
            .replace("{results}", result_html))
    return HTMLResponse(page)


@app.get("/", response_class=HTMLResponse)
def index(birth_year: int = 0, pia: float = 0.0):
    if not birth_year or not pia:
        return _render("", "", "")
    try:
        req = CalcRequest(birth_year=birth_year, pia=pia)
    except ValidationError as e:
        return _render(str(birth_year), str(pia),
                       f"<p class='be'>{e.errors()[0]['msg']}</p>")
    r = calculate(req)
    rows = "".join(
        f"<tr><td>{c.age}</td><td>{_money(c.monthly_benefit)}</td>"
        f"<td>{_money(c.cumulative_at_75)}</td><td>{_money(c.cumulative_at_80)}</td>"
        f"<td>{_money(c.cumulative_at_85)}</td><td>{_money(c.cumulative_at_90)}</td></tr>"
        for c in r.claims)
    be_lines = "".join(
        f"<p class='be'>Claim at <b>{p.earlier_age}</b> vs <b>{p.later_age}</b>: "
        f"waiting wins from age <b>{p.break_even_age}</b>"
        + ("" if p.break_even_age else " (never within 100)") + "</p>"
        for p in r.break_evens)
    block = (RESULT_BLOCK
             .replace("{fra}", r.fra)
             .replace("{rows}", rows)
             .replace("{be_lines}", be_lines)
             .replace("{note}", r.note))
    return _render(str(birth_year), _echo(pia), block)


@app.get("/api/break-even")
def api(birth_year: int, pia: float, ages: str = ""):
    claim = [int(a) for a in ages.split(",")] if ages else [62, 67, 70]
    try:
        return calculate(CalcRequest(birth_year=birth_year, pia=pia,
                                     claim_ages=claim)).model_dump()
    except ValidationError as e:
        return JSONResponse(status_code=422, content={"detail": e.errors()})


IRMAA_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Roth Conversion IRMAA Calculator 2026 - will it raise your Medicare costs?</title>
<meta name="description" content="See what a Roth conversion does to your Medicare
Part B and Part D costs: your IRMAA tier, the surcharge, and how much MAGI room
you have before the next cliff.">
<style>
 body{font-family:system-ui,sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem;line-height:1.5}
 h1{font-size:1.5rem} form{display:grid;gap:.8rem;max-width:24rem}
 label{font-size:.9rem;display:grid;gap:.2rem}
 input,select{font:inherit;padding:.4rem}
 button{font:inherit;padding:.5rem;width:fit-content}
 .be{background:#f0f7f0;padding:.6rem .8rem;margin:.4rem 0}
 .warn{background:#fdf0f0;padding:.6rem .8rem;margin:.4rem 0}
 .note{font-size:.8rem;color:#555}
</style></head><body>
<h1>Roth conversion &middot; IRMAA calculator</h1>
<p>A Roth conversion raises your reported income for the year - and Medicare
reads that income two years later. See your tier today and what a conversion
would cost in Part B and Part D surcharges.</p>
<form method="get" action="/irmaa">
 <label>Filing status
  <select name="status">
   <option value="single">Single</option>
   <option value="joint">Married filing jointly</option>
   <option value="separate">Married filing separately</option>
  </select></label>
 <label>MAGI before conversion (USD) <input name="magi" type="number" min="0" required value="{magi}"></label>
 <label>Roth conversion amount (USD) <input name="conv" type="number" min="0" required value="{conv}"></label>
 <button type="submit">Calculate</button>
</form>
{results}
<p class="note">2026 tiers from the
<a href="https://www.medicare.gov/publications/11579-medicare-costs.pdf">official
Medicare 2026 costs fact sheet</a> (PDF). IRMAA uses the tax return from two
years earlier. Estimates per person; not tax advice.</p>
</body></html>"""

IRMAA_RESULT = """
<h2>Today (tier {t1}): Part B {b1}/mo + Part D surcharge {d1}/mo = {a1}/yr</h2>
<h2>With the conversion (tier {t2}): Part B {b2}/mo + Part D surcharge {d2}/mo = {a2}/yr</h2>
<p class="{cls}">{verdict}</p>
<p class="note">{lookback}</p>
<p class="note">{note}</p>"""


@app.get("/irmaa", response_class=HTMLResponse)
def irmaa_page(status: str = "single", magi: float = 0, conv: float = 0):
    if not magi:
        return HTMLResponse(IRMAA_PAGE.replace("{magi}", "100000")
                            .replace("{conv}", "0").replace("{results}", ""))
    try:
        req = IrmaaRequest(status=status, magi=magi, roth_conversion=conv)
    except ValidationError as e:
        return HTMLResponse(IRMAA_PAGE.replace("{magi}", str(magi))
                            .replace("{conv}", str(conv))
                            .replace("{results}", f"<p class='warn'>{e.errors()[0]['msg']}</p>"))
    r = irmaa_calculate(req)
    money = lambda x: f"${x:,.2f}"
    if r.extra_annual_medicare_cost == 0:
        verdict = (f"Stays in tier {r.after.tier}: the conversion adds "
                   f"{money(0)} in Medicare surcharges.")
        cls = "be"
    else:
        verdict = (f"The conversion adds {money(r.extra_annual_medicare_cost)} per year "
                   f"in Medicare surcharges, per person (tier {r.before.tier} &rarr; "
                   f"tier {r.after.tier}).")
        cls = "warn"
    if r.room_to_next_bracket is not None:
        verdict += (f" Today you have {money(r.room_to_next_bracket)} of MAGI room "
                    f"before the next cliff.")
    block = (IRMAA_RESULT
             .replace("{t1}", str(r.before.tier)).replace("{b1}", money(r.before.part_b_monthly))
             .replace("{d1}", money(r.before.part_d_monthly_add)).replace("{a1}", money(r.before.annual_total))
             .replace("{t2}", str(r.after.tier)).replace("{b2}", money(r.after.part_b_monthly))
             .replace("{d2}", money(r.after.part_d_monthly_add)).replace("{a2}", money(r.after.annual_total))
             .replace("{verdict}", verdict).replace("{cls}", cls)
             .replace("{lookback}", r.lookback_note).replace("{note}", r.note))
    return HTMLResponse(IRMAA_PAGE.replace("{magi}", _echo(magi))
                        .replace("{conv}", _echo(conv)).replace("{results}", block))


@app.get("/api/irmaa")
def irmaa_api(status: str, magi: float, conv: float = 0):
    try:
        return irmaa_calculate(IrmaaRequest(status=status, magi=magi,
                                            roth_conversion=conv)).model_dump()
    except ValidationError as e:
        return JSONResponse(status_code=422, content={"detail": e.errors()})


# MCP streamable HTTP at /mcp (stateless: Cloud Run instances come and go).
# Mounted last so the routes above win the path match.
app.mount("/", mcp_app, name="mcp")
