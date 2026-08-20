import type { Metadata } from "next";
import Link from "next/link";
import { fetchPipelineList } from "./actions";

// Pipeline — 2026-08-20, slice 2. Replaces NovaShell.tsx's honest "Soon"
// Pipeline nav stub with the real thing: every prospect actually persisted
// via the "Save to Pipeline" button (slice 1) through
// site_pipeline.generate_and_store(), not Nova's ephemeral demo state.
//
// Read-only, by design, matching this repo's own micro-sliced build order:
// re-audit/history is its own later slice, not bundled into "show the
// list" just because it's already open.
export const metadata: Metadata = {
  title: "Pipeline — GEO Suite",
  description: "Every prospect actually persisted through Save to Pipeline.",
};

export const dynamic = "force-dynamic"; // reads the session cookie; never static

function formatRunAt(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
}

export default async function PipelinePage() {
  const result = await fetchPipelineList();

  return (
    <div className="nova-app" data-accent="blue" style={{ display: "block", height: "auto", overflow: "visible" }}>
      <main style={{ maxWidth: 880, margin: "0 auto", padding: "40px 24px 80px" }}>
        <div style={{ marginBottom: 28 }}>
          <Link href="/nova" style={{ color: "var(--nv-text2)", fontSize: 13, textDecoration: "none" }}>
            ← Back to Nova
          </Link>
        </div>
        <h1 style={{ fontFamily: "var(--nv-serif)", fontSize: 32, margin: "0 0 8px", color: "var(--nv-text)" }}>
          Pipeline
        </h1>
        <p style={{ color: "var(--nv-text2)", fontSize: 15, lineHeight: 1.6, maxWidth: 640, margin: "0 0 32px" }}>
          Prospects actually saved through <strong>Save to Pipeline</strong> in Nova — a real, persisted
          site with its own generated pages and audit score, not a browser-session-only preview.
        </p>

        {!result.live ? (
          <div
            style={{
              padding: 24,
              borderRadius: 10,
              background: "var(--nv-surface)",
              border: "1px solid var(--nv-line)",
              color: "var(--nv-text2)",
            }}
          >
            {result.reason === "not-signed-in"
              ? "Sign in to view the Pipeline."
              : result.reason === "supabase-not-configured"
              ? "Backend not configured for this environment."
              : `Could not load the Pipeline right now (${result.reason}).`}
          </div>
        ) : result.sites.length === 0 ? (
          <div
            style={{
              padding: 24,
              borderRadius: 10,
              background: "var(--nv-surface)",
              border: "1px solid var(--nv-line)",
              color: "var(--nv-text2)",
              fontSize: 13.5,
            }}
          >
            Nothing saved yet. Audit a prospect and save it as a lead in Prospecting, then use
            <strong> Save to Pipeline</strong> to persist it here for real.
          </div>
        ) : (
          <div style={{ display: "grid", gap: 14 }}>
            {result.sites.map((site) => (
              <article
                key={site.site_id}
                style={{
                  background: "var(--nv-surface)",
                  border: "1px solid var(--nv-line)",
                  borderRadius: 10,
                  padding: "16px 20px",
                  boxShadow: "var(--nv-shadow)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
                  <h3 style={{ margin: 0, fontSize: 16, color: "var(--nv-text)" }}>
                    {site.business_name || "(name unavailable)"}
                  </h3>
                  <span
                    style={{
                      fontSize: 10,
                      letterSpacing: 0.5,
                      color: site.passed ? "var(--nv-metal)" : "var(--nv-text3)",
                      border: `1px solid ${site.passed ? "var(--nv-metal-dim)" : "var(--nv-line)"}`,
                      borderRadius: 5,
                      padding: "2px 7px",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {site.score != null ? `${site.score}/100` : "—"} {site.passed ? "· passed" : "· below gate"}
                  </span>
                </div>
                <div style={{ fontSize: 13, color: "var(--nv-text2)", marginTop: 4 }}>
                  {site.city || "City unknown"} · saved {formatRunAt(site.run_at)}
                </div>
                <div style={{ fontSize: 11, color: "var(--nv-text3)", marginTop: 8, fontFamily: "monospace" }}>
                  {site.site_id}
                </div>
              </article>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
