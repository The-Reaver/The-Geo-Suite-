-- Site pipeline persistence tables: content_pages, schema_records,
-- optimization_files, audit_results. These back site_pipeline.py's
-- generate_and_store() and the four repositories in app/repositories/*.py
-- (SupabaseContentPagesRepository, SupabaseSchemaRecordsRepository,
-- SupabaseOptimizationFilesRepository, SupabaseAuditResultsRepository),
-- written and tested against this exact row shape from day one but with
-- no real tables to write to -- the original schema migration's own
-- comment deliberately deferred this "until it's a real, current
-- requirement." That requirement is now real: this is slice 0 of making
-- the Pipeline section of the app actually persist, rather than only
-- living in one backend server process's memory (which is what
-- GET_SITE_REPOS() in routers/sites.py falls back to whenever
-- GEO_USE_SUPABASE_SITE_REPOS isn't set to "1" -- true today, so nothing
-- generated through /sites/{id}/audit currently survives a redeploy).

-- ---------------------------------------------------------------------------
-- content_pages: one row per generated page (home/about/privacy/
-- accessibility/service-*), versioned on repeat saves to the same slug.
-- page_type/status check values match content_pages_repository.py's
-- _VALID_PAGE_TYPES / _VALID_STATUSES exactly.
-- ---------------------------------------------------------------------------
create table public.content_pages (
  id          uuid primary key default gen_random_uuid(),
  site_id     uuid not null,
  slug        text not null,
  title       text not null,
  page_type   text not null check (page_type in ('home', 'service', 'faq', 'about', 'privacy', 'accessibility')),
  body_json   jsonb not null,
  status      text not null default 'draft' check (status in ('draft', 'in_review', 'approved', 'published')),
  version     integer not null default 1,
  created_at  timestamptz not null default now(),
  unique (site_id, slug)
);

-- ---------------------------------------------------------------------------
-- schema_records: one row per (site_id, page_id) -- the JSON-LD graph and
-- its validation status. SupabaseSchemaRecordsRepository.save() upserts on
-- (site_id, page_id), which needs this unique constraint to work.
-- ---------------------------------------------------------------------------
create table public.schema_records (
  id                 uuid primary key default gen_random_uuid(),
  site_id            uuid not null,
  page_id            text not null,
  schema_type        text not null,
  json_ld            jsonb not null,
  validation_status  text not null,
  created_at         timestamptz not null default now(),
  unique (site_id, page_id)
);

-- ---------------------------------------------------------------------------
-- optimization_files: append-only. One row per generation for each of
-- robots/sitemap/llms/llms_full -- latest() picks the newest generated_at
-- per (site_id, file_type), mirroring InMemoryOptimizationFilesRepository.
-- file_type check values match optimization_files_repository.py's
-- _VALID_FILE_TYPES exactly.
-- ---------------------------------------------------------------------------
create table public.optimization_files (
  id            uuid primary key default gen_random_uuid(),
  site_id       uuid not null,
  file_type     text not null check (file_type in ('llms', 'llms_full', 'robots', 'sitemap', 'manifest', 'wellknown')),
  content       text not null,
  generated_at  timestamptz not null default now()
);

create index optimization_files_site_type_idx
  on public.optimization_files (site_id, file_type, generated_at desc);

-- ---------------------------------------------------------------------------
-- audit_results: append-only. One row per audit run -- latest() picks the
-- newest run_at per site_id, mirroring InMemoryAuditResultsRepository.
-- build_id is never actually populated by any real caller today (grepped:
-- generate_and_store() never passes one) -- nullable, no default.
-- ---------------------------------------------------------------------------
create table public.audit_results (
  id          uuid primary key default gen_random_uuid(),
  site_id     uuid not null,
  build_id    uuid,
  score       integer not null,
  passed      boolean not null,
  breakdown   jsonb not null,
  trigger     text not null,
  run_at      timestamptz not null default now()
);

create index audit_results_site_run_idx
  on public.audit_results (site_id, run_at desc);

-- ---------------------------------------------------------------------------
-- table grants + RLS
-- ---------------------------------------------------------------------------
grant select, insert, update, delete
  on public.content_pages, public.schema_records, public.optimization_files, public.audit_results
  to authenticated, service_role;

alter table public.content_pages enable row level security;
alter table public.schema_records enable row level security;
alter table public.optimization_files enable row level security;
alter table public.audit_results enable row level security;

-- None of these four tables carry a client_id/agent_id column -- site_id is
-- an opaque id with no per-row tenant to scope against yet (a future slice
-- may tie site_id to a real prospect/client row). Only the backend's
-- service-role client ever writes or reads these today (every
-- Supabase*Repository method in app/repositories/*.py calls
-- get_supabase_admin()), so operator-only select is the honest policy for
-- now -- same precedent as events_select in the original schema migration.
-- No insert/update/delete policy defined: the service role bypasses RLS
-- regardless, matching that same precedent.
create policy content_pages_select on public.content_pages
  for select using (public.is_operator());

create policy schema_records_select on public.schema_records
  for select using (public.is_operator());

create policy optimization_files_select on public.optimization_files
  for select using (public.is_operator());

create policy audit_results_select on public.audit_results
  for select using (public.is_operator());
