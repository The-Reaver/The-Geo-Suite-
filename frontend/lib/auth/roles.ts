// frontend/lib/auth/roles.ts
//
// Role model for the client dashboard. Mirrors the database exactly:
//   - public.memberships.role is the enum ('owner', 'staff')
//   - public.users.is_operator is a separate flag on the user profile,
//     never a membership role, and never grantable through signup or
//     invitation.
//
// The dashboard uses these helpers to gate the six tool slot toggles,
// the members screen, and the billing card update form. Staff see the
// toggles disabled with an explanation (StaffDisabledNotice). Owners and
// the operator get full control. Keep every role check in this file so
// the gating logic never drifts between components.

export type MembershipRole = "owner" | "staff";

export const MEMBERSHIP_ROLES: readonly MembershipRole[] = [
  "owner",
  "staff",
] as const;

// Shape of the viewer as the session hook (useSession) resolves it:
// the membership role for the active client plus the operator flag
// from public.users.is_operator.
export interface ViewerRole {
  role: MembershipRole;
  isOperator: boolean;
}

export function isMembershipRole(value: unknown): value is MembershipRole {
  return value === "owner" || value === "staff";
}

// Parse a role coming off the wire. Falls back to the least privileged
// role so a malformed payload never widens access.
export function parseMembershipRole(value: unknown): MembershipRole {
  return isMembershipRole(value) ? value : "staff";
}

// Most dashboard consumers hold only a role string, a membership-like object
// with a `.role`, or nothing at all (session still loading). These helpers
// accept any of those shapes and normalize to a ViewerRole so callers never
// have to construct one by hand.
export type RoleLike =
  | ViewerRole
  | MembershipRole
  | string
  | { role?: MembershipRole | string | null; isOperator?: boolean }
  | null
  | undefined;

export function toViewerRole(input: RoleLike): ViewerRole {
  if (input == null) {
    return { role: "staff", isOperator: false };
  }
  if (typeof input === "string") {
    return { role: parseMembershipRole(input), isOperator: false };
  }
  return {
    role: parseMembershipRole(input.role),
    isOperator: Boolean((input as { isOperator?: boolean }).isOperator),
  };
}

export function isOwner(viewer: RoleLike): boolean {
  return toViewerRole(viewer).role === "owner";
}

export function isStaff(viewer: RoleLike): boolean {
  const v = toViewerRole(viewer);
  return v.role === "staff" && !v.isOperator;
}

export function isOperator(viewer: RoleLike): boolean {
  return toViewerRole(viewer).isOperator;
}

// -----------------------------------------------------------------------
// Capability checks. Components call these instead of comparing role
// strings so the rules live in one place.
// -----------------------------------------------------------------------

// Owners and the operator can flip tool slots on and off. Staff cannot.
// Account status gating (grace, suspended) is a separate concern handled
// by useAccountStatus and SuspendedBillingOnly, not here.
export function canToggleTools(viewer: RoleLike): boolean {
  const v = toViewerRole(viewer);
  return v.isOperator || v.role === "owner";
}

// Owners and the operator manage member invitations and removals.
export function canManageMembers(viewer: RoleLike): boolean {
  const v = toViewerRole(viewer);
  return v.isOperator || v.role === "owner";
}

// Owners and the operator update the card on file. This stays true even
// while the account sits in the suspended billing-only mode, because the
// whole point of that mode is letting the client fix the card.
export function canUpdateCard(viewer: RoleLike): boolean {
  const v = toViewerRole(viewer);
  return v.isOperator || v.role === "owner";
}

// Everyone with a membership can view the dashboard shell and the six
// slot cards. Staff simply see the controls disabled.
export function canViewDashboard(viewer: RoleLike): boolean {
  const v = toViewerRole(viewer);
  return v.isOperator || isMembershipRole(v.role);
}

// -----------------------------------------------------------------------
// Display helpers.
// -----------------------------------------------------------------------

export function roleLabel(viewer: RoleLike): string {
  const v = toViewerRole(viewer);
  if (v.isOperator) return "Operator";
  return v.role === "owner" ? "Owner" : "Staff";
}

// Copy shown next to disabled toggles for staff. StaffDisabledNotice
// renders this so the message stays consistent everywhere.
export const STAFF_TOGGLE_EXPLANATION =
  "Only the account owner can turn tools on or off, because each change " +
  "affects your monthly bill. Ask your owner to make this change.";
// Compatibility aliases for consumers that reference these names.
export type Role = MembershipRole;
export const ROLE_LABELS: Record<MembershipRole, string> = {
  owner: "Owner",
  staff: "Staff",
};
