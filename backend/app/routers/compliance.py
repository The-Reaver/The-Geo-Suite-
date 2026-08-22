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
import logging
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

# 2026-08-22, Opus 5 review of 902c4e1, finding F1 (critical): this used
# to resolve three directories up from this file to the repo-root
# knowledge_core/ folder -- correct for a local checkout, but wrong for
# the actual deployed backend. Railway's backend service builds from
# rootDirectory=/backend (railway.json's dockerfilePath is relative to
# that), and backend/Dockerfile's `COPY . .` only copies what's inside
# backend/ into the image -- knowledge_core/ lives at the repo root and
# was never in the container at all. Verified directly: in prod this made
# _load_atomic_notes() permanently cache the empty-corpus fallback below,
# silently zeroing every note count on GET /compliance/library since it
# shipped 2026-08-20, and turning every ratify/reject 404 the moment
# mini-slice 2 added them -- an error message that actively lied, since
# the note IS real, only the corpus lookup was broken.
#
# Real fix: the corpus now lives INSIDE the backend package
# (app/data/regulatory/atomic_notes.json, a vendored copy -- see
# tests/test_compliance_notes_migration.py's drift guard, which fails
# loudly if this copy and the root knowledge_core/ one ever diverge), so
# it's genuinely part of what backend/Dockerfile ships regardless of
# repo layout. The root-level copy stays in place too -- MANIFEST.md's
# own provenance notes reference it living in that folder, and it's the
# one a local/full-checkout session actually edits when the corpus is
# regenerated.
_ATOMIC_NOTES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "regulatory", "atomic_notes.json",
)

_logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_atomic_notes() -> dict:
    """Loaded once per process -- static vendored data, not a live query.
    A missing file degrades to zero notes everywhere rather than a 500
    (same fallback shape as before), but now logs loudly first -- a
    silent empty-corpus degradation is exactly the failure mode that let
    F1 above go undetected in production for two days."""
    try:
        with open(_ATOMIC_NOTES_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        _logger.warning(
            "compliance atomic_notes.json not found at %s -- every note "
            "count/lookup will read as zero/unknown until this is fixed",
            os.path.abspath(_ATOMIC_NOTES_PATH),
        )
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
def ratify_note(note_id: str, body: RatificationRequest = RatificationRequest(), payload: dict = Depends(require_lawyer)):
    nid = note_id.strip()
    if nid not in _real_note_ids():
        raise HTTPException(status_code=404, detail="Unknown compliance note")
    repo = get_compliance_notes_repo()
    return repo.set_status(nid, status="ratified", reviewed_by=_reviewer_id(payload), reason=body.reason)


@router.post("/library/notes/{note_id}/reject")
def reject_note(note_id: str, body: RatificationRequest = RatificationRequest(), payload: dict = Depends(require_lawyer)):
    nid = note_id.strip()
    if nid not in _real_note_ids():
        raise HTTPException(status_code=404, detail="Unknown compliance note")
    repo = get_compliance_notes_repo()
    return repo.set_status(nid, status="rejected", reviewed_by=_reviewer_id(payload), reason=body.reason)


@router.get("/library")
def compliance_library(payload: dict = Depends(require_sales_agent)):
    """Every raw_law/ source, grouped by domain, with its real citation
    metadata and real draft note count/sample. Every entry carries the same
    honest caveat every source file itself carries: not yet lawyer-reviewed
    -- these are draft notes, not a ratified legal opinion.

    2026-08-22, mini-slice 3: sample_notes changed shape from a bare list
    of body strings to a list of {id, body, status} objects -- the
    frontend can't build a real ratify/reject control for a note it has
    no id for, and can't show a real status badge without knowing the
    overlay's current verdict on that specific note (draft is the
    default, same as everywhere else -- "no row" still means draft).
    Only this one route/frontend page consumes this shape (confirmed via
    grep before changing it), so this is a safe, contained change, not a
    versioned API break."""
    notes_data = _load_atomic_notes()
    notes_by_file = notes_data.get("notes_by_file", {})
    statuses_by_id = {row["note_id"]: row["status"] for row in get_compliance_notes_repo().list_statuses()}

    domains = []
    total = 0
    total_draft_notes = 0
    for label, citations in _DOMAINS:
        sources = []
        for c in citations:
            file_notes = notes_by_file.get(c["file"], [])
            # 2026-08-22, mini-slice-3 review F5: note_count/verification_status
            # used to be static -- note_count was every matched note for the
            # file regardless of status (so the UI's own "N draft notes"
            # label kept saying "3 draft notes" even after all 3 were
            # ratified), and verification_status was a hardcoded literal
            # that could never change no matter how many real ratifications
            # happened. Both now derive from statuses_by_id, the same
            # overlay already used for sample_notes' per-note status.
            ratified = sum(1 for n in file_notes if statuses_by_id.get(n["id"], "draft") == "ratified")
            rejected = sum(1 for n in file_notes if statuses_by_id.get(n["id"], "draft") == "rejected")
            draft_count = len(file_notes) - ratified - rejected
            total_draft_notes += draft_count
            if ratified or rejected:
                parts = []
                if ratified:
                    parts.append(f"{ratified} ratified")
                if rejected:
                    parts.append(f"{rejected} rejected")
                if draft_count:
                    parts.append(f"{draft_count} pending")
                verification_status = "Lawyer-reviewed: " + ", ".join(parts)
            else:
                verification_status = "Not yet lawyer-reviewed"
            sources.append({
                "law": c["law"],
                "citation": c["citation"],
                "file": c["file"],
                "source_url": c.get("source_url"),
                "relevance": c["relevance"],
                "verification_status": verification_status,
                "note_count": draft_count,
                "sample_notes": [
                    {"id": n["id"], "body": n["body"], "status": statuses_by_id.get(n["id"], "draft")}
                    for n in file_notes[:3]
                ],
            })
        total += len(sources)
        domains.append({
            "domain": label,
            "sources": sources,
            "detection_status": _DETECTION_STATUS.get(label),
        })

    ratified_count = sum(1 for status in statuses_by_id.values() if status == "ratified")

    return {
        "domains": domains,
        "total_sources": total,
        "lawyer_ratified_count": ratified_count,
        "total_draft_notes": total_draft_notes,
        "orphaned_notes_count": len(notes_data.get("orphaned_notes", [])),
    }
