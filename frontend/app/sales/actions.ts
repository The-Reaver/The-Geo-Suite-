"use client";

import { z } from "zod";
import { supabase } from "@/lib/supabaseClient";

/*
 * 2026-08-16: fixed a real, confirmed auth bug (SITE_GENERATOR_FINDINGS_2026-08-16.md
 * item 4) -- /sales/audit-current, /sales/preview, and /sales/lead all sit behind
 * require_sales_agent/require_owner (FastAPI's HTTPBearer, auto_error=True), and
 * every fetch call here previously sent only Content-Type, no Authorization.
 *
 * 2026-08-19: that first fix pulled the session server-side via a Next.js
 * Server Action (@supabase/ssr's createServerClient reading next/headers
 * cookies()), "the same pattern already proven in app/nova/actions.ts" --
 * except that pattern was never actually proven against a real session. This
 * app's session lives in browser localStorage (lib/supabaseClient.ts), not
 * cookies, so a server-side cookie read always finds nothing and every call
 * here always returned "Your session has expired," regardless of the real
 * signed-in state. Rewritten to plain client-side calls (this file is only
 * ever invoked from SalesWizard.tsx, a "use client" component), matching the
 * pattern lib/api.ts and lib/api/toggles.ts already use correctly.
 */
async function getBearerToken(): Promise<{ token: string } | { error: string }> {
  try {
    const { data, error } = await supabase.auth.getSession();
    if (error || !data.session) {
      return { error: "Your session has expired. Please sign in again to run a live audit." };
    }
    return { token: data.session.access_token };
  } catch {
    return { error: "Could not verify your session. Please sign in again." };
  }
}

// 2026-08-16, SITE_GENERATOR_FINDINGS_2026-08-16.md item 3 (the "cheap half"):
// the backend's BusinessFactsReq (backend/app/routers/sales_preview.py) already
// accepts subtype/street/region/postal_code/telephone -- this form just never
// collected or sent them, so a real prospect scored lower than the generator
// is capable of, from missing input, not generator quality. All five stay
// optional here: filling them in improves the proposed score, but nothing
// about the fast three-field pitch flow should get slower or harder to submit.
const auditSchema = z.object({
  businessName: z.string().min(1, "Business Name is required"),
  city: z.string().min(1, "City is required"),
  websiteUrl: z.string().url("Must be a valid URL"),
  subtype: z.string().optional(),
  street: z.string().optional(),
  region: z.string().optional(),
  postalCode: z.string().optional(),
  telephone: z.string().optional(),
});

export async function auditCurrentSite(formData: FormData) {
  const data = Object.fromEntries(formData.entries());
  const parsed = auditSchema.safeParse(data);
  if (!parsed.success) {
    return { error: "Invalid form data", issues: parsed.error.issues };
  }

  // 2026-08-19: this file moved to a plain client-side module (see the
  // getBearerToken comment above), so the bare, non-NEXT_PUBLIC_ "API_URL"
  // this used is a server-only env var -- undefined in the browser, always
  // silently falling back to localhost in production. Matches the
  // NEXT_PUBLIC_API_BASE_URL convention every other client-side API module
  // in this app already uses.
  const apiUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    "http://localhost:8000";

  const auth = await getBearerToken();
  if ("error" in auth) return { error: auth.error };

  // Real audit of the prospect's current site. No fallback score on
  // failure, ever — a failed or unreachable call surfaces as an explicit
  // error so a rep never presents a fabricated number live.
  let auditRes: Response;
  try {
    auditRes = await fetch(`${apiUrl}/sales/audit-current`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${auth.token}`,
      },
      body: JSON.stringify({ url: parsed.data.websiteUrl }),
    });
  } catch {
    return { error: "Could not reach the audit service. Please try again in a moment." };
  }

  if (!auditRes.ok) {
    let detail = "";
    try {
      const body = await auditRes.json();
      detail = body?.detail ? ` (${body.detail})` : "";
    } catch {
      // response wasn't JSON, ignore
    }
    return { error: `Audit failed${detail}. Please check the URL and try again.` };
  }

  const auditJson = await auditRes.json();
  if (typeof auditJson.score !== "number") {
    return { error: "Audit service returned an unexpected response. Please try again." };
  }
  const currentScore = auditJson.score;

  // Real proposed-site preview and score, built from the actual business
  // facts. Field names below match the backend's BusinessFactsReq — the
  // previous version sent businessName/city/websiteUrl, which don't match
  // any field the backend accepts, so this call was silently failing
  // validation on every real attempt.
  let previewRes: Response;
  try {
    previewRes = await fetch(`${apiUrl}/sales/preview`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${auth.token}`,
      },
      body: JSON.stringify({
        business_name: parsed.data.businessName,
        locality: parsed.data.city,
        domain: parsed.data.websiteUrl,
        subtype: parsed.data.subtype || "",
        street: parsed.data.street || "",
        region: parsed.data.region || "",
        postal_code: parsed.data.postalCode || "",
        telephone: parsed.data.telephone || "",
      }),
    });
  } catch {
    return { error: "Could not reach the preview service. Please try again in a moment." };
  }
  // NOTE: /sales/preview still requires require_owner (owner/admin), not
  // require_sales_agent -- unlike audit-current/report/kit/lead, it was not
  // part of the 2026-08-16 Phase 0 widening (GEO_DEVELOPMENT_LOG.md, that
  // pass explicitly names audit-current/report/kit/lead, not preview). A
  // caller with only the sales_agent role will still 403 here even with a
  // valid token attached. Whether this wizard is meant to run under an
  // owner login only, or /preview should widen too, is a real open
  // question for the operator, not decided here.

  if (!previewRes.ok) {
    let detail = "";
    try {
      const body = await previewRes.json();
      detail = body?.detail ? ` (${body.detail})` : "";
    } catch {
      // response wasn't JSON, ignore
    }
    return { error: `Preview generation failed${detail}. Please try again.` };
  }

  const previewJson = await previewRes.json();
  // Backend returns preview_url (snake_case) and a real score, not the
  // previous hard-coded 96 or the mis-keyed previewJson.previewUrl (which
  // never existed on the real response, so previewUrl always fell back to
  // the placeholder before this fix).
  if (typeof previewJson.score !== "number" || !previewJson.preview_url) {
    return { error: "Preview service returned an unexpected response. Please try again." };
  }

  return {
    success: true,
    data: {
      currentScore,
      proposedScore: previewJson.score,
      previewUrl: previewJson.preview_url,
      ...parsed.data,
    },
  };
}

// Strict TCPA consent boolean check
const leadSchema = z.object({
  name: z.string().min(1, "Name is required"),
  email: z.string().email("Invalid email"),
  phone: z.string().min(10, "Phone required"),
  consent: z.boolean().refine(val => val === true, {
    message: "Consent is strictly required."
  }),
});

export async function submitLead(formData: FormData) {
  const data = Object.fromEntries(formData.entries());
  const consentValue = data.consent === "on" || data.consent === "true";

  // Mathematical failsafe for boolean check (is not True)
  if (consentValue !== true) {
    return { error: "You must check the consent box to proceed." };
  }

  const payload = { ...data, consent: consentValue };
  const parsed = leadSchema.safeParse(payload);

  if (!parsed.success) {
    return { error: "Invalid lead data", issues: parsed.error.issues };
  }

  // 2026-08-19: this file moved to a plain client-side module (see the
  // getBearerToken comment above), so the bare, non-NEXT_PUBLIC_ "API_URL"
  // this used is a server-only env var -- undefined in the browser, always
  // silently falling back to localhost in production. Matches the
  // NEXT_PUBLIC_API_BASE_URL convention every other client-side API module
  // in this app already uses.
  const apiUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    "http://localhost:8000";

  const auth = await getBearerToken();
  if ("error" in auth) return { error: auth.error };

  // No silent "graceful fallback" success on a failed save — a rep needs to
  // know if a captured lead didn't actually persist, not see a confirmation
  // screen for a lead that was never written.
  let res: Response;
  try {
    res = await fetch(`${apiUrl}/sales/lead`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${auth.token}`,
      },
      body: JSON.stringify(parsed.data),
    });
  } catch {
    return { error: "Could not reach the lead-capture service. Please try again in a moment." };
  }

  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = body?.detail ? ` (${body.detail})` : "";
    } catch {
      // response wasn't JSON, ignore
    }
    return { error: `Could not save this lead${detail}. Please try again.` };
  }

  return { success: true };
}
