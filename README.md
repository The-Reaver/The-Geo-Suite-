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
fill in real Supabase values for project `e7e387ee-65f4-4b5a-9b14-c8e665f79d29`.
