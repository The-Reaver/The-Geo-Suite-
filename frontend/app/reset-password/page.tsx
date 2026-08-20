// frontend/app/reset-password/page.tsx
// Landing page for a Supabase password-reset email link. ResetPasswordForm
// reads URL search params (useSearchParams), so it needs a Suspense
// boundary during prerender -- same pattern app/login/page.tsx already uses
// for LoginForm.

import type { Metadata } from "next";
import { Suspense } from "react";
import Link from "next/link";
import ResetPasswordForm from "@/components/auth/ResetPasswordForm";

export const metadata: Metadata = {
  title: "Set a new password",
  description: "Set a new password for your GEO Suite account.",
};

export default function ResetPasswordPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-lg font-semibold text-slate-900"
          >
            <span
              aria-hidden="true"
              className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white"
            >
              G
            </span>
            <span>GEO Suite</span>
          </Link>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
          <div className="mb-6">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
              Set a new password
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Choose a new password for your account.
            </p>
          </div>

          <Suspense fallback={null}>
            <ResetPasswordForm />
          </Suspense>
        </div>
      </div>
    </main>
  );
}
