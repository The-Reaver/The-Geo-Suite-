// Nova field service worker — Phase 1 of the sales-agent offline build
// (2026-08-16, OFFLINE_ARCHITECTURE_BRAIN_TRUST_2026-08-16.md section F).
//
// Scope: registered at scope "/nova/" (see lib/registerServiceWorker.ts),
// which this file's own root-level location ("/nova-sw.js") is allowed to
// claim without a Service-Worker-Allowed header, since /nova/ sits inside
// this script's default maximum scope of "/".
//
// Job: cache the Nova app SHELL (the page itself, its JS/CSS chunks) so the
// React app can boot with zero signal. Deliberately does NOT cache or
// intercept prospect/kit DATA — that is explicit IndexedDB reads/writes in
// application code (lib/offlineStore.ts, lib/fieldSync.ts), never implicit
// service-worker fetch interception, so a "cached as of" timestamp can
// always be shown accurately and nothing about staleness is ever silent
// (Celestina's finding C, binding on this whole design).
//
// Explicitly bypassed, never cached: /nova/kit, /nova/report,
// /nova/site-generator (always live-generated, caching them would silently
// serve a stale Sales Kit as if it were fresh), anything cross-origin (the
// FastAPI backend), and any non-GET request.

const SHELL_CACHE = "nova-shell-v1";

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(
        names
          .filter((name) => name.startsWith("nova-shell-") && name !== SHELL_CACHE)
          .map((name) => caches.delete(name))
      )
    ).then(() => self.clients.claim())
  );
});

function isBypassed(url) {
  return (
    url.pathname === "/nova/kit" ||
    url.pathname === "/nova/report" ||
    url.pathname === "/nova/site-generator" ||
    url.pathname.startsWith("/nova/kit?") ||
    url.pathname.startsWith("/nova/report?")
  );
}

function isShellRequest(url, sameOrigin) {
  if (!sameOrigin) return false;
  if (isBypassed(url)) return false;
  return (
    url.pathname === "/nova" ||
    url.pathname.startsWith("/_next/") ||
    url.pathname === "/nova-manifest.json" ||
    url.pathname.startsWith("/icons/")
  );
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return; // never cache/intercept writes

  const url = new URL(req.url);
  const sameOrigin = url.origin === self.location.origin;
  if (!isShellRequest(url, sameOrigin)) return; // let the network handle everything else natively

  event.respondWith(
    fetch(req)
      .then((res) => {
        // Only cache real, complete responses -- an opaque/error response
        // cached as "success" would mean an offline reload silently serves
        // a broken shell instead of falling through to the network again.
        if (res && res.ok) {
          const copy = res.clone();
          caches.open(SHELL_CACHE).then((cache) => cache.put(req, copy));
        }
        return res;
      })
      .catch(() =>
        caches.match(req).then((cached) => {
          if (cached) return cached;
          if (req.mode === "navigate") {
            return new Response(
              "<!doctype html><meta charset=\"utf-8\"><body style=\"font-family:system-ui;padding:40px\">" +
                "<h2>Nova isn't cached yet</h2>" +
                "<p>You're offline and this is the first time this device has loaded Nova. " +
                "Load it once with a real connection, then it works offline.</p></body>",
              { status: 200, headers: { "Content-Type": "text/html; charset=utf-8" } }
            );
          }
          return new Response("", { status: 504, statusText: "Offline and not cached" });
        })
      )
  );
});
