import type { Metadata } from "next";
import Link from "next/link";
import { AccountGate } from "./AccountGate";

// Account settings (2026-08-22): a real place to manage your own account
// from inside Nova. Before Slice 1, the sidebar's user block
// (NovaShell.tsx's nv-user) had nowhere to send a click -- the only
// existing password flow was forgot-password, for someone already locked
// out, not a signed-in user proactively changing it.
//
// Slice 1: change password. Slice 2a: START a change-email request
// (AccountEmailForm.tsx) -- both real prerequisites confirmed done by the
// operator first: "Secure email change" is on for this project, and
// /nova/account is on Supabase's redirect-URL allow-list. Slice 2b
// (handling the confirmation-link landing UX) is deliberately its own
// later slice -- see AccountEmailForm.tsx's own header for why.
export const metadata: Metadata = {
  title: "Account — GEO Suite",
  description: "Manage your GEO Suite account.",
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
          Manage your GEO Suite account.
        </p>
        <AccountGate />
      </main>
    </div>
  );
}
