# MailRail public-surface decision

MailRail is an **operator communication rail** (settlement receipts, alerts, inbound postmaster). It is **not** a public x402 product.

## What was exposed

Unauthenticated clients could:

- Call MCP `mailrail.send` and send email/webhooks using the host's Resend/SMTP/webhook credentials.
- Call MCP `mailrail.inbound` and write into the inbox ledger.
- `GET /mailrail/ledger` and `GET /mailrail/inbox` and dump those messages.
- `POST /mailrail/inbound` without a token.

That is open-relay + inbox disclosure on a public seller host. **Do not list these on Smithery.**

## Decision

MailRail is owned by one operator agent: **`x402-mailrail-postmaster`**. No other agent_id may send, ingest, or read ledgers.

| Surface | Public? | Gate |
|---|---|---|
| MCP `mailrail.send` / `mailrail.inbound` / `mailrail.status` | No | Not registered on the public FastMCP server; handlers refuse unless `agent_id=x402-mailrail-postmaster` |
| `POST /mailrail/inbound` | No | `Authorization: Bearer $OPERATOR_TOKEN` **and** `X-Agent-Id: x402-mailrail-postmaster` (fail closed) |
| `GET /mailrail/ledger` / `inbox` / `stats` | No | Same bearer + agent id |
| `GET /mailrail/health` | Yes, readiness only | No message bodies; no admin recipient |
| `GET /agent/mailrail` | Yes, agent card only | No ledgers |
| Internal `mailrail.send_agent_mail` from settlement code | Yes (server-side, as postmaster) | Not an HTTP/MCP public tool |

Public Smithery catalog is x402 / commerce / swarm / pulse / ops / city only.

Operator notify: GitHub issue (if `GITHUB_TOKEN`) and/or email to `MAILRAIL_ADMIN_RECIPIENT` or `CONTACT_EMAIL` (default `kwizzlesurp10@gmail.com`).
