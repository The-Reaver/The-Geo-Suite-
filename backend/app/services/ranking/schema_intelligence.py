# SPEC: SPEC_CCC_M3_CITATION_INFLUENCE
"""Schema intelligence — FDS + PAYLOAD|STRUCTURAL|ABSENT (reuses audit_engine parsers)."""
from __future__ import annotations

from typing import Any

from ..audit_engine import _extract_jsonld, _find_local_business, _parse_html, _types_of
from .cii_weights import weight

FISCHMAN_NOTE = (
    "Fischman (2026): generic schema presence has no statistically significant "
    "effect on citation probability once organic rank is controlled "
    "(OR = 0.678, p = 0.296). Prefer attribute-rich payloads over bare Organization."
)


def _is_empty(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, str) and not val.strip():
        return True
    if isinstance(val, (list, dict)) and len(val) == 0:
        return True
    return False


def audit_schema(html: str) -> dict:
    dom = _parse_html(html or "")
    nodes, errors = _extract_jsonld(dom)
    lb, is_specific = _find_local_business(nodes)
    types: list[str] = []
    for n in nodes or []:
        types.extend(_types_of(n))
    return {
        "nodes": nodes or [],
        "errors": errors or [],
        "types": sorted(set(types)),
        "local_business": lb,
        "is_specific_subtype": bool(is_specific),
        "has_jsonld": bool(nodes),
    }


def factual_density(schema_profile: dict) -> dict:
    profile = schema_profile or {}
    if not profile.get("has_jsonld") and not profile.get("nodes"):
        return {
            "FDS": None,
            "classification": "ABSENT",
            "awards": [],
            "penalties": [],
            "weights_status": "UNVALIDATED",
            "reason": "no parseable JSON-LD",
        }
    score = 0.0
    awards: list[str] = []
    penalties: list[str] = []
    concrete = False
    nodes = profile.get("nodes") or []
    blob_objs = [n for n in nodes if isinstance(n, dict)]
    lb = profile.get("local_business")
    if isinstance(lb, dict):
        blob_objs = [lb] + blob_objs

    def has_key(*keys: str) -> bool:
        for obj in blob_objs:
            for k in keys:
                if k in obj and not _is_empty(obj.get(k)):
                    return True
        return False

    checks = [
        (("price", "priceRange", "offers"), "fds.award.price", "price"),
        (("aggregateRating",), "fds.award.aggregateRating", "aggregateRating"),
        (("additionalProperty", "model", "category"), "fds.award.specifications", "specifications"),
        (("reviewCount", "ratingCount"), "fds.award.review_count", "review_count"),
        (("availability", "potentialAction"), "fds.award.availability", "availability"),
    ]
    for keys, wkey, label in checks:
        if has_key(*keys):
            score += weight(wkey)["value"]
            awards.append(label)
            concrete = True

    # FAQ
    for obj in blob_objs:
        types = _types_of(obj)
        if "FAQPage" in types or obj.get("mainEntity"):
            score += weight("fds.award.faq")["value"]
            awards.append("faq")
            concrete = True
            break
    if has_key("author", "employee", "medicalSpecialty"):
        score += weight("fds.award.credentials")["value"]
        awards.append("credentials")
        concrete = True
    if has_key("dateModified", "datePublished"):
        score += weight("fds.award.date")["value"]
        awards.append("date")
        concrete = True

    # empty property penalties
    for obj in blob_objs:
        for k, v in obj.items():
            if k.startswith("@"):
                continue
            if _is_empty(v):
                score -= weight("fds.penalty.empty_property")["value"]
                penalties.append(f"empty:{k}")

    types = profile.get("types") or []
    if "Organization" in types and not profile.get("is_specific_subtype") and not concrete:
        score -= weight("fds.penalty.generic_organization")["value"]
        penalties.append("generic_organization")

    fds = max(0.0, min(100.0, score))
    return {
        "FDS": fds,
        "awards": awards,
        "penalties": penalties,
        "concrete_field": concrete,
        "weights_status": "UNVALIDATED",
        "reason": "fds_scored",
    }


def classify_payload(schema_profile: dict) -> str:
    dens = factual_density(schema_profile)
    if dens.get("FDS") is None and dens.get("classification") == "ABSENT":
        return "ABSENT"
    if not schema_profile.get("has_jsonld") and not schema_profile.get("nodes"):
        return "ABSENT"
    threshold = weight("fds.threshold.payload")["value"]
    if dens["FDS"] is not None and dens["FDS"] >= threshold and dens.get("concrete_field"):
        return "PAYLOAD"
    return "STRUCTURAL"


def generate_attribute_rich_jsonld(page: dict, facts: dict) -> dict:
    """Never invent rating/price/review fields not supplied in facts."""
    facts = facts or {}
    clinic: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "MedicalClinic",
        "name": facts.get("name") or page.get("name") or "Clinic",
    }
    if facts.get("url"):
        clinic["url"] = facts["url"]
    if facts.get("telephone"):
        clinic["telephone"] = facts["telephone"]
    if facts.get("address"):
        clinic["address"] = facts["address"]
    if facts.get("priceRange"):
        clinic["priceRange"] = facts["priceRange"]
    # aggregateRating only when real rating supplied
    if facts.get("ratingValue") is not None and facts.get("reviewCount") is not None:
        clinic["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": facts["ratingValue"],
            "reviewCount": facts["reviewCount"],
        }
    graph: list[dict] = [clinic]
    for svc in facts.get("services") or []:
        graph.append({
            "@type": "Service",
            "name": svc.get("name"),
            "provider": {"@type": "MedicalClinic", "name": clinic["name"]},
        })
    faqs = facts.get("faqs") or []
    if faqs:
        graph.append({
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": q.get("q"),
                    "acceptedAnswer": {"@type": "Answer", "text": q.get("a")},
                }
                for q in faqs
                if q.get("q") and q.get("a")
            ],
        })
    return {"@context": "https://schema.org", "@graph": graph}


def authority_opportunity(domain_authority: float | None) -> dict:
    if domain_authority is None:
        return {
            "status": "UNKNOWN",
            "recommendation": None,
            "reason": "domain authority unknown — no recommendation",
        }
    thr = weight("authority.dr_threshold")["value"]
    if float(domain_authority) <= thr:
        return {
            "status": "LOW_AUTHORITY_OPPORTUNITY",
            "recommendation": "Prioritise attribute-rich schema payloads (Fischman low-DR advantage).",
            "dr": float(domain_authority),
            "threshold": thr,
            "note": FISCHMAN_NOTE,
        }
    return {
        "status": "ABOVE_THRESHOLD",
        "recommendation": None,
        "dr": float(domain_authority),
        "threshold": thr,
    }


def schema_report(html: str) -> dict:
    profile = audit_schema(html)
    dens = factual_density(profile)
    classification = classify_payload(profile)
    out = {
        "profile": profile,
        "density": dens,
        "classification": classification,
        "gap_note": None,
        "weights_status": "UNVALIDATED",
    }
    if classification == "STRUCTURAL":
        out["gap_note"] = FISCHMAN_NOTE
    if classification == "ABSENT":
        out["density"]["FDS"] = None
    return out
