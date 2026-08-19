"""Pydantic schemas backing the compliance-checker's citation-rigor work
(see the module docstring on compliance_checker.py for the three-phase
ruling this is Phase 1 of, and check_citation_records() for how these are
validated beyond field-presence).

CitationRecord is deliberately narrow: it records that a *lawyer* looked at
a specific piece of published evidence and scoped exactly what it does and
does not support for a specific marketing claim. Nothing here makes a legal
judgment on its own -- construction just enforces that the record is
structurally complete enough to be reviewed at all (no field left blank or
whitespace-only), the same floor every other required field in this
codebase gets from Pydantic already.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, field_validator


class ClaimStrength(str, Enum):
    """How strongly a marketing claim asserts the underlying science is
    settled, per the substantiation-bar rule: a hedged opinion ("may help")
    and an establishment claim ("studies show X treats Y") are not the same
    representation and do not carry the same evidentiary bar. See
    compliance_checker._ESTABLISHMENT_CLAIM_MIN_BOUNDARY_LENGTH.
    """

    HEDGED_OPINION = "hedged_opinion"
    ESTABLISHMENT_CLAIM = "establishment_claim"


_REQUIRED_TEXT_FIELDS = (
    "study_reference",
    "claim_scope",
    "limitation",
    "applicability_boundary",
)


class CitationRecord(BaseModel):
    """One lawyer-scoped mapping from a real study to one marketing claim.

    source_note_id: optional pointer into knowledge_core, when the citation
    was sourced from a note already in the Core rather than supplied fresh.
    study_reference: the citation itself (authors, journal, year, and an
    identifier such as a DOI or PMID where available).
    claim_scope: exactly what the study supports -- including its route of
    administration / modality (e.g. "local injection" vs "systemic"), not
    just the topic, since a citation only substantiates a claim that shares
    the same modality and population as what was actually studied.
    limitation: the study's own stated limitation or a contradicting
    finding, required and distinct from claim_scope, so a citation can't be
    used to support a claim without also carrying its own caveat.
    applicability_boundary: who/what the finding actually applies to.
    claim_strength: whether the marketing claim this record backs is a
    hedged opinion or an establishment claim (see ClaimStrength).
    """

    source_note_id: Optional[str] = None
    study_reference: str
    claim_scope: str
    limitation: str
    applicability_boundary: str
    claim_strength: ClaimStrength

    @field_validator(*_REQUIRED_TEXT_FIELDS)
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty or whitespace-only")
        return value
