-- Compliance ratification mini-slice 2, Opus 5 review (902c4e1) finding
-- F7: the 2000-character bound on `reason` only lived in the route
-- layer's Pydantic model (RatificationRequest, routers/compliance.py).
-- SupabaseComplianceNotesRepository.set_status() itself has no such
-- limit -- a real gap for any future caller that reaches the repository
-- without going through the route (a script, a different route, a
-- future mini-slice). Enforcing it at the database layer closes that
-- permanently, the same "the DB is the real backstop, not just the API
-- layer" discipline already applied to compliance_notes' status CHECK
-- constraint in the original migration.
alter table public.compliance_notes
  add constraint compliance_notes_reason_length check (char_length(reason) <= 2000);
