import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { NextRequest } from "next/server";

/*
 * Site Generator, wired to the real, already-built backend it had never been
 * connected to (site_engine.generate_site() -> a real, compliance-gated,
 * 48h-expiring shareable preview link). Same session-auth proxy pattern as
 * app/nova/report/route.ts and app/nova/kit/route.ts.
 *
 * 2026-08-16: first wired to POST /sales/site-generator-example, which always
 * reuses sales_kit.py's ILLUSTRATIVE_HBOT_EXAMPLE server-side -- a reliable,
 * zero-input fixture, but that meant clicking "Site Generator" right after
 * auditing a real prospect opened someone else's site, the demo's most
 * visible "wait, that's not the business we just looked at" moment.
 *
 * 2026-08-20: NovaShell.tsx's siteGeneratorHref now appends the currently
 * audited prospect's real facts as query params whenever hero.url is set
 * (a real auditRow() call, never the fixed opening state or a Presenter Mode
 * step). When those params are present, POST them to /sales/preview instead
 * -- the same real site_engine.generate_site() -> real audit -> compliance-
 * gated preview pipeline, just carrying this prospect's own facts rather
 * than the fixture. No real prospect in context (a bare click, or a
 * Presenter Mode step) falls back to /sales/site-generator-example exactly
 * as before -- still a guaranteed-good, zero-input demo path.
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

export async function GET(req: NextRequest) {
  const supaUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supaKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!supaUrl || !supaKey) return notice("Backend not configured for this environment.");

  const cookieStore = cookies();
  const supabase = createServerClient(supaUrl, supaKey, {
    cookies: { getAll: () => cookieStore.getAll(), setAll: () => {} },
  });
  const { data, error } = await supabase.auth.getSession();
  if (error || !data.session) return notice("Please sign in to run the Site Generator.", 401);

  const params = req.nextUrl.searchParams;
  const businessName = params.get("businessName");

  // Real prospect in context -> real facts through /sales/preview. Every
  // field below is optional server-side (BusinessFactsReq); only send what
  // the query string actually carries rather than inventing blanks.
  const endpoint = businessName ? "/sales/preview" : "/sales/site-generator-example";
  const body: Record<string, unknown> | undefined = businessName
    ? (() => {
        const facts: Record<string, unknown> = { business_name: businessName };
        const str = (key: string, field: string) => {
          const v = params.get(key);
          if (v) facts[field] = v;
        };
        str("domain", "domain");
        str("street", "street");
        str("locality", "locality");
        str("region", "region");
        str("postalCode", "postal_code");
        str("telephone", "telephone");
        const ratingValue = params.get("ratingValue");
        if (ratingValue) {
          facts.rating = { value: Number(ratingValue), count: Number(params.get("ratingCount") ?? 0) };
        }
        return facts;
      })()
    : undefined;

  try {
    const res = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${data.session.access_token}`,
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
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
