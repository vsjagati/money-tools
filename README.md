# Money Tools

US retirement calculators. Every number cited to a public source; every rule
tested against SSA's own published percentages. See `docs/SOURCES.md`.

## Install

**Claude Code** (one command each):

```
/plugin marketplace add vsjagati/money-tools
/plugin install money-tools@money-tools-marketplace
```

**Any MCP client** (Cursor, Claude Desktop connectors, Goose, ...): add a
remote server with the URL

```
https://money-tools-547074823179.asia-south1.run.app/mcp
```

**Just use the calculators**: [Social Security break-even](https://money-tools-547074823179.asia-south1.run.app/)
· [Roth conversion IRMAA](https://money-tools-547074823179.asia-south1.run.app/irmaa)
· [RMD](https://money-tools-547074823179.asia-south1.run.app/rmd)

Reference pages: [2026 IRMAA brackets](https://money-tools-547074823179.asia-south1.run.app/irmaa/brackets)
· [RMD table &amp; ages](https://money-tools-547074823179.asia-south1.run.app/rmd/table)

Also listed in the [official MCP registry](https://registry.modelcontextprotocol.io):
`io.github.vsjagati/money-tools`.

## Tools

- **Social Security break-even** — monthly benefit and cumulative totals for
  claiming at 62/67/70 (or any whole ages), with pairwise break-even ages.
  All figures in today's dollars.
- **Roth conversion IRMAA** — what a conversion does to Medicare Part B/D
  costs two years later, per 2026 tiers.
- **RMD** — this year's required minimum distribution and the next two, from
  the IRS Uniform Lifetime Table; flags the unresolved 1959-birth ambiguity
  in the law instead of guessing.

## Run locally

```
python -m venv .venv
.venv/Scripts/python -m pip install -e . fastapi uvicorn httpx pytest
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m uvicorn money_tools.app:app --port 8080
```

Web: http://127.0.0.1:8080/?birth_year=1965&pia=2500
JSON API: http://127.0.0.1:8080/api/break-even?birth_year=1965&pia=2500&ages=62,68,70

## MCP server (for Claude and other MCP clients)

Two transports, same tools (`ss_break_even`, `roth_irmaa`, `rmd`):

- **Streamable HTTP** (live): `https://money-tools-547074823179.asia-south1.run.app/mcp`
- **stdio** (local): `.venv/Scripts/python -m money_tools.mcp_server`

## Deploy (Cloud Run, scale-to-zero)

```
gcloud run deploy money-tools --source . --region asia-south1 \
  --allow-unauthenticated --max-instances 1 --memory 256Mi --cpu 1
```

Cost guardrails: min instances 0 (idle = free), max instances 1 (hard compute
ceiling), budget alert $2/month on the project.
