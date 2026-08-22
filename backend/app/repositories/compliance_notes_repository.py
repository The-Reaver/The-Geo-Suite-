"""
Compliance-note ratification-status persistence.

Compliance ratification, mini-slice 1 (2026-08-22): closes the gap found in
this session's own audit -- GET /compliance/library (compliance.py) is
entirely read-only, sourced from the vendored
knowledge_core/feeds/regulatory/raw_law/atomic_notes.json, with a
permanently-zero "lawyer_ratified_count" and no code path anywhere that
lets anyone ratify, reject, or record who reviewed a note.

Design: an OVERLAY, not a copy. The vendored JSON stays the immutable
source of each note's real text/citation -- this table only ever stores
the workflow STATUS layered on top of a note, keyed by the note's own
existing id (a 32-char hex string already present in the JSON). A note
with no row in this table is implicitly "draft" (the JSON's own default
status) -- a row is only ever created the first time a real ratify/reject
action happens. Deliberately NOT pre-seeded with all 91 known note ids at
migration time: that would bake application data (a set of ids that can
change whenever the vendored JSON is regenerated) into a schema migration,
a real drift risk with no corresponding guard, and the Supabase tooling's
own guidance is explicit -- don't hardcode references to generated ids in
data migrations. "No row yet" is a real, valid state this repository's
read path already handles, not a gap to paper over with seed data.

Deliberately current-state-only, not an append-only history table (a
ratify followed by a later reject overwrites the earlier row rather than
both existing side by side). This IS a real, known tradeoff, not an
oversight -- Opus 5 Architect-seat review flagged it directly: a full
history table is the "expensive to reverse after routes exist" version of
this decision. Staying with current-state-only for mini-slice 1 because
(a) no route or UI consumes history yet, so building it now is speculative,
and (b) an events-log entry (below) already gives an append-only record of
every change, which recovers most of the real value of full history (who
changed what, when) without a second table and a more complex read path.
If a future slice needs to show a full timeline in the UI, promoting from
"one events-log entry per change" to a real history table is a well-
defined, additive migration -- not a data-loss risk, since the events
themselves are already the append-only source of truth.
"""
from datetime import datetime, timezone
from typing import Protocol, Any

# 2026-08-22: must stay in sync with the real DB CHECK constraint in
# supabase/migrations/20260822120000_compliance_notes_table.sql, per
# tests/test_compliance_notes_migration.py's drift-guard -- same pattern
# already proven for content_pages's page_type/status sets.
_VALID_STATUSES = {"draft", "ratified", "rejected"}


def note_status_to_row(note_id: str, *, status: str, reviewed_by: str, reason: str = "") -> dict:
    # 2026-08-22, Opus 5 Security-seat review: reviewed_by used to default
    # to "" (silently stored as NULL -- an anonymous ratification/rejection
    # was the path of least resistance). This codebase already ruled
    # against exactly this shape once, for a different table
    # (sales_preview.py's save_lead(): "a caller could previously
    # attribute a lead to any agent_id it liked" -- fixed by taking
    # agent_id from the verified JWT's sub claim, never the request body).
    # A legal-ratification record is a strictly higher-stakes place for
    # attribution forgery than a sales lead. reviewed_by is now a required
    # keyword arg (no default) at the repository boundary, and non-draft
    # statuses additionally require it to be real, non-empty text -- the
    # route layer (a later slice) is responsible for populating it from
    # the verified caller identity, never from a request body field, same
    # as save_lead's own fix.
    nid = str(note_id).strip()
    if not nid:
        raise ValueError("note_id must not be empty")
    if status not in _VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}. Must be one of {_VALID_STATUSES}")
    reviewed_by = (reviewed_by or "").strip()
    if status != "draft" and not reviewed_by:
        raise ValueError(f"reviewed_by is required when status is {status!r}")
    # reviewed_at is stamped here (not left to a DB default) so it updates
    # on every real status change, in both the InMemory and Supabase
    # implementations alike -- unlike first_reviewed_at (DB-managed only,
    # set once on first insert, deliberately never part of this payload so
    # an upsert on a later ratify/reject can't silently overwrite it).
    return {
        "note_id": nid,
        "status": status,
        "reviewed_by": reviewed_by or None,
        "reason": (reason or "").strip() or None,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }


class ComplianceNotesRepository(Protocol):
    def set_status(self, note_id: str, *, status: str, reviewed_by: str, reason: str = "") -> dict: ...
    def get_status(self, note_id: str) -> dict | None: ...
    def list_statuses(self) -> list[dict]: ...


class InMemoryComplianceNotesRepository:
    def __init__(self):
        # Dict mapping note_id -> row. Absence means "draft" -- the
        # caller's job to interpret, not this repository's.
        self._notes: dict[str, dict] = {}

    def set_status(self, note_id: str, *, status: str, reviewed_by: str, reason: str = "") -> dict:
        row = note_status_to_row(note_id, status=status, reviewed_by=reviewed_by, reason=reason)
        self._notes[row["note_id"]] = row
        return row

    def get_status(self, note_id: str) -> dict | None:
        return self._notes.get(str(note_id).strip())

    def list_statuses(self) -> list[dict]:
        return list(self._notes.values())


class SupabaseComplianceNotesRepository:
    """Production repository for compliance-note ratification status."""
    def __init__(self, client: Any = None):
        self._client = client

    def _get_client(self):
        if self._client is not None:
            return self._client
        # Same lazy-singleton, service-role-client pattern already proven
        # in content_pages_repository.py's SupabaseContentPagesRepository
        # -- routes through the shared factory, never reads a config field
        # this repo's .env.example has never actually populated.
        from ..core.supabase_client import SupabaseConfigError, get_supabase_admin
        try:
            self._client = get_supabase_admin()
        except SupabaseConfigError as exc:
            raise RuntimeError(str(exc)) from exc
        return self._client

    def set_status(self, note_id: str, *, status: str, reviewed_by: str, reason: str = "") -> dict:
        db = self._get_client()
        row = note_status_to_row(note_id, status=status, reviewed_by=reviewed_by, reason=reason)
        res = db.table("compliance_notes").upsert(row, on_conflict="note_id").execute()
        data = getattr(res, "data", [])
        result = data[0] if data else row
        self._log_status_change(db, row)
        return result

    def _log_status_change(self, db, row: dict) -> None:
        # 2026-08-22, Opus 5 Security-seat review: current-state-only
        # storage (see this module's own docstring) means a later
        # overwrite silently erases who made an earlier ratification/
        # rejection and why -- against this codebase's own established
        # audit-trail standard (sales_preview.py's _log_prospect_access:
        # "an audit trail an agent could edit or suppress isn't one").
        # Mirrors that exact pattern: always written through the admin
        # client, from server code the caller can't influence, and
        # best-effort -- a logging failure must never block the real
        # ratify/reject action it's logging.
        #
        # Placed in the repository (the one real choke point every status
        # change must pass through), not at the route layer the way
        # _log_prospect_access is -- a future second route calling
        # set_status() directly can't accidentally skip logging the way
        # it could if this lived in route-handler code instead.
        try:
            db.table("events").insert({
                "client_id": None,
                "event_type": f"compliance_note_{row['status']}",
                "payload": {
                    "note_id": row["note_id"],
                    "reviewed_by": row["reviewed_by"],
                    "reason": row["reason"],
                },
            }).execute()
        except Exception:
            pass

    def get_status(self, note_id: str) -> dict | None:
        db = self._get_client()
        res = db.table("compliance_notes").select("*").eq("note_id", str(note_id).strip()).execute()
        data = getattr(res, "data", [])
        return data[0] if data else None

    def list_statuses(self) -> list[dict]:
        db = self._get_client()
        res = db.table("compliance_notes").select("*").execute()
        return getattr(res, "data", [])
