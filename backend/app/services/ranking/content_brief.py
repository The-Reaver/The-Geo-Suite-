# SPEC: SPEC_CCC_M3_CITATION_INFLUENCE
"""BLUF content briefs — entities only when observed on a competitor URL."""
from __future__ import annotations

from .citation_influence import citation_influence_index, detect_pricing, topical_relevance, trust_cues
from .schema_intelligence import schema_report


def entity_checklist(competitor_pages: list[dict], cluster: dict) -> list[dict]:
    items: list[dict] = []
    for page in competitor_pages or []:
        url = page.get("url")
        if not url:
            continue
        for ent in page.get("entities") or []:
            items.append({
                "entity": ent,
                "observed_on": url,
                "cluster": (cluster or {}).get("name"),
            })
        # no brainstorming — skip pages without observed entities
    return items


def build_brief(cluster: dict, gap_analysis: dict, competitor_pages: list[dict]) -> dict:
    checklist = entity_checklist(competitor_pages, cluster)
    return {
        "bluf": (
            f"Close citation gaps for cluster '{(cluster or {}).get('name')}' "
            f"by matching observed competitor entities and attribute-rich schema."
        ),
        "required_entities": checklist,
        "required_schema": "MedicalClinic + Service + FAQPage with real facts only",
        "heading_structure": (cluster or {}).get("headings") or ["What it is", "Who it helps", "Pricing", "FAQ"],
        "freshness_markers": ["Visible dateModified", "Recent FAQ update"],
        "competitor_elements": [
            {"url": p.get("url"), "entities": p.get("entities") or []}
            for p in (competitor_pages or [])
            if p.get("url")
        ],
        "gaps": gap_analysis or {},
    }


def score_draft(draft_text: str, cluster: dict) -> dict:
    terms = list((cluster or {}).get("terms") or [])
    topical = topical_relevance(draft_text or "", terms)
    pricing = detect_pricing(draft_text or "")
    trust = trust_cues(draft_text or "")
    # schema absent on bare draft text
    components = {
        "topical_relevance": topical.get("score"),
        "pricing_presence": pricing.get("score"),
        "freshness": None,
        "trust_cues": trust.get("score"),
        "schema_fds": None,
    }
    return {
        "cii": citation_influence_index(components),
        "breakdown": components,
        "weights_status": "UNVALIDATED",
    }
