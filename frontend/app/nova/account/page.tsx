import type { Metadata } from "next";
import Link from "next/link";
import { AccountPasswordForm } from "./AccountPasswordForm";

// Account settings, Slice 1 (2026-08-22): a real place to change your own
// password from inside Nova. Before this, the sidebar's user block
// (NovaShell.tsx's nv-user) had nowhere to send a click -- the only
// existing password flow was forgot-password, for someone already locked
// out, not a signed-in user proactively changing it. Email change is a
// separate, later slice (Slice 2) -- it needs an operator-side redirect-
// URL allow-list addition first, same requirement /forgot-password already
// needed (see README.md's Supabase Auth setup section).
export const metadata: Metadata = {
  title: "Account — GEO Suite",
  description: "Change your GEO Suite account password.",
};

export default function AccountPage() {
  return (
    <div className="nova-app" data-accent="blue" style={{ display: "block", height: "auto", overflow: "visible" }}>
      <main style={{ maxWidth: 560, margin: "0 auto", padding: "40px 24px 80px" }}>
        <div style={{ marginBottom: 28 }}>
          <Link href="/nova" style={{ color: "var(--nv-text2)", fontSize: 13, textDecoration: "none" }}>
            ← Back to Nova
          </Link>
        </div>
        <h1 style={{ fontFamily: "var(--nv-serif)", fontSize: 32, margin: "0 0 8px", color: "var(--nv-text)" }}>
          Account
        </h1>
        <p style={{ color: "var(--nv-text2)", fontSize: 15, lineHeight: 1.6, marginBottom: 32 }}>
          Change your password below.
        </p>
        <AccountPasswordForm />
      </main>
    </div>
  );
}
