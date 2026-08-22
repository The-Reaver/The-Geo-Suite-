"use server";

/*
 * Server-side fetch for the Compliance Library page (GET /compliance/library,
 * backend/app/routers/compliance.py). Same session-auth pattern as
 * app/nova/actions.ts's discoverProspects() -- reads the Supabase session
 * from cookies, calls the backend with the bearer token.
 *
 * 2026-08-20: replaces NovaShell.tsx's fake, hardcoded "3 pending" Compliance
 * Library nav badge with this page's real data.
 *
 * 2026-08-22, mini-slice 3: adds the real ratify/reject actions
 * (POST /compliance/library/notes/{id}/ratify|reject, mini-slice 2) and
 * canReview -- whether the SIGNED-IN user can actually use them.
 *
 * canReview is derived from sessionData.session.user.app_metadata.role,
 * NOT from GET /auth/me. Verified directly before writing this: /auth/me
 * (frontend/lib/api.ts's CurrentUser, backed by
 * auth_service.py::get_profile()) reads role from the `memberships`
 * table -- a completely different, unsynced authorization system from
 * the JWT app_metadata.role claim core/permissions.py::require_lawyer
 * actually checks. Using /auth/me here would show ratify/reject controls
 * based on the wrong role system entirely. Supabase's JS client already
 * decodes app_metadata onto session.user for free -- no separate call or
 * manual JWT decode needed. This is display-only, same as every other
 * client-side role check in this app: the real enforcement is
 * require_lawyer on the backend, which runs regardless of what this page
 * shows or hides.
 */

import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { fetchWithTimeout, isTimeoutError } from "../lib/fetchWithTimeout";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export type NoteStatus = "draft" | "ratified" | "rejected";

export type ComplianceNote = {
  id: string;
  body: string;
  status: NoteStatus;
};

export type ComplianceSource = {
  law: string;
  citation: string;
  file: string;
  source_url: string | null;
  relevance: string;
  verification_status: string;
  note_count: number;
  sample_notes: ComplianceNote[];
};

export type ComplianceDetectionStatus = {
  has_check: boolean;
  wired_into_publish_gate: boolean;
  note: string;
};

export type ComplianceDomain = {
  domain: string;
  sources: ComplianceSource[];
  detection_status: ComplianceDetectionStatus | null;
};

export type ComplianceLibraryResult =
  | {
      live: true;
      domains: ComplianceDomain[];
      totalSources: number;
      totalDraftNotes: number;
      orphanedNotesCount: number;
      lawyerRatifiedCount: number;
      canReview: boolean;
    }
  | { live: false; reason: string };

async function getSupabaseSession() {
  const supaUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supaKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!supaUrl || !supaKey) return null;

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
  const { data, error } = await supabase.auth.getSession();
  if (error || !data.session) return null;
  return data.session;
}

export async function fetchComplianceLibrary(): Promise<ComplianceLibraryResult> {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY) {
    return { live: false, reason: "supabase-not-configured" };
  }

  try {
    const session = await getSupabaseSession();
    if (!session) {
      return { live: false, reason: "not-signed-in" };
    }

    const res = await fetchWithTimeout(`${API_BASE_URL}/compliance/library`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
      cache: "no-store",
    });
    if (!res.ok) {
      return { live: false, reason: `backend-${res.status}` };
    }
    const data = await res.json();
    if (!Array.isArray(data?.domains)) {
      return { live: false, reason: "malformed-response" };
    }
    const role = (session.user.app_metadata as Record<string, unknown> | undefined)?.role;
    return {
      live: true,
      domains: data.domains,
      totalSources: data.total_sources ?? 0,
      totalDraftNotes: data.total_draft_notes ?? 0,
      orphanedNotesCount: data.orphaned_notes_count ?? 0,
      lawyerRatifiedCount: data.lawyer_ratified_count ?? 0,
      canReview: role === "lawyer" || role === "owner" || role === "admin",
    };
  } catch (err) {
    return { live: false, reason: isTimeoutError(err) ? "timeout" : "unreachable" };
  }
}

export type ReviewNoteResult =
  | { ok: true; status: NoteStatus }
  | { ok: false; reason: string };

async function reviewNote(noteId: string, action: "ratify" | "reject", reason: string): Promise<ReviewNoteResult> {
  try {
    const session = await getSupabaseSession();
    if (!session) return { ok: false, reason: "not-signed-in" };

    const res = await fetchWithTimeout(`${API_BASE_URL}/compliance/library/notes/${encodeURIComponent(noteId)}/${action}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.access_token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ reason }),
      cache: "no-store",
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      const detail = data?.detail;
      return { ok: false, reason: typeof detail === "string" && detail ? detail : `backend-${res.status}` };
    }
    const data = await res.json();
    return { ok: true, status: data.status };
  } catch (err) {
    return { ok: false, reason: isTimeoutError(err) ? "timeout" : "unreachable" };
  }
}

export async function ratifyComplianceNote(noteId: string, reason: string): Promise<ReviewNoteResult> {
  return reviewNote(noteId, "ratify", reason);
}

export async function rejectComplianceNote(noteId: string, reason: string): Promise<ReviewNoteResult> {
  return reviewNote(noteId, "reject", reason);
}
