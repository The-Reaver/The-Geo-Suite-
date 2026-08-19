
/**
 * Next.js configuration for the frontend.
 *
 * This config keeps the app PWA-friendly. The web manifest lives at
 * frontend/public/manifest.json and Next.js serves it from /manifest.json,
 * which is the path frontend/app/layout.tsx links in its metadata. A service
 * worker added in a later task will live in frontend/public so the browser
 * can register it at the site root scope.
 *
 * The backend URL comes from the environment only. You set
 * NEXT_PUBLIC_API_BASE_URL in frontend/.env.local. No secret ever lives in
 * this file.
 */

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // Rewrite /backend/* to the FastAPI service so the browser talks to one
  // origin during local development. The target reads from the environment
  // and falls back to the local FastAPI default port.
  async rewrites() {
    const apiBaseUrl =
      process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
    return [
      {
        source: "/backend/:path*",
        destination: `${apiBaseUrl}/:path*`,
      },
    ];
  },

  // Serve the manifest with the correct content type, cache the app icons,
  // and keep the service worker fresh so updates reach installed clients
  // quickly.
  async headers() {
    return [
      {
        source: "/manifest.json",
        headers: [
          {
            key: "Content-Type",
            value: "application/manifest+json",
          },
          {
            key: "Cache-Control",
            value: "public, max-age=3600",
          },
        ],
      },
      {
        source: "/icons/:path*",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=86400",
          },
        ],
      },
      {
        source: "/sw.js",
        headers: [
          {
            key: "Cache-Control",
            value: "no-cache, no-store, must-revalidate",
          },
          {
            key: "Service-Worker-Allowed",
            value: "/",
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;