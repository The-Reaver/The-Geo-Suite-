import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { NextRequest } from "next/server";

/*
 * Site Generator, wired to the real, already-built backend it had never been
 * connected to (POST /sales/site-generator-example -> site_engine.generate_site()
 * -> a real, compliance-gated, 48h-expiring shareable preview link). Same
 * session-auth proxy pattern as app/nova/report/route.ts and app/nova/kit/route.ts.
 *
 * The backend route reuses sales_kit.py's ILLUSTRATIVE_HBOT_EXAMPLE (the same
 * fixture the Sales Kit's "after" example uses, server-side — not sent from
 * here) so both demo surfaces show one consistent real score, not two
 * different numbers for the same claim. This route just triggers it and
 * redirects to the real generated site, so "Open" shows the actual output,
 * not a summary page about it.
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

function notice(msg: string, status = 200) {
  return new Response(
    `<!doctype html><meta charset="utf-8"/><body style="font-family:system-ui;padding:40px;color:#333">
     <h2>Site Generator unavailable</h2><p>${msg}</p></body>`,
    { status, headers: { "Content-Type": "text/html; charset=utf-8" } }
  );
}

export async function GET(_req: NextRequest) {
  const supaUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supaKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!supaUrl || !supaKey) return notice("Backend not configured for this environment.");

  const cookieStore = cookies();
  const supabase = createServerClient(supaUrl, supaKey, {
    cookies: { getAll: () => cookieStore.getAll(), setAll: () => {} },
  });
  const { data, error } = await supabase.auth.getSession();
  if (error || !data.session) return notice("Please sign in to run the Site Generator.", 401);

  try {
    const res = await fetch(`${API_BASE_URL}/sales/site-generator-example`, {
      method: "POST",
      headers: { Authorization: `Bearer ${data.session.access_token}` },
      cache: "no-store",
    });
    if (!res.ok) {
      const detail = await res.text();
      return notice(`Could not generate the site (backend ${res.status}): ${detail}`, 502);
    }
    const result = await res.json();
    if (!result?.preview_url) return notice("Generator ran but returned no preview link.", 502);
    return Response.redirect(result.preview_url, 302);
  } catch {
    return notice("The Site Generator service is unreachable right now.", 502);
  }
}
