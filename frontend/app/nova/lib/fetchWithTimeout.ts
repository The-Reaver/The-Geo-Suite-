/*
 * Phase 3 (2026-08-16): honest-failure messaging for network timeouts.
 *
 * Plain `fetch()` has no default timeout -- on a genuinely weak-but-present
 * signal (navigator.onLine stays true; the request just never resolves),
 * every call site that used bare fetch() would hang indefinitely: a stuck
 * spinner, no error, no explanation. That is exactly the silent-failure
 * mode this whole offline design exists to refuse (Celestina's finding C),
 * it just wasn't reachable by the existing "fully offline" checks, which
 * only catch navigator.onLine === false, not "online but too slow to
 * finish a request." This module closes that gap for every live network
 * call the sales-agent PWA makes (actions.ts, fieldSync.ts).
 *
 * No directive at the top -- this is a plain utility, safe to import from
 * both a "use server" module (actions.ts, running in the Next.js server
 * runtime) and a "use client" module (fieldSync.ts, running in the
 * browser); fetch/AbortController/setTimeout are standard in both.
 */

// 12s: longer than the backend's own outbound crawl timeout (10s, see
// sales_preview.py's httpx.AsyncClient(timeout=10.0)) since this leg is
// agent-phone-to-our-backend, not our-backend-to-a-third-party-site, and
// should normally be faster -- but on a real degraded connection in the
// field, 12s is long enough to let a slow-but-working request finish
// without leaving the agent staring at a dead spinner through most of an
// appointment.
export const NETWORK_TIMEOUT_MS = 12_000;

export async function fetchWithTimeout(
  url: string,
  init: RequestInit = {},
  timeoutMs: number = NETWORK_TIMEOUT_MS
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

/** True when a caught error is this timeout firing, not some other network failure. */
export function isTimeoutError(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}
