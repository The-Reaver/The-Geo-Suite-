/**
 * frontend/lib/api.ts
 *
 * Typed client for the FastAPI backend.
 * Every request attaches the current Supabase access token as a bearer
 * token so the backend can verify the caller and apply role checks.
 *
 * Keep this file as the single place the frontend talks to the backend.
 * Components import these functions instead of calling fetch directly.
 */

import { supabase } from "./supabaseClient";
import type { Role } from "./auth/roles";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/* ------------------------------------------------------------------ */
/* Types shared with the backend Pydantic schemas                      */
/* ------------------------------------------------------------------ */

export interface Client {
  id: string;
  name: string;
  created_at: string;
}

export interface Membership {
  id: string;
  client_id: string;
  user_id: string;
  email: string;
  role: Role;
  is_operator: boolean;
  created_at: string;
}

export interface CurrentUser {
  user_id: string;
  email: string;
  client: Client;
  role: Role;
  is_operator: boolean;
}

export interface Invitation {
  id: string;
  client_id: string;
  email: string;
  status: "pending" | "accepted" | "revoked" | "expired";
  invited_by: string;
  created_at: string;
  expires_at: string;
}

export interface SignupRequest {
  email: string;
  password: string;
  client_name: string;
}

export interface SignupResponse {
  user_id: string;
  client: Client;
  role: Role;
}

export interface InviteRequest {
  email: string;
}

export interface AcceptInviteRequest {
  token: string;
}

export interface AcceptInviteResponse {
  membership: Membership;
  client: Client;
}

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/* ------------------------------------------------------------------ */
/* Core request helper                                                 */
/* ------------------------------------------------------------------ */

async function getAccessToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  /** Set false for endpoints that work without a session, such as signup. */
  auth?: boolean;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (auth) {
    const token = await getAccessToken();
    if (!token) {
      throw new ApiError(401, "You are not signed in.");
    }
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}.`;
    try {
      const payload = await response.json();
      if (typeof payload?.detail === "string") {
        detail = payload.detail;
      }
    } catch {
      // The body was not JSON. Keep the default detail message.
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

/* ------------------------------------------------------------------ */
/* Auth                                                                */
/* ------------------------------------------------------------------ */

/**
 * Creates the Supabase user, the client record, and the owner membership
 * in one backend call. The first signup for a client always becomes the
 * owner. Operator status is never grantable through this path.
 */
export async function signup(payload: SignupRequest): Promise<SignupResponse> {
  return request<SignupResponse>("/auth/signup", {
    method: "POST",
    body: payload,
    auth: false,
  });
}

/**
 * Returns the signed-in user with their client, role, and operator flag.
 * Use this after login to decide what the UI shows.
 */
export async function getCurrentUser(): Promise<CurrentUser> {
  return request<CurrentUser>("/auth/me");
}

/* ------------------------------------------------------------------ */
/* Accounts                                                            */
/* ------------------------------------------------------------------ */

/** Returns the caller's client account. Backend: GET /accounts/me. */
export async function getAccount(): Promise<Client> {
  return request<Client>("/accounts/me");
}

/** Lists every member of the caller's client. Backend: GET /accounts/me/members. */
export async function listMembers(): Promise<Membership[]> {
  return request<Membership[]>("/accounts/me/members");
}

/* ------------------------------------------------------------------ */
/* Invitations                                                         */
/* ------------------------------------------------------------------ */

/**
 * Sends an invitation to join the caller's client as staff.
 * The backend rejects this call unless the caller is the owner.
 */
export async function createInvitation(payload: InviteRequest): Promise<Invitation> {
  return request<Invitation>("/invitations", {
    method: "POST",
    body: payload,
  });
}

/** Lists invitations for the caller's client. */
export async function listInvitations(): Promise<Invitation[]> {
  return request<Invitation[]>("/invitations");
}

/** Revokes a pending invitation. Owner only, enforced by the backend. */
export async function revokeInvitation(invitationId: string): Promise<void> {
  return request<void>(`/invitations/${invitationId}`, {
    method: "DELETE",
  });
}

/**
 * Accepts an invitation using the token from the invite link.
 * The invitee joins as staff. Staff cannot update the card or
 * activate a paid tool. The backend enforces both rules.
 */
export async function acceptInvitation(
  payload: AcceptInviteRequest
): Promise<AcceptInviteResponse> {
  return request<AcceptInviteResponse>("/invitations/accept", {
    method: "POST",
    body: payload,
  });
}

/* ------------------------------------------------------------------ */
/* Generic helpers + convenience object                                */
/* ------------------------------------------------------------------ */

/**
 * Generic POST helper for endpoints that do not yet have a dedicated
 * typed wrapper. Defaults to an unauthenticated call because the only
 * current caller is signup, which runs before a session exists.
 */
export async function apiPost<T>(
  path: string,
  body?: unknown,
  options: { auth?: boolean } = {}
): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body,
    auth: options.auth ?? false,
  });
}

/**
 * Backend POST /invitations/accept returns MembershipResponse. The invite
 * page reads the role and the client id off it (there is no client_name on
 * this response).
 */
export interface AcceptInvitationResult {
  id: string;
  client_id: string;
  user_id: string;
  role: Role;
  created_at: string;
}

/**
 * Convenience object some pages import as `api`. It groups the auth and
 * invitation calls behind a single import. Note: the members/invitation
 * helpers here are superseded by lib/api/members.ts for the dashboard; they
 * remain for the invite-accept flow.
 */
export const api = {
  signup,
  getCurrentUser,
  getAccount,
  createInvitation,
  revokeInvitation,
  acceptInvitation: (token: string): Promise<AcceptInvitationResult> =>
    request<AcceptInvitationResult>("/invitations/accept", {
      method: "POST",
      body: { token },
    }),
  post: apiPost,
};