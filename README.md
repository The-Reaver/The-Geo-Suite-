# GEO Suite

AI-search-visibility auditing, compliance checking, site generation, and
prospecting for client websites — the audit engine, compliance checker,
Nova (the sales-floor app), and the sales wizard.

Split out of `Stag-GEO-Platform` on 2026-08-19, which bundled this product
together with an unrelated client-facing tool-toggle marketplace. This repo
carries only GEO's working code, plus real, tested roadmap modules that
exist but aren't wired to a live caller yet (Sonar, ecosystem/backlink,
ranking intelligence, attribution). It has its own independent Supabase
project — no shared tenancy with the tool-set product this was split from.

## Structure

- `backend/` — FastAPI app (`app/main.py`). `pip install -e ".[dev]"` from
  `backend/`, then `uvicorn app.main:app --reload`.
- `frontend/` — Next.js 14 App Router app. `npm install && npm run dev`
  from `frontend/`.
- `supabase/migrations/` — this repo's own schema (`clients`, `users`,
  `memberships`, `events`, `prospects` — deliberately not the deferred
  client-dashboard tables; see the migration file's header for why).
- `knowledge_core/feeds/regulatory/raw_law/` — the 20-document regulatory
  law corpus the compliance checker cites against. Plain files, no
  database dependency.
- `tests/` — run the full battery with `python ci_verify_geo.py` from the
  repo root.

## Environment

Copy `.env.example` to `.env` at the repo root (backend) and
`frontend/.env.local.example` to `frontend/.env.local` (frontend), then
fill in real Supabase values for project `lhzxmvjwqllmnqecfxpm`.

## Railway gotchas

Both `backend/` and `frontend/` ship a `railway.json` naming `Dockerfile`
as the builder. That alone is not enough — 2026-08-20, both services in
this repo's Railway project came up on **Railpack**, not Dockerfile,
despite `source.repo` correctly pointing at this repo. The frontend
service also still carried `privateNetworkEndpoint: "stag-platform"`, a
leftover from whatever it was connected to before this repo existed.
Railway's per-service builder setting overrides the repo's own
`railway.json` and doesn't get corrected just by repointing `Source` at a
new repo. Fix: explicitly set each service's Dockerfile path via the
Railway dashboard (Settings → Build → Builder → Dockerfile) or API
(`update-service` with `dockerfilePath: "Dockerfile"`) — do this any time
a service's source repo changes, don't assume the config file alone wins.
Same root cause `Stag-GEO-Platform`'s own Dockerfiles already document;
it recurred here on a brand-new service, not just a long-lived one.

A plain "Redeploy" also reuses the previous build/image rather than
pulling the latest commit — see `Stag-GEO-Platform/RAILWAY_ENV_MANIFEST.md`
gotcha #4 for the full writeup. A real `git push` to `main` is what
reliably triggers a fresh build here.

The frontend's initial deploy went out with zero `NEXT_PUBLIC_*` variables
set on the Railway service, and hitting `/login` failed with a browser
"failed to fetch" error. Next.js inlines `NEXT_PUBLIC_*` values into the
client bundle at **build time**, not runtime — `lib/supabaseClient.ts`'s
placeholder fallback (`https://placeholder-project.supabase.co`) got baked
into the shipped JS, so every browser call actually tried to reach that
fake host. Fixing this took two steps, not one:

1. Setting the real variables on the Railway service and forcing a fresh
   build (`git push`, per the Redeploy-reuses-old-image gotcha above) —
   this alone was **not enough** and still shipped `/login` broken.
2. The actual missing piece: **Dockerfile builds on Railway are isolated
   from the host environment by design.** Railway service variables are
   not automatically visible inside `docker build`, even when they're set
   and even on a genuinely fresh build — a Dockerfile has to opt in with
   an explicit `ARG` (matching the variable name) plus an `ENV` to make it
   visible to the `RUN npm run build` step's own process environment,
   since Docker's `ARG` alone does not persist as a real env var readable
   via `process.env` in Node. `frontend/Dockerfile`'s build stage now
   declares `ARG`/`ENV` for all four `NEXT_PUBLIC_*` vars used at build
   time; Railway auto-supplies matching-named service variables as build
   args once the Dockerfile asks for them, no extra config needed.
   (`backend/Dockerfile` doesn't need this: FastAPI reads config from
   `os.environ` at runtime, not at build time, so backend vars only ever
   needed to be set on the service, not threaded through the build.)

Verified locally (no Docker daemon in the dev sandbox, so this was
verified by exporting the same vars before `npm run build` rather than an
actual `docker build`): with the vars present, both the real Supabase URL
and the placeholder fallback string exist in the output bundle (the
placeholder is just the ternary's unreached other branch, harmless) — but
critically, `process.env.NEXT_PUBLIC_*` gets inlined to the *real* value
Next.js's compiler substitutes at every reference, including in the
client-side JS chunk actually shipped to the browser for `/login`. Without
the vars, only the placeholder string exists anywhere in the build.

## Pipeline persistence

`POST /sites/{id}/audit` (routers/sites.py) generates a site, audits it, and
-- if it passes -- persists it via `site_pipeline.generate_and_store()`.
"Persists" only means something real once the backend service has
`GEO_USE_SUPABASE_SITE_REPOS=1` set: without it, `get_site_repos()` falls
back to module-level in-memory singletons, which don't survive a redeploy.
Setting it to `1` requires the four tables in
`supabase/migrations/20260820160000_site_pipeline_tables.sql` to actually
be applied first (`content_pages`, `schema_records`, `optimization_files`,
`audit_results` -- deliberately deferred in the original schema migration
until this became "a real, current requirement"). Same pattern as the
sibling `GEO_USE_SUPABASE_CLIENT_STORE` flag in `client_store.py`: not in
`.env.example` (that file only documents vars `config.py` itself reads),
set directly as a Railway service variable instead.

Same pattern again for compliance-note ratification: `GEO_USE_SUPABASE_COMPLIANCE_REPOS=1`
(routers/compliance.py) switches `get_compliance_notes_repo()` from an
in-memory singleton to the real `compliance_notes` table (`supabase/
migrations/20260822120000_compliance_notes_table.sql`, applied live to
project `lhzxmvjwqllmnqecfxpm` on 2026-08-22). Without it, every
ratify/reject lives only in the running backend process's memory.

## Auth roles

Three roles existed before 2026-08-22: `admin` (full access, `require_admin`
-- the only gate `owner` alone does not clear, e.g. `POST`/`GET /clients`),
`owner` (broad access via `require_owner`/`require_sales_agent`/etc., but
not `require_admin`'s own routes), and `sales_agent` (the sales-floor
routes). Compliance ratification added a
fourth, `lawyer` (`core/permissions.py::require_lawyer`) — a real,
separate person reviews and ratifies/rejects compliance notes, not the
operator acting through their own owner login (2026-08-22 operator
decision). Same as `sales_agent`'s own precedent: this codebase can add
the *code* half of a role (the permission check), but setting
`app_metadata.role = "lawyer"` on a real Supabase user is an operator-only
action in the Supabase dashboard/Auth admin API — not something to do
from here.

## Auth: password reset

`/forgot-password` calls `supabase.auth.resetPasswordForEmail(email, { redirectTo: "<frontend-origin>/reset-password" })`;
`/reset-password` is where the emailed link lands and where the user sets
a new password. Supabase rejects (silently falls back to the project's
default Site URL) any `redirectTo` that isn't on that project's Auth →
URL Configuration → **Redirect URLs** allow-list — add both
`https://the-geo-suite-frontend-production.up.railway.app/reset-password`
(prod) and `http://localhost:3000/reset-password` (local dev) there for
project `lhzxmvjwqllmnqecfxpm`. This is dashboard-only config, not
exposed through any Supabase MCP tool used in this repo's setup — an
operator step, same as the other Supabase dashboard values documented
above.
