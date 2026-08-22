"use client";

/*
 * Account settings, Slice 2b, step 1 (2026-08-22): detect and show ONLY
 * the "first confirmation link clicked" state -- per the operator's
 * explicit "thin everything out" mandate, this is deliberately not the
 * whole confirmation-landing feature. Real, verified Supabase behavior
 * (github.com/orgs/supabase/discussions/42520, community-documented, not
 * an official stable contract): clicking the FIRST of the two required
 * confirmation links (Secure email change is on for this project) lands
 * back here with a `message` query param and no `code` param -- the
 * session and email are untouched at this point, nothing to detect via
 * auth state, just a URL param to read. The SECOND link's landing
 * (a `code` param, the point where the email change actually completes)
 * is a separate, later step -- it needs its own research into whether
 * @supabase/ssr's browser client auto-exchanges that code or whether this
 * page has to do it explicitly, not assumed here.
 *
 * Rendered ABOVE AccountGate, not instead of it -- the user's session is
 * completely unaffected by clicking only the first link, so there's no
 * reason to hide the rest of the page.
 */

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

function Banner() {
  const searchParams = useSearchParams();
  const message = searchParams.get("message");

  if (!message) return null;

  return (
    <div
      role="status"
      style={{
        padding: 16,
        borderRadius: 10,
        background: "var(--nv-surface)",
        border: "1px solid var(--nv-pos)",
        color: "var(--nv-text2)",
        fontSize: 14,
        marginBottom: 28,
      }}
    >
      {decodeURIComponent(message.replace(/\+/g, " "))}
    </div>
  );
}

export function EmailChangeStatusBanner() {
  return (
    <Suspense fallback={null}>
      <Banner />
    </Suspense>
  );
}
