"use client";

/**
 * frontend/lib/auth/useSession.ts
 *
 * Session hook for the client dashboard shell. Wraps Supabase auth and
 * hydrates the profile row from public.users plus the membership row from
 * public.memberships so every screen knows three things:
 *
 *   1. Who you are (profile, from public.users).
 *   2. Which client you belong to and in what role (public.memberships).
 *   3. Whether you carry the operator flag (users.is_operator, read only
 *      here, never writable from the browser).
 *
 * The role drives the owner and staff gating in the tool slot cards, the
 * member screens, and the billing screens. The access token feeds the
 * fetch helpers in lib/api so the FastAPI backend can verify the caller.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  createClient,
  type Session,
  type SupabaseClient,
} from "@supabase/supabase-js";
import { type Role, isOwner, isStaff } from "./roles";

// ---------------------------------------------------------------------------
// Supabase browser client (singleton)
// ---------------------------------------------------------------------------

let browserClient: SupabaseClient | null = null;

export function getSupabaseBrowserClient(): SupabaseClient {
  if (browserClient) return browserClient;

  // Fall back to placeholders when the keys are absent so the production
  // build never blocks on live keys during static prerender (same
  // convention as lib/env.ts and lib/supabaseClient.ts). Real values come
  // from the deploy environment at runtime.
  const url =
    process.env.NEXT_PUBLIC_SUPABASE_URL &&
    process.env.NEXT_PUBLIC_SUPABASE_URL.trim().length > 0
      ? process.env.NEXT_PUBLIC_SUPABASE_URL
      : "https://placeholder-project.supabase.co";
  const anonKey =
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY &&
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY.trim().length > 0
      ? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
      : "placeholder-anon-key";

  browserClient = createClient(url, anonKey, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
    },
  });

  return browserClient;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Mirrors public.users. */
export interface UserProfile {
  id: string;
  email: string;
  fullName: string | null;
  isOperator: boolean;
}

/** Mirrors public.memberships joined to public.clients. */
export interface Membership {
  id: string;
  clientId: string;
  clientName: string;
  role: Role;
}

export type SessionStatus = "loading" | "authenticated" | "unauthenticated";

export interface SessionState {
  /** loading until the first auth check and profile fetch settle. */
  status: SessionStatus;
  /**
   * Convenience alias for the active client membership (carries role,
   * clientId, clientName). Truthy when the caller belongs to a client;
   * null for operator-only accounts. Dashboard screens read session?.role.
   */
  session: Membership | null;
  /** Convenience flag: true while status === "loading". */
  loading: boolean;
  /** Profile row from public.users, null until authenticated. */
  user: UserProfile | null;
  /** Membership for the active client, null for operator-only accounts. */
  membership: Membership | null;
  /** True when users.is_operator is set. Read only in the browser. */
  isOperator: boolean;
  /** True when membership.role is owner. Owners see live toggles. */
  isOwner: boolean;
  /** True when membership.role is staff. Staff see disabled toggles. */
  isStaff: boolean;
  /** Current Supabase access token for Authorization headers. */
  accessToken: string | null;
  /** Non-fatal load error, surfaced so screens can show a retry notice. */
  error: string | null;
  /** Returns a fresh access token, refreshing the session if needed. */
  getAccessToken: () => Promise<string | null>;
  /** Signs out and clears local session state. */
  signOut: () => Promise<void>;
  /** Re-runs the profile and membership fetch. */
  refresh: () => Promise<void>;
}

// ---------------------------------------------------------------------------
// Internal loaders
// ---------------------------------------------------------------------------

interface LoadedIdentity {
  user: UserProfile;
  membership: Membership | null;
}

async function loadIdentity(
  supabase: SupabaseClient,
  session: Session
): Promise<LoadedIdentity> {
  const authUserId = session.user.id;

  const { data: profileRow, error: profileError } = await supabase
    .from("users")
    .select("id, email, full_name, is_operator")
    .eq("id", authUserId)
    .single();

  if (profileError || !profileRow) {
    throw new Error(
      profileError?.message ?? "Your profile row could not be loaded."
    );
  }

  const user: UserProfile = {
    id: profileRow.id,
    email: profileRow.email,
    fullName: profileRow.full_name ?? null,
    isOperator: Boolean(profileRow.is_operator),
  };

  // A user belongs to at most one client in this product. RLS scopes the
  // read, so this returns only rows the caller may see.
  const { data: membershipRow, error: membershipError } = await supabase
    .from("memberships")
    .select("id, client_id, role, clients ( name )")
    .eq("user_id", authUserId)
    .limit(1)
    .maybeSingle();

  if (membershipError) {
    throw new Error(membershipError.message);
  }

  let membership: Membership | null = null;
  if (membershipRow) {
    const clientRelation = membershipRow.clients as
      | { name: string }
      | { name: string }[]
      | null;
    const clientName = Array.isArray(clientRelation)
      ? clientRelation[0]?.name ?? ""
      : clientRelation?.name ?? "";

    membership = {
      id: membershipRow.id,
      clientId: membershipRow.client_id,
      clientName,
      role: membershipRow.role as Role,
    };
  }

  return { user, membership };
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useSession(): SessionState {
  const supabase = useMemo(() => getSupabaseBrowserClient(), []);

  const [status, setStatus] = useState<SessionStatus>("loading");
  const [user, setUser] = useState<UserProfile | null>(null);
  const [membership, setMembership] = useState<Membership | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mountedRef = useRef(true);

  const applySession = useCallback(
    async (session: Session | null) => {
      if (!session) {
        if (!mountedRef.current) return;
        setUser(null);
        setMembership(null);
        setAccessToken(null);
        setError(null);
        setStatus("unauthenticated");
        return;
      }

      try {
        const identity = await loadIdentity(supabase, session);
        if (!mountedRef.current) return;
        setUser(identity.user);
        setMembership(identity.membership);
        setAccessToken(session.access_token);
        setError(null);
        setStatus("authenticated");
      } catch (err) {
        if (!mountedRef.current) return;
        setUser(null);
        setMembership(null);
        setAccessToken(session.access_token);
        setError(
          err instanceof Error ? err.message : "Session load failed."
        );
        setStatus("authenticated");
      }
    },
    [supabase]
  );

  useEffect(() => {
    mountedRef.current = true;

    supabase.auth
      .getSession()
      .then(({ data }) => applySession(data.session))
      .catch(() => {
        if (!mountedRef.current) return;
        setStatus("unauthenticated");
      });

    const { data: listener } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        void applySession(session);
      }
    );

    return () => {
      mountedRef.current = false;
      listener.subscription.unsubscribe();
    };
  }, [supabase, applySession]);

  const getAccessToken = useCallback(async (): Promise<string | null> => {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token ?? null;
    if (mountedRef.current) setAccessToken(token);
    return token;
  }, [supabase]);

  const signOut = useCallback(async (): Promise<void> => {
    await supabase.auth.signOut();
    if (!mountedRef.current) return;
    setUser(null);
    setMembership(null);
    setAccessToken(null);
    setError(null);
    setStatus("unauthenticated");
  }, [supabase]);

  const refresh = useCallback(async (): Promise<void> => {
    const { data } = await supabase.auth.getSession();
    await applySession(data.session);
  }, [supabase, applySession]);

  const role = membership?.role ?? null;

  return {
    status,
    session: membership,
    loading: status === "loading",
    user,
    membership,
    isOperator: user?.isOperator ?? false,
    isOwner: isOwner(role),
    isStaff: isStaff(role),
    accessToken,
    error,
    getAccessToken,
    signOut,
    refresh,
  };
}

export default useSession;