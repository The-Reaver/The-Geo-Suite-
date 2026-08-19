import type { Metadata } from "next";
import ServiceWorkerRegister from "./ServiceWorkerRegister";

// Nova's own PWA identity, per OFFLINE_ARCHITECTURE_BRAIN_TRUST_2026-08-16.md
// section E: a Progressive Web App scoped to /nova/, not the base platform's
// /dashboard manifest (frontend/public/manifest.json, wired in the root
// layout). Overrides `manifest` for every route under app/nova/*; page.tsx's
// own metadata (title/description) still applies on top of this.
export const metadata: Metadata = {
  manifest: "/nova-manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "GEO Field",
  },
};

export default function NovaLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <ServiceWorkerRegister />
      {children}
    </>
  );
}
