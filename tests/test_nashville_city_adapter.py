"""Nashville (bna) extra public city adapter — catalog + unpaid 402."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.city_compliance import registry
from app.config import settings
from app.main import app

client = TestClient(app)


def test_bna_is_public_at_city_network_price() -> None:
    codes = {c["code"] for c in registry.list_cities()}
    assert "bna" in codes
    entry = next(c for c in registry.list_cities() if c["code"] == "bna")
    assert entry["price"] == settings.city_network_price
    assert entry["paid_url"].endswith("/us/bna/property-check")


def test_bna_unpaid_property_check_is_402_not_stub() -> None:
    response = client.get("/us/bna/property-check")
    assert response.status_code != 404
    assert response.status_code != 501
    if response.status_code == 503:
        return
    assert response.status_code == 402
