"use client";

/*
 * Compliance ratification mini-slice 3: the real approve/reject control
 * per note, replacing the plain <li>"note text"</li> the read-only page
 * used to render. One instance per sample note -- each carries its own
 * status/pending/error state, since a page can show 20-40 of these at
 * once (up to 3 sample notes x ~13 sources) and one note's action must
 * never disable or misreport another's.
 *
 * canReview gates whether Ratify/Reject render at all -- real enforcement
 * is core/permissions.py::require_lawyer on the backend regardless, this
 * is purely so a sales agent (who'd just get a 403) doesn't see buttons
 * that can't work for them.
 */

import { useState } from "react";
import { ratifyComplianceNote, rejectComplianceNote, type NoteStatus } from "./actions";

const STATUS_LABEL: Record<NoteStatus, string> = {
  draft: "Draft",
  ratified: "Ratified",
  rejected: "Rejected",
};

const STATUS_COLOR: Record<NoteStatus, string> = {
  draft: "var(--nv-text3)",
  ratified: "var(--nv-ok, #1a7f37)",
  rejected: "var(--nv-warn, #b91c1c)",
};

export function NoteReview({
  noteId,
  body,
  initialStatus,
  canReview,
}: {
  noteId: string;
  body: string;
  initialStatus: NoteStatus;
  canReview: boolean;
}) {
  const [status, setStatus] = useState<NoteStatus>(initialStatus);
  const [pending, setPending] = useState<"ratify" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [showReason, setShowReason] = useState(false);

  async function act(action: "ratify" | "reject") {
    if (pending) return;
    setPending(action);
    setError(null);
    const result = action === "ratify" ? await ratifyComplianceNote(noteId, reason) : await rejectComplianceNote(noteId, reason);
    setPending(null);
    if (result.ok) {
      setStatus(result.status);
      setShowReason(false);
    } else {
      setError(result.reason);
    }
  }

  return (
    <li style={{ fontSize: 13, color: "var(--nv-text2)", lineHeight: 1.5, marginBottom: 12, listStyle: "none" }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
        <span
          style={{
            fontSize: 9.5,
            letterSpacing: 0.5,
            textTransform: "uppercase",
            whiteSpace: "nowrap",
            marginTop: 2,
            padding: "1px 6px",
            borderRadius: 4,
            color: STATUS_COLOR[status],
            border: `1px solid ${STATUS_COLOR[status]}`,
          }}
        >
          {STATUS_LABEL[status]}
        </span>
        <span>&ldquo;{body}&rdquo;</span>
      </div>

      {canReview ? (
        <div style={{ marginTop: 6, marginLeft: 2 }}>
          {showReason ? (
            <input
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Reason (optional)"
              maxLength={2000}
              style={{
                fontSize: 12,
                padding: "4px 8px",
                borderRadius: 6,
                border: "1px solid var(--nv-line)",
                marginBottom: 6,
                width: "100%",
                maxWidth: 360,
                display: "block",
              }}
            />
          ) : null}
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <button
              type="button"
              onClick={() => act("ratify")}
              disabled={pending !== null}
              style={{
                fontSize: 11.5,
                fontWeight: 600,
                color: "var(--nv-ok, #1a7f37)",
                background: "none",
                border: "1px solid var(--nv-ok, #1a7f37)",
                borderRadius: 6,
                padding: "3px 10px",
                cursor: pending ? "wait" : "pointer",
              }}
            >
              {pending === "ratify" ? "Ratifying…" : "Ratify"}
            </button>
            <button
              type="button"
              onClick={() => act("reject")}
              disabled={pending !== null}
              style={{
                fontSize: 11.5,
                fontWeight: 600,
                color: "var(--nv-warn, #b91c1c)",
                background: "none",
                border: "1px solid var(--nv-warn, #b91c1c)",
                borderRadius: 6,
                padding: "3px 10px",
                cursor: pending ? "wait" : "pointer",
              }}
            >
              {pending === "reject" ? "Rejecting…" : "Reject"}
            </button>
            <button
              type="button"
              onClick={() => setShowReason((v) => !v)}
              style={{ fontSize: 11, color: "var(--nv-text3)", background: "none", border: "none", cursor: "pointer" }}
            >
              {showReason ? "Hide reason" : "Add reason"}
            </button>
          </div>
          {error ? (
            <div style={{ fontSize: 11.5, color: "var(--nv-warn, #b91c1c)", marginTop: 4 }}>{error}</div>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}
