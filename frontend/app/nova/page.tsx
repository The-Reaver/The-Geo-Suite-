import type { Metadata } from "next";
import NovaShell from "./NovaShell";
import NovaErrorBoundary from "./ErrorBoundary";
import { discoverProspects } from "./actions";

// Nova app route. Server-fetches an initial live Prospecting query (falls back to
// a labeled sample when the source is off / not signed in), then renders the
// premium GEO Suite shell with Clinical Blue locked in. Open /nova in the running
// app. Live features are wired via app/nova/actions.ts.
export const metadata: Metadata = {
  title: "Nova — GEO Suite",
  description: "GEO Suite premium shell — Clinical Blue, live Prospecting.",
};

export const dynamic = "force-dynamic"; // reads the session cookie; never static

export default async function NovaPage() {
  const initial = await discoverProspects({ business_type: "hyperbaric therapy", locality: "Temecula, CA" });
  // 2026-08-09 GEO Brain Trust Presentation Mode review, Jasiah finding:
  // no error boundary existed anywhere in the shell. Wrapped here so a
  // render crash inside NovaShell shows a recoverable message instead of a
  // blank screen mid-demo.
  return (
    <NovaErrorBoundary>
      <NovaShell initial={initial} />
    </NovaErrorBoundary>
  );
}
