# SPEC: SPEC_CCC_M1_INGESTION
"""Content parse — reuse audit_engine JSON-LD; freshness order; failures ≠ thin."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from ..audit_engine import _extract_jsonld, _parse_html

_DATE_IN_TEXT = re.compile(
    r"\b(20\d{2}[-/]\d{1,2}[-/]\d{1,2})\b"
)


def resolve_freshness_date(
    *,
    schema_date_modified: str | None = None,
    http_last_modified: str | None = None,
    in_text_date: str | None = None,
    trafilatura_publish_date: str | None = None,
) -> dict:
    """ING-1.4.6 order. Unknown stays unknown — never default to crawl date."""
    for source, value in (
        ("schema_dateModified", schema_date_modified),
        ("http_Last-Modified", http_last_modified),
        ("in_text_date", in_text_date),
        ("trafilatura_publish_date", trafilatura_publish_date),
    ):
        if value:
            return {"freshness_date": value, "source": source, "status": "OK"}
    return {
        "freshness_date": None,
        "source": None,
        "status": "UNKNOWN",
        "reason": "no freshness_date resolvable",
    }


def parse_html_document(html: str, *, crawl_status: str = "OK") -> dict:
    if crawl_status in ("BLOCKED", "RATE_LIMITED", "TIMEOUT", "VENDOR_ERROR"):
        return {
            "status": crawl_status,
            "reason": f"extraction failure: {crawl_status}",
            "classification": "FAILURE",
            "jsonld": None,
            "freshness": resolve_freshness_date(),
        }
    if crawl_status == "JS_REQUIRED":
        return {
            "status": "JS_REQUIRED",
            "reason": "extraction failure: JS_REQUIRED",
            "classification": "FAILURE",
            "jsonld": None,
            "freshness": resolve_freshness_date(),
        }
    try:
        dom = _parse_html(html or "")
        nodes, errors = _extract_jsonld(dom)
    except Exception as e:  # noqa: BLE001 — domain failure, not vendor leak
        return {
            "status": "PARSE_FAILED",
            "reason": f"extraction failure: PARSE_FAILED ({e})",
            "classification": "FAILURE",
            "jsonld": None,
            "freshness": resolve_freshness_date(),
        }
    schema_mod = None
    for node in nodes or []:
        if isinstance(node, dict) and node.get("dateModified"):
            schema_mod = str(node["dateModified"])
            break
    text = html or ""
    m = _DATE_IN_TEXT.search(text)
    freshness = resolve_freshness_date(
        schema_date_modified=schema_mod,
        in_text_date=m.group(1) if m else None,
    )
    return {
        "status": "OK",
        "classification": "PARSED",
        "jsonld": nodes,
        "jsonld_errors": errors,
        "freshness": freshness,
        "reason": "parsed via audit_engine",
    }
