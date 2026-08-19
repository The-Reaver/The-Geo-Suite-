"""Shared HBOT platform / source-type registry for Sonar + ecosystem.

One domain list, two tag axes (citation source_type vs link ai_source_type).
Weights referenced here are seeds tagged UNVALIDATED — not ratified Track D numbers.
"""
from __future__ import annotations

from typing import Any

# Domain suffix → tags. Longest-suffix match wins.
_HBOT_PLATFORMS: dict[str, dict[str, str]] = {
    "healthgrades.com": {
        "source_type": "REVIEW_SITE",
        "ai_source_type": "CONSENSUS_CRITICAL",
    },
    "vitals.com": {
        "source_type": "REVIEW_SITE",
        "ai_source_type": "CONSENSUS_CRITICAL",
    },
    "ratemds.com": {
        "source_type": "REVIEW_SITE",
        "ai_source_type": "CONSENSUS_CRITICAL",
    },
    "zocdoc.com": {
        "source_type": "DIRECTORY",
        "ai_source_type": "NICHE_DIRECTORY",
    },
    "yelp.com": {
        "source_type": "DIRECTORY",
        "ai_source_type": "CONSENSUS_CRITICAL",
    },
    "webmd.com": {
        "source_type": "DIRECTORY",
        "ai_source_type": "NICHE_DIRECTORY",
    },
    "uhms.org": {
        "source_type": "DIRECTORY",
        "ai_source_type": "NICHE_DIRECTORY",
    },
    "reddit.com": {
        "source_type": "COMMUNITY",
        "ai_source_type": "COMMUNITY_INFLUENTIAL",
    },
    "youtube.com": {
        "source_type": "SOCIAL",
        "ai_source_type": "MEDIA_AUTHORITY",
    },
    "facebook.com": {
        "source_type": "SOCIAL",
        "ai_source_type": "GENERAL",
    },
    "google.com": {
        "source_type": "DIRECTORY",
        "ai_source_type": "CONSENSUS_CRITICAL",
    },
    "maps.google.com": {
        "source_type": "DIRECTORY",
        "ai_source_type": "CONSENSUS_CRITICAL",
    },
}

DEFAULT_HBOT_PLATFORM_IDS: tuple[str, ...] = (
    "google_business_profile",
    "healthgrades",
    "vitals",
    "ratemds",
    "zocdoc",
    "yelp",
    "webmd_care",
    "uhms",
    "clinic_website",
)

# Sales claim registry (machine twin of docs/SALES_CITATIONS_REGISTRY.md).
# Only RESOLVED entries may render a number.
SALES_CLAIMS: dict[str, dict[str, Any]] = {
    "claim_ai_consumer_local_45": {
        "status": "RESOLVED",
        "number": "45%",
        "wording": (
            "45% of consumers use AI tools for local business recommendations"
        ),
        "primary_url": "https://www.brightlocal.com/research/lcrs-ai-trust/",
    },
    "claim_ai_users_factcheck_88": {
        "status": "RESOLVED",
        "number": "88%",
        "wording": (
            "88% of AI users fact-check AI business recommendations"
        ),
        "primary_url": "https://www.brightlocal.com/research/lcrs-ai-trust/",
    },
    "claim_chatgpt_selectivity_1_2": {
        "status": "RESOLVED",
        "number": "1.2%",
        "wording": (
            "ChatGPT recommended 1.2% of brand locations in SOCi's 2026 LVI"
        ),
        "primary_url": (
            "https://www.soci.ai/news/"
            "in-ai-driven-discovery-few-brands-are-chosen-most-disappear/"
        ),
    },
    "claim_ai_visibility_30x": {
        "status": "RESOLVED",
        "number": "30x",
        "wording": (
            "AI local visibility is up to 30x harder than Google's local 3-Pack"
        ),
        "primary_url": (
            "https://www.soci.ai/news/"
            "in-ai-driven-discovery-few-brands-are-chosen-most-disappear/"
        ),
    },
    "claim_local_invisible_88": {
        "status": "WITHHELD",
        "number": "88%",
        "wording": "88% of local businesses are invisible in AI search",
        "primary_url": None,
        "reason": "no primary matches that exact sentence",
    },
    "claim_near_me_visit_76": {
        "status": "WITHHELD",
        "number": "76%",
        "wording": "76% of near-me searches lead to a visit within 24 hours",
        "primary_url": None,
        "reason": "primary Think-with-Google figure is 50%, not 76%",
    },
    "claim_fischman_schema_617": {
        "status": "RESOLVED",
        "number": "61.7%",
        "wording": (
            "Attribute-rich Product/Review schema was cited at 61.7% vs "
            "41.6% for generic schema (Fischman 2026; p=.012)"
        ),
        "primary_url": "https://doi.org/10.5281/zenodo.18728697",
    },
    "claim_local_top5_absent_88": {
        "status": "RESOLVED",
        "number": "88%",
        "wording": (
            "88% of local businesses never appear in AI's top-5 "
            "recommendations for their market (Avante Visibility Index, "
            "July 2026; Perplexity; one-day sample)"
        ),
        "primary_url": "https://avantevisibility.com/ai-visibility-index",
    },
    "claim_ai_asking_share_28": {
        "status": "RESOLVED",
        "number": "28%",
        "wording": (
            "Search-like ('asking') AI usage equals about 28% of global "
            "search volume (Graphite, Q4 2025 methodology)"
        ),
        "primary_url": (
            "https://content-hub.graphite.io/five-percent/"
            "ai-is-much-bigger-than-you-think"
        ),
    },
    "claim_search_share_ai_30": {
        "status": "WITHHELD",
        "number": "30%",
        "wording": "30% of all searches now use AI",
        "primary_url": None,
        "reason": (
            "no primary matches that exact sentence; use "
            "claim_ai_asking_share_28 (28% asking) instead"
        ),
    },
}


def _host(url_or_domain: str) -> str:
    text = (url_or_domain or "").strip().lower()
    text = text.replace("https://", "").replace("http://", "")
    text = text.split("/")[0]
    if text.startswith("www."):
        text = text[4:]
    return text


def lookup_platform(url_or_domain: str, *, registry: dict | None = None) -> dict | None:
    """Return the registry row for a URL/domain, or None if unregistered."""
    table = registry if registry is not None else _HBOT_PLATFORMS
    host = _host(url_or_domain)
    if not host:
        return None
    best = None
    best_len = -1
    for suffix, row in table.items():
        if host == suffix or host.endswith("." + suffix):
            if len(suffix) > best_len:
                best = row
                best_len = len(suffix)
    return best


def render_claim(claim_id: str, *, claims: dict | None = None) -> dict:
    """Return a display payload. Unresolved claims are withheld, never numbered."""
    table = claims if claims is not None else SALES_CLAIMS
    entry = table.get(claim_id)
    if entry is None:
        return {
            "claim_id": claim_id,
            "status": "WITHHELD",
            "display": "[statistic withheld: source unresolved]",
            "reason": "unknown_claim_id",
        }
    if entry.get("status") != "RESOLVED" or not entry.get("primary_url"):
        return {
            "claim_id": claim_id,
            "status": "WITHHELD",
            "display": "[statistic withheld: source unresolved]",
            "reason": entry.get("reason") or "unresolved",
            "wording": entry.get("wording"),
        }
    return {
        "claim_id": claim_id,
        "status": "RESOLVED",
        "display": entry["wording"],
        "number": entry["number"],
        "primary_url": entry["primary_url"],
    }
