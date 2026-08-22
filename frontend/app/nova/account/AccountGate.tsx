"use client";

/*
 * Shared session gate for /nova/account. Extracted out of
 * AccountPasswordForm (Slice 1) when Slice 2a (AccountEmailForm) needed
 * the same real signed-in email -- rather than duplicate the whole
 * checking/unconfigured/signed-out state machine (and its own
 * getSupabaseBrowserClient() unconfigured-throw guard, see that fix's
 * own comment history) across two sibling forms, this owns it once and
 * renders both forms as children once a real session is confirmed.
 */

import { useEffect, useState } from "react";
import { getSupabaseBrowserClient } from "../lib/supabaseBrowser";
import { AccountPasswordForm } from "./AccountPasswordForm";
import { AccountEmailForm } from "./AccountEmailForm";

type SessionState = "checking" | "signed-in" | "signed-out" | "unconfigured";

export function AccountGate() {
  const [sessionState, setSessionState] = useState<SessionState>("checking");
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    // getSupabaseBrowserClient() throws SYNCHRONOUSLY when Supabase isn't
    // configured -- must check env vars before ever calling it, not just
    // wrap the call in a .catch(), same real bug fixed once already in
    // this page's own history.
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
        You need to sign in to manage your account.{" "}
        <a href="/login?next=/nova/account" style={{ color: "var(--nv-accent)" }}>
          Sign in
        </a>
      </div>
    );
  }

  return (
    <div>
      {email ? (
        <p style={{ color: "var(--nv-text3)", fontSize: 13, marginBottom: 28 }}>
          Signed in as <strong style={{ color: "var(--nv-text2)" }}>{email}</strong>
        </p>
      ) : null}
      <div style={{ display: "grid", gap: 40 }}>
        <AccountPasswordForm />
        {email ? <AccountEmailForm currentEmail={email} /> : null}
      </div>
    </div>
  );
}
