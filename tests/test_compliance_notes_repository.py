import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.repositories.compliance_notes_repository import InMemoryComplianceNotesRepository


class TestComplianceNotesRepository(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryComplianceNotesRepository()
        self.note_id = "1c1c70554f20409e9862949567b7f8fe"

    def test_no_row_means_implicitly_draft(self):
        # The whole point of the overlay design: a note nobody has ever
        # ratified/rejected has NO row at all -- get_status returns None,
        # and the caller (not this repository) is responsible for treating
        # that as "draft." Never fabricates a placeholder row.
        self.assertIsNone(self.repo.get_status(self.note_id))
        self.assertEqual(self.repo.list_statuses(), [])

    def test_ratify_creates_a_real_row(self):
        row = self.repo.set_status(self.note_id, status="ratified", reviewed_by="lawyer@example.com", reason="Verified against the statute text.")
        self.assertEqual(row["status"], "ratified")
        self.assertEqual(row["reviewed_by"], "lawyer@example.com")
        self.assertEqual(row["reason"], "Verified against the statute text.")
        self.assertIsNotNone(row["reviewed_at"])

        loaded = self.repo.get_status(self.note_id)
        self.assertEqual(loaded["status"], "ratified")

    def test_reject_then_reratify_overwrites_not_duplicates(self):
        # A reviewer can change their mind -- the second call must
        # overwrite the same row, not create a second one for the same
        # note_id (this is an overlay of CURRENT status, not a history log).
        self.repo.set_status(self.note_id, status="rejected", reviewed_by="lawyer@example.com", reason="Not applicable.")
        second = self.repo.set_status(self.note_id, status="ratified", reviewed_by="lawyer@example.com", reason="Reconsidered.")

        self.assertEqual(second["status"], "ratified")
        self.assertEqual(len(self.repo.list_statuses()), 1)
        self.assertEqual(self.repo.get_status(self.note_id)["reason"], "Reconsidered.")

    def test_list_statuses_returns_only_notes_with_a_real_row(self):
        self.repo.set_status(self.note_id, status="ratified", reviewed_by="a@example.com")
        self.repo.set_status("another-note-id", status="rejected", reviewed_by="b@example.com")

        statuses = self.repo.list_statuses()
        self.assertEqual(len(statuses), 2)
        ids = {s["note_id"] for s in statuses}
        self.assertEqual(ids, {self.note_id, "another-note-id"})

    def test_bad_status_rejected(self):
        with self.assertRaises(ValueError):
            self.repo.set_status(self.note_id, status="approved", reviewed_by="a@example.com")

    def test_empty_note_id_rejected(self):
        with self.assertRaises(ValueError):
            self.repo.set_status("", status="ratified", reviewed_by="a@example.com")
        with self.assertRaises(ValueError):
            self.repo.set_status("   ", status="ratified", reviewed_by="a@example.com")

    def test_reviewed_by_required_when_non_draft(self):
        # Security-seat finding: an anonymous ratification/rejection was
        # the path of least resistance before this was locked down --
        # reviewed_by is now a required, non-empty kwarg whenever status
        # isn't draft. draft itself never needs a reviewer (nothing was
        # actually reviewed).
        with self.assertRaises(ValueError):
            self.repo.set_status(self.note_id, status="ratified", reviewed_by="")
        with self.assertRaises(ValueError):
            self.repo.set_status(self.note_id, status="rejected", reviewed_by="   ")
        # draft doesn't require a reviewer -- should not raise.
        row = self.repo.set_status(self.note_id, status="draft", reviewed_by="")
        self.assertEqual(row["status"], "draft")

    def test_note_id_whitespace_stripped_consistently(self):
        # Architect-seat finding: note_id was validated stripped but
        # stored unstripped, so "  <id>  " and "<id>" could silently
        # become two distinct rows for the same logical note. Both
        # directions must resolve to the same stored row.
        self.repo.set_status(f"  {self.note_id}  ", status="ratified", reviewed_by="a@example.com")
        self.assertIsNotNone(self.repo.get_status(self.note_id))
        self.assertEqual(len(self.repo.list_statuses()), 1)

        self.repo.set_status(self.note_id, status="rejected", reviewed_by="b@example.com")
        self.assertIsNotNone(self.repo.get_status(f"  {self.note_id}  "))
        self.assertEqual(len(self.repo.list_statuses()), 1)


class TestSupabaseComplianceNotesRepositoryAuditLog(unittest.TestCase):
    # Security-seat finding: current-state-only storage means a later
    # overwrite silently erases who made an earlier ratification and
    # why, unless every change is also logged to the append-only events
    # table -- and that log write must be best-effort, since a logging
    # failure must never block the real ratify/reject action it logs.
    def test_log_failure_does_not_block_set_status(self):
        from backend.app.repositories.compliance_notes_repository import (
            SupabaseComplianceNotesRepository,
        )

        class _RaisingEventsTable:
            def insert(self, *_a, **_kw):
                return self

            def execute(self):
                raise RuntimeError("events insert failed")

        class _UpsertResult:
            data = [{"note_id": "abc", "status": "ratified"}]

        class _NotesTable:
            def upsert(self, *_a, **_kw):
                return self

            def on_conflict(self, *_a, **_kw):
                return self

            def execute(self):
                return _UpsertResult()

        class _FakeClient:
            def table(self, name):
                return _RaisingEventsTable() if name == "events" else _NotesTable()

        repo = SupabaseComplianceNotesRepository(client=_FakeClient())
        result = repo.set_status("abc", status="ratified", reviewed_by="a@example.com")
        self.assertEqual(result["note_id"], "abc")


if __name__ == "__main__":
    unittest.main(argv=["ign"])
