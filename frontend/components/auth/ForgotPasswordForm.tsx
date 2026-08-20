"use client";

// Requests a Supabase password-reset email. Supabase itself never reveals
// whether an address has an account (resetPasswordForEmail succeeds either
// way, by design, to avoid email enumeration) -- this form shows the same
// confirmation regardless, and only surfaces a real error for a genuine
// failure (rate-limited, network down), which doesn't leak anything about
// the address itself.

import { useState } from "react";
import { supabase } from "@/lib/supabaseClient";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);

    const trimmed = email.trim();
    if (!EMAIL_PATTERN.test(trimmed)) {
      setFieldError("Enter a valid email address.");
      return;
    }
    setFieldError(null);
    setSubmitting(true);

    const { error } = await supabase.auth.resetPasswordForEmail(trimmed, {
      redirectTo: `${window.location.origin}/reset-password`,
    });

    setSubmitting(false);

    if (error) {
      setFormError(error.message);
      return;
    }
    setSent(true);
  }

  if (sent) {
    return (
      <div className="space-y-4 text-center">
        <div
          role="status"
          className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700"
        >
          If an account exists for <strong>{email.trim()}</strong>, a password
          reset link is on its way. Check your inbox (and spam folder) -- the
          link expires after a while, so use it soon.
        </div>
        <a
          href="/login"
          className="inline-block text-sm font-medium text-indigo-600 transition-colors hover:text-indigo-500"
        >
          Back to login
        </a>
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
          htmlFor="forgot-email"
          className="mb-1.5 block text-sm font-medium text-slate-700"
        >
          Email address
        </label>
        <input
          id="forgot-email"
          name="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={submitting}
          aria-invalid={Boolean(fieldError)}
          aria-describedby={fieldError ? "forgot-email-error" : undefined}
          placeholder="you@company.com"
          className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 disabled:bg-slate-50"
        />
        {fieldError ? (
          <p id="forgot-email-error" className="mt-1.5 text-xs text-red-600">
            {fieldError}
          </p>
        ) : null}
      </div>

      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {submitting ? "Sending..." : "Send reset link"}
      </button>

      <p className="text-center text-sm text-slate-500">
        <a
          href="/login"
          className="font-medium text-indigo-600 transition-colors hover:text-indigo-500"
        >
          Back to login
        </a>
      </p>
    </form>
  );
}
