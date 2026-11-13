# Money Tools

US retirement calculators. Every number cited to a public source; every rule
tested against SSA's own published percentages. See `docs/SOURCES.md`.

## Tools

- **Social Security break-even** — monthly benefit and cumulative totals for
  claiming at 62/67/70 (or any whole ages), with pairwise break-even ages.
  All figures in today's dollars.

## Run locally

```
python -m venv .venv
.venv/Scripts/python -m pip install -e . fastapi uvicorn httpx pytest
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m uvicorn money_tools.app:app --port 8080
```

Web: http://127.0.0.1:8080/?birth_year=1965&pia=2500
JSON API: http://127.0.0.1:8080/api/break-even?birth_year=1965&pia=2500&ages=62,68,70

## MCP server (stdio, for Claude and other MCP clients)

```
.venv/Scripts/python -m money_tools.mcp_server
```

Tool: `ss_break_even(birth_year, pia, claim_ages?)`.

## Deploy (Cloud Run, scale-to-zero)

```
gcloud run deploy money-tools --source . --region asia-south1 \
  --allow-unauthenticated --max-instances 1 --memory 256Mi --cpu 1
```

Cost guardrails: min instances 0 (idle = free), max instances 1 (hard compute
ceiling), budget alert $2/month on the project.
