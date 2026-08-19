# SPEC: SPEC_CCC_M3_CITATION_INFLUENCE
"""Entity clustering over injected SERP — NO_SERP_DATA when missing."""
from __future__ import annotations


def extract_entity_graph(serp_results: list[dict] | None) -> dict:
    if serp_results is None:
        return {
            "status": "NO_SERP_DATA",
            "graph": None,
            "reason": "SERP data source missing — not an empty graph",
        }
    nodes = {}
    edges = []
    for row in serp_results:
        entities = row.get("entities") or []
        url = row.get("url") or row.get("title") or "unknown"
        for ent in entities:
            nodes[ent] = nodes.get(ent, 0) + 1
            edges.append({"entity": ent, "source": url})
    return {
        "status": "OK",
        "graph": {"nodes": nodes, "edges": edges},
        "reason": "graph_from_injected_serp",
    }


def cluster_by_intent(keywords: list[str], graph: dict) -> list[dict]:
    if (graph or {}).get("status") == "NO_SERP_DATA":
        return []
    # Dominant entity grouping — indication vs logistics heuristic for HBOT.
    indication = []
    logistics = []
    other = []
    for kw in keywords or []:
        low = kw.lower()
        if any(x in low for x in ("cost", "price", "near me", "hours", "appointment")):
            logistics.append(kw)
        elif any(x in low for x in ("for ", "injury", "wound", "radiation", "autism", "indication")):
            indication.append(kw)
        else:
            other.append(kw)
    clusters = []
    if indication:
        clusters.append({"intent": "indication", "keywords": indication})
    if logistics:
        clusters.append({"intent": "logistics", "keywords": logistics})
    if other:
        clusters.append({"intent": "other", "keywords": other})
    return clusters


def map_content_hub(clusters: list[dict], inventory: list[dict]) -> dict:
    covered = {p.get("cluster") for p in inventory or []}
    gaps = []
    cannibal = []
    low_cii = []
    for c in clusters or []:
        name = c.get("intent")
        pages = [p for p in (inventory or []) if p.get("cluster") == name]
        if not pages:
            gaps.append(name)
        elif len(pages) > 1:
            cannibal.append({"cluster": name, "pages": [p.get("url") for p in pages]})
        for p in pages:
            if p.get("cii") is not None and float(p["cii"]) < 40:
                low_cii.append(p)
    return {
        "gaps": gaps,
        "cannibalisation": cannibal,
        "low_cii_targets": low_cii,
        "covered_intents": sorted(x for x in covered if x),
    }
