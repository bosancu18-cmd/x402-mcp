"""MN property compliance product: paid x402 HTTP resource.

Composite rental-compliance snapshot for a Minneapolis address, sourced live
from the City of Minneapolis Open Data ArcGIS services (public records):

- Active_Rental_Licenses  — license status/tier/units/expiry, joined by APN to
- CaseViolations          — regulatory-services violation case inspections
- Condemned_by_Boarding   — condemned / boarded properties

One paid call answers "is this rental licensed, and does it have a violation
or condemnation history?" — the seller side of this repo's own protocol
tooling (requirements built and settled via the same x402ResourceServer path
as the pro-tier / tool-credit flows).

Owner phone/email exist in the source data but are intentionally not served.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import settings

# ---- TTL cache for ArcGIS responses ----------------------------------------
# Avoids re-hitting the city endpoint for repeated queries within the window.
# Keyed on normalised address; entries expire after _CACHE_TTL seconds.

_CACHE_TTL = 900  # 15 minutes
_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _cache_get(key: str) -> dict[str, Any] | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, data = entry
    if time.monotonic() - ts > _CACHE_TTL:
        _cache.pop(key, None)
        return None
    return data


def _cache_set(key: str, data: dict[str, Any]) -> None:
    _cache[key] = (time.monotonic(), data)

LICENSE_FIELDS = (
    "address,apn,licenseNumber,category,tier,status,issueDate,expirationDate,"
    "licensedUnits,ownerName,ward,neighborhoodDesc,communityDesc,shortTermRental"
)
VIOLATION_FIELDS = (
    "APN,Violation_Case_Number,Case_Type,Case_Group,Status_Violation,"
    "Status_Violation_Case,Milestone_Violation_Case,Violation_Code,"
    "Violation_Code_Description,Processed_Date,Resolved_Date"
)
CONDEMNED_FIELDS = "APN,Address,VBR_Date,CONB,Ward,Neighborho"

# Written query-shaped, and this matters more here than anywhere else in the
# repo: a discovery catalog indexes the description ONCE, at the settle that
# first catalogs the resource, and never revisits it. The words below are the
# only words a buying agent can match on. So it leads with the question a buyer
# actually asks, names the locality the way people write it (Minneapolis /
# Minnesota / Hennepin County), and names the jobs this gets hired for --
# rather than describing the endpoint to another engineer.
#
# 500 chars is the CDP ceiling (_clamp_description); this sits under it.
RESOURCE_DESCRIPTION = (
    "Minneapolis rental license check — is this property licensed? Property due "
    "diligence agent for Minneapolis Minnesota (Hennepin) housing compliance open "
    "data. GET ?address= (street 1-120 chars) → compliance_verdict "
    "(licensed_clean|licensed_with_violations|unlicensed|condemned_or_boarded), "
    "rental license status/tier/units/expiration, violation cases, condemned/"
    "boarded. Live City JSON. Tenant screening, landlord DD, lending. Sample: "
    "/mn/property-check/sample."
)

# Per-resource Bazaar metadata (facilitator: name <=32, <=5 tags x <=32 chars).
# Must NOT inherit the storefront defaults (base,intelligence) — those describe
# Base L2 fee products, not Minneapolis rental compliance, and agents filter
# catalogs by these tags. Fingerprinted into the challenge cache.
SERVICE_NAME = "MN Rental License Check"
SERVICE_TAGS = ["minneapolis", "rental-license", "compliance", "housing", "diligence"]


def _escape(value: str) -> str:
    """Escape a value for an ArcGIS SQL where clause (single-quote doubling)."""
    return value.replace("'", "''")


def _iso(epoch_ms: Any) -> str | None:
    if not isinstance(epoch_ms, (int, float)):
        return None
    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).date().isoformat()


# City of Minneapolis Regulatory Services case statuses, read off the live
# CaseViolations layer (2026-10-08). The old outFields
# (Inspection_Result, Inspection_Type_Desc, Start_Date, Completed_Date) are
# not columns anymore — a query that names them is rejected, so a paid check
# cannot see violations. Status_Violation "Abate" on a Closed case is history,
# not an open violation. licensed_with_violations means at least one open line.
_CLOSED_CASE_STATUS = frozenset(
    {"closed", "cancelled", "canceled", "deleted", "void"}
)
_OPEN_CASE_STATUS = frozenset(
    {
        "open",
        "in process",
        "enforce",
        "hold",
        "pending",
        "stop work",
        "fireescrow",
        "assessed",
    }
)
_RESOLVED_VIOLATION_STATUS = frozenset(
    {
        "abate",
        "cancel",
        "cancelled",
        "canceled",
        "n/a",
        "mitigate",
        "cos",
        "transfer",
        "",
    }
)
_CLOSED_MILESTONE = frozenset(
    {"case closed", "closed", "cancelled", "canceled", "case cancelled"}
)


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _violation_is_open(row: dict) -> bool:
    """True when this violation line is still actionable, not abated history."""
    case = _norm(row.get("Status_Violation_Case"))
    viol = _norm(row.get("Status_Violation") or row.get("Inspection_Result"))
    milestone = _norm(row.get("Milestone_Violation_Case"))
    if case in _CLOSED_CASE_STATUS:
        return False
    if case in _OPEN_CASE_STATUS:
        return True
    if milestone in _CLOSED_MILESTONE and viol in _RESOLVED_VIOLATION_STATUS:
        return False
    if viol in _RESOLVED_VIOLATION_STATUS and not case:
        return False
    if viol and viol not in _RESOLVED_VIOLATION_STATUS:
        return True
    if milestone and milestone not in _CLOSED_MILESTONE:
        return True
    return False


def _epoch(row: dict, *keys: str) -> Any:
    for key in keys:
        if key in row and isinstance(row.get(key), (int, float)):
            return row[key]
    return 0


def _violation_record(row: dict) -> dict[str, Any]:
    open_line = _violation_is_open(row)
    start = row.get("Processed_Date") if "Processed_Date" in row else row.get("Start_Date")
    if "Resolved_Date" in row:
        completed = row.get("Resolved_Date")
    else:
        completed = row.get("Completed_Date")
    result = row.get("Status_Violation")
    if result is None:
        result = row.get("Inspection_Result")
    return {
        "case_number": row.get("Violation_Case_Number"),
        "case_type": row.get("Case_Type"),
        "case_group": row.get("Case_Group"),
        "inspection_result": result,
        "inspection_type": row.get("Violation_Code_Description")
        or row.get("Inspection_Type_Desc"),
        "violation_code": row.get("Violation_Code"),
        "case_status": row.get("Status_Violation_Case"),
        "milestone": row.get("Milestone_Violation_Case"),
        "open": open_line,
        "start_date": _iso(start),
        "completed_date": _iso(completed),
    }


def _buyer_summary(
    *,
    licensed: bool,
    verdict: str,
    open_count: int,
    closed_count: int,
    condemned: bool,
) -> str:
    if condemned:
        return (
            "Condemned or boarded on City of Minneapolis records. "
            "Do not treat the rental license as clear."
        )
    if not licensed:
        tail = (
            f" {open_count} open violation line(s) still on file."
            if open_count
            else " No condemned/boarded record on the address match."
        )
        return "No active Minneapolis rental license for this address." + tail
    if verdict == "licensed_with_violations":
        return (
            f"Active rental license with {open_count} open violation line(s) "
            f"and {closed_count} closed/abated. Not condemned."
        )
    if closed_count:
        return (
            f"Active rental license. {closed_count} historical violation line(s), "
            "all closed/abated. Not condemned."
        )
    return "Active rental license. No violation lines and not condemned."


async def _query(
    client: httpx.AsyncClient, dataset: str, where: str, out_fields: str, limit: int
) -> list[dict]:
    response = await client.get(
        f"{settings.mn_data_base_url}/{dataset}/FeatureServer/0/query",
        params={
            "where": where,
            "outFields": out_fields,
            "resultRecordCount": limit,
            "returnGeometry": "false",
            "f": "json",
        },
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise ValueError(f"{dataset} query error: {payload['error']}")
    return [f["attributes"] for f in payload.get("features", [])]


async def check_property(address: str) -> dict[str, Any]:
    """Compose the compliance report for a Minneapolis street address."""
    needle = _escape(address.strip().upper())

    cached = _cache_get(needle)
    if cached is not None:
        return cached

    async with httpx.AsyncClient(timeout=25.0) as client:
        licenses = await _query(
            client,
            "Active_Rental_Licenses",
            f"UPPER(address) LIKE '{needle}%'",
            LICENSE_FIELDS,
            10,
        )

        apns = sorted({l["apn"] for l in licenses if l.get("apn")})
        violations: list[dict] = []
        condemned: list[dict] = []
        if apns:
            import asyncio
            apn_list = ", ".join(f"'{_escape(a)}'" for a in apns)
            violations, condemned = await asyncio.gather(
                _query(
                    client,
                    "CaseViolations",
                    f"APN IN ({apn_list})",
                    VIOLATION_FIELDS,
                    200,
                ),
                _query(
                    client,
                    "Condemned_by_Boarding",
                    f"APN IN ({apn_list})",
                    CONDEMNED_FIELDS,
                    10,
                )
            )
        else:
            # No license found — still check condemned/boarded by address so a
            # completely unlicensed problem property is not reported as clean.
            condemned = await _query(
                client,
                "Condemned_by_Boarding",
                f"UPPER(Address) LIKE '{needle}%'",
                CONDEMNED_FIELDS,
                10,
            )

    recent_violations = sorted(
        violations,
        key=lambda v: (
            0 if _violation_is_open(v) else 1,
            -(_epoch(v, "Processed_Date", "Start_Date") or 0),
        ),
    )[:10]

    licensed = bool(licenses)
    condemned_flagged = bool(condemned)
    violation_total = len(violations)
    open_count = sum(1 for v in violations if _violation_is_open(v))
    closed_count = violation_total - open_count
    # One-token decision for agent buyers. Severity: condemned > unlicensed >
    # licensed with an OPEN violation line > clean. Abated/closed history stays
    # in violation_cases but does not flip the verdict — that false positive
    # was flagging fully abated rentals as licensed_with_violations.
    if condemned_flagged:
        compliance_verdict = "condemned_or_boarded"
    elif not licensed:
        compliance_verdict = "unlicensed"
    elif open_count > 0:
        compliance_verdict = "licensed_with_violations"
    else:
        compliance_verdict = "licensed_clean"

    report = {
        "address_queried": address.strip(),
        "compliance_verdict": compliance_verdict,
        "rental_licenses": [
            {
                "address": l.get("address"),
                "apn": l.get("apn"),
                "license_number": l.get("licenseNumber"),
                "status": l.get("status"),
                "tier": l.get("tier"),
                "category": l.get("category"),
                "licensed_units": l.get("licensedUnits"),
                "owner_name": l.get("ownerName"),
                "issue_date": _iso(l.get("issueDate")),
                "expiration_date": _iso(l.get("expirationDate")),
                "ward": l.get("ward"),
                "neighborhood": l.get("neighborhoodDesc"),
                "community": l.get("communityDesc"),
                "short_term_rental": l.get("shortTermRental"),
            }
            for l in licenses
        ],
        "licensed": licensed,
        "buyer_summary": _buyer_summary(
            licensed=licensed,
            verdict=compliance_verdict,
            open_count=open_count,
            closed_count=closed_count,
            condemned=condemned_flagged,
        ),
        "violation_cases": {
            "total": violation_total,
            "open": open_count,
            "closed": closed_count,
            "recent": [_violation_record(v) for v in recent_violations],
        },
        "condemned_or_boarded": {
            "flagged": condemned_flagged,
            "records": [
                {
                    "address": c.get("Address"),
                    "apn": c.get("APN"),
                    "vbr_date": c.get("VBR_Date"),
                    "condemned_by_boarding": c.get("CONB"),
                    "ward": c.get("Ward"),
                    "neighborhood": c.get("Neighborho"),
                }
                for c in condemned
            ],
        },
        "sources": [
            f"{settings.mn_data_base_url}/Active_Rental_Licenses/FeatureServer/0",
            f"{settings.mn_data_base_url}/CaseViolations/FeatureServer/0",
            f"{settings.mn_data_base_url}/Condemned_by_Boarding/FeatureServer/0",
        ],
        "disclaimer": (
            "Public records from City of Minneapolis Open Data, served as-is; "
            "not legal advice. Verify with the city before acting."
        ),
        "generated_at": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
    }

    _cache_set(needle, report)
    return report


# ---- x402 seller gate -------------------------------------------------------


def resource_url() -> str:
    return f"{settings.public_base_url}/mn/property-check"


# Free sample address: same shape as a paid response, fixed so the free path
# cannot substitute for the paid product (any other address still requires
# payment). Used by GET /mn/property-check/sample and discovery docs.
SAMPLE_ADDRESS = "1700 Penn Ave N"

# Bazaar discovery examples: buyers call GET {resource_url}?address=... and
# receive a report shaped like check_property()'s output. Small but faithful
# excerpts — the CDP facilitator catalogs these verbatim at settle time.
DISCOVERY_INPUT_EXAMPLE: dict[str, Any] = {"address": SAMPLE_ADDRESS}

DISCOVERY_OUTPUT_EXAMPLE: dict[str, Any] = {
    "address_queried": "1700 Penn Ave N",
    "compliance_verdict": "licensed_with_violations",
    "licensed": True,
    "rental_licenses": [
        {
            "address": "1700 PENN AVE N",
            "apn": "1602924310042",
            "license_number": "LIC394217",
            "status": "Active",
            "tier": "Tier 1",
            "category": "CONV",
            "licensed_units": 1,
            "expiration_date": "2027-03-01",
            "ward": "5",
            "neighborhood": "Willard - Hay",
        }
    ],
    "violation_cases": {
        "total": 1,
        "recent": [
            {
                "case_number": "RS-2025-01",
                "case_type": "Rental License",
                "inspection_result": "Violations Found",
                "start_date": "2025-01-01",
            }
        ],
    },
    "condemned_or_boarded": {"flagged": False, "records": []},
    "disclaimer": "Public records from City of Minneapolis Open Data.",
    "generated_at": "2026-07-16T00:00:00+00:00",
}


def build_payment_required_header() -> str:
    """Base64 x402 v2 PAYMENT-REQUIRED header for this resource.

    Delegates to build_seller_requirements so the challenge carries
    ResourceInfo plus (per BAZAAR_DISCOVERABLE) the Bazaar discovery
    extension — without it a settled payment through the CDP facilitator
    catalogs nothing and this product stays invisible to buyers.
    """
    from app import challenge_cache
    from app.models import BuildSellerRequirementsInput
    from app.x402_services import build_seller_requirements

    network = settings.x402_default_network
    price = settings.mn_property_check_price
    # Fingerprint MUST include every input baked into the cached header —
    # including per-resource Bazaar service_name/tags and the payTo cashier.
    # Omitting any of them freezes a wrong value into Redis (and into Bazaar on
    # the next settle); omitting pay_to keeps settling to a retired address.
    fp = challenge_cache.fingerprint(
        network=network,
        price=price,
        resource=resource_url(),
        pay_to=settings.x402_pay_to_address,
        discoverable=settings.bazaar_discoverable,
        description=RESOURCE_DESCRIPTION,
        input_example=DISCOVERY_INPUT_EXAMPLE,
        output_example=DISCOVERY_OUTPUT_EXAMPLE,
        service_name=SERVICE_NAME,
        service_tags=SERVICE_TAGS,
    )

    def _build() -> str:
        return build_seller_requirements(
            BuildSellerRequirementsInput(
                network=network,
                price=price,
                description=RESOURCE_DESCRIPTION,
                resource_url=resource_url(),
                mime_type="application/json",
                discovery_method="GET",
                discovery_input_example=DISCOVERY_INPUT_EXAMPLE,
                discovery_output_example=DISCOVERY_OUTPUT_EXAMPLE,
                service_name=SERVICE_NAME,
                service_tags=SERVICE_TAGS,
            )
        )["payment_required_header"]

    # Cached per (network, price, resource): the header is static and building
    # it hits the flaky CDP facilitator; serve last-known-good through an outage.
    return challenge_cache.get_or_build("mn-property-check", fp, _build)


async def verify_and_settle(payment_signature: str, payment_required: str) -> dict:
    """Verify + settle an incoming payment for this resource."""
    from app.models import VerifyPaymentInput
    from app.x402_services import _verify_and_settle_payment

    return await _verify_and_settle_payment(
        VerifyPaymentInput(
            payment_signature=payment_signature,
            payment_required=payment_required,
        )
    )
