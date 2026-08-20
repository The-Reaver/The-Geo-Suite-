"use client";

// Sets a new password from a Supabase recovery-link visit. Clicking the
// email link Supabase sends (see ForgotPasswordForm's resetPasswordForEmail
// call) lands here with the browser Supabase client (lib/supabaseClient.ts)
// auto-detecting the recovery tokens from the URL and firing a
// PASSWORD_RECOVERY auth event -- the officially documented signal for
// "show the set-new-password form now" (see Supabase's own reset-password
// guide), so this never hand-parses the token format itself. An expired or
// already-used link comes back from Supabase as an error_description in the
// URL (query or hash, depending on flow) rather than a recovery event; a
// short timeout catches the case where neither ever fires at all.

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";

const MIN_PASSWORD_LENGTH = 8;
const LINK_CHECK_TIMEOUT_MS = 5000;

type Status = "checking" | "ready" | "invalid";

function parseHashParams(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const raw = window.location.hash.startsWith("#")
    ? window.location.hash.slice(1)
    : window.location.hash;
  return Object.fromEntries(new URLSearchParams(raw));
}

export default function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [status, setStatus] = useState<Status>("checking");
  const [linkError, setLinkError] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    const queryError =
      searchParams.get("error_description") || searchParams.get("error");
    const hashParams = parseHashParams();
    const hashError = hashParams.error_description || hashParams.error;
    const linkErrorText = (queryError || hashError || "").replace(/\+/g, " ");

    if (linkErrorText) {
      setLinkError(linkErrorText);
      setStatus("invalid");
      return;
    }

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event) => {
      if (event === "PASSWORD_RECOVERY") {
        setStatus("ready");
      }
    });

    // The PASSWORD_RECOVERY event can fire before this listener attaches
    // (client init races the URL-token processing) -- a session already
    // present here means the link already worked.
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) {
        setStatus("ready");
      }
    });

    const timeout = setTimeout(() => {
      setStatus((current) => (current === "checking" ? "invalid" : current));
    }, LINK_CHECK_TIMEOUT_MS);

    return () => {
      subscription.unsubscribe();
      clearTimeout(timeout);
    };
  }, [searchParams]);

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

    if (!validate()) {
      return;
    }

    setSubmitting(true);
    const { error } = await supabase.auth.updateUser({ password });
    setSubmitting(false);

    if (error) {
      setFormError(error.message);
      return;
    }

    setDone(true);
    setTimeout(() => {
      router.push("/nova");
      router.refresh();
    }, 1200);
  }

  if (status === "checking") {
    return (
      <div className="py-10 text-center text-sm text-slate-500">
        Verifying your reset link...
      </div>
    );
  }

  if (status === "invalid") {
    return (
      <div className="space-y-4">
        <div
          role="alert"
          className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {linkError && linkError.toLowerCase().includes("expired")
            ? "This reset link has expired."
            : "This reset link is invalid or has already been used."}{" "}
          Request a new one below.
        </div>
        <a
          href="/forgot-password"
          className="block w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-center text-sm font-semibold text-white shadow-sm hover:bg-indigo-500"
        >
          Request a new link
        </a>
      </div>
    );
  }

  if (done) {
    return (
      <div
        role="status"
        className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-center text-sm text-green-700"
      >
        Password updated. Taking you in...
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-5">
      {formError ? (
        <div
          role="alert"
          className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {formError}
        </div>
      ) : null}

      <div>
        <label
          htmlFor="new-password"
          className="mb-1.5 block text-sm font-medium text-slate-700"
        >
          New password
        </label>
        <div className="relative">
          <input
            id="new-password"
            name="password"
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={submitting}
            aria-invalid={Boolean(fieldError)}
            aria-describedby={fieldError ? "new-password-error" : "new-password-hint"}
            placeholder="At least 8 characters"
            className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 pr-16 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 disabled:bg-slate-50"
          />
          <button
            type="button"
            onClick={() => setShowPassword((v) => !v)}
            disabled={submitting}
            aria-label={showPassword ? "Hide password" : "Show password"}
            className="absolute inset-y-0 right-0 flex items-center px-3.5 text-xs font-medium text-slate-500 hover:text-slate-700"
          >
            {showPassword ? "Hide" : "Show"}
          </button>
        </div>
        {!fieldError ? (
          <p id="new-password-hint" className="mt-1.5 text-xs text-slate-400">
            Use at least {MIN_PASSWORD_LENGTH} characters.
          </p>
        ) : null}
      </div>

      <div>
        <label
          htmlFor="confirm-password"
          className="mb-1.5 block text-sm font-medium text-slate-700"
        >
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
          aria-describedby={fieldError ? "new-password-error" : undefined}
          placeholder="Re-enter your new password"
          className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 disabled:bg-slate-50"
        />
        {fieldError ? (
          <p id="new-password-error" className="mt-1.5 text-xs text-red-600">
            {fieldError}
          </p>
        ) : null}
      </div>

      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {submitting ? "Updating..." : "Set new password"}
      </button>
    </form>
  );
}
