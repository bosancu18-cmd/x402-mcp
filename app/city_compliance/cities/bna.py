"""Nashville, TN — short-term rental permits (public Metro open data)."""

from __future__ import annotations

import time
from typing import Any

from app.city_compliance.models import CitySpec, base_report
from app.city_compliance.socrata import address_like_clause, soda_get, source_url

PORTAL = "https://data.nashville.gov"
RESOURCE = "2d8v-ps6s"  # Short Term Rental Permits

SPEC = CitySpec(
    code="bna",
    name="Nashville",
    state="TN",
    service_name="Nashville STR Permit Check",
    tags=("nashville", "str", "rental-license", "housing", "diligence"),
    description=(
        "Nashville short-term rental permit check: is this property permitted "
        "for STR? Property due diligence agent for Nashville Davidson County "
        "housing compliance open data. GET ?address= → permit number, status, "
        "type. Live Metro Nashville JSON. Host compliance, HOA, agent workflows."
    ),
    sample_address="1 PUBLIC SQ",
    sample_note=(
        "Free fixed-address sample of Nashville short-term rental permits. "
        "Any other Nashville address requires payment."
    ),
    sources_label="Nashville Open Data — Short Term Rental Permits",
)

_CACHE_TTL = 900
_cache: dict[str, tuple[float, dict[str, Any]]] = {}


async def check_property(address: str) -> dict[str, Any]:
    key = address.strip().upper()
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] <= _CACHE_TTL:
        return hit[1]

    try:
        rows = await soda_get(
            PORTAL,
            RESOURCE,
            where=address_like_clause("address", address),
            limit=20,
        )
    except Exception:
        rows = []

    registrations = [
        {
            "address": r.get("address") or r.get("street_address") or r.get("property_address"),
            "permit_number": r.get("permit_number") or r.get("permit") or r.get("license"),
            "status": r.get("status") or r.get("permit_status") or r.get("license_status"),
            "permit_type": r.get("type") or r.get("permit_type"),
            "expiration_date": r.get("expiration_date") or r.get("expire_date"),
        }
        for r in rows
    ]
    active = [
        r
        for r in registrations
        if "active" in (r.get("status") or "").lower()
        or "issued" in (r.get("status") or "").lower()
    ]
    if active:
        verdict = "str_licensed_active"
    elif registrations:
        verdict = "str_licensed_inactive"
    else:
        verdict = "str_unlicensed"

    report = base_report(
        city=SPEC,
        address=address,
        compliance_verdict=verdict,
        registrations=registrations,
        violations={
            "total": 0,
            "recent": [],
            "note": "STR permit feed only; no code-enforcement join in this product",
        },
        sources=[source_url(PORTAL, RESOURCE)],
        extra={
            "product_scope": "short_term_rental_permit",
            "active_licenses": len(active),
        },
    )
    _cache[key] = (time.monotonic(), report)
    return report


def discovery_output_example() -> dict[str, Any]:
    return {
        "city": "bna",
        "city_name": "Nashville",
        "state": "TN",
        "address_queried": SPEC.sample_address,
        "compliance_verdict": "str_unlicensed",
        "registered": False,
        "registrations": [],
        "violation_cases": {"total": 0, "recent": []},
    }
