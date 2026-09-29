"""US City Network MCP packaging — thin tools over existing HTTP products."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app import mcp_server
from app.city_compliance import mcp_tools as city_mcp
from app.city_compliance import registry
from app.config import settings
from app.tools_registry import EXPECTED_TOOL_NAMES


@pytest.mark.asyncio
async def test_list_us_cities_catalog_shape() -> None:
    data = await city_mcp.list_us_cities()
    assert data["network"] == "us-city-open-data-compliance"
    assert data["city_count"] >= 1
    assert "mn" in {c["code"] for c in data["cities"]}
    assert "golden_path" in data
    assert "list_us_cities" in data["golden_path"]["1_catalog"]
    assert data["cities"][0]["paid_url"].endswith("/property-check")
    assert data["cities"][0]["sample_url"].endswith("/sample")


@pytest.mark.asyncio
async def test_list_us_cities_mcp_wrapper() -> None:
    raw = await mcp_server.list_us_cities(agent_id="city-catalog-agent")
    payload = json.loads(raw)
    assert payload["meta"]["agent_id"]
    assert payload["data"]["network"] == "us-city-open-data-compliance"
    assert payload["data"]["city_count"] == len(registry.list_cities())


@pytest.mark.asyncio
async def test_get_us_city_property_sample_unknown_city() -> None:
    data = await city_mcp.get_us_city_property_sample("not-a-city")
    assert data["error"] == "unknown_city"
    assert "mn" in data["known"]


@pytest.mark.asyncio
async def test_get_us_city_property_sample_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_check(address: str) -> dict[str, Any]:
        return {"address": address, "compliance_verdict": "sample_ok", "city": "mn"}

    mod = registry.get_city("mn")
    monkeypatch.setattr(mod, "check_property", fake_check)

    data = await city_mcp.get_us_city_property_sample("mn")
    assert data["sample"] is True
    assert data["city"] == "mn"
    assert data["report"]["compliance_verdict"] == "sample_ok"
    assert data["next"]["action"] == "check_us_city_property"
    assert "EVM_PRIVATE_KEY" in data["next"]["requires_env"]


@pytest.mark.asyncio
async def test_get_us_city_property_sample_mcp_wrapper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_check(address: str) -> dict[str, Any]:
        return {"address": address, "ok": True}

    monkeypatch.setattr(registry.get_city("sea"), "check_property", fake_check)
    raw = await mcp_server.get_us_city_property_sample(
        city_code="sea", agent_id="city-sample-agent"
    )
    payload = json.loads(raw)
    assert payload["data"]["sample"] is True
    assert payload["data"]["city"] == "sea"
    assert "meta" in payload


@pytest.mark.asyncio
async def test_check_us_city_property_invalid_address() -> None:
    data = await city_mcp.check_us_city_property("mn", "   ")
    assert data["error"] == "invalid_address"


@pytest.mark.asyncio
async def test_check_us_city_property_no_wallet_handoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_probe(params):  # noqa: ANN001
        return {"payment_required": {"price": "0.10"}, "payment_required_header": "test-b64"}

    monkeypatch.setattr(city_mcp.x402_services, "get_payment_requirements", fake_probe)

    res = await city_mcp.check_us_city_property("chi", "121 N LaSalle St")
    assert getattr(res, "isError", False) is True
    assert (res.model_dump().get("meta") or res.model_dump().get("_meta") or {}).get("x402/payment-required") == "test-b64"

@pytest.mark.asyncio
async def test_check_us_city_property_with_wallet_pay_and_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Simulates what happens when a signature IS provided in ctx
    class FakeReq:
        class Params:
            meta = {"x402/payment": "fake-sig"}
        params = Params()
        
    class FakeCtx:
        class ReqCtx:
            request = FakeReq()
        request_context = ReqCtx()
        
    import httpx
    
    class FakeResponse:
        status_code = 200
        headers = {"PAYMENT-RESPONSE": "test-b64"}
        text = '{"compliance_verdict": "paid_ok"}'
        def json(self):
            return {"compliance_verdict": "paid_ok"}
            
    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, *args, **kwargs): return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: FakeClient())

    data = await city_mcp.check_us_city_property("chi", "121 N LaSalle St", ctx=FakeCtx())
    assert getattr(data, "isError", True) is False
    assert (data.model_dump().get("meta") or data.model_dump().get("_meta") or {}).get("x402/payment-response") == "test-b64"

@pytest.mark.asyncio
async def test_check_us_city_property_mcp_wrapper_no_wallet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_probe(params):  # noqa: ANN001
        return {"payment_required": {"price": "0.10"}, "payment_required_header": "test-b64"}

    monkeypatch.setattr(city_mcp.x402_services, "get_payment_requirements", fake_probe)

    # Note: the test used to call mcp_server.check_us_city_property
    raw = await mcp_server.check_us_city_property(
        city_code="nyc",
        address="1 Centre St",
        ctx=None,
        agent_id="city-paid-agent",
    )
    import json
    # _execute_tool intercepts CallToolResult and returns it directly now
    assert getattr(raw, "isError", False) is True
