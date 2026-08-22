"use client";

/*
 * Account settings, Slice 2a: START a change-email request. Deliberately
 * NOT the full feature -- per the operator's explicit "build it thinner"
 * instruction, this slice is just the form that calls
 * auth.updateUser({ email }) and shows an honest, generic "check both
 * inboxes" message. Handling the confirmation LINKS landing back on this
 * page (Slice 2b) is a separate slice on purpose: the real redirect-param
 * shape Supabase uses for that (a `message` param after the first
 * confirmation, a `code` param after the second) is confirmed real but
 * explicitly community-documented, not an official stable API contract
 * (github.com/orgs/supabase/discussions/42520) -- building against an
 * unofficial contract deserves its own isolated, carefully-tested slice,
 * not bundled into the "start the request" half which has no such risk.
 *
 * Two real prerequisites the operator confirmed done before this was
 * built, not assumed: "Secure email change" is ON for this project
 * (lhzxmvjwqllmnqecfxpm) -- meaning a change requires confirming from
 * BOTH the current and new address, not just the new one, closing a real
 * account-takeover path (a hijacked session alone can't silently redirect
 * ownership away from the real owner) -- and /nova/account is on
 * Supabase's redirect-URL allow-list (prod + localhost), the same
 * requirement /forgot-password already needed.
 */

import { useState } from "react";
import { getSupabaseBrowserClient } from "../lib/supabaseBrowser";
import { inputStyle } from "./AccountPasswordForm";

function isValidEmail(value: string): boolean {
  // Same permissive shape check already used nowhere else in this repo's
  // frontend (no existing helper to reuse) -- deliberately loose, since
  // Supabase's own server-side validation is the real authority here;
  // this only exists to catch an obviously-empty or malformed value
  // before spending a real network call on it.
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

export function AccountEmailForm({ currentEmail }: { currentEmail: string }) {
  const [newEmail, setNewEmail] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  function validate(): boolean {
    if (!isValidEmail(newEmail)) {
      setFieldError("Enter a valid email address.");
      return false;
    }
    if (newEmail.trim().toLowerCase() === currentEmail.trim().toLowerCase()) {
      setFieldError("That's already your current email.");
      return false;
    }
    setFieldError(null);
    return true;
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setDone(false);

    if (!validate()) return;

    setSubmitting(true);
    // 2026-08-22: redirects through the new server-side /auth/confirm
    // route instead of straight to /nova/account -- see that route's own
    // header for why (a real bug found live: an already-open account tab
    // never learns about a change confirmed in a different tab/context
    // without a server-side code exchange setting fresh cookies first).
    const { error } = await getSupabaseBrowserClient().auth.updateUser(
      { email: newEmail },
      { emailRedirectTo: `${window.location.origin}/auth/confirm` }
    );
    setSubmitting(false);

    if (error) {
      setFormError(error.message);
      return;
    }

    setNewEmail("");
    setDone(true);
  }

  return (
    <div>
      <h2 style={{ fontFamily: "var(--nv-serif)", fontSize: 20, color: "var(--nv-text)", margin: "0 0 16px" }}>
        Change email
      </h2>

      <form onSubmit={handleSubmit} noValidate style={{ display: "grid", gap: 16, maxWidth: 360 }}>
        {formError ? (
          <div role="alert" style={{ fontSize: 13, color: "var(--nv-warn)" }}>
            {formError}
          </div>
        ) : null}
        {done ? (
          <div role="status" style={{ fontSize: 13, color: "var(--nv-pos)" }}>
            Almost done — check both your current and new email inboxes. Each has a
            confirmation link, and both need to be clicked before the change takes effect.
            {" "}Open both links on this same device and browser — confirming from a
            different device can fail.
          </div>
        ) : null}

        <div>
          <label htmlFor="new-email" style={{ display: "block", fontSize: 12.5, color: "var(--nv-text2)", marginBottom: 6 }}>
            New email
          </label>
          <input
            id="new-email"
            name="email"
            type="email"
            autoComplete="email"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            disabled={submitting}
            aria-invalid={Boolean(fieldError)}
            aria-describedby={fieldError ? "email-field-error" : undefined}
            placeholder="you@example.com"
            style={inputStyle}
          />
          {fieldError ? (
            <p id="email-field-error" style={{ fontSize: 12, color: "var(--nv-warn)", marginTop: 6 }}>
              {fieldError}
            </p>
          ) : null}
        </div>

        <button type="submit" disabled={submitting} className="nv-btn solid" style={{ justifySelf: "start" }}>
          {submitting ? "Sending…" : "Send confirmation emails"}
        </button>
      </form>
    </div>
  );
}
