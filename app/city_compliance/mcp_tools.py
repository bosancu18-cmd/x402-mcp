"""MCP-facing wrappers around the US City Open-Data Compliance Network.

Thin packaging only — no new product surface. Catalog + free samples hit the
in-process registry; paid checks route through the same HTTP x402 URLs external
buyers use (``pay_and_fetch`` / ``get_payment_requirements``).
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from app.city_compliance import agentmail, gate, registry
from app.config import settings
from app.models import GetPaymentRequirementsInput, PayAndFetchInput
from app import x402_services


def _catalog_payload() -> dict[str, Any]:
    base = settings.public_base_url.rstrip("/")
    cities = registry.list_cities()
    return {
        "network": "us-city-open-data-compliance",
        "price": settings.city_network_price,
        "network_caip2": settings.x402_default_network,
        "city_count": len(cities),
        "cities": cities,
        "catalog_url": f"{base}/us/cities",
        "golden_path": {
            "1_catalog": "list_us_cities (this tool) or GET /us/cities",
            "2_sample": (
                "get_us_city_property_sample(city_code=…) — free fixed-address "
                "shape check before paying"
            ),
            "3_paid": (
                "check_us_city_property(city_code=…, address=…) — requires "
                "EVM_PRIVATE_KEY on the MCP client host; settles USDC via x402"
            ),
            "http_equivalent": (
                f"GET {base}/us/{{code}}/property-check?address=… "
                "with PAYMENT-SIGNATURE after 402"
            ),
        },
        "note": (
            "Each city is a separate paid resource at /us/{code}/property-check. "
            "Minneapolis (mn) is also available at canonical /mn/property-check."
        ),
    }


async def list_us_cities(*, agent_id: str | None = None) -> dict[str, Any]:
    """Free machine catalog — same payload shape as GET /us/cities + MCP path."""
    payload = _catalog_payload()
    agentmail.notify_city_call(
        "catalog",
        channel="mcp",
        agent_id=agent_id,
        price=settings.city_network_price,
        detail=f"city_count={payload['city_count']}",
    )
    return payload


async def get_us_city_property_sample(
    city_code: str,
    *,
    agent_id: str | None = None,
) -> dict[str, Any]:
    """Free fixed-address sample for one city (no payment)."""
    code = (city_code or "").strip().lower()
    try:
        mod = registry.get_city(code)
    except KeyError:
        agentmail.notify_city_call(
            "error",
            city_code=code or None,
            channel="mcp",
            agent_id=agent_id,
            detail="unknown_city",
        )
        return {
            "error": "unknown_city",
            "city": city_code,
            "known": list(registry.known_codes()),
            "catalog_url": f"{settings.public_base_url.rstrip('/')}/us/cities",
            "hint": "Call list_us_cities() for codes, paid_url, and sample_address.",
        }

    spec = mod.SPEC
    try:
        report = await mod.check_property(spec.sample_address)
    except Exception as exc:  # noqa: BLE001 — surface upstream failure to agent
        agentmail.notify_city_call(
            "error",
            city_code=spec.code,
            city_name=spec.name,
            state=spec.state,
            channel="mcp",
            agent_id=agent_id,
            address=spec.sample_address,
            detail=f"upstream_open_data_unavailable:{type(exc).__name__}",
        )
        return {
            "error": "upstream_open_data_unavailable",
            "city": spec.code,
            "detail": "city open-data source timed out or refused; retry shortly",
            "exception_type": type(exc).__name__,
            "sample_url": gate.sample_url(spec),
            "paid_url": gate.resource_url(spec),
        }

    paid = gate.resource_url(spec)
    agentmail.notify_city_call(
        "sample",
        city_code=spec.code,
        city_name=spec.name,
        state=spec.state,
        channel="mcp",
        agent_id=agent_id,
        address=spec.sample_address,
        price=gate.price_for(spec),
        verdict=agentmail.verdict_from_report(report),
        paid=False,
    )
    return {
        "sample": True,
        "city": spec.code,
        "name": spec.name,
        "state": spec.state,
        "sample_address": spec.sample_address,
        "note": spec.sample_note,
        "paid_endpoint": paid,
        "paid_url": paid,
        "sample_url": gate.sample_url(spec),
        "price": gate.price_for(spec),
        "network": settings.x402_default_network,
        "report": report,
        "next": {
            "action": "check_us_city_property",
            "city_code": spec.code,
            "address": "<street address 1-120 chars>",
            "requires_env": ["EVM_PRIVATE_KEY"],
            "http": f"{paid}?address=<url-encoded street>",
            "note": (
                "Sample is a fixed address only. Pay for an arbitrary address "
                "via check_us_city_property or pay_and_fetch on paid_url."
            ),
        },
    }


def _paid_url(city_code: str, address: str) -> tuple[Any, str] | dict[str, Any]:
    code = (city_code or "").strip().lower()
    try:
        mod = registry.get_city(code)
    except KeyError:
        return {
            "error": "unknown_city",
            "city": city_code,
            "known": list(registry.known_codes()),
            "catalog_url": f"{settings.public_base_url.rstrip('/')}/us/cities",
        }
    addr = (address or "").strip()
    if not addr or len(addr) > 120:
        return {
            "error": "invalid_address",
            "detail": "address must be 1-120 chars",
            "city": code,
            "sample_address": mod.SPEC.sample_address,
            "hint": (
                f"Try get_us_city_property_sample(city_code={code!r}) for a free "
                "fixed-address report first."
            ),
        }
    url = f"{gate.resource_url(mod.SPEC)}?address={quote(addr, safe='')}"
    return mod, url


async def check_us_city_property(
    city_code: str,
    address: str,
    *,
    ctx: Any = None,
    max_price_usdc: float | None = None,
    preferred_network: str | None = None,
    agent_id: str | None = None,
) -> Any:
    """Paid compliance check via the live HTTP x402 resource.

    Uses standard MCP payment rails via _meta.
    """
    from mcp.types import CallToolResult, TextContent
    import json as _json
    import httpx

    resolved = _paid_url(city_code, address)
    if isinstance(resolved, dict):
        return resolved
    mod, url = resolved
    spec = mod.SPEC
    price = gate.price_for(spec)

    payment_signature = None
    if ctx and hasattr(ctx, "request_context"):
        req = ctx.request_context.request
        if req and req.params and hasattr(req.params, "meta") and req.params.meta:
            payment_signature = req.params.meta.get("x402/payment")

    if not payment_signature:
        try:
            probe = await x402_services.get_payment_requirements(
                GetPaymentRequirementsInput(url=url, method="GET")
            )
        except httpx.RequestError as exc:
            return CallToolResult(
                isError=True,
                content=[TextContent(type="text", text=_json.dumps({
                    "error": "upstream_unavailable",
                    "detail": f"failed to fetch payment requirements: {exc}"
                }))]
            )
        except Exception as exc:
            return CallToolResult(
                isError=True,
                content=[TextContent(type="text", text=_json.dumps({
                    "error": "internal_error",
                    "detail": f"failed to generate payment requirements: {exc}"
                }))]
            )
        payment_required = probe.get("payment_required")
        
        agentmail.notify_city_call(
            "paid_probe",
            city_code=spec.code,
            city_name=spec.name,
            state=spec.state,
            channel="mcp",
            agent_id=agent_id,
            address=address.strip(),
            price=price,
            paid=False,
            detail="buyer_wallet_not_configured",
        )
        
        if not payment_required:
            return {"error": "challenge_failed", "probe": probe}
            
        return CallToolResult(
            isError=True,
            meta={"x402/payment-required": probe.get("payment_required_header")},
            content=[TextContent(type="text", text=_json.dumps({
                "error": "PaymentRequired",
                "message": "This tool requires x402 payment.",
                "payment_required": payment_required
            }))]
        )

    # We have a signature, make the request
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers={"PAYMENT-SIGNATURE": payment_signature})
    except httpx.RequestError as exc:
        return CallToolResult(
            isError=True,
            content=[TextContent(type="text", text=_json.dumps({
                "error": "upstream_unavailable",
                "detail": f"failed to complete payment request: {exc}"
            }))]
        )
    except Exception as exc:
        return CallToolResult(
            isError=True,
            content=[TextContent(type="text", text=_json.dumps({
                "error": "internal_error",
                "detail": f"unexpected error during payment request: {exc}"
            }))]
        )
        
    payment_response = resp.headers.get("PAYMENT-RESPONSE")
    
    if resp.status_code != 200:
        return CallToolResult(
            isError=True,
            content=[TextContent(type="text", text=resp.text)]
        )
        
    body_report = None
    try:
        body_report = resp.json()
    except Exception:
        pass
        
    agentmail.notify_city_call(
        "paid_mcp",
        city_code=spec.code,
        city_name=spec.name,
        state=spec.state,
        channel="mcp",
        agent_id=agent_id,
        address=address.strip(),
        price=price,
        verdict=agentmail.verdict_from_report(body_report),
        paid=True,
    )
    
    meta_dict = {}
    if payment_response:
        meta_dict["x402/payment-response"] = payment_response

    return CallToolResult(
        isError=False,
        meta=meta_dict if meta_dict else None,
        content=[TextContent(type="text", text=resp.text)]
    )
