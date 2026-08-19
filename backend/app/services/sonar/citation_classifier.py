"""Sonar RAD-2.1 — citation vs mention classifier + source-type tagging.

Unweighted measurement. No SOV/CSI/gap scoring here (MSG-047: defer scored layers).
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from ..platform_registry import lookup_platform

_URL_IN_TEXT_RE = re.compile(
    r"https?://[^\s<>\"')\]]+|www\.[^\s<>\"')\]]+",
    re.I,
)


def _norm_domain(value: str) -> str:
    text = (value or "").strip().lower()
    if "://" not in text and text.startswith("www."):
        text = "https://" + text
    if "://" in text:
        host = urlparse(text).netloc.lower()
    else:
        host = text.split("/")[0]
    if host.startswith("www."):
        host = host[4:]
    return host.rstrip(".")


def _domain_matches(url: str, brand_domains: list[str]) -> bool:
    host = _norm_domain(url)
    if not host:
        return False
    for domain in brand_domains:
        owned = _norm_domain(domain)
        if not owned:
            continue
        if host == owned or host.endswith("." + owned):
            return True
    return False


def _alias_positions(text: str, aliases: list[str]) -> list[dict]:
    """Word-boundary matches only; substring-inside-word does not count."""
    hits: list[dict] = []
    for alias in aliases:
        alias = (alias or "").strip()
        if not alias:
            continue
        pattern = re.compile(rf"\b{re.escape(alias)}\b", re.I)
        for match in pattern.finditer(text):
            hits.append({
                "alias": alias,
                "start": match.start(),
                "end": match.end(),
                "position_in_response": match.start(),
            })
    hits.sort(key=lambda h: h["start"])
    return hits


def _link_spans(text: str, cited_urls: list[str]) -> list[dict]:
    spans: list[dict] = []
    for match in _URL_IN_TEXT_RE.finditer(text):
        spans.append({
            "url": match.group(0),
            "start": match.start(),
            "end": match.end(),
        })
    # Cited URLs may not appear inline (footnote-style). Treat them as
    # citations at end-of-response so presence still counts.
    lower_text = text.lower()
    for url in cited_urls:
        if url and url.lower() not in lower_text:
            spans.append({
                "url": url,
                "start": len(text),
                "end": len(text),
                "implicit": True,
            })
    return spans


def classify_references(
    response_text: str,
    cited_urls: list[str] | None = None,
    *,
    brand_domains: list[str],
    brand_aliases: list[str],
) -> dict:
    """Split brand references into CITATION or MENTION (RAD-2.1.1/2/3).

    CITATION: a hyperlink (inline or in cited_urls) resolves to a brand domain.
    MENTION: brand alias appears with no brand link within ±50 characters.
    URLs matching no brand domain are excluded from both counts.
    """
    text = response_text or ""
    urls = list(cited_urls or [])
    citations: list[dict] = []
    mentions: list[dict] = []

    link_spans = _link_spans(text, urls)
    brand_links = [
        span for span in link_spans
        if _domain_matches(span["url"], brand_domains)
    ]
    for span in brand_links:
        citations.append({
            "kind": "CITATION",
            "url": span["url"],
            "position_in_response": span["start"],
            "implicit": bool(span.get("implicit")),
        })

    for hit in _alias_positions(text, brand_aliases):
        near_link = False
        for span in brand_links:
            # Implicit end-of-response footnotes do not suppress text mentions.
            if span.get("implicit"):
                continue
            if abs(span["start"] - hit["start"]) <= 50:
                near_link = True
                break
        if near_link:
            continue
        # If this alias sits on a brand citation URL string itself, skip.
        covered_by_citation = False
        for span in brand_links:
            if span["start"] <= hit["start"] < span["end"]:
                covered_by_citation = True
                break
        if covered_by_citation:
            continue
        mentions.append({
            "kind": "MENTION",
            "alias": hit["alias"],
            "position_in_response": hit["position_in_response"],
        })

    total = len(citations) + len(mentions)
    ratio = (len(citations) / total) if total else None
    return {
        "citations": citations,
        "mentions": mentions,
        "citation_ratio": ratio,
        "reason": (
            "not seen in any tracked response"
            if total == 0
            else f"{len(citations)} citation(s), {len(mentions)} mention(s)"
        ),
    }


def tag_source_type(url: str, *, registry: dict | None = None) -> str:
    """RAD-2.1.4 — FIRST_PARTY is caller-owned; else registry or UNKNOWN."""
    row = lookup_platform(url, registry=registry)
    if row is None:
        return "UNKNOWN"
    return row.get("source_type") or "UNKNOWN"


def citation_ratio(citations: int, mentions: int) -> float | None:
    total = citations + mentions
    if total == 0:
        return None
    return citations / total
