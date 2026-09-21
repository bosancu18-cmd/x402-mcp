# Cloud/dev env steward

Canonical system prompt (copy into Cursor / Grok / Claude cloud agents):

- `.claude/agents/x402-env-steward.md`
- `.grok/agents/x402-env-steward.md`

Those files win on a conflict. This page is the operator index.

## What it manages

Private Google Drive file **`x402-mcp.env`** (folder `x402-mcp private environment`, owner-only). Cloud/dev agents install it to `/workspace/.env` (gitignored). It is **not** the production Render secret store.

## Invoke

> You are x402-env-steward. Follow `.claude/agents/x402-env-steward.md`. Authenticate Google Drive if needed, install `x402-mcp.env` to `/workspace/.env` without printing it, and audit that Drive permissions are owner-only. Do not spend. Do not touch `EVM_PRIVATE_KEY` / `SVM_PRIVATE_KEY`. Do not commit `.env`. Do not list this agent on MCP or `/.well-known/agents.json`.

## Do not

- Share the Drive folder
- Put spend keys in Drive
- Commit `.env`
- Advertise this steward on public discovery (`app/agent_surface.py`, OpenAPI, Smithery)
