-- Compliance-note ratification-status persistence. Compliance ratification,
-- mini-slice 1 (2026-08-22). Backs
-- app/repositories/compliance_notes_repository.py's SupabaseComplianceNotesRepository.
--
-- This is an OVERLAY, not a copy of note content: the 91 real notes'
-- text/citations stay in the vendored
-- knowledge_core/feeds/regulatory/raw_law/atomic_notes.json (this repo has
-- no kc_notes table and building one is a separate architecture decision,
-- per this session's own earlier finding). This table only ever stores the
-- workflow STATUS layered on top of a note, keyed by the note's own
-- existing id (a 32-char hex string already present in the JSON). A note
-- with no row here is implicitly "draft" -- deliberately NOT pre-seeded
-- with all known note ids at migration time, since that would bake
-- application data (a set that changes whenever the vendored JSON is
-- regenerated) into a schema migration with no corresponding drift guard.
--
-- status check values match compliance_notes_repository.py's
-- _VALID_STATUSES exactly.
create table public.compliance_notes (
  note_id            text primary key,
  status             text not null default 'draft' check (status in ('draft', 'ratified', 'rejected')),
  reviewed_by        text,
  reviewed_at        timestamptz,
  reason             text,
  first_reviewed_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- table grants + RLS
-- ---------------------------------------------------------------------------
-- select-only: same precedent as site_pipeline's tables -- only the
-- backend's service-role client ever writes this table (bypasses RLS
-- regardless), so insert/update/delete grants to `authenticated` would be
-- dead weight with no matching RLS policy to make them safe to reach.
grant select
  on public.compliance_notes
  to authenticated, service_role;

alter table public.compliance_notes enable row level security;

-- Same precedent as content_pages/schema_records/optimization_files/
-- audit_results (20260820160000_site_pipeline_tables.sql): only the
-- backend's service-role client ever writes or reads this table today
-- (SupabaseComplianceNotesRepository calls get_supabase_admin()), which
-- bypasses RLS regardless -- operator-only select is the honest policy,
-- no insert/update/delete policy needed.
create policy compliance_notes_select on public.compliance_notes
  for select using (public.is_operator());
