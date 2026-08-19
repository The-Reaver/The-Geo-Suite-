"use client";

/*
 * Browser-side Supabase client. Every existing Supabase call in this repo
 * (app/nova/actions.ts, app/nova's route.ts proxy files) runs server-side via
 * createServerClient, which is exactly why nothing here could be cached by
 * a service worker or persisted to IndexedDB before Phase 1 -- the fetch
 * never touched the browser at all. This client exists so "Sync for the
 * field" can call the FastAPI backend directly from the browser, the same
 * way any other client-side offline-capable app would, per Celestina's
 * proposal section B (OFFLINE_ARCHITECTURE_BRAIN_TRUST_2026-08-16.md).
 */

import { createBrowserClient } from "@supabase/ssr";

let client: ReturnType<typeof createBrowserClient> | null = null;

export function getSupabaseBrowserClient() {
  if (client) return client;
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anonKey) {
    throw new Error("Supabase is not configured in this environment (NEXT_PUBLIC_SUPABASE_URL/ANON_KEY missing).");
  }
  client = createBrowserClient(url, anonKey);
  return client;
}

/** The caller's own access token, or null if not signed in. Never throws on a missing session --
 * "not signed in" is a real, expected state this whole app already handles honestly elsewhere. */
export async function getBrowserAccessToken(): Promise<string | null> {
  const supabase = getSupabaseBrowserClient();
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}
