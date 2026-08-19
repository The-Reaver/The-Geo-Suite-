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
      return {
        name: String(d.name ?? "Unknown"),
        locality: String(d.locality ?? ""),
        readiness: null, // not audited yet — never fabricated
        status: tier === "INCOMPLETE" ? "Incomplete" : String(tier),
        confirm: needs.length ? needs.join(" · ") : "—",
        url,
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
