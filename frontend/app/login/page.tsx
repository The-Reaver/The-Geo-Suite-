// frontend/app/login/page.tsx
// Login page for the client dashboard. Renders the shared LoginForm component
// inside a centered card layout. The form itself handles Supabase auth calls
// through frontend/lib/supabaseClient.ts and redirects on success.

import type { Metadata } from "next"
import { Suspense } from "react"
import Link from "next/link"
import LoginForm from "@/components/auth/LoginForm"

export const metadata: Metadata = {
  title: "Log in",
  description: "Log in to your account to manage your team and tools.",
}

export default function LoginPage() {
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
              S
            </span>
            <span>Studio</span>
          </Link>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
          <div className="mb-6">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
              Welcome back
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Log in with your email and password to open your dashboard.
            </p>
          </div>

          <Suspense fallback={null}>
            <LoginForm />
          </Suspense>

          <div className="mt-6 border-t border-slate-100 pt-6 text-center text-sm text-slate-500">
            <p>
              New here?{" "}
              <Link
                href="/signup"
                className="font-medium text-indigo-600 transition-colors hover:text-indigo-500"
              >
                Create your account
              </Link>
            </p>
            <p className="mt-2">
              Joining a team? Use the invitation link from your email to accept
              your invite.
            </p>
          </div>
        </div>

        <p className="mt-6 text-center text-xs text-slate-400">
          Your first signup creates the account and makes you the owner.
          Invited teammates join as staff.
        </p>
      </div>
    </main>
  )
}