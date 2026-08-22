/*
 * Server-side landing point for Supabase email-confirmation links,
 * replacing a direct `emailRedirectTo: /nova/account` that (confirmed via
 * a real Explore investigation, 2026-08-22) left an already-open
 * /nova/account tab permanently unaware of a change confirmed by clicking
 * links opened in a different browser tab/context (an email client) --
 * the operator hit this exact bug live, testing the real flow.
 *
 * @supabase/ssr's browser client stores sessions in COOKIES, and
 * Supabase's own documented pattern for that architecture is exactly
 * this: a Route Handler that exchanges the confirmation `code` server-side
 * via the server Supabase client and sets the resulting cookies on the
 * response, so the NEXT request to /nova/account (a real page load, not a
 * stale in-memory tab) already carries the updated session.
 *
 * Both real link shapes Supabase's Secure Email Change sends land here,
 * since both now share the same emailRedirectTo -- must handle both in
 * this one change or the already-shipped first-link flow (the `message`
 * param, EmailChangeStatusBanner.tsx) would break the moment the redirect
 * target changes:
 *   - First link clicked: `message` param, no `code` -- no session change
 *     yet, just forward the param through unchanged.
 *   - Second link clicked: `code` param -- exchange it for a real session,
 *     completing the change.
 *
 * Deliberately NOT in this route: revoking other active sessions
 * (auth.signOut({ scope: 'others' })) -- a separate, later slice (Bug B
 * in the plan file), kept apart from this route's own job of getting the
 * NEW session correctly established here first.
 */

import { createServerClient, type CookieOptions } from "@supabase/ssr";
import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const message = searchParams.get("message");

  if (!code) {
    // First link (message present) or an unrecognized visit -- no session
    // change to make. Forward `message` through unchanged if present.
    const url = new URL("/nova/account", origin);
    if (message) url.searchParams.set("message", message);
    return NextResponse.redirect(url);
  }

  const supaUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supaKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!supaUrl || !supaKey) {
    return NextResponse.redirect(new URL("/nova/account?error=not-configured", origin));
  }

  const cookieStore = cookies();
  const response = NextResponse.redirect(new URL("/nova/account", origin));
  const supabase = createServerClient(supaUrl, supaKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet: { name: string; value: string; options: CookieOptions }[]) {
        cookiesToSet.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
      },
    },
  });

  const { error } = await supabase.auth.exchangeCodeForSession(code);
  if (error) {
    return NextResponse.redirect(new URL(`/nova/account?error=${encodeURIComponent(error.message)}`, origin));
  }

  return response;
}
