"use client";

/*
 * Account settings, Slice 1: change password. The entry point (NovaShell's
 * nv-user block) previously had nowhere to go -- there was no in-app path
 * to change a password at all, only the forgot-password flow for someone
 * already locked out. This reuses the exact form UX already proven in
 * ResetPasswordForm.tsx (8-char minimum, show/hide toggle, confirm-match
 * check) but through the Nova-specific browser client
 * (nova/lib/supabaseBrowser.ts), not the pre-Nova lib/supabaseClient.ts
 * singleton those auth pages use -- this page only ever renders inside an
 * already-authenticated Nova session, so it belongs on Nova's own client,
 * matching Sign Out's precedent.
 *
 * Real Supabase behavior, checked before building (not assumed): a valid
 * session is enough to call auth.updateUser({ password }) -- no current-
 * password re-entry required unless the project's dashboard has "Require
 * current password when changing password" turned on, which it isn't
 * today. If that's ever enabled, this call will start failing with a real,
 * surfaced error (Supabase returns a real error.message for it) rather
 * than silently succeeding -- not something this slice needs to guess at
 * or pre-empt.
 *
 * Email change (Slice 2) is deliberately NOT in this file -- it's a real
 * double opt-in flow needing an operator-side redirect-URL allow-list
 * addition first, sequenced as its own slice.
 */

import { useEffect, useState } from "react";
import { getSupabaseBrowserClient } from "../lib/supabaseBrowser";

const MIN_PASSWORD_LENGTH = 8;

type SessionState = "checking" | "signed-in" | "signed-out" | "unconfigured";

const inputStyle: React.CSSProperties = {
  width: "100%",
  fontSize: 14,
  padding: "10px 14px",
  borderRadius: 9,
  border: "1px solid var(--nv-line)",
  color: "var(--nv-text)",
  background: "var(--nv-surface)",
  outline: "none",
};

export function AccountPasswordForm() {
  const [sessionState, setSessionState] = useState<SessionState>("checking");
  const [email, setEmail] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    // 2026-08-22: getSupabaseBrowserClient() throws SYNCHRONOUSLY when
    // Supabase isn't configured (missing env vars) -- calling it directly
    // inside a .then() chain meant that throw happened before the promise
    // chain even existed, crashing the component instead of degrading
    // honestly, same class of case NovaShell's own auth effect already
    // guards against. Caught live via a real browser render before this
    // shipped, not assumed safe from the diff alone.
    if (!process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY) {
      setSessionState("unconfigured");
      return;
    }
    getSupabaseBrowserClient()
      .auth.getSession()
      .then(({ data }) => {
        if (data.session?.user?.email) {
          setEmail(data.session.user.email);
          setSessionState("signed-in");
        } else {
          setSessionState("signed-out");
        }
      })
      .catch(() => setSessionState("signed-out"));
  }, []);

  function validate(): boolean {
    if (password.length < MIN_PASSWORD_LENGTH) {
      setFieldError(`Use at least ${MIN_PASSWORD_LENGTH} characters.`);
      return false;
    }
    if (password !== confirmPassword) {
      setFieldError("Passwords don't match.");
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
    const { error } = await getSupabaseBrowserClient().auth.updateUser({ password });
    setSubmitting(false);

    if (error) {
      setFormError(error.message);
      return;
    }

    setPassword("");
    setConfirmPassword("");
    setDone(true);
  }

  if (sessionState === "checking") {
    return <p style={{ color: "var(--nv-text3)", fontSize: 13 }}>Checking your session…</p>;
  }

  if (sessionState === "unconfigured") {
    return (
      <p style={{ color: "var(--nv-text3)", fontSize: 13 }}>
        The live account system isn&rsquo;t configured in this environment.
      </p>
    );
  }

  if (sessionState === "signed-out") {
    return (
      <div
        style={{
          padding: 20,
          borderRadius: 10,
          background: "var(--nv-surface)",
          border: "1px solid var(--nv-line)",
          color: "var(--nv-text2)",
          fontSize: 14,
        }}
      >
        You need to sign in to change your password.{" "}
        <a href="/login?next=/nova/account" style={{ color: "var(--nv-accent)" }}>
          Sign in
        </a>
      </div>
    );
  }

  return (
    <div>
      {email ? (
        <p style={{ color: "var(--nv-text3)", fontSize: 13, marginBottom: 20 }}>
          Signed in as <strong style={{ color: "var(--nv-text2)" }}>{email}</strong>
        </p>
      ) : null}

      <form onSubmit={handleSubmit} noValidate style={{ display: "grid", gap: 16, maxWidth: 360 }}>
        {formError ? (
          <div role="alert" style={{ fontSize: 13, color: "var(--nv-warn)" }}>
            {formError}
          </div>
        ) : null}
        {done ? (
          <div role="status" style={{ fontSize: 13, color: "var(--nv-pos)" }}>
            Password updated.
          </div>
        ) : null}

        <div>
          <label htmlFor="new-password" style={{ display: "block", fontSize: 12.5, color: "var(--nv-text2)", marginBottom: 6 }}>
            New password
          </label>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input
              id="new-password"
              name="password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={submitting}
              aria-invalid={Boolean(fieldError)}
              placeholder={`At least ${MIN_PASSWORD_LENGTH} characters`}
              style={inputStyle}
            />
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              disabled={submitting}
              aria-label={showPassword ? "Hide password" : "Show password"}
              style={{ fontSize: 12, color: "var(--nv-text3)", background: "none", border: "none", cursor: "pointer", whiteSpace: "nowrap" }}
            >
              {showPassword ? "Hide" : "Show"}
            </button>
          </div>
        </div>

        <div>
          <label htmlFor="confirm-password" style={{ display: "block", fontSize: 12.5, color: "var(--nv-text2)", marginBottom: 6 }}>
            Confirm new password
          </label>
          <input
            id="confirm-password"
            name="confirm_password"
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            disabled={submitting}
            aria-invalid={Boolean(fieldError)}
            aria-describedby={fieldError ? "password-field-error" : undefined}
            placeholder="Re-enter your new password"
            style={inputStyle}
          />
          {fieldError ? (
            <p id="password-field-error" style={{ fontSize: 12, color: "var(--nv-warn)", marginTop: 6 }}>
              {fieldError}
            </p>
          ) : null}
        </div>

        <button type="submit" disabled={submitting} className="nv-btn solid" style={{ justifySelf: "start" }}>
          {submitting ? "Updating…" : "Update password"}
        </button>
      </form>
    </div>
  );
}
