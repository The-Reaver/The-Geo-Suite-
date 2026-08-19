# SPEC: SPEC_CCC_M3_CITATION_INFLUENCE
"""Citation Influence Index and supporting detectors."""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from ..compliance.compliance_checker import DEFAULT_HIGH_RISK_TERMS, check_marketing_claims
from .cii_weights import cii_component_weights
from .factor_audit import _fact_tokens
from .schema_intelligence import audit_schema, factual_density, schema_report

_PRICE_RE = re.compile(
    r"\$\s?\d[\d,]*(?:\.\d{2})?|\b(?:price|pricing|costs?\s+from)\b",
    re.I,
)
_TRUST_RE = re.compile(
    r"\b(?:UHMS|peer[- ]reviewed|study|studies|randomized|accredited|board[- ]certified|"
    r"according to|cited in|PMID)\b",
    re.I,
)
_SUPERIORITY_RE = re.compile(
    r"\b(?:best|guaranteed|miracle|#1|number one|cures?|eliminates)\b",
    re.I,
)


def topical_relevance(page_text: str, cluster_terms: list[str], *, embedder=None) -> dict:
    text = (page_text or "").lower()
    terms = [t for t in (cluster_terms or []) if t]
    if embedder is not None:
        # Optional inject; offline default is lexical overlap.
        try:
            score = float(embedder(page_text, terms))
            return {
                "score": max(0.0, min(100.0, score)),
                "method": "embedder",
                "model_id": getattr(embedder, "model_id", "injected"),
            }
        except Exception:  # noqa: BLE001
            pass
    if not terms:
        return {"score": None, "method": "overlap", "reason": "no cluster terms"}
    hits = sum(1 for t in terms if t.lower() in text)
    score = 100.0 * hits / len(terms)
    return {
        "score": score,
        "method": "overlap",
        "hits": hits,
        "terms": len(terms),
        "model_id": "lexical_overlap_v1",
    }


def detect_pricing(page_text: str) -> dict:
    found = bool(_PRICE_RE.search(page_text or ""))
    findings = check_marketing_claims(page_text or "")
    recommendation = None
    if found:
        recommendation = (
            "publish a transparent price or range"
            if not findings
            else "pricing present — review marketing claims before placement near outcomes"
        )
    elif not findings:
        recommendation = "publish a transparent price or range"
    else:
        recommendation = "resolve marketing findings before publishing pricing near claims"
    return {
        "present": found,
        "score": 100.0 if found else 0.0,
        "recommendation": recommendation,
        "compliance_findings": findings,
    }


def freshness_score(freshness_date, *, today=None) -> float | None:
    if freshness_date is None:
        return None
    if today is None:
        today = date.today()
    elif isinstance(today, datetime):
        today = today.date()
    if isinstance(freshness_date, datetime):
        freshness_date = freshness_date.date()
    elif isinstance(freshness_date, str):
        freshness_date = date.fromisoformat(freshness_date[:10].replace("/", "-"))
    age = (today - freshness_date).days
    if age <= 30:
        return 100.0
    if age <= 90:
        return 80.0
    if age <= 180:
        return 60.0
    if age <= 365:
        return 40.0
    return 20.0


def trust_cues(page_text: str) -> dict:
    text = page_text or ""
    cues = _TRUST_RE.findall(text)
    unsupported: list[str] = []
    for m in _SUPERIORITY_RE.finditer(text):
        span = text[max(0, m.start() - 40): m.end() + 40]
        unsupported.append(span.strip())
    # Route high-risk terms through compliance list
    lowered = text.lower()
    for term in DEFAULT_HIGH_RISK_TERMS:
        if term.lower() in lowered:
            unsupported.append(f"high-risk:{term}")
    routed = []
    if unsupported:
        routed.append("compliance_checker")
    score = min(100.0, 20.0 * len(set(c.lower() for c in cues)))
    return {
        "score": score,
        "cues": cues,
        "unsupported_claims": unsupported,
        "route": routed,
    }


def classify_edit(previous_text: str, current_text: str) -> dict:
    prev_kinds = {k for _, k in _fact_tokens(previous_text or "")}
    curr_tokens = _fact_tokens(current_text or "")
    curr_kinds = {k for _, k in curr_tokens}
    # Also treat new pricing as substantive factual entity.
    prev_price = bool(_PRICE_RE.search(previous_text or ""))
    curr_price = bool(_PRICE_RE.search(current_text or ""))
    new_facts = (curr_kinds - prev_kinds) or (curr_price and not prev_price)
    if new_facts:
        return {
            "class": "SUBSTANTIVE",
            "reason": "new factual entity detected (price/stat/date/entity)",
        }
    return {
        "class": "FORMATTING_ONLY",
        "reason": (
            "Vishwakarma: formatting-only edits have negligible citation impact"
        ),
    }


def citation_influence_index(components: dict, *, weights=None) -> dict:
    wpayload = cii_component_weights() if weights is None else weights
    w = wpayload["weights"] if "weights" in wpayload else wpayload
    measured = {}
    for key in ("topical_relevance", "pricing_presence", "freshness", "trust_cues", "schema_fds"):
        val = (components or {}).get(key)
        if val is None:
            continue
        measured[key] = float(val)
    if len(measured) < 3:
        return {
            "CII": None,
            "reason": "insufficient_components",
            "measured": measured,
            "weights_status": wpayload.get("status", "UNVALIDATED"),
        }
    num = 0.0
    den = 0.0
    used = {}
    for key, val in measured.items():
        wk = float(w[key])
        # freshness/components expected on 0-100 scale
        num += wk * val
        den += wk
        used[key] = {"value": val, "weight": wk, "status": "UNVALIDATED"}
    return {
        "CII": num / den if den else None,
        "components": used,
        "reason": "cii_scored",
        "weights_status": wpayload.get("status", "UNVALIDATED"),
    }


def deconstruct_competitor(html: str, cluster_terms: list[str]) -> dict:
    report = schema_report(html or "")
    # crude text
    text = re.sub(r"<[^>]+>", " ", html or "")
    topical = topical_relevance(text, cluster_terms)
    pricing = detect_pricing(text)
    trust = trust_cues(text)
    dens = report["density"]
    components = {
        "topical_relevance": topical.get("score"),
        "pricing_presence": pricing.get("score"),
        "freshness": None,
        "trust_cues": trust.get("score"),
        "schema_fds": dens.get("FDS"),
    }
    cii = citation_influence_index(components)
    return {
        "schema": report,
        "topical": topical,
        "pricing": pricing,
        "trust": trust,
        "cii": cii,
    }
