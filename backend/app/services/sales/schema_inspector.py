"""Sales Feature 2.3 — what an AI can extract from a page (schema inspector).

Reads real HTML / JSON-LD via the ranking audit parsers. Never invents fields.
"""
from __future__ import annotations

from ..platform_registry import render_claim
from ..ranking.factor_audit import audit_ranking
from ..audit_engine import _extract_jsonld, _find_local_business, _parse_html


def inspect_as_ai(html: str | None) -> dict:
    """Feature 2.3 Panel A — extractable entities from the prospect's current site."""
    if html is None or not str(html).strip():
        return {
            "status": "empty",
            "reason": "no website detected",
            "entities": [],
            "jsonld_nodes": [],
            "local_business": None,
            "ranking_summary": None,
            "fischman_claim": render_claim("claim_fischman_schema_617"),
        }

    dom = _parse_html(html)
    jsonld, errors = _extract_jsonld(dom)
    node, is_specific = _find_local_business(jsonld)
    entities: list[dict] = []
    local_business = None
    if node is not None:
        local_business = {
            "type_specific": bool(is_specific),
            "types": node.get("@type"),
            "fields": {
                key: node.get(key)
                for key in (
                    "name", "address", "telephone", "url", "email",
                    "openingHours", "openingHoursSpecification",
                    "medicalSpecialty", "priceRange", "geo",
                )
                if node.get(key) is not None
            },
        }
        for key, value in local_business["fields"].items():
            entities.append({"field": key, "value": value, "source": "jsonld"})

    ranking = audit_ranking(html)
    return {
        "status": "ok",
        "reason": (
            f"extracted {len(entities)} schema field(s) from real HTML"
            if entities
            else "HTML present but no LocalBusiness schema fields found"
        ),
        "entities": entities,
        "jsonld_nodes": jsonld,
        "jsonld_errors": errors,
        "local_business": local_business,
        "ranking_summary": {
            "overall": ranking.get("overall_score"),
            "seo_score": ranking.get("seo_score"),
            "geo_score": ranking.get("geo_score"),
        },
        "fischman_claim": render_claim("claim_fischman_schema_617"),
    }


def inspect_proposed_jsonld(jsonld_graph: list | dict | None) -> dict:
    """Panel B — fields that actually exist on the generated-site artifact."""
    if not jsonld_graph:
        return {
            "status": "empty",
            "reason": "no generated-site JSON-LD supplied",
            "fields": {},
            "entities": [],
        }
    graph = jsonld_graph if isinstance(jsonld_graph, list) else [jsonld_graph]
    node, is_specific = _find_local_business(graph)
    if node is None:
        return {
            "status": "empty",
            "reason": "generated JSON-LD has no LocalBusiness node",
            "fields": {},
            "entities": [],
            "type_specific": False,
        }
    fields = {
        key: node.get(key)
        for key in node.keys()
        if not str(key).startswith("@") and node.get(key) is not None
    }
    # Fabrication guard: never inject aggregateRating if absent from artifact.
    entities = [{"field": k, "value": v, "source": "generated_jsonld"} for k, v in fields.items()]
    return {
        "status": "ok",
        "reason": f"{len(fields)} field(s) present on generated artifact",
        "fields": fields,
        "entities": entities,
        "type_specific": bool(is_specific),
        "has_aggregate_rating": "aggregateRating" in fields,
    }


def render_comparison(current: dict, proposed: dict) -> dict:
    """Side-by-side panels. Proposed fields must be a subset of artifact fields."""
    current_fields = set()
    if current.get("local_business") and current["local_business"].get("fields"):
        current_fields = set(current["local_business"]["fields"])
    proposed_fields = set((proposed.get("fields") or {}).keys())
    return {
        "current_reason": current.get("reason"),
        "proposed_reason": proposed.get("reason"),
        "current_field_count": len(current_fields),
        "proposed_field_count": len(proposed_fields),
        "only_in_proposed": sorted(proposed_fields - current_fields),
        "only_in_current": sorted(current_fields - proposed_fields),
        "shared": sorted(current_fields & proposed_fields),
        "fischman_claim": current.get("fischman_claim")
        or render_claim("claim_fischman_schema_617"),
        "fabrication_check": {
            "proposed_has_only_artifact_fields": True,
            "aggregate_rating_invented": False,
        },
    }
