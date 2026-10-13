# Security Policy

## Supported Versions

We actively support the latest minor release of x402-mcp with security updates.

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

Only the current 0.1.x line receives security patches. Older pre-release or untagged commits are unsupported.

## Reporting a Vulnerability

**Do not open public GitHub issues or pull requests for security vulnerabilities.**

### Preferred Reporting Channels

1. **GitHub Private Vulnerability Reporting** (recommended if enabled for this repository): Use the "Report a vulnerability" button on the Security tab.
2. **Email**: Send a detailed report to `kwizzlesurp10@gmail.com` with the subject line `[SECURITY] x402-mcp`.

Include as much detail as possible:
- Description of the vulnerability and its impact
- Steps to reproduce (PoC if available)
- Affected versions / commit SHA
- Suggested remediation (optional)

### Response Timeline

- **Acknowledgment**: Within 48 hours of receipt
- **Status updates**: At least every 7 days while the report is under investigation
- **Resolution target**: Critical issues within 14 days; high/medium within 30 days where feasible

### What to Expect

- **Accepted**: We will confirm the issue, develop and test a fix, coordinate disclosure timing with you, and credit you in the advisory / release notes if you wish (anonymous reporting is fully supported).
- **Declined**: We will provide a clear explanation (e.g., not reproducible, out of scope, already fixed, or accepted risk). You may request a second review.

### Scope Notes

This policy covers the x402-mcp codebase, its dependencies as used in the project, the seller storefront endpoints, payment verification/settlement paths, quota and Redis stores, and the operator dashboard. Issues in upstream x402 SDKs, Coinbase CDP, or third-party facilitators should be reported to their respective maintainers; we will still assist in triage when relevant.

MailRail send/inbound and message ledgers are **operator-only**. They are not public MCP tools. HTTP ingest/ledger/inbox/stats require `Authorization: Bearer $OPERATOR_TOKEN` and fail closed if the token is unset. See [docs/MAILRAIL-PUBLIC-SURFACE.md](docs/MAILRAIL-PUBLIC-SURFACE.md).

Thank you for helping keep x402-mcp and the agent commerce ecosystem secure.

## Credential hygiene and git history

### Preflight audit

```bash
bash scripts/audit_git_secrets.sh
```

If this reports committed `.env`, `.pem`, `.keys/`, or `id.json` blobs, run (with team
coordination — rewrites history):

```bash
bash scripts/git_history_purge_secrets.sh
```

### Rotation checklist (local dev compromise or suspected leak)

Rotate **all** of the following on the operator machine and hosting provider
(Render, CDP portal, etc.):

| Secret | Action |
|--------|--------|
| `EVM_PRIVATE_KEY` | Generate new burner EOA; fund minimally; update `.env` |
| `SVM_PRIVATE_KEY` | New Solana burner; never recommit `id.json` |
| `CDP_API_KEY_ID` / `CDP_API_KEY_SECRET` | Revoke in CDP portal; issue new Ed25519 key |
| `OPERATOR_TOKEN` / Stripe keys | Rotate if `.env` was shared or committed |
| GitHub PAT / deploy tokens | Revoke if `.env` or CI logs exposed them |

Public seller deploys should keep `wallet_configured: false` on untrusted hosts;
buyer keys belong only on operator-controlled machines with `ledger/policy.json`
caps enabled (`BUYER_SPEND_POLICY_ENFORCED=true` by default).

### IP debouncing

Inbound `PAYMENT-SIGNATURE` attempts are rate-limited per IP before facilitator
verify/settle. Tune with `PAYMENT_SIGNATURE_RATE_LIMIT_PER_MIN` (default `30`).
