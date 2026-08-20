"use server";

/*
 * Server-side fetch for the Compliance Library page (GET /compliance/library,
 * backend/app/routers/compliance.py). Same session-auth pattern as
 * app/nova/actions.ts's discoverProspects() -- reads the Supabase session
 * from cookies, calls the backend with the bearer token.
 *
 * 2026-08-20: replaces NovaShell.tsx's fake, hardcoded "3 pending" Compliance
 * Library nav badge with this page's real data.
 */

import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { fetchWithTimeout, isTimeoutError } from "../lib/fetchWithTimeout";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export type ComplianceSource = {
  law: string;
  citation: string;
  file: string;
  source_url: string | null;
  relevance: string;
  verification_status: string;
  note_count: number;
  sample_notes: string[];
};

export type ComplianceDomain = {
  domain: string;
  sources: ComplianceSource[];
};

export type ComplianceLibraryResult =
  | {
      live: true;
      domains: ComplianceDomain[];
      totalSources: number;
      totalDraftNotes: number;
      orphanedNotesCount: number;
    }
  | { live: false; reason: string };

export async function fetchComplianceLibrary(): Promise<ComplianceLibraryResult> {
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

    const res = await fetchWithTimeout(`${API_BASE_URL}/compliance/library`, {
      headers: { Authorization: `Bearer ${sessionData.session.access_token}` },
      cache: "no-store",
    });
    if (!res.ok) {
      return { live: false, reason: `backend-${res.status}` };
    }
    const data = await res.json();
    if (!Array.isArray(data?.domains)) {
      return { live: false, reason: "malformed-response" };
    }
    return {
      live: true,
      domains: data.domains,
      totalSources: data.total_sources ?? 0,
      totalDraftNotes: data.total_draft_notes ?? 0,
      orphanedNotesCount: data.orphaned_notes_count ?? 0,
    };
  } catch (err) {
    return { live: false, reason: isTimeoutError(err) ? "timeout" : "unreachable" };
  }
}
