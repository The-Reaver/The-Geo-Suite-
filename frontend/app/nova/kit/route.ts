import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { NextRequest } from "next/server";

/*
 * Same-origin proxy for the Sales Kit, mirroring app/nova/report/route.ts.
 * The browser can't attach a Bearer token when opening a link, so this GET
 * handler reads the operator's Supabase session server-side, calls the
 * backend POST /sales/kit with the token, and streams the rendered HTML
 * back. NovaShell opens /nova/kit?url=...&business_name=... in a new tab.
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

function notice(msg: string, status = 200) {
  return new Response(
    `<!doctype html><meta charset="utf-8"/><body style="font-family:system-ui;padding:40px;color:#333">
     <h2>Sales Kit unavailable</h2><p>${msg}</p></body>`,
    { status, headers: { "Content-Type": "text/html; charset=utf-8" } }
  );
}

export async function GET(req: NextRequest) {
  const url = req.nextUrl.searchParams.get("url") ?? "";
  const businessName = req.nextUrl.searchParams.get("business_name") ?? "";
  if (!url) return notice("No site URL was provided for the Sales Kit.");

  const supaUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supaKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!supaUrl || !supaKey) return notice("Backend not configured for this environment.");

  const cookieStore = cookies();
  const supabase = createServerClient(supaUrl, supaKey, {
    cookies: { getAll: () => cookieStore.getAll(), setAll: () => {} },
  });
  const { data, error } = await supabase.auth.getSession();
  if (error || !data.session) return notice("Please sign in to generate a Sales Kit.", 401);

  try {
    const res = await fetch(`${API_BASE_URL}/sales/kit`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${data.session.access_token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ url, business_name: businessName }),
      cache: "no-store",
    });
    if (!res.ok) return notice(`Could not generate the Sales Kit (backend ${res.status}).`, 502);
    const html = await res.text();
    return new Response(html, { headers: { "Content-Type": "text/html; charset=utf-8" } });
  } catch {
    return notice("The Sales Kit service is unreachable right now.", 502);
  }
}
