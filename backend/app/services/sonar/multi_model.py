"""Sonar multi-model comparison scaffolding (unweighted).

Fans out classified engine responses into a comparison grid. Does not compute
SOV, CSI, or other registry-weighted scores (MSG-047 deferral).
Wilson lives in visibility_metrics (single source).
"""
from __future__ import annotations

from .citation_classifier import classify_references, citation_ratio
from .visibility_metrics import wilson_interval

ENGINE_STATUS_OK = "OK"
ENGINE_STATUS_UNAVAILABLE = "UNAVAILABLE"


def compare_engines(
    engine_results: dict[str, dict],
    *,
    brand_domains: list[str],
    brand_aliases: list[str],
) -> dict:
    """Build a per-engine citation/mention grid from raw responses.

    Each value in engine_results is either:
      {"status": "UNAVAILABLE", "reason": "..."} or
      {"status": "OK", "response_text": str, "cited_urls": list[str]}
    """
    rows: list[dict] = []
    ok_engines = 0
    cited_engines = 0
    seen_engines = 0

    for engine, payload in sorted(engine_results.items()):
        status = (payload or {}).get("status") or ENGINE_STATUS_OK
        if status == ENGINE_STATUS_UNAVAILABLE or payload.get("error"):
            rows.append({
                "engine": engine,
                "status": ENGINE_STATUS_UNAVAILABLE,
                "reason": payload.get("reason") or payload.get("error")
                or "engine unavailable",
                "citations": [],
                "mentions": [],
                "citation_ratio": None,
            })
            continue

        classified = classify_references(
            payload.get("response_text") or "",
            payload.get("cited_urls") or [],
            brand_domains=brand_domains,
            brand_aliases=brand_aliases,
        )
        ok_engines += 1
        has_cite = bool(classified["citations"])
        has_mention = bool(classified["mentions"])
        if has_cite:
            cited_engines += 1
        if has_cite or has_mention:
            seen_engines += 1
        rows.append({
            "engine": engine,
            "status": ENGINE_STATUS_OK,
            "citations": classified["citations"],
            "mentions": classified["mentions"],
            "citation_ratio": classified["citation_ratio"],
            "reason": classified["reason"],
        })

    # Presence rate over engines that actually responded (not UNAVAILABLE).
    presence_ci = None
    if ok_engines:
        presence_ci = wilson_interval(seen_engines, ok_engines)

    return {
        "rows": rows,
        "ok_engines": ok_engines,
        "cited_engines": cited_engines,
        "seen_engines": seen_engines,
        "unavailable_engines": sum(
            1 for r in rows if r["status"] == ENGINE_STATUS_UNAVAILABLE
        ),
        "presence_rate": (
            seen_engines / ok_engines if ok_engines else None
        ),
        "presence_wilson_95": presence_ci,
        "sample_note": (
            "single-pass comparison scaffolding; not a multi-iteration rate"
        ),
        "weights_status": "UNVALIDATED",
        "scored_layers": "deferred",
    }


def summarize_presence(comparison: dict) -> str:
    """Human label for the grid — no scored SOV."""
    if comparison["ok_engines"] < 2:
        return "INSUFFICIENT_DATA"
    if comparison["seen_engines"] == 0:
        return "INVISIBLE"
    if comparison["cited_engines"] >= 3:
        return "VISIBLE"
    if comparison["cited_engines"] >= 1 or comparison["seen_engines"] >= 2:
        return "PARTIALLY_VISIBLE"
    return "INVISIBLE"
