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
 * Real link/redirect shapes Supabase's Secure Email Change actually sends
 * here (all now share this one emailRedirectTo):
 *   - First link clicked: `message` param, no `code` -- no session change
 *     yet, forwarded through unchanged to EmailChangeStatusBanner.tsx.
 *   - Second link clicked: `code` param -- exchanged for a real session,
 *     completing the change.
 *   - An expired or already-used link (the single most likely real
 *     failure -- links are single-use, 5-minute validity): no `code` at
 *     all, `error`/`error_code`/`error_description` instead. The
 *     original version of this route silently swallowed this exact case
 *     into a clean-looking redirect -- fixed, see supabaseErrorText below.
 *
 * A full Brain Trust review pass (Architect + Security + an independent
 * Opus reviewer, run blind to each other, 2026-08-22) found and this
 * commit fixes: a production-breaking origin bug (see realOrigin()), a
 * discarded-cookies bug on the error path, a swallowed-real-failure bug,
 * and an unhandled-throw path. See inline comments at each fix for the
 * specific finding it closes.
 *
 * 2026-08-22, Bug B (the operator's own real security expectation, raised
 * live while testing Bug A's fix): once the NEW session is confirmed
 * established here (the exchange above), revoke every OTHER active
 * session for this user via revokeOtherSessions() below (auth.signOut({
 * scope: 'others' })), called AFTER destination/pendingCookies are
 * already decided -- deliberately outside the exchange's own try/catch,
 * so it can never be mistaken for being covered by that catch; it owns
 * its own error handling entirely.
 *
 * Safety of this call verified directly against installed auth-js
 * source (node_modules/@supabase/auth-js), not assumed from public docs,
 * then adversarially re-verified by an independent Opus 5 review pass
 * (2026-08-22) that traced the actual @supabase/ssr cookie-adapter code
 * too, not just auth-js:
 *   - With scope 'others', GoTrueClient._signOut() calls only the admin
 *     revoke endpoint and explicitly skips removeCurrentSession() --
 *     the branch that would fire a SIGNED_OUT event and touch cookies.
 *   - Even the internal __loadSession() this still runs through can't
 *     reach a cookie write here: @supabase/ssr's storage adapter serves
 *     getItem from its own already-written in-memory cache (not a fresh
 *     cookie read), so the just-exchanged session reads back as fresh
 *     and never triggers a token-refresh write. True "under any sane
 *     configuration" (rules out only a pathological JWT expiry under 90s
 *     or major host/Supabase clock skew, both far outside anything this
 *     deploy runs).
 *   - Even if a write ever did fire, @supabase/ssr's setAll always
 *     carries the FULL accumulated cookie state, never a delta -- so
 *     pendingCookies (reassigned wholesale on every setAll call) is safe
 *     by construction, not by coincidence.
 *
 * Two real, load-bearing limitations, kept honest rather than implied
 * away by the code:
 *   - GoTrue's own signOut(scope:'others') treats a 401/403/404 from the
 *     revoke endpoint as a *successful* no-op (returns error: null) --
 *     an auth-level rejection of the revoke is structurally invisible to
 *     this route. Only network/5xx-class failures are ever observable
 *     here, which is what revokeOtherSessions()'s own logging can catch.
 *   - Revocation is not instantaneous for already-issued access tokens:
 *     scope:'others' invalidates refresh tokens/sessions server-side, but
 *     a stateless JWT another device is already holding keeps validating
 *     locally (signature + exp) until it naturally expires (up to the
 *     project's access-token lifetime, 1hr by default) -- only that
 *     device's own next getUser()/refresh call actually fails.
 *   - This route assumes it's only ever reached via an email-change
 *     confirmation link. If it's ever reused as the redirect target for
 *     a different Supabase flow (magic link, signup, OAuth), both the
 *     hardcoded success copy AND this session-revoke would fire wrongly
 *     -- don't repoint another flow's redirectTo/Site URL at this route
 *     without revisiting this whole file first.
 *   - The PKCE code-verifier's device-bound-cookie property is what
 *     keeps a prefetched/leaked confirmation link (e.g. an email client's
 *     link-scanner) from ever reaching this revoke at all -- the
 *     exchange fails first with a verifier-missing error. That's a
 *     structural property of PKCE, not something this file guarantees on
 *     its own; noted here because it's load-bearing for this feature's
 *     safety, not incidental.
 */

import { createServerClient, type CookieOptions } from "@supabase/ssr";
import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";

// 2026-08-22, Security-seat Brain Trust review, finding F1 (HIGH,
// confirmed by direct source-reading of Next 14.2.35's internals, not
// assumed): `new URL(request.url).origin` is NOT the real deployed
// domain in production. `next start` (this app's real Dockerfile CMD)
// has no -H/hostname flag, so Next's own request-URL reconstruction
// falls back to a placeholder base ("http://n") -- every redirect this
// route issued would have pointed at that broken host. This bug is
// specific to `next start`; `next dev` (used for all local testing this
// slice) behaves correctly, so no local test could have caught it --
// confirmed by tracing the actual difference in Next's own source, not
// discovered by symptom. request.nextUrl.origin does NOT fix this either
// (also verified directly): NextURL's .origin/.host getters read the
// same raw parsed URL, not the header-corrected hostname (that
// correction only feeds i18n locale detection internally). The real fix
// reads the actual proxy headers directly, bypassing Next's broken
// internal reconstruction entirely -- x-forwarded-host/-proto are the
// standard headers Railway's edge (and virtually every reverse proxy)
// sets on the real inbound request.
function realOrigin(request: NextRequest): string {
  const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host");
  const protocol = request.headers.get("x-forwarded-proto") ?? "https";
  if (host) return `${protocol}://${host}`;
  // Last-resort fallback only -- should be unreachable in both local dev
  // (curl/browser always send a real Host header) and production (Railway
  // always sets x-forwarded-host), kept only so this can never throw.
  return new URL(request.url).origin;
}

// searchParams.get() already fully decodes per the application/
// x-www-form-urlencoded spec (including turning `+` into a space) -- no
// manual decodeURIComponent()/`+`-replace belongs anywhere in this
// function. EmailChangeStatusBanner.tsx does both on top of an
// already-decoded value today, a real, separate bug (can throw on a
// stray `%` and double-un-escapes) -- fixed in its own follow-up commit,
// not folded in here since it's a different file/root cause.
function toAccount(origin: string, message?: string | null): URL {
  const url = new URL("/nova/account", origin);
  if (message) url.searchParams.set("message", message);
  return url;
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const origin = realOrigin(request);
  const code = searchParams.get("code");
  const message = searchParams.get("message");
  // 2026-08-22, independent-Opus review finding #3 (HIGH): Supabase's
  // real failure redirect for an expired/already-used confirmation link
  // (the single most likely real-world failure -- links are single-use,
  // 5-minute validity) carries NO `code` at all, only `error`/
  // `error_code`/`error_description`. The original version of this route
  // treated "no code" as automatically the harmless first-link case,
  // silently swallowing every real failure into a clean-looking redirect
  // with the old email still showing and zero explanation.
  const supabaseErrorText = searchParams.get("error_description") || searchParams.get("error");

  if (!code) {
    // A real failure (expired/used link) takes priority over the benign
    // first-link `message` case -- both could theoretically be present,
    // but a real error is the more important thing to surface.
    return NextResponse.redirect(toAccount(origin, supabaseErrorText ?? message));
  }

  const supaUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supaKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!supaUrl || !supaKey) {
    return NextResponse.redirect(toAccount(origin, "The live account system isn't configured in this environment."));
  }

  // 2026-08-22, Architect + Security seat findings (both independently
  // flagged the same real bug): the original version built `response`
  // BEFORE knowing whether the exchange would succeed, then abandoned it
  // for a fresh NextResponse.redirect() on any error path -- discarding
  // whatever cookies (including verifier cleanup) `setAll` had already
  // written. Fixed structurally: collect cookies-to-set into a plain
  // array, decide the final destination once the outcome is known, THEN
  // build exactly one response with both applied together.
  let pendingCookies: { name: string; value: string; options: CookieOptions }[] = [];
  const cookieStore = cookies();
  const supabase = createServerClient(supaUrl, supaKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet: { name: string; value: string; options: CookieOptions }[]) {
        pendingCookies = cookiesToSet;
      },
    },
  });

  let destination: URL;
  let exchangeSucceeded = false;
  try {
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    exchangeSucceeded = !error;
    destination = error
      ? toAccount(origin, error.message)
      // Real, positive confirmation the change actually completed --
      // closes the earlier open item of whether the live-updating
      // "Signed in as" line alone was enough feedback; this is the
      // explicit success message on top of it, at effectively no extra
      // cost since this exact code path was already being built.
      : toAccount(origin, "Your email address has been updated.");
  } catch {
    // 2026-08-22, independent-Opus finding #5: retrievePKCEVerifier runs
    // outside exchangeCodeForSession's own AuthError-catching try/catch
    // in installed auth-js -- a non-auth throw (e.g. a genuine network
    // failure) would otherwise escape this route entirely as an
    // unhandled exception, producing a raw Next.js 500 on an auth URL
    // instead of a real, actionable message.
    destination = toAccount(origin, "Something went wrong confirming your email change. Try the link again, or request a new change.");
  }

  if (exchangeSucceeded) {
    await revokeOtherSessions(supabase);
  }

  const response = NextResponse.redirect(destination);
  pendingCookies.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
  return response;
}

// Bug B fix -- see the file header comment for the full safety analysis
// (why this can't disturb pendingCookies) and the two real, documented
// limitations it can't see around. Deliberately its own function, called
// after `destination` is already decided, so it can never be mistaken
// for being covered by the exchange's own try/catch above.
//
// 2026-08-22, independent-Opus review finding #1 (REAL BUG, now fixed):
// the first version of this fix only wrapped the call in try/catch and
// discarded the resolved `{ error }` -- but GoTrue's signOut() catches
// and RETURNS AuthError instances rather than throwing them, and that
// includes AuthRetryableFetchError (Supabase down/network failure/5xx),
// so the realistic failure modes were silently discarded with no log at
// all, not even the console.error the old code implied would fire.
//
// 2026-08-22, independent-Opus review finding #7 (REAL BUG, now fixed):
// the underlying GoTrue fetch call carries no timeout/AbortSignal, so an
// unbounded await here could hold this route's redirect open for
// minutes on a hung Supabase call, for a step this route itself treats
// as non-fatal. Bounded with a 3s race; the underlying call is left to
// resolve/reject on its own afterward (its result is discarded either
// way, and the rejection path is pre-caught below so it can't become an
// unhandled promise rejection in the server process).
async function revokeOtherSessions(supabase: ReturnType<typeof createServerClient>): Promise<void> {
  const revokeCall = supabase.auth
    .signOut({ scope: "others" })
    .catch((err: unknown) => ({ error: err instanceof Error ? err : new Error(String(err)) }));

  const timedOut = new Promise<{ error: Error }>((resolve) => {
    setTimeout(() => resolve({ error: new Error("revoke call did not resolve within 3s") }), 3000);
  });

  const { error } = await Promise.race([revokeCall, timedOut]);
  if (error) {
    // Review finding #2: GoTrue's own signOut(scope:'others') treats a
    // 401/403/404 from the revoke endpoint as a *successful* no-op
    // (returns error: null) -- an auth-level rejection is structurally
    // invisible to this route. This log can only ever catch network/5xx/
    // timeout-class failures, never confirm the revoke actually reached
    // and was accepted by Supabase.
    console.error("auth/confirm: revoke of other sessions did not complete cleanly:", error.message);
  }
}
