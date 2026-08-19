// frontend/lib/supabaseClient.ts
//
// Browser Supabase client for GEO Suite.
// You create one client per browser session and reuse it everywhere.
//
// 2026-08-19: uses @supabase/ssr's createBrowserClient, not plain
// @supabase/supabase-js createClient. The repo this was split out of
// (Stag-GEO-Platform) used plain createClient here, which persists the
// session to localStorage only -- invisible to any server-side code that
// reads cookies. That mismatch caused a real, confirmed-live bug: Nova's
// own Server Actions (app/nova/actions.ts, which read the session via
// next/headers cookies() + createServerClient for its Prospecting/Audit/
// Save-Lead calls) could never find a session, so live discovery silently
// always fell back to sample data regardless of sign-in state, and a
// similar bug in a different route crashed outright. createBrowserClient
// writes the session to both cookies and localStorage, so this one client
// serves client-side reads (getAccessToken below) and server-side cookie
// reads (Nova's Server Actions) correctly without patching each one.
//
// Environment variables (set in .env.local, never committed):
//   NEXT_PUBLIC_SUPABASE_URL       - your Supabase project URL
//   NEXT_PUBLIC_SUPABASE_ANON_KEY  - your Supabase anon public key
//
// The anon key is safe to expose to the browser. Row-level security in
// this project's Supabase migrations scopes every query to the caller's
// client membership. Never place the service-role key in this file or
// anywhere in frontend code.

import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";

// Fall back to placeholders when the keys are absent so the production
// build never blocks on live keys during static prerender. At runtime the
// real values come from the deploy environment; with a placeholder the
// client still constructs and only network calls fail, which the UI
// handles gracefully.
const supabaseUrl =
  process.env.NEXT_PUBLIC_SUPABASE_URL &&
  process.env.NEXT_PUBLIC_SUPABASE_URL.trim().length > 0
    ? process.env.NEXT_PUBLIC_SUPABASE_URL
    : "https://placeholder-project.supabase.co";
const supabaseAnonKey =
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY &&
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY.trim().length > 0
    ? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
    : "placeholder-anon-key";

// Module-level singleton. Next.js may evaluate this module more than once
// during development hot reloads, so you cache the client on globalThis to
// avoid creating duplicate auth listeners.
const globalForSupabase = globalThis as unknown as {
  supabase: SupabaseClient | undefined;
};

export const supabase: SupabaseClient =
  globalForSupabase.supabase ?? createBrowserClient(supabaseUrl, supabaseAnonKey);

if (process.env.NODE_ENV !== "production") {
  globalForSupabase.supabase = supabase;
}

/**
 * Returns the current access token, or null when no one is signed in.
 * frontend/lib/api.ts calls this to attach the bearer token on every
 * request to the FastAPI backend.
 */
export async function getAccessToken(): Promise<string | null> {
  const { data, error } = await supabase.auth.getSession();
  if (error || !data.session) {
    return null;
  }
  return data.session.access_token;
}

/**
 * Returns the signed-in user, or null when no session exists.
 * Components use this for display only. Authorization decisions live in
 * database RLS policies and in backend/app/core/permissions.py, never in
 * the browser.
 */
export async function getCurrentUser() {
  const { data, error } = await supabase.auth.getUser();
  if (error || !data.user) {
    return null;
  }
  return data.user;
}

/**
 * Signs the user out and clears the stored session.
 * Callers handle navigation after this resolves.
 */
export async function signOut(): Promise<void> {
  await supabase.auth.signOut();
}

export default supabase;