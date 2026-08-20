# Demo script

No demo script existed anywhere in this repo before 2026-08-20 — this is
that document. Written after the click path below was actually built and
verified against real code, not drafted ahead of the work. Update this file
whenever the click path changes; a stale script is worse than none.

## Pre-flight (5 minutes before anyone arrives)

- Confirm the backend and frontend are both up and pointed at the same
  Supabase project (`SUPABASE_URL` on the backend must match
  `NEXT_PUBLIC_SUPABASE_URL` on the frontend — see `README.md`'s Railway
  gotchas if either service was recently redeployed).
- Log in once yourself before the audience arrives, as the account you'll
  actually demo under. Two roles exist (`owner`, `sales_agent`) and one real
  asymmetry matters here: `POST /sales/site-generator-example` (the
  no-prospect-selected Site Generator fallback) is `owner`-only, while every
  other sales-floor route (`audit-current`, `preview`, `report`, `kit`,
  `lead`) is `sales_agent`-accessible. If you're demoing as a `sales_agent`
  login, **audit a real prospect before opening Site Generator** — once a
  prospect is selected, Site Generator calls `/sales/preview` instead (see
  below), which `sales_agent` can reach. A bare click with no prospect
  selected under a `sales_agent` login will 403.
- If live web discovery is configured (`GEO_PLACES_API_KEY` +
  `GEO_PLACES_API_URL` set on the backend), do one test search to confirm
  it's actually returning live results, not silently falling back to
  sample data. If those two variables aren't set, Prospecting always shows
  the two labeled `Sample data` rows (Paradise Hyperbarics, Hyperbaric Lab)
  — that's expected, not broken, and the UI already labels it honestly.
- Note today's date. Presenter Mode's six businesses were measured live
  2026-08-16 (per the code's own comment) — if it's been a while, consider
  spot-checking one or two against the real site before staking the room's
  trust on those exact numbers.

## The click path (safest to riskiest, in order)

### 1. Open with Presenter Mode

`Start Presenter Mode` (bottom of the Nova sidebar). Zero network
dependency, six real pre-scored businesses, 7-second auto-advance, any
click or keypress jumps forward immediately. This is the single most
reliable thing in the app — nothing here can fail live, no matter the
network, the backend, or the Supabase connection. Open with it, not with a
live call, so the room has something impressive and unbreakable before
anything that touches the network.

`Exit Presenter Mode` when ready to move to a real, live walkthrough.

### 2. A real prospect audit

Either a live `New Search` (if the Places source is configured) or the
labeled `Sample data` rows. Click `Audit` on one row — this is a genuine
live fetch of that business's actual homepage through
`POST /sales/audit-current`, scored by the real audit engine. If asked
whether this is real: yes, this exact score is being computed right now
against that business's live site, not looked up from a cache.

### 3. "The Fix"

Click **The Fix** in the sidebar. Shows the real top-5 gap list from the
audit that just ran (`fix_list`, truncated to 5 by design — the engine
computes more than the panel shows). Each gap names its rubric category and
point value.

### 4. Site Generator — on the real audited prospect

Click **Site Generator**. With a prospect selected from step 2, this now
sends that prospect's real captured facts (name, address, phone, rating if
known) to `POST /sales/preview`, which runs the real site generator and a
real audit against the freshly generated site, then opens it through a
compliance-gated, 48-hour expiring preview link. **This is the moment that
used to be broken** (it always opened a fixed fictional business regardless
of what was on screen) — now it opens a site actually built from the
prospect just audited above. If no prospect is selected, it falls back to
a fixed illustrative example instead, honestly labeled as such in the page
itself.

### 5. Compliance Library

Click **Compliance Library** in the sidebar. Real page now — not the old
placeholder badge. Shows all 20 regulatory sources this app's compliance
checker actually cites against, grouped by domain (medical marketing, patient
privacy, lead-contact compliance, AI-visibility), each with its real draft
note count and expandable sample text. **Every source and every note is
explicitly marked "Not yet lawyer-reviewed."** This is the natural landing
point for a lawyer stakeholder — it's real content, not a mockup, and the
honesty labeling is the whole point of the session.

If asked "is this legal advice": no — say so directly. Every law file and
every note carries that caveat by design; that's precisely why this session
exists.

### 6. Sales Kit — close here

In the **Discovered prospects** table, the row you audited in step 2 now
has an "Open" link in its **Sales Kit** column (it only appears once that
row has both a URL and a readiness score — audit it first). The sidebar's
own "Sales Kit" item is a label, not a link; the table is the real
entry point. Combines the real "before" score from the live audit with an
explicitly-labeled illustrative "after" example (never presented as the
prospect's actual future site) and pricing. A `PRELIMINARY` banner appears
on the score — see below for how to talk about it if asked.

## The PRELIMINARY banner

Shows up on hero cards and every generated Sales Kit because
`rubric.AI_SEARCH_READINESS_CLAIMS_PAUSED = True` — a live, deliberate
operator ruling, not a bug or a rendering glitch. If asked about it, a
short, honest answer: *"We paused making unqualified claims about AI-search
readiness while we finish validating the rubric's category weights against
a cited source. Everything you're seeing is the real, measured audit score
— the pause is specifically about the marketing claim layered on top of
it, not the measurement itself."* Don't improvise this live if you can help
it; script it, since it's exactly the kind of question a careful stakeholder
(a lawyer, in particular) will ask directly.

## If something breaks live

Fall back to Presenter Mode. It has zero dependency on anything that can
fail — network, backend, Supabase, the Places API. `Start Presenter Mode`
again and keep going; don't try to live-debug in front of an audience.

## What's real vs. what's demo-ready polish, if asked directly

Everything in the click path above is genuinely real — real audits, real
generated sites, real citations, real draft notes. Two things worth being
upfront about if a technical stakeholder pushes:

- The generated site's **interior pages** (about, services, privacy) look
  identical across all three visual themes today — only the homepage
  varies by theme. A real, disclosed gap, not hidden.
- **Prospecting's live search** only returns real results if
  `GEO_PLACES_API_KEY`/`GEO_PLACES_API_URL` are configured for this
  deployment; otherwise it's the two labeled sample rows. Both are honest
  states, never fabricated data.

## Not yet in this click path

`backend/app/routers/reports.py` (executive summaries, engine breakdowns,
competitive views, alerting) is real, tested, and reachable over the API as
of 2026-08-20, but has no frontend page yet — don't click-demo it; it isn't
wired into Nova's UI. Mention it only if asked what's coming next.
