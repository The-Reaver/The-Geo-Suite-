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
fake host. Setting the real variables on the Railway service is not enough
by itself: because "Redeploy" reuses the old image (previous gotcha), the
service has to go through an actual fresh build — via a real `git push` —
for the new values to get compiled in. Same applies to the backend's
`FRONTEND_ORIGIN`/Supabase vars in spirit, though those are read at
runtime (`config.py`, plain `os.environ`), so a container restart is
enough there; it's specifically `NEXT_PUBLIC_*` build-time inlining that
needs a fresh build.
