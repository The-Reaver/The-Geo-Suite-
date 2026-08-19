"use client";

/*
 * Client-side (browser fetch, not a Next.js server action) calls to the
 * FastAPI backend, built specifically so their results can be written to
 * IndexedDB by the caller -- a Next.js server action's response never
 * reaches code that could persist it client-side. Backs the "Sync for the
 * field" action (NovaShell.tsx) per Phase 1 of
 * OFFLINE_ARCHITECTURE_BRAIN_TRUST_2026-08-16.md.
 *
 * Deliberately NOT routed through a service worker cache -- the data layer
 * here is explicit IndexedDB reads/writes in application code, not implicit
 * SW fetch interception, so a "cached as of" badge can always be shown
 * accurately and nothing about staleness is ever silent. nova-sw.js's job
 * is caching the app shell (JS/CSS) so the page can boot offline at all,
 * not caching this data.
 */

import { getBrowserAccessToken } from "./supabaseBrowser";
import type { CachedProspect, OutboxEntry } from "./offlineStore";
import { fetchWithTimeout, isTimeoutError } from "./fetchWithTimeout";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export type FieldSyncResult =
  | { ok: true; prospects: CachedProspect[]; kitsSynced: number; kitsFailed: number }
  | { ok: false; reason: string };

/** Fetch the caller's own assigned prospects directly from the browser. */
async function fetchMyProspects(token: string): Promise<CachedProspect[]> {
  const res = await fetchWithTimeout(`${API_BASE_URL}/sales/my-prospects`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`my-prospects returned ${res.status}`);
  const data = await res.json();
  const rows: any[] = Array.isArray(data?.prospects) ? data.prospects : [];
  const syncedAt = new Date().toISOString();
  return rows.map((r) => ({
    id: String(r.id),
    business_name: String(r.business_name ?? ""),
    contact_name: r.contact_name ?? null,
    contact_email: r.contact_email ?? null,
    city: r.city ?? null,
    current_score: typeof r.current_score === "number" ? r.current_score : null,
    agent_id: String(r.agent_id ?? ""),
    created_at: r.created_at,
    syncedAt,
  }));
}

/** Fetch and return one prospect's Sales Kit HTML, direct from the browser. */
async function fetchSalesKitHtml(token: string, url: string, businessName: string): Promise<string> {
  const res = await fetchWithTimeout(`${API_BASE_URL}/sales/kit`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ url, business_name: businessName }),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`sales/kit returned ${res.status}`);
  return res.text();
}

/**
 * The "Sync for the field" action: pull the agent's assigned prospects and
 * a fresh Sales Kit per prospect, and write all of it to IndexedDB. Manual,
 * explicit, agent-triggered -- never silent/automatic background sync, per
 * Celestina's finding C and E ("silent background sync that fails quietly
 * is worse than no offline support, because it produces false confidence").
 *
 * A per-prospect kit fetch failure does not abort the whole sync -- the
 * prospect list itself is the load-bearing piece; a missing kit for one
 * business is a partial, honestly-reported result, not a total failure.
 */
export async function syncForTheField(
  putProspects: (p: CachedProspect[]) => Promise<void>,
  putSalesKit: (k: { prospectId: string; url: string; businessName: string; html: string; syncedAt: string }) => Promise<void>,
  prospectUrls: Record<string, string> // prospect id -> the business's real URL, since `prospects` rows don't carry one today
): Promise<FieldSyncResult> {
  let token: string | null;
  try {
    token = await getBrowserAccessToken();
  } catch {
    // getSupabaseBrowserClient() throws synchronously when
    // NEXT_PUBLIC_SUPABASE_URL/ANON_KEY are missing -- an unconfigured
    // environment, not a network problem. Caught here so it degrades to an
    // honest reason instead of an unhandled rejection.
    return { ok: false, reason: "supabase-not-configured" };
  }
  if (!token) return { ok: false, reason: "not-signed-in" };

  let prospects: CachedProspect[];
  try {
    prospects = await fetchMyProspects(token);
  } catch (err) {
    // 2026-08-16, Phase 3: a timed-out prospect pull is a weak-signal story,
    // not a hard-unreachable one -- the agent should hear that distinction.
    return { ok: false, reason: isTimeoutError(err) ? "timeout" : "unreachable" };
  }

  await putProspects(prospects);

  let kitsSynced = 0;
  let kitsFailed = 0;
  const syncedAt = new Date().toISOString();
  for (const p of prospects) {
    const url = prospectUrls[p.id];
    if (!url) continue; // no known site for this prospect yet -- nothing to pre-render
    try {
      const html = await fetchSalesKitHtml(token, url, p.business_name);
      await putSalesKit({ prospectId: p.id, url, businessName: p.business_name, html, syncedAt });
      kitsSynced += 1;
    } catch {
      kitsFailed += 1;
    }
  }

  return { ok: true, prospects, kitsSynced, kitsFailed };
}

export type DrainResult =
  | { ok: true; synced: number; discardedStale: number; failed: number }
  | { ok: false; reason: string };

/**
 * Phase 2, write-side offline: send every queued customization edit to the
 * backend. Agent/reconnect-triggered, per Celestina's finding E — never
 * automatic silent background sync. Each entry is sent independently; one
 * failure doesn't block the rest, matching syncForTheField's own partial-
 * failure discipline. A "stale, discarded" response from the server (the
 * last-write-wins comparison losing) is treated as a completed sync, not a
 * failure — the outbox entry's job was to reach the server and be judged,
 * not to win.
 */
export async function drainOutbox(
  getAllOutboxEntries: () => Promise<OutboxEntry[]>,
  markSynced: (id: string) => Promise<void>,
  markFailed: (id: string, error: string) => Promise<void>
): Promise<DrainResult> {
  let token: string | null;
  try {
    token = await getBrowserAccessToken();
  } catch {
    return { ok: false, reason: "supabase-not-configured" };
  }
  if (!token) return { ok: false, reason: "not-signed-in" };

  const entries = await getAllOutboxEntries();
  const pending = entries.filter((e) => e.status === "pending" || e.status === "failed");

  let synced = 0;
  let discardedStale = 0;
  let failed = 0;

  for (const entry of pending) {
    try {
      const res = await fetchWithTimeout(`${API_BASE_URL}/sales/prospects/${entry.prospectId}/customize`, {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          note: entry.note,
          selected_gap_indices: entry.selectedGapIndices,
          client_timestamp: entry.clientTimestamp,
        }),
        cache: "no-store",
      });
      if (!res.ok) {
        await markFailed(entry.id, `backend-${res.status}`);
        failed += 1;
        continue;
      }
      const data = await res.json();
      await markSynced(entry.id); // reached the server either way — applied or honestly discarded as stale
      if (data?.applied) synced += 1;
      else discardedStale += 1;
    } catch (err) {
      // 2026-08-16, Phase 3: a customization that timed out mid-sync is a
      // weak-signal failure, worth retrying on a better connection -- a
      // distinct, honest story from "the backend is unreachable."
      await markFailed(entry.id, isTimeoutError(err) ? "timeout" : "unreachable");
      failed += 1;
    }
  }

  return { ok: true, synced, discardedStale, failed };
}
