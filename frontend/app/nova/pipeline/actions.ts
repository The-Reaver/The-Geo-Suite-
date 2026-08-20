"use server";

/*
 * Server-side fetch for the Pipeline list page (GET /sites/pipeline,
 * backend/app/routers/sites.py). Same session-auth pattern as
 * app/nova/compliance/actions.ts's fetchComplianceLibrary().
 *
 * 2026-08-20, Pipeline slice 2: replaces NovaShell.tsx's honest "Soon"
 * Pipeline nav stub with this page's real data -- every prospect actually
 * persisted via the "Save to Pipeline" button (slice 1), not the
 * ephemeral demo state Nova otherwise shows.
 */

import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { fetchWithTimeout, isTimeoutError } from "../lib/fetchWithTimeout";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export type PipelineSite = {
  site_id: string;
  business_name: string | null;
  city: string | null;
  score: number | null;
  passed: boolean | null;
  run_at: string | null;
};

export type PipelineListResult =
  | { live: true; sites: PipelineSite[] }
  | { live: false; reason: string };

export async function fetchPipelineList(): Promise<PipelineListResult> {
  const supaUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supaKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!supaUrl || !supaKey) {
    return { live: false, reason: "supabase-not-configured" };
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
      return { live: false, reason: "not-signed-in" };
    }

    const res = await fetchWithTimeout(`${API_BASE_URL}/sites/pipeline`, {
      headers: { Authorization: `Bearer ${sessionData.session.access_token}` },
      cache: "no-store",
    });
    if (!res.ok) {
      return { live: false, reason: `backend-${res.status}` };
    }
    const data = await res.json();
    if (!Array.isArray(data?.sites)) {
      return { live: false, reason: "malformed-response" };
    }
    return { live: true, sites: data.sites };
  } catch (err) {
    return { live: false, reason: isTimeoutError(err) ? "timeout" : "unreachable" };
  }
}
