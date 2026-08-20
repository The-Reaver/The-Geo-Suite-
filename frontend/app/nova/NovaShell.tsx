"use client";

/*
 * Nova shell — the premium GEO Suite look, with all candidate accent designs
 * built in and switchable live. Operator plan: build every design in, switch
 * between them, then delete the losers and keep the one the partner picks.
 *
 * Porcelain is the constant canvas; the four accents (Clinical Blue, Apothecary
 * Sage, Calm Teal, Bordeaux) are medically grounded (blue=trust, green/teal=
 * healing; bordeaux=private-clinic luxe). Compliance Library leads the sidebar
 * per the data-lineage ruling (Source -> Engine -> Sales Floor). "Focus Mode" is
 * the renamed accessibility state. Styles live scoped under .nova-app in
 * globals.css, so nothing here leaks into any other screen.
 *
 * To PRUNE to the winner later: drop the losing entries from ACCENTS below and
 * delete their [data-accent="..."] blocks in globals.css.
 */

import { useEffect, useState, useTransition } from "react";
import { discoverProspects, auditSite, saveLead, saveToPipeline, type DiscoverResult, type ProspectRow } from "./actions";
import { syncForTheField, drainOutbox } from "./lib/fieldSync";
import { getBrowserAccessToken } from "./lib/supabaseBrowser";
import { fetchPricingTiers, type PricingTier } from "./lib/pricing";
import {
  putProspects, getAllCachedProspects, putSalesKit, type CachedProspect,
  queueOutboxEntry, getAllOutboxEntries, getPendingOutboxCount, markOutboxSynced, markOutboxFailed,
} from "./lib/offlineStore";

// Clinical Blue is the chosen accent (operator, 2026-08-09). The other candidate
// accents were pruned after the live palette study; the shell is fixed to
// data-accent="blue". Focus Mode (the renamed accessibility state) persists.
const FOCUS_KEY = "nova.focus";

// Labeled sample shown when the live Prospecting source is off/unauthorized, so
// the premium shell still reads well without fabricating live results.
//
// 2026-08-15: swapped from fictional Austin placeholders to the two real
// businesses the operator picked for the actual demo (Paradise Hyperbarics,
// Hyperbaric Lab). readiness is left null on purpose, not pre-filled — the
// backend already scored these live (14/100 and 29/100, verified this same
// session, see GEO_DEVELOPMENT_LOG.md) but showing a static number here would
// remove the "Audit" button, i.e. the actual live-in-front-of-the-partner
// moment. Once Supabase auth is live, clicking Audit runs the real
// /sales/audit-current call against these real URLs.
const SAMPLE_ROWS: ProspectRow[] = [
  { name: "Paradise Hyperbarics", locality: "Temecula, CA", readiness: null, status: "Incomplete", confirm: "ownership · payment · indications", url: "https://www.paradisehyperbarics.com/" },
  { name: "Hyperbaric Lab", locality: "Laguna Hills, CA", readiness: null, status: "Incomplete", confirm: "ownership · payment · indications", url: "https://hyperbariclab.com/" },
];

// Presenter Mode — 2026-08-16, operator's business partner is a doctor who
// will showcase this app live at a conference and wants it to drive itself.
// Auto-advances on a timer; any click or keypress jumps to the next step and
// resets the timer, so the doctor keeps a manual override without needing to
// stay fully hands-off. Never a live network call mid-presentation: these six
// businesses were measured live on 2026-08-16 via the real audit engine
// (rescore_2026-08-16.py, hbot_rescored_2026-08-16.json) — real numbers,
// pre-loaded for stage reliability, not fabricated and not fetched fresh in
// front of an audience where a slow or flaky site could stall the room.
type DemoStep = { name: string; locality: string; score: number; gap: string; url: string };
const PRESENTER_SCRIPT: DemoStep[] = [
  { name: "34th Street Chiropractic", locality: "—", score: 11, url: "https://www.healthcarechiropractic.com/",
    gap: "[Structured Data and Schema, up to 17 pts] no LocalBusiness node found in JSON-LD" },
  { name: "American Regenerative Clinic", locality: "MI", score: 26, url: "https://americanregen.com/hyperbaric-oxygen-therapy/",
    gap: "[Structured Data and Schema, up to 14 pts] no LocalBusiness node found in JSON-LD" },
  { name: "Chicago Neuro", locality: "—", score: 31, url: "https://chicagoneuro.com/",
    gap: "[Structured Data and Schema, up to 10 pts] no LocalBusiness node found in JSON-LD" },
  { name: "Hyperbaric Wellness Center", locality: "Morgan Hill, CA", score: 37, url: "https://www.hyperbaricwellnessmorganhill.com/",
    gap: "[Structured Data and Schema, up to 12 pts] no LocalBusiness node found in JSON-LD" },
  { name: "Advanced Hyperbaric Recovery", locality: "—", score: 65, url: "https://www.hyperbaricoxygentherapy.com/",
    gap: "[Structured Data and Schema, up to 4 pts] missing Organization schema" },
  { name: "Maui Longevity Rx", locality: "HI", score: 70, url: "https://mauilongevityrx.com/",
    gap: "[Structured Data and Schema, up to 2 pts] no Service or FAQPage schema found on any page" },
];
const PRESENTER_STEP_MS = 7000;

// 2026-08-20: fallback only, for when GET /sales/pricing-tiers can't be
// reached (offline, signed out) -- backend/app/core/pricing.py is the real
// source of truth these mirror. Kept here so the panel never just goes
// blank, same honest-fallback pattern as SAMPLE_ROWS above.
const FALLBACK_PRICING_TIERS: PricingTier[] = [
  { name: "Starter", price: 500, tag: "Foundational AI-search readiness", popular: false, bullets: [
    "Live AI-Search Readiness audit", "Gap report vs. the 93-point publish gate",
    "Monthly readiness re-check", "No site rebuild included"] },
  { name: "Full-Service Growth", price: 2500, tag: "Everything to clear the gate and stay there", popular: true, bullets: [
    "Generated site tuned to clear the 93-point gate", "Hosting, SSL, uptime monitoring",
    "Ongoing AI-visibility + local SEO optimization", "Monthly compliance + readiness report",
    "Unlimited content updates"] },
  { name: "Growth + Social", price: 4500, tag: "For practices ready to dominate online", popular: false, bullets: [
    "Everything in Full-Service Growth, plus", "YouTube, Instagram, Facebook management",
    "Review + reputation engine", "We handle everything — send us raw content"] },
];

// Parses audit_engine's fix_list format, "[Category Name, up to N pts] description",
// into displayable parts. Falls back to the raw string if the shape ever changes —
// never hides a real finding just because it didn't match a regex.
const GAP_RE = /^\[(.+?), up to (\d+) pts?\]\s*(.*)$/;
function parseGap(gap: string): { category: string; points: string; description: string } {
  const m = GAP_RE.exec(gap);
  if (!m) return { category: "", points: "", description: gap };
  return { category: m[1] ?? "", points: m[2] ?? "", description: m[3] ?? "" };
}

function Icon({ d, extra }: { d: string; extra?: string }) {
  return (
    <svg viewBox="0 0 24 24">
      <path d={d} />
      {extra ? <path d={extra} /> : null}
    </svg>
  );
}

export default function NovaShell({ initial }: { initial: DiscoverResult }) {
  const [focus, setFocus] = useState(false);
  const [live, setLive] = useState(initial.live);
  const [rows, setRows] = useState<ProspectRow[]>(initial.live ? initial.rows : SAMPLE_ROWS);
  const [businessType, setBusinessType] = useState("hyperbaric therapy");
  const [locality, setLocality] = useState("Temecula, CA");
  const [pending, startTransition] = useTransition();
  const [pricingTiers, setPricingTiers] = useState<PricingTier[]>(FALLBACK_PRICING_TIERS);

  // 2026-08-20: pulls the real tiers from the backend once on mount so this
  // panel and the Sales Kit's HTML read the same single source of truth
  // (core/pricing.py) instead of two hand-synced copies. Falls back to
  // FALLBACK_PRICING_TIERS (already the default state) on any failure --
  // never a blank panel.
  useEffect(() => {
    let cancelled = false;
    fetchPricingTiers().then((result) => {
      if (!cancelled && result.ok) setPricingTiers(result.tiers);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // Real, measured score (verified live this session, not fabricated — see
  // GEO_DEVELOPMENT_LOG.md 2026-08-15) — Paradise Hyperbarics scored 14/100.
  // preliminary: true — the Brain Trust HOLD on score trustworthiness was
  // lifted 2026-08-16 (independent re-verification passed cleanly), but
  // rubric.AI_SEARCH_READINESS_CLAIMS_PAUSED stays true for a separate,
  // still-open reason: the category weights have no cited empirical source.
  const [hero, setHero] = useState<{
    name: string; score: number; preliminary: boolean; gap?: string; gaps?: string[];
    prospectId?: string; url?: string; locality?: string;
    // 2026-08-20: carried through from ProspectRow so Site Generator can
    // build the currently-audited prospect's real BusinessFactsReq instead
    // of always the illustrative fixture -- see the "Site Generator" nav
    // link below. Absent for the fixed opening demo state and Presenter
    // Mode steps, same as url/locality above.
    region?: string; street?: string; postalCode?: string; telephone?: string;
    domain?: string; ratingValue?: number; ratingCount?: number;
    // 2026-08-20, Pipeline slice 1: carried through from ProspectRow.businessType
    // so Save to Pipeline can send a real subtype instead of always "".
    businessType?: string;
  }>({
    name: "Paradise Hyperbarics",
    score: 14,
    preliminary: true,
  });
  // 2026-08-16: the "Save Lead" gap, flagged and deliberately deferred in both
  // Phase 1 and Phase 2's dev log entries -- without it, "Sync for the field"
  // never has anything of the agent's own to sync, which blocks the real
  // device test from being completable at all. savingLead guards the button
  // against a double-submit; leadSaved gives it a persistent "Saved" state
  // rather than reverting once hero.prospectId is set.
  const [savingLead, setSavingLead] = useState(false);
  // Pipeline slice 1: "Save to Pipeline" state. pipelineResult holds the
  // last real outcome (score/passed/fixList on a gate failure) so the UI
  // can show *why* a save didn't go through, not just that it didn't.
  const [savingToPipeline, setSavingToPipeline] = useState(false);
  const [pipelineResult, setPipelineResult] = useState<
    { ok: true; score: number | null } | { ok: false; score: number | null; reason: string; fixList?: string[] } | null
  >(null);
  // Presenter Mode state — see PRESENTER_SCRIPT above.
  const [presenting, setPresenting] = useState(false);
  const [presentIdx, setPresentIdx] = useState(0);
  // "The Fix" — 2026-08-16: un-stubbed. auditSite() already returns the
  // real full gap list (up to 5, from result.fix_list server-side); it was
  // being fetched and thrown away. Toggled open, not a separate page, so it
  // reads against whichever business is currently in the hero card.
  const [showFix, setShowFix] = useState(false);
  const [auditingIdx, setAuditingIdx] = useState<number | null>(null);
  // Phase 1 offline state (2026-08-16). isOnline drives the honest "offline"
  // AUDIT_REASONS message and which data source (live vs. cached) the shell
  // falls back to. syncState/lastSynced back the "Sync for the field" action
  // and its own visible cached-as-of reporting — never silent, per
  // Celestina's finding C.
  const [isOnline, setIsOnline] = useState(true);
  const [syncState, setSyncState] = useState<"idle" | "syncing" | "done" | "error">("idle");
  const [lastSyncedAt, setLastSyncedAt] = useState<string | null>(null);
  const [syncSummary, setSyncSummary] = useState<string | null>(null);
  // Phase 2 (write-side offline) state: the note/gap-picker customization
  // form for whichever prospect is currently in `hero`, and the outbox
  // pending-count indicator Celestina's review requires be visible.
  const [noteDraft, setNoteDraft] = useState("");
  const [selectedGapIndices, setSelectedGapIndices] = useState<number[]>([]);
  const [outboxPending, setOutboxPending] = useState(0);
  const [customizeSaved, setCustomizeSaved] = useState(false);
  // 2026-08-09 GEO Brain Trust Presentation Mode review, Jasiah finding: a
  // failed live action (audit or search) previously failed silently — the
  // spinner just stopped with no explanation. Surfaced here instead of
  // swallowed, so a demo in front of a prospect never goes quiet.
  const [actionError, setActionError] = useState<string | null>(null);
  // 2026-08-16: /nova has no server-side auth gate (middleware.ts only
  // protects /admin/:path*, by design -- see that file's own comment) and
  // every action already degrades honestly to "sign in again" when there's
  // no session. But nothing ever told a genuinely unauthenticated visitor
  // (e.g. a bookmarked /nova link, the real case that surfaced this) HOW to
  // sign in -- a real dead end, discovered live. authStatus starts
  // "checking" and flips to "signed-in" | "signed-out" | "unconfigured"
  // (Supabase env vars missing entirely -- a different, legitimate case,
  // e.g. local dev with no env: the existing sample-data demo fallback
  // stays exactly as-is for that one).
  const [authStatus, setAuthStatus] = useState<"checking" | "signed-in" | "signed-out" | "unconfigured">("checking");

  const AUDIT_REASONS: Record<string, string> = {
    "not-signed-in": "Your session expired. Sign in again to run a live audit.",
    "supabase-not-configured": "The live audit source isn't configured in this environment.",
    unreachable: "Couldn't reach the audit engine. Check your connection and try again.",
    // 2026-08-16, Phase 1: a distinct reason from "unreachable" per
    // Celestina's finding C — "unreachable" reads as possibly transient
    // (worth retrying); a genuinely offline device needs its own honest
    // message so the agent doesn't assume a retry will fix something that
    // structurally cannot be fixed by retrying.
    offline: "You're offline. Live audits need a connection — showing synced data instead where available.",
    // 2026-08-16, Phase 3: a third distinct case from both of the above --
    // navigator.onLine can read true while the connection is too weak to
    // finish a request. Before this, that case fell through to "unreachable"
    // at best, or just hung with no message at all (bare fetch has no
    // default timeout) -- a stuck spinner through part of an appointment,
    // exactly the silent failure this whole design exists to refuse.
    timeout: "Your connection is too weak right now — the request timed out. Try again, or continue with your last synced data.",
  };

  function reasonToMessage(reason: string): string {
    return AUDIT_REASONS[reason] ?? `The audit didn't complete (${reason}). Try again.`;
  }

  function runSearch() {
    // Discovering brand-new prospects cannot work offline, ever — this is a
    // live search, not something any pre-sync could have prepared (Celestina's
    // table, OFFLINE_ARCHITECTURE_BRAIN_TRUST_2026-08-16.md). Fail honestly
    // rather than let the server action hang with no signal.
    if (!isOnline) {
      setActionError(reasonToMessage("offline"));
      return;
    }
    setActionError(null);
    startTransition(async () => {
      const r = await discoverProspects({ business_type: businessType, locality });
      setLive(r.live);
      setRows(r.live && r.rows.length ? r.rows : SAMPLE_ROWS);
    });
  }

  // 2026-08-16, Phase 2: a synced/cached prospect (real id, already has a
  // score from a prior sync) had no way to become the hero selection at
  // all once loaded offline — auditRow() requires a url and a live
  // network call, neither available for a cached row. This is the
  // zero-network path: load what's already in view into hero directly, so
  // "review and customize a cached prospect with zero signal" (the
  // operator's actual stated requirement) is reachable, not just
  // theoretically supported by the data layer underneath it.
  function loadProspectIntoHero(i: number) {
    const row = rows[i];
    if (!row || !row.id) return;
    setHero({ name: row.name, score: row.readiness ?? 0, preliminary: true, prospectId: row.id });
    setNoteDraft("");
    setSelectedGapIndices([]);
  }

  // Live audit of one prospect via the real backend; fills its readiness and
  // promotes it into the hero gauge. Never fabricates: only a returned score updates the UI.
  function auditRow(i: number) {
    const row = rows[i];
    if (!row || !row.url) return;
    // 2026-08-16, Phase 1: a live audit fetches the prospect's real site at
    // that moment — structurally impossible with zero signal, not a
    // retryable error. Fail honestly and immediately rather than let the
    // request hang and surface a generic "unreachable" a retry can't fix.
    if (!isOnline) {
      setActionError(reasonToMessage("offline"));
      return;
    }
    setAuditingIdx(i);
    setActionError(null);
    startTransition(async () => {
      const a = await auditSite(row.url);
      setAuditingIdx(null);
      if (a.ok && a.score != null) {
        const s = a.score;
        setRows((prev) => prev.map((r, j) => (j === i ? { ...r, readiness: s } : r)));
        setHero({
          name: row.name, score: s, preliminary: a.preliminary, gap: a.gaps[0], gaps: a.gaps,
          url: row.url, locality: row.locality,
          region: row.region, street: row.street, postalCode: row.postalCode, telephone: row.telephone,
          domain: row.domain, ratingValue: row.ratingValue, ratingCount: row.ratingCount,
          businessType: row.businessType,
        });
      } else {
        setActionError(reasonToMessage(a.reason));
      }
    });
  }

  // Saves the currently-audited hero business as this agent's own tracked
  // prospect (POST /sales/lead via saveLead()) -- closes the real gap named
  // in both the Phase 1 and Phase 2 dev log entries. Requires hero.url: a
  // hero that came from a real audit (auditRow) or a cached/synced row
  // (loadProspectIntoHero, which already has a prospectId and skips this
  // entirely) has one; the fixed opening demo state and Presenter Mode steps
  // do not, so the button stays correctly disabled for those without any
  // extra guard logic needed here.
  function saveLeadAsProspect() {
    if (!hero.url || hero.prospectId || savingLead) return;
    setSavingLead(true);
    setActionError(null);
    startTransition(async () => {
      const result = await saveLead({
        businessName: hero.name,
        score: hero.score,
        city: hero.locality,
        websiteUrl: hero.url,
      });
      setSavingLead(false);
      if (result.ok && result.prospectId) {
        setHero((h) => ({ ...h, prospectId: result.prospectId! }));
      } else {
        setActionError(reasonToMessage(result.reason));
      }
    });
  }

  // Pipeline slice 1: persist the currently-audited prospect for real
  // (POST /sites/{site_id}/audit -> site_pipeline.generate_and_store()),
  // reusing hero.prospectId (minted by saveLeadAsProspect above) as
  // site_id. Requires both a saved lead AND a real audit, matching the
  // same "save a lead first" / "audit first" honesty this shell already
  // applies to every other gated action.
  function saveToPipelineAction() {
    if (!hero.prospectId || !hero.url || savingToPipeline) return;
    setSavingToPipeline(true);
    setPipelineResult(null);
    startTransition(async () => {
      const result = await saveToPipeline({
        siteId: hero.prospectId!,
        businessName: hero.name,
        businessType: hero.businessType,
        street: hero.street,
        locality: hero.locality,
        region: hero.region,
        postalCode: hero.postalCode,
        telephone: hero.telephone,
        domain: hero.domain,
        ratingValue: hero.ratingValue,
        ratingCount: hero.ratingCount,
      });
      setSavingToPipeline(false);
      if (result.ok) {
        setPipelineResult({ ok: true, score: result.score });
      } else {
        setPipelineResult({ ok: false, score: result.score, reason: result.reason, fixList: result.fixList });
      }
    });
  }

  // Exit-to-safety: Amaya/Celestina (Brain Trust, 2026-08-09) both flagged
  // that nothing in the shell could reset a demo that had gone sideways —
  // a stuck audit, a bad search, a wrong hero row. This returns every piece
  // of session-local demo state to its opening defaults. Focus Mode is a
  // standing accessibility preference, not demo state, so it is left alone.
  function resetDemo() {
    setLive(initial.live);
    setRows(initial.live ? initial.rows : SAMPLE_ROWS);
    setBusinessType("hyperbaric therapy");
    setLocality("Temecula, CA");
    setHero({ name: "Paradise Hyperbarics", score: 14, preliminary: true });
    setAuditingIdx(null);
    setActionError(null);
    setPresenting(false);
    setPresentIdx(0);
    setShowFix(false);
  }

  function applyPresenterStep(i: number) {
    const step = PRESENTER_SCRIPT[i];
    if (!step) return;
    // preliminary: true — matches rubric.AI_SEARCH_READINESS_CLAIMS_PAUSED as of
    // 2026-08-16 (this script uses pre-loaded real scores, not a live API call,
    // so it can't read the flag directly). The Brain Trust HOLD this flag once
    // also covered was lifted 2026-08-16 after clean independent re-verification;
    // the flag now stays true solely for the separate weight-sourcing gap. Update
    // this if that gap is ever closed and the flag flips false.
    setHero({ name: step.name, score: step.score, preliminary: true, gap: step.gap, gaps: [step.gap] });
  }

  function startPresenting() {
    setActionError(null);
    setPresentIdx(0);
    applyPresenterStep(0);
    setPresenting(true);
    // Auto-open The Fix so the full real gap list (not just the top line
    // already in the pass/fail copy) is visible for the whole tour — a more
    // complete story for the doctor's audience, no manual toggling needed.
    setShowFix(true);
  }

  function stopPresenting() {
    setPresenting(false);
    setShowFix(false);
  }

  function advancePresenting() {
    setPresentIdx((i) => {
      const next = (i + 1) % PRESENTER_SCRIPT.length;
      applyPresenterStep(next);
      return next;
    });
  }

  // Real session check, once on mount. Never throws on a missing/unconfigured
  // session -- getBrowserAccessToken() already returns null rather than
  // rejecting, matching every other honest-failure path in this file.
  useEffect(() => {
    const supaUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const supaKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    if (!supaUrl || !supaKey) {
      setAuthStatus("unconfigured");
      return;
    }
    getBrowserAccessToken()
      .then((token) => setAuthStatus(token ? "signed-in" : "signed-out"))
      .catch(() => setAuthStatus("signed-out"));
  }, []);

  // Auto-advance timer — resets on every step change so a manual advance
  // (click/keypress, below) gets the doctor a full fresh interval too.
  useEffect(() => {
    if (!presenting) return;
    const t = setTimeout(advancePresenting, PRESENTER_STEP_MS);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [presenting, presentIdx]);

  // Manual override — any click or keypress while presenting jumps forward
  // immediately, per the operator's 2026-08-16 ruling (auto-advance with a
  // manual override, not fully hands-off and not click-only).
  //
  // Bug found and fixed live, 2026-08-16: the click that starts Presenter
  // Mode (on "Start Presenter Mode") is still bubbling up the real DOM tree
  // to `window` at the moment this effect runs and attaches its listener —
  // React's commit-phase effects fire synchronously within the same click
  // dispatch, before the native event finishes bubbling. That meant every
  // start immediately double-advanced (step 1 shown for an instant, then
  // silently skipped to step 2) before a human ever saw or clicked anything.
  // Deferring attachment by one tick (setTimeout 0) lets the originating
  // click's bubble phase finish first.
  useEffect(() => {
    if (!presenting) return;
    const onAdvance = (e: Event) => {
      // Don't hijack a click on the Exit Presenter Mode control itself.
      if (e instanceof MouseEvent && (e.target as HTMLElement)?.closest?.("[data-presenter-exit]")) return;
      advancePresenting();
    };
    const attach = setTimeout(() => {
      window.addEventListener("click", onAdvance);
      window.addEventListener("keydown", onAdvance);
    }, 0);
    return () => {
      clearTimeout(attach);
      window.removeEventListener("click", onAdvance);
      window.removeEventListener("keydown", onAdvance);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [presenting]);

  const GAUGE_C = 326.7;
  const heroScore = Math.min(100, Math.max(0, hero.score));
  const gaugeOffset = GAUGE_C * (1 - heroScore / 100);
  const belowGate = hero.score < 93;

  // 2026-08-20: Site Generator used to always open the illustrative fixture,
  // even with a real, just-audited prospect on screen -- the demo's most
  // visible "wait, that's not the business we just looked at" moment.
  // hero.url only gets set by a real auditRow() call (or a loaded/cached
  // real prospect), never by the fixed opening state or a Presenter Mode
  // step, so gating on it here means those two stay on the guaranteed-good
  // illustrative fallback exactly as before -- only a genuinely audited
  // prospect gets its own real facts sent through.
  const siteGeneratorHref = (() => {
    if (!hero.url) return "/nova/site-generator";
    const domain = hero.domain || hero.url.replace(/^https?:\/\//, "").replace(/\/.*$/, "");
    const params = new URLSearchParams();
    params.set("businessName", hero.name);
    if (domain) params.set("domain", domain);
    if (hero.street) params.set("street", hero.street);
    if (hero.locality) params.set("locality", hero.locality);
    if (hero.region) params.set("region", hero.region);
    if (hero.postalCode) params.set("postalCode", hero.postalCode);
    if (hero.telephone) params.set("telephone", hero.telephone);
    if (hero.ratingValue != null) params.set("ratingValue", String(hero.ratingValue));
    if (hero.ratingCount != null) params.set("ratingCount", String(hero.ratingCount));
    return `/nova/site-generator?${params.toString()}`;
  })();

  // Restore Focus Mode so a demo opens where the operator left it.
  useEffect(() => {
    if (typeof window !== "undefined" && localStorage.getItem(FOCUS_KEY) === "1") setFocus(true);
  }, []);

  // Phase 1 offline state: real browser connectivity, not simulated. On a
  // genuine loss of signal, fall back to whatever was last synced to
  // IndexedDB rather than leaving the shell showing live-looking data it
  // can no longer verify. Mount-time: show the real outbox count so a
  // reload doesn't lose track of unsynced work.
  useEffect(() => {
    refreshOutboxCount();
    if (typeof navigator === "undefined") return;
    setIsOnline(navigator.onLine);
    const goOnline = () => {
      setIsOnline(true);
      // Reconnect-triggered drain, per Celestina's finding E ("an
      // agent-triggered OR reconnect-triggered 'Sync now'" — explicitly not
      // the Background Sync API, and explicitly not silent: the pending
      // count visibly changes, and syncSummary reports the real outcome
      // EVEN when the drain couldn't run at all — a bug caught live in this
      // same pass: the original version only reported the success path's
      // sub-counts, so "reconnected but not signed in, nothing synced"
      // silently reported nothing, which is exactly the silent-failure
      // mode this whole offline design exists to refuse).
      getPendingOutboxCount().then((pendingBefore) => {
        if (pendingBefore === 0) return; // nothing queued — no report needed, not a failure
        drainOutbox(getAllOutboxEntries, markOutboxSynced, markOutboxFailed).then((drain) => {
          refreshOutboxCount();
          if (!drain.ok) {
            setSyncSummary(`Reconnected, but couldn't sync ${pendingBefore} queued change(s): ${reasonToMessage(drain.reason)}`);
            return;
          }
          if (drain.synced || drain.discardedStale || drain.failed) {
            setSyncSummary(
              `Reconnected — synced ${drain.synced} customization(s)` +
              (drain.discardedStale ? `, ${drain.discardedStale} superseded by a newer edit` : "") +
              (drain.failed ? `, ${drain.failed} failed (will retry next sync).` : ".")
            );
          }
        });
      });
    };
    const goOffline = () => {
      setIsOnline(false);
      loadCachedProspectsIntoView();
    };
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadCachedProspectsIntoView() {
    try {
      const cached = await getAllCachedProspects();
      if (!cached.length) return; // nothing synced yet — leave the current view as-is, don't clear it
      setRows(
        cached.map((p) => ({
          id: p.id,
          name: p.business_name,
          locality: p.city || "",
          readiness: p.current_score ?? null,
          status: "Incomplete",
          confirm: "",
          url: "",
        }))
      );
      const newest = cached.reduce((a, b) => (a.syncedAt > b.syncedAt ? a : b));
      setLastSyncedAt(newest.syncedAt);
    } catch {
      // IndexedDB unavailable (private browsing, unsupported browser) —
      // the shell just has nothing to fall back to, same as "no sync yet."
    }
  }

  async function refreshOutboxCount() {
    try {
      setOutboxPending(await getPendingOutboxCount());
    } catch {
      // IndexedDB unavailable — nothing to count, same as zero pending.
    }
  }

  async function runFieldSync() {
    setSyncState("syncing");
    setSyncSummary(null);
    // "Sync for the field" pulls this agent's own saved prospects, not
    // whatever happens to be in the currently-displayed Prospecting search
    // results — those are discovered-but-not-yet-saved candidates, a
    // different set. See runFieldSync's own summary message when the
    // synced list is empty for why that distinction matters honestly.
    const urlsByProspectId: Record<string, string> = {};
    const result = await syncForTheField(putProspects, putSalesKit, urlsByProspectId);

    // Phase 2: the same action also drains the write-side outbox, agent-
    // triggered per Celestina's finding E. Read-side and write-side sync are
    // one combined "Sync for the field" step for the agent, not two
    // separate buttons to remember to press.
    const drain = await drainOutbox(getAllOutboxEntries, markOutboxSynced, markOutboxFailed);
    await refreshOutboxCount();

    if (!result.ok) {
      setSyncState("error");
      setSyncSummary(reasonToMessage(result.reason));
      return;
    }
    setSyncState("done");
    setLastSyncedAt(new Date().toISOString());

    if (result.prospects.length > 0) {
      setRows(result.prospects.map((p) => ({
        id: p.id,
        name: p.business_name,
        locality: p.city || "",
        readiness: p.current_score ?? null,
        status: "Incomplete",
        confirm: "",
        url: "",
      })));
      const first = result.prospects[0];
      if (first) {
        setHero({ name: first.business_name, score: first.current_score ?? 0, preliminary: true, prospectId: first.id });
      }
    }

    const drainNote = drain.ok
      ? (drain.synced || drain.discardedStale || drain.failed
          ? ` Customizations: ${drain.synced} synced` +
            (drain.discardedStale ? `, ${drain.discardedStale} superseded by a newer edit` : "") +
            (drain.failed ? `, ${drain.failed} failed (will retry next sync).` : ".")
          : "")
      : ` Customizations couldn't sync (${reasonToMessage(drain.reason)}).`;

    if (result.prospects.length === 0) {
      setSyncSummary("No saved prospects yet — nothing to sync. Save a lead first, then sync for the field." + drainNote);
    } else {
      setSyncSummary(
        `Synced ${result.prospects.length} prospect(s). Sales Kits: ${result.kitsSynced} ready` +
        (result.kitsFailed ? `, ${result.kitsFailed} failed (no known site URL or fetch error).` : ".") +
        drainNote
      );
    }
  }

  async function saveCustomizationOffline() {
    if (!hero.prospectId) return;
    await queueOutboxEntry({
      prospectId: hero.prospectId,
      note: noteDraft,
      selectedGapIndices,
      clientTimestamp: new Date().toISOString(),
    });
    await refreshOutboxCount();
    setCustomizeSaved(true);
    setTimeout(() => setCustomizeSaved(false), 2500);
  }

  function toggleGapIndex(i: number) {
    setSelectedGapIndices((prev) => (prev.includes(i) ? prev.filter((x) => x !== i) : [...prev, i]));
  }

  function toggleFocus() {
    setFocus((f) => {
      const n = !f;
      if (typeof window !== "undefined") localStorage.setItem(FOCUS_KEY, n ? "1" : "0");
      return n;
    });
  }

  // Real gate: an unauthenticated visitor (a bookmarked /nova link, most
  // realistically) sees a clear path to sign in instead of the full shell
  // with dead-end "sign in again" errors on every action. "checking" and
  // "unconfigured" both fall through to the normal shell below -- checking
  // is momentary, and unconfigured means there's no real backend to sign
  // into anyway (the existing sample-data demo fallback covers that case).
  if (authStatus === "signed-out") {
    return (
      <div className="nova-app" data-accent="blue">
        <main className="nv-wrap" style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh" }}>
          <div className="nv-panel" style={{ maxWidth: 420, textAlign: "center", padding: "40px 32px" }}>
            <h1 style={{ fontFamily: "var(--nv-serif)", fontSize: 24, marginBottom: 8 }}>Sign in to continue</h1>
            <p style={{ color: "var(--nv-text3)", marginBottom: 24 }}>
              Your session has expired or you're not signed in yet. Sign in to see your real prospects,
              run live audits, and sync for the field.
            </p>
            <a href="/login?next=/nova" className="nv-btn solid" style={{ display: "inline-flex" }}>
              Sign in
            </a>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className={`nova-app${focus ? " is-focus" : ""}`} data-accent="blue">
      <aside>
        <div className="nv-brand">
          <svg width="32" height="32" viewBox="0 0 40 40">
            <circle cx="20" cy="20" r="18" fill="none" stroke="var(--nv-metal)" strokeWidth="1.5" />
            <circle cx="20" cy="20" r="11" fill="none" stroke="var(--nv-accent)" strokeWidth="1.5" />
            <circle cx="20" cy="20" r="3.4" fill="var(--nv-metal)" />
          </svg>
          <div style={{ display: "flex", alignItems: "baseline", gap: 9 }}>
            <span className="nv-mark">GE<b>O</b></span>
            <span className="nv-sub">Suite</span>
          </div>
        </div>
        <div className="nv-rule" />
        <nav>
          <div className="nv-sec">Source of Truth</div>
          {/* 2026-08-20: was a plain unclickable <div> with a hardcoded,
              fake "3 pending" badge -- no page, no route, no backend
              endpoint behind it at all. Real page now at /nova/compliance
              (GET /compliance/library), matching the honest "Live" tag
              pattern The Fix/Site Generator/Sales Kit already use rather
              than a count this component would have to fetch just to
              render the sidebar. */}
          <a className="nv-item source" href="/nova/compliance">
            <Icon d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7z" extra="M9 12l2 2 4-4" />
            Compliance Library <span className="nv-tag">Live</span>
          </a>
          <div className="nv-sec">Engine · fed by the Library</div>
          {/* 2026-08-09 GEO Brain Trust review, Amaya/Celestina/Jasiah finding:
              these items looked clickable but did nothing. Not yet wired to a
              Nova-native page — linking out to the older dashboard's different
              design system mid-demo is a separate call this fix doesn't make
              on its own — so they carry an honest "Soon" state instead of a
              silent dead click. */}
          <div className="nv-item soon" aria-disabled="true"><Icon d="M4 19V5M4 19h16M8 15l3-4 3 2 4-6" />Audit <span className="nv-soon">Soon</span></div>
          {/* 2026-08-16: un-stubbed. Toggles a panel below the hero card
              listing every real gap for whichever business is currently
              audited — data auditSite() already fetched (up to 5 real
              findings from audit_engine's fix_list) and was being thrown
              away, showing only the single top gap. */}
          <button
            className="nv-item"
            style={{ width: "100%", background: "none", border: "none", textAlign: "left", cursor: "pointer" }}
            onClick={() => setShowFix((v) => !v)}
            type="button"
            aria-pressed={showFix}
          >
            <Icon d="M12 20V10M6 20v-4M18 20V6" />The Fix <span className="nv-tag">Live</span>
          </button>
          {/* 2026-08-16: wired to the real, already-built backend
              (site_engine.generate_site()) that just had never been
              connected to the Nova UI. Opens the real generated site, not a
              summary about it.
              2026-08-20: was always calling the illustrative-example route
              regardless of what was on screen -- the demo's most visible
              "that's not the business we just audited" moment. siteGeneratorHref
              (above) now carries the real audited prospect's facts as query
              params when one is selected; route.ts posts those to the real
              /sales/preview endpoint instead, falling back to the
              illustrative fixture only when no real prospect is in context. */}
          <a className="nv-item" href={siteGeneratorHref} target="_blank" rel="noreferrer">
            <Icon d="M9 12l2 2 4-4" extra="M12 3a9 9 0 100 18 9 9 0 000-18" />Site Generator <span className="nv-tag">Live</span>
          </a>
          <div className="nv-item soon" aria-disabled="true"><Icon d="M6 3h9l5 5v13H6z" extra="M9 13h7M9 17h7" />Reports <span className="nv-soon">Soon</span></div>
          <div className="nv-sec">Sales Floor</div>
          <div className="nv-item active"><Icon d="M18 18l-4-4" extra="M4 11a7 7 0 1014 0 7 7 0 00-14 0" />Prospecting <span className="nv-tag">Live</span></div>
          {/* 2026-08-20, Pipeline slice 2: real page at /nova/pipeline
              (GET /sites/pipeline) -- every prospect actually persisted via
              the "Save to Pipeline" button (slice 1), not the ephemeral
              demo state. Same honest "Live" tag pattern as Compliance
              Library above. */}
          <a className="nv-item source" href="/nova/pipeline">
            <Icon d="M4 5h16M4 12h10M4 19h6" />Pipeline <span className="nv-tag">Live</span>
          </a>
          {/* 2026-08-16: real minimal build for the investor demo — an audited
              prospect (readiness != null) can open its Sales Kit; before that,
              same honest "Soon" state as the other unwired items. */}
          <div className="nv-item"><Icon d="M4 7h16v13H4zM8 7V4h8v3" />Sales Kit <span className="nv-tag">Live</span></div>
        </nav>
        <div className="nv-foot">
          <button className="nv-fx" onClick={toggleFocus} aria-pressed={focus}>
            <svg style={{ width: 18, height: 18, stroke: "var(--nv-accent)", strokeWidth: 1.5, fill: "none" }} viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="3" /><path d="M12 3v3M12 18v3M3 12h3M18 12h3" />
            </svg>
            <span>
              <span className="nv-fx-l">Focus Mode {focus ? "· ON" : ""}</span>
              <span className="nv-fx-d" style={{ display: "block" }}>Calmer layout, higher contrast, one step at a time</span>
            </span>
            <span className="nv-switch" />
          </button>
          <div className="nv-user">
            <div className="nv-avatar">A</div>
            <div><div className="nv-nm">Abad Morel</div><div className="nv-rl">Operator · Sales</div></div>
          </div>
          <div className="nv-online" role="status">
            <span className={`nv-online-dot${isOnline ? " on" : ""}`} />
            {isOnline ? "Online" : "Offline — showing synced data"}
          </div>
          <button
            className="nv-restart"
            onClick={runFieldSync}
            type="button"
            disabled={syncState === "syncing"}
            title="Pulls your assigned prospects and a fresh Sales Kit for each into this device, so you can review them with zero signal."
          >
            <svg viewBox="0 0 24 24"><path d="M17 2.1l4 4-4 4" /><path d="M3 12.2v-2a4 4 0 014-4h12.8" /><path d="M7 21.9l-4-4 4-4" /><path d="M21 11.8v2a4 4 0 01-4 4H4.2" /></svg>
            {syncState === "syncing" ? "Syncing…" : "Sync for the field"}
          </button>
          {syncSummary ? <div className="nv-sync-note">{syncSummary}</div> : null}
          {lastSyncedAt ? (
            <div className="nv-sync-note nv-sync-timestamp">Cached as of {new Date(lastSyncedAt).toLocaleString()}</div>
          ) : null}
          {outboxPending > 0 ? (
            <div className="nv-sync-note nv-outbox-pending" role="status">
              {outboxPending} change{outboxPending === 1 ? "" : "s"} waiting to sync
            </div>
          ) : null}
          <button
            className="nv-restart"
            style={presenting ? { borderColor: "var(--nv-accent)", color: "var(--nv-accent)" } : undefined}
            onClick={presenting ? stopPresenting : startPresenting}
            type="button"
            data-presenter-exit={presenting ? "true" : undefined}
          >
            <svg viewBox="0 0 24 24"><path d="M6 4l14 8-14 8V4z" /></svg>
            {presenting ? "Exit Presenter Mode" : "Start Presenter Mode"}
          </button>
          <button className="nv-restart" onClick={resetDemo} type="button">
            <svg viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 1 3 6.7" /><path d="M3 12V7M3 12h5" /></svg>
            Restart demo
          </button>
        </div>
      </aside>

      {presenting ? (
        <div className="nv-presenting" data-presenter-exit="true" role="status">
          <span className="dot" />
          Presenting · {presentIdx + 1}/{PRESENTER_SCRIPT.length} — click or press any key to advance
          <button data-presenter-exit="true" onClick={stopPresenting} type="button">Exit</button>
        </div>
      ) : null}

      <main>
        <div className="nv-top">
          <div><div className="nv-crumb">Sales Floor</div><div className="nv-title">Prospecting</div></div>
          <div className="nv-spacer" />
          <div className="nv-cmdk">
            <input
              value={businessType}
              onChange={(e) => setBusinessType(e.target.value)}
              placeholder="business type"
              aria-label="business type"
              style={{ background: "transparent", border: "none", outline: "none", color: "var(--nv-text)", width: 120 }}
            />
            <span style={{ color: "var(--nv-text3)" }}>in</span>
            <input
              value={locality}
              onChange={(e) => setLocality(e.target.value)}
              placeholder="city"
              aria-label="city"
              style={{ background: "transparent", border: "none", outline: "none", color: "var(--nv-text)", width: 80 }}
            />
            <kbd>⌘K</kbd>
          </div>
          <button className="nv-btn solid" onClick={runSearch} disabled={pending}>
            {pending ? "Searching…" : "＋ New Search"}
          </button>
        </div>

        <div className="nv-wrap">
          <div className="nv-hero">
            <svg className="nv-gauge" viewBox="0 0 120 120">
              <circle cx="60" cy="60" r="52" fill="none" stroke="var(--nv-track)" strokeWidth="10" />
              <circle cx="60" cy="60" r="52" fill="none" stroke="var(--nv-accent)" strokeWidth="10" strokeLinecap="round" strokeDasharray="326.7" strokeDashoffset={gaugeOffset} transform="rotate(-90 60 60)" />
              <g transform="rotate(324 60 60)"><line x1="60" y1="6" x2="60" y2="18" stroke="var(--nv-warn)" strokeWidth="2.5" /></g>
              <text x="60" y="58" textAnchor="middle" fontFamily="var(--nv-serif)" fontSize="30" fill="var(--nv-text)">{hero.score}</text>
              <text x="60" y="72" textAnchor="middle" fontSize="8" fill="var(--nv-text3)">/ 100</text>
              <text x="60" y="115" textAnchor="middle" fontSize="7" fill="var(--nv-warn)">GATE 93</text>
            </svg>
            <div className="nv-hc">
              <div className="k">Live prospect audit · {hero.name}</div>
              <div className="h">AI-Search Readiness <span className="nv-num">{hero.score}</span> / 100</div>
              {belowGate ? (
                <p>This clinic sits <span className="gate">below the 93-point publish gate</span> — effectively invisible to ChatGPT, Perplexity and Google AI Overviews. That gap is the sale. Measured live, never fabricated.</p>
              ) : (
                <p>This site <span style={{ color: "var(--nv-pos)" }}>clears the 93-point publish gate</span> — already legible to AI answer engines. Measured live, never fabricated.</p>
              )}
              <div className="win">
                <svg style={{ width: 16, height: 16, stroke: "var(--nv-pos)", strokeWidth: 1.8, fill: "none" }} viewBox="0 0 24 24"><path d="M4 14l5 5 11-13" /></svg>
                Our generated site clears the gate at <b>96</b> — a documented, defensible jump (Sales Kit's live illustrative example, freshly re-measured 2026-08-16).
              </div>
              {hero.preliminary ? (
                <div className="nv-prelim" role="note">
                  <svg style={{ width: 14, height: 14, stroke: "var(--nv-warn)", strokeWidth: 1.8, fill: "none", flex: "none" }} viewBox="0 0 24 24">
                    <circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16h.01" />
                  </svg>
                  <span>
                    Preliminary — the rubric's category weights (20/20/12/13/15/10/10) aren't yet
                    traced to a cited source or confidence interval. The score itself is real and
                    was independently re-verified (2026-08-16: a fresh test-suite run plus a
                    bit-for-bit spot re-score of 5 live businesses, both clean); it's the
                    weighting behind it that's still open.
                  </span>
                </div>
              ) : null}
            </div>
          </div>

          {showFix ? (
            <div className="nv-panel nv-fix">
              <h3><span className="dot" />The Fix · {hero.name}</h3>
              {hero.gaps && hero.gaps.length ? (
                <ul className="nv-fix-list">
                  {hero.gaps.map((g, i) => {
                    const p = parseGap(g);
                    return (
                      <li key={i}>
                        {hero.prospectId ? (
                          <input
                            type="checkbox"
                            className="nv-fix-check"
                            checked={selectedGapIndices.includes(i)}
                            onChange={() => toggleGapIndex(i)}
                            aria-label={`Highlight this gap in ${hero.name}'s Sales Kit`}
                          />
                        ) : null}
                        {p.category ? (
                          <>
                            <span className="nv-fix-cat">{p.category}</span>
                            <span className="nv-fix-pts">up to {p.points} pts</span>
                            <span className="nv-fix-desc">{p.description}</span>
                          </>
                        ) : (
                          <span className="nv-fix-desc">{p.description}</span>
                        )}
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="nv-fix-empty">Run an audit above to see this business's real gap list here.</p>
              )}

              {/* Phase 2, write-side offline: one note field, one gap picker
                  (the checkboxes above), nothing heavier — the Amaya-scoped
                  definition of "customize" both Brain Trust reviews used.
                  Gated on a real prospectId: only a saved, synced prospect
                  can be customized, matching the same "Audit first"/"save
                  a lead first" honesty this shell already applies elsewhere. */}
              {hero.prospectId ? (
                <div className="nv-customize">
                  <label htmlFor="nv-note" className="nv-customize-label">Note for this prospect</label>
                  <textarea
                    id="nv-note"
                    className="nv-customize-note"
                    value={noteDraft}
                    onChange={(e) => setNoteDraft(e.target.value)}
                    placeholder="e.g. Mentioned they just redid their site last year — lead with the schema gap, not the redesign pitch."
                    rows={3}
                  />
                  <button className="nv-btn" type="button" onClick={saveCustomizationOffline}>
                    {customizeSaved ? "Saved — queued to sync" : "Save (works offline)"}
                  </button>
                  <p className="nv-customize-hint">
                    Saves to this device immediately, even with zero signal. Syncs the next time you
                    press "Sync for the field" or reconnect.
                  </p>
                  {/* Pipeline slice 1: needs a real audit (hero.url) on top of
                      the saved-prospect gate this whole branch already sits
                      behind -- a lead saved without ever being audited has no
                      facts yet worth generating a site from. */}
                  {hero.url ? (
                    <div className="nv-pipeline">
                      <button
                        className="nv-btn"
                        type="button"
                        onClick={saveToPipelineAction}
                        disabled={savingToPipeline}
                      >
                        {savingToPipeline
                          ? "Saving to Pipeline…"
                          : pipelineResult?.ok
                          ? "Saved to Pipeline — save again"
                          : "Save to Pipeline"}
                      </button>
                      {pipelineResult ? (
                        pipelineResult.ok ? (
                          <p className="nv-customize-hint">
                            Saved. Generated site scored {pipelineResult.score ?? "—"}/100 and is now
                            persisted, not just shown in this session.
                          </p>
                        ) : (
                          <p className="nv-customize-hint">
                            {/* Known short reason codes (not-signed-in, timeout, ...) get the
                                friendly AUDIT_REASONS copy; a real gate-failure message from the
                                backend (e.g. "Audit scored 85; publish threshold is 93.") is
                                already a full sentence and shown as-is, not re-wrapped. */}
                            Didn't save: {AUDIT_REASONS[pipelineResult.reason] ? reasonToMessage(pipelineResult.reason) : pipelineResult.reason}
                            {pipelineResult.score != null ? ` (scored ${pipelineResult.score}/100)` : ""}
                            {pipelineResult.fixList && pipelineResult.fixList.length
                              ? ` — top gap: ${pipelineResult.fixList[0]}`
                              : ""}
                          </p>
                        )
                      ) : (
                        <p className="nv-customize-hint">
                          Generates a real site from this prospect's facts and persists it, so it
                          survives past this session instead of only living here.
                        </p>
                      )}
                    </div>
                  ) : null}
                </div>
              ) : hero.url ? (
                <div className="nv-customize">
                  <p className="nv-fix-empty">
                    Customizing a Sales Kit needs a saved prospect first.
                  </p>
                  <button className="nv-btn" type="button" onClick={saveLeadAsProspect} disabled={savingLead}>
                    {savingLead ? "Saving…" : `Save ${hero.name} as a lead`}
                  </button>
                  <p className="nv-customize-hint">
                    Saves this business to your prospect list so you can sync, customize, and revisit
                    it offline.
                  </p>
                </div>
              ) : (
                <p className="nv-fix-empty">
                  Customizing a Sales Kit needs a saved prospect. Sync for the field to load your
                  assigned prospects, then customize from there.
                </p>
              )}
            </div>
          ) : null}

          {actionError ? (
            <div className="nv-err" role="alert">
              <svg style={{ width: 16, height: 16, stroke: "currentColor", strokeWidth: 1.8, fill: "none", flex: "none" }} viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16h.01" />
              </svg>
              {actionError}
              <button onClick={() => setActionError(null)} type="button">Dismiss</button>
            </div>
          ) : null}

          <div className="nv-plans">
            {pricingTiers.map((tier) => (
              <div key={tier.name} className={tier.popular ? "nv-plan popular" : "nv-plan"}>
                {tier.popular ? <div className="nv-plan-badge">Most popular</div> : null}
                <div className="nv-plan-name">{tier.name}</div>
                <div className="nv-plan-price">
                  <span className="nv-num">${tier.price.toLocaleString()}</span>
                  <span className="nv-plan-per">/mo</span>
                </div>
                <div className="nv-plan-tag">{tier.tag}</div>
                <ul>
                  {tier.bullets.map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <p className="nv-plan-note">Illustrative pricing — pending final sign-off. Compared to <span className="nv-num">$78,400</span> for the equivalent agency scope (audit + site + report).</p>

          <div className="nv-panel">
            <h3>
              <span className="dot" />Discovered prospects
              <span
                style={{
                  marginLeft: "auto",
                  fontSize: 10,
                  letterSpacing: "1.5px",
                  textTransform: "uppercase",
                  color: live ? "var(--nv-pos)" : "var(--nv-text3)",
                  border: "1px solid",
                  borderColor: live ? "var(--nv-pos)" : "var(--nv-hair)",
                  borderRadius: 5,
                  padding: "2px 8px",
                }}
              >
                {live ? "Live" : "Sample data"}
              </span>
            </h3>
            <table>
              <thead><tr><th>Business</th><th>Locality</th><th>Readiness</th><th>Status</th><th>To confirm on the call</th><th>Report</th><th>Sales Kit</th></tr></thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={`${r.name}-${i}`}>
                    <td><span className="co">{r.name}</span></td>
                    <td>{r.locality}</td>
                    <td>
                      {r.readiness != null && r.id ? (
                        <button
                          className="nv-score nv-score-btn"
                          type="button"
                          onClick={() => loadProspectIntoHero(i)}
                          title="View this prospect — works offline, no network call"
                        >
                          {r.readiness}
                        </button>
                      ) : r.readiness != null ? (
                        <span className="nv-score">{r.readiness}</span>
                      ) : r.url ? (
                        <button
                          className="nv-btn"
                          style={{ padding: "4px 12px", fontSize: 11 }}
                          onClick={() => auditRow(i)}
                          disabled={auditingIdx === i}
                        >
                          {auditingIdx === i ? "Auditing…" : "Audit"}
                        </button>
                      ) : (
                        <span className="nv-score">—</span>
                      )}
                    </td>
                    <td><span className="nv-pill inc">{r.status}</span></td>
                    <td>{r.confirm}</td>
                    <td>
                      {r.url ? (
                        <a
                          href={`/nova/report?url=${encodeURIComponent(r.url)}&client_name=${encodeURIComponent(r.name)}`}
                          target="_blank"
                          rel="noreferrer"
                          style={{ color: "var(--nv-accent)", fontWeight: 600 }}
                        >
                          Open
                        </a>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      {r.url && r.readiness != null ? (
                        <a
                          href={`/nova/kit?url=${encodeURIComponent(r.url)}&business_name=${encodeURIComponent(r.name)}`}
                          target="_blank"
                          rel="noreferrer"
                          style={{ color: "var(--nv-accent)", fontWeight: 600 }}
                        >
                          Open
                        </a>
                      ) : (
                        <span style={{ color: "var(--nv-text3)" }}>Audit first</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}
