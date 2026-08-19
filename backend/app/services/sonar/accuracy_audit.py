# SPEC: SPEC_CCC_M2_SONAR
"""Sonar RAD-2.5 — claim extraction and fact-sheet verification.

Medical CRITICAL severity routes through compliance_checker.DEFAULT_HIGH_RISK_TERMS
— one list per fact; do not maintain a second high-risk vocabulary here.
"""
from __future__ import annotations

import re
from typing import Any

from ..compliance.compliance_checker import DEFAULT_HIGH_RISK_TERMS

_FIELD_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("phone", re.compile(
        r"\b(?:phone|call|tel)[:\s]*(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})\b",
        re.I,
    )),
    ("phone", re.compile(r"\b(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})\b")),
    ("address", re.compile(
        r"\b(?:at|located at|address[:\s]+)([A-Za-z0-9][^.]{8,80})",
        re.I,
    )),
    ("hours", re.compile(
        r"\b(?:hours?|open)[:\s]+([A-Za-z0-9][^.]{3,60})",
        re.I,
    )),
    ("pricing", re.compile(
        r"\b(?:\$\s?\d[\d,]*(?:\.\d{2})?(?:\s*/\s*\w+)?|"
        r"pricing[:\s]+[^.]{3,40})\b",
        re.I,
    )),
    ("chamber_type", re.compile(
        r"\b((?:mono|multi)place(?:\s+chamber)?|chamber(?:\s+type)?[:\s]+[^.]{3,40})\b",
        re.I,
    )),
    ("credentials", re.compile(
        r"\b((?:UHMS|board[- ]certified|MD|DO|NP|RN)[^.]{0,40})\b",
        re.I,
    )),
    ("indications_treated", re.compile(
        r"\b(?:treats?|treatment for|indicated for|helps with)\s+([^.]{3,80})",
        re.I,
    )),
]


def _norm(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s/+.$]", "", text)
    return text


def _alias_window(text: str, aliases: list[str], *, radius: int = 120) -> str:
    """Prefer claim text near a brand alias; else whole response."""
    if not aliases:
        return text
    best = None
    for alias in aliases:
        alias = (alias or "").strip()
        if not alias:
            continue
        for match in re.finditer(rf"\b{re.escape(alias)}\b", text, re.I):
            start = max(0, match.start() - radius)
            end = min(len(text), match.end() + radius)
            chunk = text[start:end]
            if best is None or len(chunk) > len(best):
                best = chunk
    return best if best is not None else text


def extract_claims(response_text: str, *, brand_aliases: list[str]) -> list[dict]:
    """Pull candidate factual claims near brand mentions."""
    text = response_text or ""
    window = _alias_window(text, brand_aliases or [])
    claims: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for field, pattern in _FIELD_PATTERNS:
        for match in pattern.finditer(window):
            raw = (match.group(1) if match.lastindex else match.group(0)).strip()
            key = (field, _norm(raw))
            if not raw or key in seen:
                continue
            seen.add(key)
            claims.append({
                "field": field,
                "text": raw,
                "position_in_response": match.start(),
                "source_window": window[max(0, match.start() - 20): match.end() + 20],
            })
    return claims


def verify_claims(claims: list[dict], *, fact_sheet: dict) -> list[dict]:
    """Compare claims to a client-maintained fact sheet."""
    sheet = fact_sheet or {}
    superseded = sheet.get("superseded") or {}
    results: list[dict] = []
    for claim in claims or []:
        field = claim.get("field") or ""
        claimed = _norm(claim.get("text"))
        truth = sheet.get(field)
        status = "UNVERIFIED"
        reason = "no ground truth for this claim"
        matched_term = None

        if field == "indications_treated":
            treated = sheet.get("indications_treated") or []
            treated_norms = {_norm(x) for x in treated if x}
            # Contradiction: claim names an indication the clinic does not treat.
            not_treated = sheet.get("indications_not_treated") or []
            not_norms = {_norm(x) for x in not_treated if x}
            hit_not = next((t for t in not_norms if t and t in claimed), None)
            hit_yes = next((t for t in treated_norms if t and t in claimed), None)
            if hit_not:
                status = "HALLUCINATION"
                reason = f"claims treatment for indication not on fact sheet: {hit_not}"
                matched_term = hit_not
            elif hit_yes:
                status = "ACCURATE"
                reason = "indication matches fact sheet"
                matched_term = hit_yes
            elif truth is None and not treated_norms and not not_norms:
                status = "UNVERIFIED"
                reason = "no ground truth for this claim"
            else:
                status = "UNVERIFIED"
                reason = "indication not listed on fact sheet"
        elif truth is None and field not in superseded:
            status = "UNVERIFIED"
            reason = "no ground truth for this claim"
        else:
            truth_n = _norm(truth)
            old_n = _norm(superseded.get(field)) if field in superseded else ""
            if truth_n and (claimed == truth_n or truth_n in claimed or claimed in truth_n):
                status = "ACCURATE"
                reason = "matches fact sheet"
            elif old_n and (claimed == old_n or old_n in claimed or claimed in old_n):
                status = "STALE"
                reason = "matches superseded fact sheet value"
            elif truth_n:
                status = "HALLUCINATION"
                reason = "contradicts fact sheet"
            else:
                status = "UNVERIFIED"
                reason = "no ground truth for this claim"

        results.append({
            "field": field,
            "claim_text": claim.get("text"),
            "status": status,
            "reason": reason,
            "matched_term": matched_term,
            "fact_sheet_value": sheet.get(field),
        })
    return results


def _high_risk_hit(text: str) -> str | None:
    lowered = (text or "").lower()
    # Longer phrases first so "treats autism" wins over "autism".
    ordered = sorted(DEFAULT_HIGH_RISK_TERMS, key=len, reverse=True)
    for term in ordered:
        if term and term.lower() in lowered:
            return term
    return None


def severity(verification: dict) -> str:
    """Map verification to severity. Medical hallucination → CRITICAL."""
    verification = verification or {}
    status = verification.get("status")
    if status != "HALLUCINATION":
        if status == "STALE":
            return "MEDIUM"
        if status == "UNVERIFIED":
            return "INFO"
        return "NONE"

    blob = " ".join(
        str(verification.get(k) or "")
        for k in ("claim_text", "reason", "matched_term", "field")
    )
    hit = _high_risk_hit(blob)
    if hit:
        return "CRITICAL"
    if verification.get("field") == "indications_treated":
        # Indication hallucination is always medical exposure for HBOT.
        return "CRITICAL"
    return "HIGH"


def correction_packet(verification: dict) -> dict:
    """Operator-facing packet for a verified finding."""
    verification = verification or {}
    sev = severity(verification)
    hit = None
    if sev == "CRITICAL":
        blob = " ".join(
            str(verification.get(k) or "")
            for k in ("claim_text", "reason", "matched_term")
        )
        hit = _high_risk_hit(blob) or verification.get("matched_term")

    packet = {
        "field": verification.get("field"),
        "status": verification.get("status"),
        "severity": sev,
        "claim_text": verification.get("claim_text"),
        "correct_value": verification.get("fact_sheet_value"),
        "reason": verification.get("reason"),
        "compliance_high_risk_term": hit,
        "route": (
            "compliance_checker.DEFAULT_HIGH_RISK_TERMS"
            if hit
            else "fact_sheet"
        ),
    }
    return packet
