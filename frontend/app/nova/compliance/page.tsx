import type { Metadata } from "next";
import Link from "next/link";
import { fetchComplianceLibrary } from "./actions";
import { NoteReview } from "./NoteReview";

// Compliance Library — 2026-08-20. Replaces NovaShell.tsx's sidebar nav item,
// which was a plain unclickable <div> with a hardcoded, fake "3 pending"
// badge: no page, no route, no backend endpoint behind it. This is the real
// thing — every raw_law/ source GEO Suite's compliance checker actually
// cites, grouped by domain, plus the real draft atomic notes vendored into
// knowledge_core/feeds/regulatory/raw_law/atomic_notes.json.
//
// 2026-08-22, mini-slice 3: real approve/reject controls (NoteReview.tsx)
// per sample note, wired to mini-slice 2's ratify/reject routes. Visible
// to any signed-in Nova user (this page's own auth gate is
// require_sales_agent, unchanged), but only actionable for a lawyer/
// owner/admin -- see actions.ts's canReview for why that check reads the
// real JWT app_metadata.role claim, not GET /auth/me.
export const metadata: Metadata = {
  title: "Compliance Library — GEO Suite",
  description: "The real law sources and draft notes the compliance checker cites against.",
};

export const dynamic = "force-dynamic"; // reads the session cookie; never static

export default async function ComplianceLibraryPage() {
  const result = await fetchComplianceLibrary();

  return (
    <div className="nova-app" data-accent="blue" style={{ display: "block", height: "auto", overflow: "visible" }}>
      <main style={{ maxWidth: 880, margin: "0 auto", padding: "40px 24px 80px" }}>
        <div style={{ marginBottom: 28 }}>
          <Link href="/nova" style={{ color: "var(--nv-text2)", fontSize: 13, textDecoration: "none" }}>
            ← Back to Nova
          </Link>
        </div>
        <h1 style={{ fontFamily: "var(--nv-serif)", fontSize: 32, margin: "0 0 8px", color: "var(--nv-text)" }}>
          Compliance Library
        </h1>
        <p style={{ color: "var(--nv-text2)", fontSize: 15, lineHeight: 1.6, maxWidth: 640, margin: "0 0 32px" }}>
          Every regulatory source the compliance checker cites against, and the real draft notes
          already pulled from each one. Every source here carries the same caveat its own document
          does: <strong>not yet lawyer-reviewed.</strong> Nothing on this page is legal advice.
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
              ? "Sign in to view the Compliance Library."
              : result.reason === "supabase-not-configured"
              ? "Backend not configured for this environment."
              : `Could not load the Compliance Library right now (${result.reason}).`}
          </div>
        ) : (
          <>
            <div style={{ display: "flex", gap: 24, marginBottom: 36, flexWrap: "wrap" }}>
              <Stat label="Sources" value={result.totalSources} />
              <Stat label="Draft notes" value={result.totalDraftNotes} />
              <Stat
                label="Lawyer-ratified"
                value={result.lawyerRatifiedCount}
                note={result.lawyerRatifiedCount === 0 ? "none yet" : undefined}
              />
              {result.orphanedNotesCount > 0 ? (
                <Stat label="Notes pending a source file" value={result.orphanedNotesCount} note="see MANIFEST.md" />
              ) : null}
            </div>

            {result.domains.map((domain) => (
              <section key={domain.domain} style={{ marginBottom: 40 }}>
                <h2
                  style={{
                    fontSize: 12,
                    letterSpacing: 2,
                    textTransform: "uppercase",
                    color: "var(--nv-text3)",
                    borderBottom: "1px solid var(--nv-line)",
                    paddingBottom: 8,
                    marginBottom: 16,
                  }}
                >
                  {domain.domain}
                </h2>
                {domain.detection_status ? (
                  <div
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: 10,
                      marginBottom: 16,
                      padding: "10px 14px",
                      borderRadius: 8,
                      background: "var(--nv-surface)",
                      border: "1px solid var(--nv-line)",
                    }}
                  >
                    <span
                      style={{
                        fontSize: 10,
                        letterSpacing: 0.5,
                        whiteSpace: "nowrap",
                        borderRadius: 5,
                        padding: "2px 7px",
                        marginTop: 1,
                        color: domain.detection_status.wired_into_publish_gate
                          ? "var(--nv-ok, #1a7f37)"
                          : domain.detection_status.has_check
                          ? "var(--nv-metal)"
                          : "var(--nv-text3)",
                        border: `1px solid ${
                          domain.detection_status.wired_into_publish_gate
                            ? "var(--nv-ok, #1a7f37)"
                            : domain.detection_status.has_check
                            ? "var(--nv-metal-dim)"
                            : "var(--nv-line)"
                        }`,
                      }}
                    >
                      {domain.detection_status.wired_into_publish_gate
                        ? "LIVE CHECK"
                        : domain.detection_status.has_check
                        ? "BUILT, NOT ENFORCED"
                        : "NO AUTOMATED CHECK"}
                    </span>
                    <p style={{ fontSize: 12.5, color: "var(--nv-text2)", lineHeight: 1.55, margin: 0 }}>
                      {domain.detection_status.note}
                    </p>
                  </div>
                ) : null}
                <div style={{ display: "grid", gap: 14 }}>
                  {domain.sources.map((source) => (
                    <article
                      key={source.file}
                      style={{
                        background: "var(--nv-surface)",
                        border: "1px solid var(--nv-line)",
                        borderRadius: 10,
                        padding: "16px 20px",
                        boxShadow: "var(--nv-shadow)",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12 }}>
                        <h3 style={{ margin: 0, fontSize: 16, color: "var(--nv-text)" }}>{source.law}</h3>
                        <span
                          style={{
                            fontSize: 10,
                            letterSpacing: 0.5,
                            color: "var(--nv-metal)",
                            border: "1px solid var(--nv-metal-dim)",
                            borderRadius: 5,
                            padding: "2px 7px",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {source.note_count} draft note{source.note_count === 1 ? "" : "s"}
                        </span>
                      </div>
                      <div style={{ fontSize: 13, color: "var(--nv-text2)", marginTop: 4 }}>{source.citation}</div>
                      <p style={{ fontSize: 13.5, color: "var(--nv-text2)", lineHeight: 1.55, margin: "10px 0" }}>
                        {source.relevance}
                      </p>
                      <div style={{ fontSize: 11.5, color: "var(--nv-text3)", marginBottom: source.sample_notes.length ? 10 : 0 }}>
                        {source.source_url ? (
                          <a href={source.source_url} target="_blank" rel="noreferrer" style={{ color: "var(--nv-accent)" }}>
                            Source ↗
                          </a>
                        ) : (
                          "No direct source URL on file"
                        )}
                        {" · "}
                        {source.verification_status}
                      </div>
                      {source.sample_notes.length ? (
                        <details>
                          <summary style={{ cursor: "pointer", fontSize: 12.5, color: "var(--nv-accent)" }}>
                            Sample notes ({source.note_count})
                          </summary>
                          <ul style={{ margin: "10px 0 0", paddingLeft: 0 }}>
                            {source.sample_notes.map((note) => (
                              <NoteReview
                                key={note.id}
                                noteId={note.id}
                                body={note.body}
                                initialStatus={note.status}
                                canReview={result.canReview}
                              />
                            ))}
                          </ul>
                        </details>
                      ) : null}
                    </article>
                  ))}
                </div>
              </section>
            ))}
          </>
        )}
      </main>
    </div>
  );
}

function Stat({ label, value, note }: { label: string; value: number; note?: string }) {
  return (
    <div>
      <div style={{ fontFamily: "var(--nv-num)", fontSize: 26, color: "var(--nv-text)" }}>{value}</div>
      <div style={{ fontSize: 11, letterSpacing: 1, textTransform: "uppercase", color: "var(--nv-text3)" }}>
        {label}
        {note ? <span style={{ display: "block", textTransform: "none", letterSpacing: 0 }}>{note}</span> : null}
      </div>
    </div>
  );
}
