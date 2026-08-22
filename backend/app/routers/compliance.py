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

2026-08-22, mini-slice 2: the read/browse surface above now sits alongside
a real lawyer-review workflow -- POST .../notes/{id}/ratify and /reject,
gated `require_lawyer` (a real, dedicated auth role added this same slice,
per the operator's explicit 2026-08-22 decision: a real separate lawyer
reviews these, not the operator acting through their own owner login).
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.permissions import require_sales_agent, require_lawyer
from app.services.compliance import regulatory_citations as rc
from app.repositories.compliance_notes_repository import (
    InMemoryComplianceNotesRepository,
    SupabaseComplianceNotesRepository,
)

router = APIRouter(prefix="/compliance", tags=["compliance"])

# Same module-level-singleton / env-var-gated pattern already proven in
# sites.py's get_site_repos() -- an InMemory repo persists across requests
# within one running process when Supabase isn't configured, so a test
# run or a session with no live credentials never invents a live Supabase
# round-trip just because GEO_USE_SUPABASE_COMPLIANCE_REPOS happens to be
# unset in an environment that otherwise has Supabase configured.
_COMPLIANCE_NOTES_REPO = InMemoryComplianceNotesRepository()


def _use_supabase_compliance_repo() -> bool:
    if os.environ.get("GEO_USE_SUPABASE_COMPLIANCE_REPOS", "").strip() != "1":
        return False
    try:
        from app.core.supabase_client import get_supabase_admin

        get_supabase_admin()
        return True
    except Exception:
        return False


def get_compliance_notes_repo():
    if _use_supabase_compliance_repo():
        return SupabaseComplianceNotesRepository()
    return _COMPLIANCE_NOTES_REPO


class RatificationRequest(BaseModel):
    # Deliberately no `status`/`reviewed_by` field here -- status comes
    # from which endpoint was called (ratify vs. reject), never from the
    # request body, so a caller can't send an arbitrary status string; and
    # reviewed_by comes from the verified JWT's sub claim (see the route
    # bodies below), never from here, closing the exact caller-supplied-
    # identity anti-pattern this codebase already ruled against once for
    # sales_preview.py's agent_id and again for this same repository's
    # own reviewed_by parameter.
    reason: str = Field(default="", max_length=2000)


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


def _real_note_ids() -> set[str]:
    """Every note id the vendored corpus actually knows about (matched +
    orphaned) -- the overlay's set_status() would happily accept a
    made-up id (it doesn't validate against the corpus, by design, since
    the repository layer has no reason to know about atomic_notes.json).
    The route layer is the right place to reject a note_id nothing real
    backs, before it ever reaches the repository."""
    notes_data = _load_atomic_notes()
    ids: set[str] = set()
    for file_notes in notes_data.get("notes_by_file", {}).values():
        ids.update(n["id"] for n in file_notes)
    ids.update(n["id"] for n in notes_data.get("orphaned_notes", []))
    return ids


def _reviewer_id(payload: dict) -> str:
    reviewer = str(payload.get("sub") or "").strip()
    if not reviewer:
        # Same shape as sales_preview.py's own agent_id extraction --
        # verify_token already guarantees a valid, signature-checked
        # token reached this point, so a missing sub claim here means a
        # malformed/unusual token, not a normal caller error.
        raise HTTPException(status_code=401, detail="Token missing a subject claim")
    return reviewer


@router.post("/library/notes/{note_id}/ratify")
async def ratify_note(note_id: str, body: RatificationRequest, payload: dict = Depends(require_lawyer)):
    if note_id not in _real_note_ids():
        raise HTTPException(status_code=404, detail="Unknown compliance note")
    repo = get_compliance_notes_repo()
    return repo.set_status(note_id, status="ratified", reviewed_by=_reviewer_id(payload), reason=body.reason)


@router.post("/library/notes/{note_id}/reject")
async def reject_note(note_id: str, body: RatificationRequest, payload: dict = Depends(require_lawyer)):
    if note_id not in _real_note_ids():
        raise HTTPException(status_code=404, detail="Unknown compliance note")
    repo = get_compliance_notes_repo()
    return repo.set_status(note_id, status="rejected", reviewed_by=_reviewer_id(payload), reason=body.reason)


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

    ratified_count = sum(
        1 for row in get_compliance_notes_repo().list_statuses() if row["status"] == "ratified"
    )

    return {
        "domains": domains,
        "total_sources": total,
        "lawyer_ratified_count": ratified_count,
        "total_draft_notes": notes_data.get("matched_notes", 0),
        "orphaned_notes_count": len(notes_data.get("orphaned_notes", [])),
    }
