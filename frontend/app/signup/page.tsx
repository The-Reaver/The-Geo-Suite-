import type { Metadata } from "next";
import Link from "next/link";
import SignupForm from "../../components/auth/SignupForm";

export const metadata: Metadata = {
  title: "Create your account",
  description: "Sign up to create your GEO Suite account.",
};

export default function SignupPage() {
  return (
    <main className="min-h-screen bg-slate-50 flex flex-col lg:flex-row">
      {/* Brand and value panel */}
      <section className="hidden lg:flex lg:w-1/2 flex-col justify-between bg-slate-900 px-12 py-14 text-white">
        <div>
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-lg font-semibold tracking-tight"
          >
            <span
              aria-hidden="true"
              className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-500 text-base font-bold"
            >
              G
            </span>
            GEO Suite
          </Link>
        </div>

        <div className="max-w-md">
          <h1 className="text-3xl font-semibold leading-tight tracking-tight">
            Start your account.
          </h1>
          <p className="mt-4 text-slate-300">
            Your first signup creates your business account and makes you its
            owner.
          </p>

          <ul className="mt-8 space-y-4">
            {[
              "You become the owner on signup",
              "Every finding is labeled documented or hypothesis",
              "Your data stays scoped to your account with row level security",
            ].map((item) => (
              <li key={item} className="flex items-start gap-3">
                <span
                  aria-hidden="true"
                  className="mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-500/20 text-indigo-300"
                >
                  <svg
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    className="h-3.5 w-3.5"
                  >
                    <path
                      fillRule="evenodd"
                      d="M16.704 5.29a1 1 0 0 1 .006 1.414l-7.2 7.3a1 1 0 0 1-1.42.004L4.29 10.21a1 1 0 1 1 1.42-1.408l3.084 3.11 6.496-6.588a1 1 0 0 1 1.414-.006Z"
                      clipRule="evenodd"
                    />
                  </svg>
                </span>
                <span className="text-sm text-slate-200">{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Form panel */}
      <section className="flex w-full lg:w-1/2 items-center justify-center px-4 py-12 sm:px-6">
        <div className="w-full max-w-md">
          {/* Mobile brand header */}
          <div className="mb-8 flex items-center justify-center lg:hidden">
            <Link
              href="/"
              className="inline-flex items-center gap-2 text-lg font-semibold tracking-tight text-slate-900"
            >
              <span
                aria-hidden="true"
                className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-base font-bold text-white"
              >
                G
              </span>
              GEO Suite
            </Link>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
            <header className="mb-6">
              <h2 className="text-2xl font-semibold tracking-tight text-slate-900">
                Create your account
              </h2>
              <p className="mt-2 text-sm text-slate-600">
                You sign up once and become the owner of your account.
              </p>
            </header>

            <SignupForm />

            <p className="mt-6 text-center text-sm text-slate-600">
              Already have an account?{" "}
              <Link
                href="/login"
                className="font-medium text-indigo-600 hover:text-indigo-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 rounded"
              >
                Log in
              </Link>
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}