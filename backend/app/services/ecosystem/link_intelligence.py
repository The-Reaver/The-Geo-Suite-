# SPEC: SPEC_CCC_M4_ECOSYSTEM_FOOTPRINT
"""Link intelligence — UNKNOWN backlink score is NULL not GENERAL base."""
from __future__ import annotations

from .eco_weights import weight
from .footprint_manager import tag_ai_source_type


def find_link_gaps(
    brand_domain: str,
    competitor_domains: list[str],
    backlink_index: dict,
) -> list[dict]:
    index = backlink_index or {}
    brand_links = set(index.get(brand_domain) or [])
    gaps = []
    for comp in competitor_domains or []:
        for src in index.get(comp) or []:
            if src not in brand_links:
                gaps.append({
                    "source": src,
                    "competitor": comp,
                    "brand_domain": brand_domain,
                    "gap_type": "competitor_has_link_brand_missing",
                })
    return gaps


def score_backlink(link: dict, *, registry: dict | None = None) -> dict:
    domain = (link or {}).get("domain") or (link or {}).get("source") or ""
    source_type = tag_ai_source_type(domain, registry=registry)
    if source_type == "UNKNOWN":
        return {
            "score": None,
            "source_type": "UNKNOWN",
            "reason": "UNKNOWN source type returns NULL not GENERAL base",
            "partial": True,
            "missing": ["source_type_base"],
            "weights_status": "UNVALIDATED",
        }
    try:
        base = weight(f"eco.base.{source_type}")["value"]
    except KeyError:
        return {
            "score": None,
            "source_type": source_type,
            "reason": "no base weight for source type",
            "partial": True,
            "missing": ["source_type_base"],
        }
    missing = []
    da = link.get("domain_authority")
    if da is None:
        authority_adj = 0.0
        missing.append("domain_authority")
    else:
        authority_adj = 20.0 * (float(da) / 100.0)
    placement = (link.get("placement") or "unknown").lower()
    if placement == "in-content":
        placement_adj = 10.0
    elif placement in ("footer", "sidebar"):
        placement_adj = -5.0
    else:
        placement_adj = 0.0
    anchor_rel = float(link.get("anchor_relevance") or 0.0)
    anchor_adj = 10.0 * max(0.0, min(1.0, anchor_rel))
    score = max(0.0, min(100.0, base + authority_adj + placement_adj + anchor_adj))
    return {
        "score": score,
        "source_type": source_type,
        "partial": bool(missing),
        "missing": missing,
        "weights_status": "UNVALIDATED",
        "reason": "backlink_scored" if not missing else "partial score; missing " + ",".join(missing),
    }


def prioritise_outreach(gaps: list[dict], citation_gaps: list[dict]) -> list[dict]:
    ranked = []
    cite_platforms = {g.get("platform") for g in (citation_gaps or [])}
    for g in gaps or []:
        boost = 10 if g.get("source") in cite_platforms or g.get("platform") in cite_platforms else 0
        ranked.append({**g, "priority": 50 + boost})
    ranked.sort(key=lambda r: r["priority"], reverse=True)
    return ranked
