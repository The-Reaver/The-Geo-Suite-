"use client";

// SignupForm renders the first-run signup experience.
// The first signup creates the client account and grants the signer the
// owner membership on the backend. Operator status is never grantable
// here. It lives only in the database seed.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";
import { apiPost } from "@/lib/api";

type SignupPayload = {
  business_name: string;
  email: string;
  password: string;
};

type SignupResponse = {
  client_id: string;
  membership_role: "owner" | "staff";
};

type FieldErrors = {
  businessName?: string;
  email?: string;
  password?: string;
};

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_PASSWORD_LENGTH = 8;

export default function SignupForm() {
  const router = useRouter();

  const [businessName, setBusinessName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function validate(): boolean {
    const errors: FieldErrors = {};

    if (businessName.trim().length < 2) {
      errors.businessName = "Enter your business name.";
    }
    if (!EMAIL_PATTERN.test(email.trim())) {
      errors.email = "Enter a valid email address.";
    }
    if (password.length < MIN_PASSWORD_LENGTH) {
      errors.password = "Use at least 8 characters.";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);

    if (!validate()) {
      return;
    }

    setSubmitting(true);

    try {
      const payload: SignupPayload = {
        business_name: businessName.trim(),
        email: email.trim().toLowerCase(),
        password,
      };

      // The backend creates the Supabase user, the client row, and the
      // owner membership in one transaction.
      await apiPost<SignupResponse>("/auth/signup", payload);

      // Establish the browser session so the dashboard loads signed in.
      const { error: signInError } = await supabase.auth.signInWithPassword({
        email: payload.email,
        password: payload.password,
      });

      if (signInError) {
        // The account exists. Send the user to login rather than blocking.
        router.push("/login?created=1");
        return;
      }

      // New accounts have no base subscription yet. Send them to the card
      // step, which creates the $19 base subscription and then lands them on
      // the dashboard.
      router.push("/subscribe");
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : "Signup failed. Check your details and try again.";
      setFormError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Create your account
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          You become the owner of your business account. Your 19 dollar base
          fee covers unlimited team seats.
        </p>
      </div>

      {formError ? (
        <div
          role="alert"
          className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {formError}
        </div>
      ) : null}

      <form onSubmit={handleSubmit} noValidate className="space-y-5">
        <div>
          <label
            htmlFor="business-name"
            className="mb-1.5 block text-sm font-medium text-slate-700"
          >
            Business name
          </label>
          <input
            id="business-name"
            name="business_name"
            type="text"
            autoComplete="organization"
            value={businessName}
            onChange={(e) => setBusinessName(e.target.value)}
            disabled={submitting}
            aria-invalid={Boolean(fieldErrors.businessName)}
            aria-describedby={
              fieldErrors.businessName ? "business-name-error" : undefined
            }
            className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 disabled:bg-slate-50"
            placeholder="Acme Plumbing"
          />
          {fieldErrors.businessName ? (
            <p id="business-name-error" className="mt-1.5 text-xs text-red-600">
              {fieldErrors.businessName}
            </p>
          ) : null}
        </div>

        <div>
          <label
            htmlFor="signup-email"
            className="mb-1.5 block text-sm font-medium text-slate-700"
          >
            Email
          </label>
          <input
            id="signup-email"
            name="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={submitting}
            aria-invalid={Boolean(fieldErrors.email)}
            aria-describedby={fieldErrors.email ? "email-error" : undefined}
            className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 disabled:bg-slate-50"
            placeholder="you@business.com"
          />
          {fieldErrors.email ? (
            <p id="email-error" className="mt-1.5 text-xs text-red-600">
              {fieldErrors.email}
            </p>
          ) : null}
        </div>

        <div>
          <label
            htmlFor="signup-password"
            className="mb-1.5 block text-sm font-medium text-slate-700"
          >
            Password
          </label>
          <div className="relative">
            <input
              id="signup-password"
              name="password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={submitting}
              aria-invalid={Boolean(fieldErrors.password)}
              aria-describedby={
                fieldErrors.password ? "password-error" : "password-hint"
              }
              className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 pr-16 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 disabled:bg-slate-50"
              placeholder="At least 8 characters"
            />
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              className="absolute inset-y-0 right-0 flex items-center px-3.5 text-xs font-medium text-slate-500 transition hover:text-slate-700"
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? "Hide" : "Show"}
            </button>
          </div>
          {fieldErrors.password ? (
            <p id="password-error" className="mt-1.5 text-xs text-red-600">
              {fieldErrors.password}
            </p>
          ) : (
            <p id="password-hint" className="mt-1.5 text-xs text-slate-400">
              Use at least 8 characters.
            </p>
          )}
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? "Creating your account..." : "Create account"}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-slate-500">
        Already have an account?{" "}
        <a
          href="/login"
          className="font-medium text-indigo-600 transition hover:text-indigo-700"
        >
          Log in
        </a>
      </p>
    </div>
  );
}