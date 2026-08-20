"use server";

/*
 * Live wiring for the Nova Prospecting panel. Calls the real backend Prospecting
 * service (POST /prospecting/discover, built 2026-08-08) with the operator's
 * Supabase session token, following the same auth pattern as
 * app/dashboard/geo/actions.ts. Returns UI-ready rows.
 *
 * Honesty: discovery yields only discoverable facts, so a fresh candidate has no
 * audit readiness score yet (readiness comes from the audit engine, a separate
 * step) — readiness is returned as null, never invented. When the live source is
 * unconfigured/unauthorized/unreachable, we return { live: false } and the shell
 * shows a clearly-labeled sample, matching the demo-data honesty precedent.
 */

import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { fetchWithTimeout, isTimeoutError } from "./lib/fetchWithTimeout";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export type ProspectRow = {
  name: string;
  locality: string;
  readiness: number | null;
  status: string;
  confirm: string;
  url: string; // the prospect's site, used to run a live audit; "" when unknown
  // 2026-08-16, Phase 2: the real prospects.id, present only for a row
  // sourced from a saved lead (synced or cached) -- absent for a
  // discovered-but-not-yet-saved Prospecting search result or the sample
  // rows. Customization (the note/gap picker) needs a real id to attach to.
  id?: string;
  // 2026-08-20: the backend's /prospecting/discover response already
  // carries these (prospect_source.py's "discovered" dict) -- they were
  // being fetched and dropped. Needed to send Site Generator this
  // prospect's real facts instead of always the illustrative fixture, the
  // same class of thrown-away-real-data gap "The Fix" had. Every field
  // stays optional and honestly absent when a directory pull genuinely
  // can't know it (e.g. faqs/same_as never come from Places-style
  // discovery) -- never fabricated to fill a gap.
  region?: string;
  street?: string;
  postalCode?: string;
  telephone?: string;
  domain?: string;
  ratingValue?: number;
  ratingCount?: number;
  // 2026-08-20, Pipeline slice 1: prospect_source.py already computes this
  // per candidate (normalize_place()'s inferred_practice_type, from the
  // discovered listing's own categories) and discover_and_rank() already
  // returns it -- it was being fetched and dropped, same class of gap the
  // other fields on this type were added to close. Explicitly "inferred,"
  // not confirmed -- may be "" when the source has no matching category.
  // Needed for Save to Pipeline: BusinessFacts.subtype is what selects the
  // generated site's schema.org @type, palette, and typography.
  businessType?: string;
};

export type DiscoverResult = {
  live: boolean;
  reason: string;
  rows: ProspectRow[];
};

export type DiscoverQuery = {
  business_type: string;
  locality?: string;
  region?: string;
  limit?: number;
};

export async function discoverProspects(query: DiscoverQuery): Promise<DiscoverResult> {
  // No Supabase env → cannot authenticate; fall back honestly.
  const supaUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supaKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!supaUrl || !supaKey) {
    return { live: false, reason: "supabase-not-configured", rows: [] };
  }

  try {
    const cookieStore = cookies();
    const supabase = createServerClient(supaUrl, supaKey, {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll() {
          /* read-only in this action */
        },
      },
    });

    const { data: sessionData, error } = await supabase.auth.getSession();
    if (error || !sessionData.session) {
      return { live: false, reason: "not-signed-in", rows: [] };
    }

    const res = await fetchWithTimeout(`${API_BASE_URL}/prospecting/discover`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${sessionData.session.access_token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        business_type: query.business_type,
        locality: query.locality ?? "",
        region: query.region ?? "",
        limit: query.limit ?? 20,
      }),
      cache: "no-store",
    });

    if (!res.ok) {
      return { live: false, reason: `backend-${res.status}`, rows: [] };
    }

    const data = await res.json();
    const candidates: any[] = Array.isArray(data?.candidates) ? data.candidates : [];

    // The live source is off until GEO_PLACES_API_KEY is set; that comes back as
    // status DISABLED with zero candidates. Treat "no candidates" as not-live so
    // the shell shows the labeled sample rather than an empty premium screen.
    if (candidates.length === 0) {
      return { live: false, reason: data?.status ?? "empty", rows: [] };
    }

    const rows: ProspectRow[] = candidates.map((c) => {
      const d = c?.discovered ?? {};
      const needs: string[] = Array.isArray(c?.needs_confirmation) ? c.needs_confirmation : [];
      const tier = c?.score?.tier ?? "INCOMPLETE";
      const domain = String(d.domain ?? "").trim();
      const website = String(d.website ?? "").trim();
      const url = domain ? `https://${domain}` : website;
      // The Places-style source is provider-agnostic (prospect_source.py's own
      // docstring) and unconfigured in every environment this was built
      // against, so "rating" here has never been exercised against a real
      // provider response -- handle both a {value, count} object (this
      // codebase's own Rating shape) and a bare number defensively, rather
      // than assuming one and silently dropping the other.
      const rating = d.rating;
      const ratingValue =
        typeof rating === "number" ? rating : typeof rating?.value === "number" ? rating.value : undefined;
      const ratingCount = typeof rating?.count === "number" ? rating.count : undefined;
      return {
        name: String(d.name ?? "Unknown"),
        locality: String(d.locality ?? ""),
        readiness: null, // not audited yet — never fabricated
        status: tier === "INCOMPLETE" ? "Incomplete" : String(tier),
        confirm: needs.length ? needs.join(" · ") : "—",
        url,
        region: String(d.region ?? "") || undefined,
        street: String(d.street ?? "") || undefined,
        postalCode: String(d.postal_code ?? "") || undefined,
        telephone: String(d.telephone ?? "") || undefined,
        domain: domain || undefined,
        ratingValue,
        ratingCount,
        businessType: String(c?.inferred_practice_type ?? "") || undefined,
      };
    });

    return { live: true, reason: data?.status ?? "ok", rows };
  } catch (err) {
    // 2026-08-16, Phase 3: a timeout is a distinct, honest reason from a
    // hard connection failure -- "the connection is too slow right now" is
    // a different, more accurate story than "couldn't reach it at all",
    // and the two shouldn't be collapsed into the same generic message.
    return { live: false, reason: isTimeoutError(err) ? "timeout" : "unreachable", rows: [] };
  }
}

export type AuditResult = {
  ok: boolean;
  score: number | null;
  gaps: string[];
  reason: string;
  // 2026-08-16 operator ruling: client-facing "AI-Search Readiness" claims
  // pause until the rubric weight-sourcing gap is closed. Mirrors
  // rubric.AI_SEARCH_READINESS_CLAIMS_PAUSED from the backend.
  preliminary: boolean;
};

/**
 * Run a live audit of a prospect's site via the real backend (/sales/audit-current).
 * Returns the measured AI-Search readiness score and top gaps — never fabricated;
 * on any failure returns ok:false with a reason so the UI stays honest.
 */
export async function auditSite(url: string): Promise<AuditResult> {
  if (!url) return { ok: false, score: null, gaps: [], reason: "no-url", preliminary: true };
  const supaUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supaKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!supaUrl || !supaKey)
    return { ok: false, score: null, gaps: [], reason: "supabase-not-configured", preliminary: true };

  try {
    const cookieStore = cookies();
    const supabase = createServerClient(supaUrl, supaKey, {
      cookies: { getAll: () => cookieStore.getAll(), setAll: () => {} },
    });
    const { data: sessionData, error } = await supabase.auth.getSession();
    if (error || !sessionData.session)
      return { ok: false, score: null, gaps: [], reason: "not-signed-in", preliminary: true };

    const res = await fetchWithTimeout(`${API_BASE_URL}/sales/audit-current`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${sessionData.session.access_token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ url }),
      cache: "no-store",
    });
    if (!res.ok)
      return { ok: false, score: null, gaps: [], reason: `backend-${res.status}`, preliminary: true };
    const data = await res.json();
    return {
      ok: true,
      score: typeof data?.score === "number" ? data.score : null,
      gaps: Array.isArray(data?.top_gaps) ? data.top_gaps : [],
      reason: "ok",
      preliminary: data?.preliminary !== false,
    };
  } catch (err) {
    // 2026-08-16, Phase 3: same distinction as discoverProspects -- a live
    // audit that times out on a weak signal is not the same failure as one
    // that can't reach the backend at all, and the agent needs to know which.
    return {
      ok: false, score: null, gaps: [],
      reason: isTimeoutError(err) ? "timeout" : "unreachable",
      preliminary: true,
    };
  }
}

export type SaveLeadResult = { ok: boolean; prospectId: string | null; reason: string };

/**
 * Save the currently-audited business as this agent's own tracked prospect
 * (POST /sales/lead) -- the real, closing gap flagged in both Phase 1 and
 * Phase 2 of the offline PWA build: nothing in Nova has ever called this
 * already-built, already-tested backend route. Without it, "Sync for the
 * field" has nothing of the agent's own to sync -- Prospecting search
 * results are discovered, not saved, and only a saved prospect gets
 * synced/cached. Same honest-failure pattern as auditSite/discoverProspects:
 * never a silent success, always a real reason on any failure.
 */
export async function saveLead(params: {
  businessName: string;
  score: number;
  city?: string;
  websiteUrl?: string;
}): Promise<SaveLeadResult> {
  const supaUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supaKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!supaUrl || !supaKey)
    return { ok: false, prospectId: null, reason: "supabase-not-configured" };

  try {
    const cookieStore = cookies();
    const supabase = createServerClient(supaUrl, supaKey, {
      cookies: { getAll: () => cookieStore.getAll(), setAll: () => {} },
    });
    const { data: sessionData, error } = await supabase.auth.getSession();
    if (error || !sessionData.session)
      return { ok: false, prospectId: null, reason: "not-signed-in" };

    const res = await fetchWithTimeout(`${API_BASE_URL}/sales/lead`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${sessionData.session.access_token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        business_name: params.businessName,
        current_score: Math.round(params.score),
        city: params.city || "",
        website_url: params.websiteUrl || null,
      }),
      cache: "no-store",
    });
    if (!res.ok) return { ok: false, prospectId: null, reason: `backend-${res.status}` };
    const data = await res.json();
    // save_lead() returns {status: "success", lead: <inserted row>} -- the id
    // lives at data.lead.id, not top-level (confirmed by reading the route directly).
    const prospectId = typeof data?.lead?.id === "string" ? data.lead.id : null;
    if (!prospectId) return { ok: false, prospectId: null, reason: "no-id-returned" };
    return { ok: true, prospectId, reason: "ok" };
  } catch (err) {
    return { ok: false, prospectId: null, reason: isTimeoutError(err) ? "timeout" : "unreachable" };
  }
}

export type SaveToPipelineResult = {
  ok: boolean;
  score: number | null;
  passed: boolean;
  reason: string;
  fixList?: string[];
};

/**
 * Pipeline slice 1: persist the currently-audited prospect for real, via
 * POST /sites/{site_id}/audit (routers/sites.py -- generates a fresh site
 * from these facts, audits and compliance-gates it, and on a pass calls
 * site_pipeline.generate_and_store()). Reuses the prospect's own existing
 * id (minted by saveLead/POST /sales/lead) as site_id, rather than
 * inventing a separate identity for "the same business, but persisted."
 *
 * Every BusinessFacts field this sends comes from data Nova already
 * carries on hero -- nothing invented to fill a gap. A field the caller
 * doesn't have (e.g. businessType, when discovery had no matching
 * category) goes through as "", which the backend schema accepts; that
 * degrades the generated site's schema.org @type/theme selection but
 * never fabricates a fact.
 *
 * On failure this route can genuinely mean the generated site itself
 * didn't clear the publish gate (400, with a real score + fix_list) or
 * failed the compliance gate (400, with a real score + blocking list) --
 * both are surfaced, not collapsed into a generic error, same honesty
 * pattern as auditSite/saveLead above.
 */
export async function saveToPipeline(params: {
  siteId: string;
  businessName: string;
  businessType?: string;
  street?: string;
  locality?: string;
  region?: string;
  postalCode?: string;
  telephone?: string;
  domain?: string;
  ratingValue?: number;
  ratingCount?: number;
}): Promise<SaveToPipelineResult> {
  const supaUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supaKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!supaUrl || !supaKey)
    return { ok: false, score: null, passed: false, reason: "supabase-not-configured" };

  try {
    const cookieStore = cookies();
    const supabase = createServerClient(supaUrl, supaKey, {
      cookies: { getAll: () => cookieStore.getAll(), setAll: () => {} },
    });
    const { data: sessionData, error } = await supabase.auth.getSession();
    if (error || !sessionData.session)
      return { ok: false, score: null, passed: false, reason: "not-signed-in" };

    const facts: Record<string, unknown> = {
      business_name: params.businessName,
      subtype: params.businessType || "",
      street: params.street || "",
      locality: params.locality || "",
      region: params.region || "",
      postal_code: params.postalCode || "",
      telephone: params.telephone || "",
      domain: params.domain || "",
    };
    if (params.ratingValue != null) {
      facts.rating = { value: params.ratingValue, count: params.ratingCount ?? 0 };
    }

    const res = await fetchWithTimeout(`${API_BASE_URL}/sites/${params.siteId}/audit`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${sessionData.session.access_token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ facts }),
      cache: "no-store",
    });

    const data = await res.json().catch(() => null);

    if (!res.ok) {
      // sites.py raises HTTPException(detail={message, score, fix_list |
      // blocking}) on a real gate failure -- FastAPI nests that under
      // "detail", not top-level.
      const detail = data?.detail;
      return {
        ok: false,
        score: typeof detail?.score === "number" ? detail.score : null,
        passed: false,
        reason: detail?.message || `backend-${res.status}`,
        fixList: Array.isArray(detail?.fix_list) ? detail.fix_list : undefined,
      };
    }

    return {
      ok: true,
      score: typeof data?.score === "number" ? data.score : null,
      passed: Boolean(data?.passed),
      reason: "ok",
    };
  } catch (err) {
    return {
      ok: false, score: null, passed: false,
      reason: isTimeoutError(err) ? "timeout" : "unreachable",
    };
  }
}
