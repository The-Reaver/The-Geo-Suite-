// Shared backend-error-to-user-facing-string extraction. Was duplicated
// (worse, in a weaker inline form) between app/nova/actions.ts and
// app/nova/compliance/actions.ts -- relocated here so both real callers
// share the same 200-char cap (a raw PyJWT/Pydantic exception string
// reaching the UI unbounded is a real information-leak risk, not just a
// cosmetic concern) and the same handling of Pydantic's array-shaped
// validation-error `detail` shape.
export function extractErrorDetail(data: unknown, status: number): string {
  const detail = (data as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string" && detail.trim()) return detail.slice(0, 200);
  if (Array.isArray(detail) && detail.length && typeof detail[0]?.msg === "string") {
    return detail[0].msg.slice(0, 200);
  }
  return `backend-${status}`;
}
