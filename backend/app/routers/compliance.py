"""Compliance router — the real Compliance Library data.

2026-08-20: replaces a frontend nav item (NovaShell.tsx's "Compliance
Library") that was a plain unclickable <div> with a hardcoded, fake
"3 pending" badge -- no page, no route, no backend endpoint behind it at
all. This surfaces the real citation/source data regulatory_citations.py
already carries for all 20 raw_law/ files, grouped by domain, plus the real
atomic notes vendored into knowledge_core/feeds/regulatory/raw_law/
atomic_notes.json (see that file and MANIFEST.md's 2026-08-20 section for
where they came from and the one known gap: 3 of 91 notes cite a source URL
with no matching file in this repo).

Read/browse only. No lawyer-review workflow (promoting a note from draft to
ratified) lives here -- that's the lawyer's own follow-on work per the
operator's framing ("demo it and then own refining that area"), not
something to build ahead of that session.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

from fastapi import APIRouter, Depends

from app.core.permissions import require_sales_agent
from app.services.compliance import regulatory_citations as rc

router = APIRouter(prefix="/compliance", tags=["compliance"])

_DOMAINS: list[tuple[str, list[dict]]] = [
    ("Medical marketing claims", rc._MARKETING_CITATIONS),
    ("Patient data privacy", rc._PHI_CITATIONS),
    ("Lead-contact compliance", rc._LEAD_CONTACT_CITATIONS),
    ("AI-visibility / AI-generated content", rc._AI_VISIBILITY_CITATIONS),
]

# 2026-08-20: real, current status of automated detection per domain --
# not aspirational, and not silent about the gaps. Kept in sync with
# compliance_checker.py's own module docstring by hand (both are read by
# a human, not generated from one source) since that's a short, stable
# list, not a place worth adding indirection for.
_DETECTION_STATUS: dict[str, dict] = {
    "Medical marketing claims": {
        "has_check": True,
        "wired_into_publish_gate": True,
        "note": (
            "check_marketing_claims() is live in the publish gate today. "
            "check_citation_records() (structural QA over lawyer-authored "
            "citation records) is also built and tested but not yet wired "
            "in -- it has nothing real to check until ratified citation "
            "records exist, which your review would help produce."
        ),
    },
    "Patient data privacy": {
        "has_check": True,
        "wired_into_publish_gate": True,
        "note": "check_phi_testimonials() is live in the publish gate today.",
    },
    "Lead-contact compliance": {
        "has_check": False,
        "wired_into_publish_gate": False,
        "note": (
            "No automated check exists, deliberately. This repo has no "
            "automated calling, texting, or outbound-email infrastructure "
            "today, so there's nothing for TCPA/CAN-SPAM detection logic "
            "to check yet. Whether/how TCPA's automated-dialing "
            "restrictions apply to Nova's manual-dial prospecting workflow "
            "is a real open question for your review, not something to "
            "guess at in code."
        ),
    },
    "AI-visibility / AI-generated content": {
        "has_check": True,
        "wired_into_publish_gate": False,
        "note": (
            "check_ai_claims_marketing() is built and tested -- flags "
            "unsubstantiated AI-related marketing language (e.g. "
            '"AI-powered" with no nearby evidence), grounded in the FTC\'s '
            "AI-claims guidance and the real FTC v. Workado matter. Not "
            "yet enforced in the publish gate, pending your review, same "
            "status as citation_records above. It also applies to GEO "
            "Suite's own report/Sales Kit copy, not just client sites."
        ),
    },
}

_ATOMIC_NOTES_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "knowledge_core", "feeds", "regulatory", "raw_law", "atomic_notes.json",
    )
)


@lru_cache(maxsize=1)
def _load_atomic_notes() -> dict:
    """Loaded once per process -- static vendored data, not a live query.
    Missing file (e.g. a checkout that predates the 2026-08-20 vendoring)
    degrades to zero notes everywhere rather than a 500."""
    try:
        with open(_ATOMIC_NOTES_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"notes_by_file": {}, "orphaned_notes": [], "total_notes": 0, "matched_notes": 0}


@router.get("/library")
async def compliance_library(payload: dict = Depends(require_sales_agent)):
    """Every raw_law/ source, grouped by domain, with its real citation
    metadata and real draft note count/sample. Every entry carries the same
    honest caveat every source file itself carries: not yet lawyer-reviewed
    -- these are draft notes, not a ratified legal opinion."""
    notes_data = _load_atomic_notes()
    notes_by_file = notes_data.get("notes_by_file", {})

    domains = []
    total = 0
    for label, citations in _DOMAINS:
        sources = []
        for c in citations:
            file_notes = notes_by_file.get(c["file"], [])
            sources.append({
                "law": c["law"],
                "citation": c["citation"],
                "file": c["file"],
                "source_url": c.get("source_url"),
                "relevance": c["relevance"],
                "verification_status": "Not yet lawyer-reviewed",
                "note_count": len(file_notes),
                "sample_notes": [n["body"] for n in file_notes[:3]],
            })
        total += len(sources)
        domains.append({
            "domain": label,
            "sources": sources,
            "detection_status": _DETECTION_STATUS.get(label),
        })

    return {
        "domains": domains,
        "total_sources": total,
        "lawyer_ratified_count": 0,
        "total_draft_notes": notes_data.get("matched_notes", 0),
        "orphaned_notes_count": len(notes_data.get("orphaned_notes", [])),
    }
