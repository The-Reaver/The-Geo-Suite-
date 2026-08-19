"use client";

/*
 * Registers nova-sw.js scoped to /nova/, not the base platform's manifest
 * or service worker (there isn't one yet at the base level either, but this
 * keeps Nova's offline behavior self-contained regardless). Runs once on
 * mount from ServiceWorkerRegister below. Never throws into the render
 * tree -- a failed registration (unsupported browser, non-HTTPS in some
 * environments) degrades to "no offline support," not a broken page.
 */

export function registerNovaServiceWorker(): void {
  if (typeof window === "undefined") return;
  if (!("serviceWorker" in navigator)) return;
  navigator.serviceWorker.register("/nova-sw.js", { scope: "/nova/" }).catch(() => {
    // Silent on purpose here specifically: this is infrastructure setup,
    // not a user-facing action. The user-facing honesty guarantee lives in
    // "Sync for the field" and the cached-as-of badges, which report their
    // own real state regardless of whether the shell itself is cached.
  });
}
