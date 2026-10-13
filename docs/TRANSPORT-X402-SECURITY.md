# Transport architecture: HTTP settlement headers vs SSE

This document resolves a common confusion: **Mission Control SSE** (`GET /events`)
is not the x402 payment transport, and **MCP Streamable HTTP** intentionally
uses JSON bodies rather than SSE for tool calls.

## x402 v2 paid HTTP resources (seller storefront)

Paid SKUs (`/us/{city}/property-check`, `/mn/property-check`, diligence packs,
composites, etc.) follow the x402 v2 wire contract:

| Direction | Header | Role |
|-----------|--------|------|
| Server → client (402) | `PAYMENT-REQUIRED` | Base64 payment requirements |
| Client → server (retry) | `PAYMENT-SIGNATURE` | Buyer authorization |
| Server → client (200) | `PAYMENT-RESPONSE` | Settlement receipt |

Settlement confirmation **must** ride on the **same HTTP response** that
delivers the paid JSON body. That is why successful paid routes return a
normal `JSONResponse` with a `PAYMENT-RESPONSE` header — not an SSE stream.

CORS exposes these headers explicitly (`app/main.py`) so browser clients can
read receipts after payment.

## What SSE is for (and is not)

| Endpoint | Purpose | x402 settlement? |
|----------|---------|------------------|
| `GET /events` | Mission Control telemetry (tool calls, swarm phases, OS alerts) | **No** |
| Legacy MCP SSE mount | Remote MCP clients (when enabled) | **No** — payments use MCP payment errors / `_meta` |
| MCP Streamable HTTP (`json_response=True`) | Smithery / HTTP gateways parse JSON-RPC | Tool credits use commerce overlay; on-chain seller SKUs are HTTP routes above |

**Intentional design:** Real-time SSE is used for **observability**, not for
returning `PAYMENT-RESPONSE`. Mixing settlement headers into an SSE channel would
break x402scan probes, CDP validate_endpoint expectations, and single-request
buyer agents that expect one HTTP round-trip with headers.

## MCP tool transport

`FastMCP` is configured with `json_response=True` and `stateless_http=True`
(`app/mcp_server.py`) so hosted gateways receive plain JSON-RPC bodies. That is
**not** a bug relative to x402 HTTP seller routes — it is a separate transport
for MCP tool discovery and buyer tooling (`pay_and_fetch`, Bazaar probes, etc.).

## Rate limiting before cryptographic work

1. **402 challenges** (no signature): cheap; demand metrics may record probes.
2. **Signed attempts** (`PAYMENT-SIGNATURE` / legacy `X-PAYMENT`): debounced
   per client IP **before** facilitator verify/settle (`payment_signature_rate_limit`
   middleware in `app/main.py`).
3. **Outbound buyer spends** (`pay_and_fetch`): capped by `ledger/policy.json`
   daily/monthly totals when `BUYER_SPEND_POLICY_ENFORCED=true` (default).

## Verification (no spend)

```bash
# Unpaid must be 402 with PAYMENT-REQUIRED, not 422
curl -s -o /dev/null -w "%{http_code}\n" -H "x-demand-ignore: 1" \
  "https://x402-mcp.onrender.com/us/sea/property-check"

# SSE is telemetry only — not used for PAYMENT-RESPONSE
curl -s -N -H "Accept: text/event-stream" --max-time 3 \
  "https://x402-mcp.onrender.com/events" | head -3
```
