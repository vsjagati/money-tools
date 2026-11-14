"""Web + JSON API for the Social Security break-even calculator."""

from __future__ import annotations

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import ValidationError

from contextlib import asynccontextmanager

from money_tools.breakeven import Request as CalcRequest, calculate
from money_tools.irmaa import Request as IrmaaRequest, calculate as irmaa_calculate
from money_tools.rmd import Request as RmdRequest, calculate as rmd_calculate
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
<p><a href="/irmaa">Roth conversion &middot; IRMAA &rarr;</a> &nbsp;
<a href="/rmd">Required minimum distribution (RMD) &rarr;</a></p>
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
years earlier. Estimates per person; not tax advice.
See the <a href="/irmaa/brackets">full 2026 IRMAA bracket table</a>.</p>
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


RMD_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RMD Calculator 2026 - how much must you withdraw this year?</title>
<meta name="description" content="Your required minimum distribution for this
year and the next two, from the IRS Uniform Lifetime Table: amount, deadline,
and when your first RMD is due.">
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
 .warn{background:#fff8e8;padding:.6rem .8rem;margin:.4rem 0}
 .note{font-size:.8rem;color:#555}
</style></head><body>
<h1>Required minimum distribution (RMD) calculator</h1>
<p>The IRS makes you pull a slice out of traditional IRAs every year from
age 73. See what you must withdraw, by when, and when yours starts.</p>
<form method="get" action="/rmd">
 <label>Birth year <input name="birth_year" type="number" min="1935" max="1965" required value="{by}"></label>
 <label>All traditional/SEP/SIMPLE IRA balances last Dec 31 (USD) <input name="balance" type="number" min="1" step="0.01" required value="{bal}"></label>
 <button type="submit">Calculate</button>
</form>
{results}
<p class="note">Sources: IRS
<a href="https://www.irs.gov/pub/irs-pdf/p590b.pdf">Pub 590-B</a> (Uniform
Lifetime Table) &middot; Treasury/IRS
<a href="https://www.federalregister.gov/documents/2024/07/19/2024-14542/required-minimum-distributions">final
rule 89 FR 58886</a> (RMD ages) &middot;
<a href="https://www.irs.gov/retirement-plans/retirement-plan-and-ira-required-minimum-distributions-faqs">IRS
RMD FAQs</a>. Not tax advice. See the <a href="/rmd/table">full RMD table &amp; RMD ages by birth year</a>.</p>
</body></html>"""

RMD_RESULT = """
<p class="be">{status}</p>
<table><tr><th>Year</th><th>Your age</th><th>Divisor</th><th>RMD</th><th>Deadline</th></tr>
{rows}</table>
{ambiguity}
<p class="note">{penalty}</p>
<p class="note">{note}</p>"""


@app.get("/rmd", response_class=HTMLResponse)
def rmd_page(birth_year: int = 0, balance: float = 0):
    if not birth_year or not balance:
        return HTMLResponse(RMD_PAGE.replace("{by}", "1953")
                            .replace("{bal}", "500000").replace("{results}", ""))
    try:
        req = RmdRequest(birth_year=birth_year, balance=balance)
    except ValidationError as e:
        return HTMLResponse(RMD_PAGE.replace("{by}", str(birth_year))
                            .replace("{bal}", _echo(balance))
                            .replace("{results}", f"<p class='warn'>{e.errors()[0]['msg']}</p>"))
    r = rmd_calculate(req)
    rows = "".join(
        f"<tr><td>{x.year}</td><td>{x.age}</td><td>{x.distribution_period}</td>"
        f"<td>${x.rmd:,.2f}</td><td style='text-align:left'>{x.deadline}</td></tr>"
        for x in r.rows)
    ambiguity = (f"<p class='warn'>{r.ambiguity_note}</p>" if r.ambiguity_note else "")
    block = (RMD_RESULT
             .replace("{status}", r.status)
             .replace("{rows}", rows)
             .replace("{ambiguity}", ambiguity)
             .replace("{penalty}", r.penalty_note)
             .replace("{note}", r.note))
    return HTMLResponse(RMD_PAGE.replace("{by}", str(birth_year))
                        .replace("{bal}", _echo(balance))
                        .replace("{results}", block))


@app.get("/api/rmd")
def rmd_api(birth_year: int, balance: float):
    try:
        return rmd_calculate(RmdRequest(birth_year=birth_year, balance=balance)).model_dump()
    except ValidationError as e:
        return JSONResponse(status_code=422, content={"detail": e.errors()})


IRMAA_BRACKETS_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>2026 IRMAA Brackets (Official Medicare Tiers) - Part B &amp; Part D Costs</title>
<meta name="description" content="The full 2026 IRMAA bracket table straight from
Medicare's official costs fact sheet: Part B and Part D surcharges by income,
the two-year lookback, and the cliff rule that makes one extra dollar costly.">
<style>
 body{font-family:system-ui,sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem;line-height:1.5}
 h1{font-size:1.5rem} h2{font-size:1.15rem;margin-top:1.6rem}
 table{border-collapse:collapse;margin:1rem 0}
 th,td{border:1px solid #ccc;padding:.4rem .7rem;text-align:right;font-variant-numeric:tabular-nums}
 th:first-child,td:first-child{text-align:left}
 .be{background:#f0f7f0;padding:.6rem .8rem;margin:.4rem 0}
 .note{font-size:.8rem;color:#555}
</style></head><body>
<h1>2026 IRMAA brackets</h1>
<p><a href="/irmaa">Run the IRMAA calculator &rarr;</a> &nbsp; <a href="/rmd">RMD calculator &rarr;</a></p>
<p>IRMAA (income-related monthly adjustment amount) is the surcharge Medicare
adds to your Part B and Part D premiums once your income passes a threshold.
For 2026 costs, Medicare reads your <b>2024</b> tax return - a two-year
lookback.</p>
<h2>The 2026 tiers (per person, per month)</h2>
<table><tr><th>Tier</th><th>Single MAGI</th><th>Married filing jointly</th><th>Part B</th><th>Part D add</th></tr>
{tiers}</table>
<p>Part D amounts are on top of your plan's premium; the national base part D
premium for 2026 is $38.99. Tier 1 is the standard premium - most people pay
it with no surcharge.</p>
<h2>Why one extra dollar hurts: the cliff rule</h2>
<p class="be">The brackets are cliffs, not phases. Land $1 over a threshold
and the <b>whole</b> surcharge for that tier applies for the year. A single
filer at $109,000 pays $202.90 for Part B; at $109,001 they pay $284.10 plus a
$14.50 Part D surcharge.</p>
<h2>Married filing separately</h2>
<p>The income bands collapse: at or under $109,000 you stay in tier 1, and
above it you jump straight to tier 5 ($649.20 Part B + $83.30 Part D), then
tier 6 from $391,000.</p>
<h2>Can you fight a tier?</h2>
<p>Yes. If a life-changing event - retirement, a spouse's death, divorce,
job loss - cut your income after the year Medicare is reading, you can ask
Social Security to reassess using <a href="https://www.ssa.gov/forms/ssa-44.html">form
SSA-44</a>. Otherwise the tier stands until the lookback catches up with your
real income.</p>
<p class="note">Every figure above is from the official
<a href="https://www.medicare.gov/publications/11579-medicare-costs.pdf">2026
Medicare costs fact sheet</a> (PDF). MAGI here is adjusted gross income plus
tax-exempt interest. Not tax advice.</p>
</body></html>"""


@app.get("/irmaa/brackets", response_class=HTMLResponse)
def irmaa_brackets_page():
    from money_tools.irmaa import _TIERS
    bands = ["$109,000 or less", "$218,000 or less", "$137,000 or less",
             "$274,000 or less", "$171,000 or less", "$342,000 or less",
             "$205,000 or less", "$410,000 or less", "under $500,000",
             "under $750,000", "$500,000 or more", "$750,000 or more"]
    rows = "".join(
        f"<tr><td>{t + 1}</td><td>{bands[2 * t]}</td><td>{bands[2 * t + 1]}</td>"
        f"<td>${_TIERS[t][3]:,.2f}</td><td>${_TIERS[t][4]:,.2f}</td></tr>"
        for t in range(6))
    return HTMLResponse(IRMAA_BRACKETS_PAGE.replace("{tiers}", rows))


RMD_TABLE_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RMD Table 2026-2027: IRS Uniform Lifetime Table &amp; RMD Ages by Birth Year</title>
<meta name="description" content="The IRS Uniform Lifetime Table (every divisor
from age 72 to 120+), what age your RMDs start by birth year, when the first
one is due, and the 25% penalty for missing one - all from official sources.">
<style>
 body{font-family:system-ui,sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem;line-height:1.5}
 h1{font-size:1.5rem} h2{font-size:1.15rem;margin-top:1.6rem}
 table{border-collapse:collapse;margin:1rem 0}
 th,td{border:1px solid #ccc;padding:.35rem .6rem;text-align:right;font-variant-numeric:tabular-nums}
 th:first-child,td:first-child{text-align:left}
 .be{background:#f0f7f0;padding:.6rem .8rem;margin:.4rem 0}
 .warn{background:#fff8e8;padding:.6rem .8rem;margin:.4rem 0}
 .note{font-size:.8rem;color:#555}
</style></head><body>
<h1>RMD table &amp; RMD ages</h1>
<p><a href="/rmd">Run the RMD calculator &rarr;</a> &nbsp; <a href="/irmaa">IRMAA calculator &rarr;</a></p>
<p>Your required minimum distribution each year is the prior December 31
balance divided by a divisor from the IRS Uniform Lifetime Table, using the
age you reach that year.</p>
<h2>What age do RMDs start?</h2>
<table><tr><th>Birth year</th><th>RMD age</th><th>First RMD year</th></tr>
{ages}</table>
<p class="warn">Born in 1959? The law sets the age as both 73 and 75 - final
IRS rules have not resolved it. Plan for 73 (2032), the earlier reading.</p>
<h2>Your first RMD gets a grace period - use it carefully</h2>
<p class="be">The first RMD can wait until <b>April 1</b> of the following
year. Every later RMD is due by December 31. Defer the first one and you owe
<b>two</b> RMDs in the same year - which can push your income up into a
higher tax bracket or an <a href="/irmaa/brackets">IRMAA tier</a>.</p>
<h2>Uniform Lifetime Table (divisors)</h2>
<table><tr><th>Age</th><th>Divisor</th><th>Age</th><th>Divisor</th><th>Age</th><th>Divisor</th><th>Age</th><th>Divisor</th></tr>
{table}</table>
<p>Example: age 75, $300,000 in IRAs last Dec 31 &rarr; $300,000 &divide; 24.6
= <b>$12,195.12</b> must come out this year.</p>
<h2>Miss it and the tax is 25%</h2>
<p>A missed or short RMD faces a 25% excise tax on the amount not withdrawn,
cut to 10% if corrected within two years (file Form 5329). Compute the RMD
for each IRA you own; you may withdraw the total from one or more of them.
If your sole beneficiary is a spouse 10+ years younger, the Joint Life table
gives smaller RMDs.</p>
<p class="note">Divisors from IRS <a href="https://www.irs.gov/pub/irs-pdf/p590b.pdf">Publication
590-B</a> (2025), Appendix B. RMD ages from the Treasury/IRS
<a href="https://www.federalregister.gov/documents/2024/07/19/2024-14542/required-minimum-distributions">final
rule 89 FR 58886</a>. Deadlines and penalties from the
<a href="https://www.irs.gov/retirement-plans/retirement-plan-and-ira-required-minimum-distributions-faqs">IRS
RMD FAQs</a>. Not tax advice.</p>
</body></html>"""


@app.get("/rmd/table", response_class=HTMLResponse)
def rmd_table_page():
    from money_tools.rmd import _PERIODS, applicable_age
    age_rows = [
        ("Before 1951", "72", "the year you turned 72"),
        ("1951 - 1958", "73", "birth year + 73 (e.g. 1957 &rarr; 2030)"),
        ("1959", "73 or 75 (unresolved)", "2032 or 2034"),
        ("1960 or later", "75", "the year you turn 75"),
    ]
    ages = "".join(f"<tr><td>{y}</td><td>{a}</td><td>{f}</td></tr>" for y, a, f in age_rows)
    items = sorted(_PERIODS.items())
    cols = 4
    per = (len(items) + cols - 1) // cols
    cells = []
    for chunk in range(per):
        row = ""
        for c in range(cols):
            i = chunk + c * per
            if i < len(items):
                row += f"<td>{items[i][0]}</td><td>{items[i][1]}</td>"
        cells.append(f"<tr>{row}</tr>")
    return HTMLResponse(RMD_TABLE_PAGE.replace("{ages}", ages)
                        .replace("{table}", "".join(cells)))


# MCP streamable HTTP at /mcp (stateless: Cloud Run instances come and go).
# Mounted last so the routes above win the path match.
app.mount("/", mcp_app, name="mcp")
