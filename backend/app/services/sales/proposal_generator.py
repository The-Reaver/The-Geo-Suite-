"""Sales Feature 3.4 — proposal assembly from existing artifacts.

Reproduces inputs; does not recompute, round, or invent midpoints.
Payment / e-signature are operator-configured interfaces only.
"""
from __future__ import annotations

from typing import Any, Protocol

from ..platform_registry import render_claim


class PaymentProvider(Protocol):
    def checkout_url(self, tier: str, prospect_id: str) -> str: ...


class ESignProvider(Protocol):
    def envelope_url(self, proposal_id: str) -> str: ...


class NullPaymentProvider:
    """Builder stub — operator replaces with real credentials."""

    def checkout_url(self, tier: str, prospect_id: str) -> str:
        return f"operator-configured://checkout/{tier}/{prospect_id}"


class NullESignProvider:
    def envelope_url(self, proposal_id: str) -> str:
        return f"operator-configured://esign/{proposal_id}"


def build_proposal(
    prospect: dict,
    audit: dict,
    roi: dict,
    site: dict,
    *,
    tier: str,
    pricing_tiers: dict | None = None,
    payment: PaymentProvider | None = None,
    esign: ESignProvider | None = None,
    claim_ids: list[str] | None = None,
) -> dict:
    """Assemble a proposal document from source artifacts."""
    if not tier:
        return {
            "ok": False,
            "reason": "tier required; pricing is operator-configured",
        }
    tiers = pricing_tiers or {}
    if tier not in tiers:
        return {
            "ok": False,
            "reason": (
                f"tier {tier!r} not in operator-configured pricing_tiers — "
                "builder must not default a price"
            ),
        }

    audit_verdict = audit.get("verdict") or audit.get("status")
    insufficient = audit_verdict == "INSUFFICIENT_DATA"

    # Reproduce ROI interval exactly — no midpoint.
    roi_block = {
        "lost_lo": roi.get("lost_lo"),
        "lost_hi": roi.get("lost_hi"),
        "status": roi.get("status"),
        "assumptions": roi.get("assumptions"),
        "display": None,
    }
    if roi.get("lost_lo") is not None and roi.get("lost_hi") is not None:
        roi_block["display"] = (
            f"at least {roi['lost_lo']} (range {roi['lost_lo']} – {roi['lost_hi']})"
        )

    claims = []
    for claim_id in claim_ids or []:
        claims.append(render_claim(claim_id))

    proposal_id = f"prop-{prospect.get('name', 'clinic').lower().replace(' ', '-')}-{tier}"
    pay = payment or NullPaymentProvider()
    sign = esign or NullESignProvider()

    sections: list[dict[str, Any]] = [
        {
            "id": "prospect",
            "title": "Prospect",
            "body": {
                "name": prospect.get("name"),
                "city": prospect.get("city"),
                "service": prospect.get("service"),
            },
        },
        {
            "id": "audit",
            "title": "Visibility audit",
            "body": {
                "verdict": audit_verdict,
                "cited_engines": audit.get("cited_engines"),
                "seen_engines": audit.get("seen_engines"),
                "insufficient_data_statement": (
                    "INSUFFICIENT_DATA: fewer than required engines returned "
                    "a usable response — this is not a pass."
                    if insufficient
                    else None
                ),
            },
        },
        {
            "id": "roi",
            "title": "Opportunity range",
            "body": roi_block,
        },
        {
            "id": "site",
            "title": "Proposed site artifact",
            "body": {
                "site_id": site.get("site_id") or site.get("id"),
                "screenshot_refs": list(site.get("screenshots") or []),
                # Pass through scores exactly if present.
                "audit_score": site.get("audit_score"),
            },
        },
        {
            "id": "pricing",
            "title": "Operator pricing tier",
            "body": {
                "tier": tier,
                "price": tiers[tier],  # exact operator value
            },
        },
        {
            "id": "claims",
            "title": "Cited statistics",
            "body": {"claims": claims},
        },
    ]

    return {
        "ok": True,
        "proposal_id": proposal_id,
        "tier": tier,
        "sections": sections,
        "insufficient_data": insufficient,
        "payment_url": pay.checkout_url(tier, str(prospect.get("id") or proposal_id)),
        "esign_url": sign.envelope_url(proposal_id),
        "reason": "proposal assembled from source artifacts without recomputation",
    }
