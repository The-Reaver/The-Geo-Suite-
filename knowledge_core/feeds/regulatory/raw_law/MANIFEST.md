# Raw Law Staging — Manifest

Federal and California tiers staged 2026-08-15. Operator-supplied primary sources added same day,
upgrading two previously weak files and adding three new ones for the AI-visibility domain.

Every file here is source text only — nothing here is a legal conclusion. Layer 2 (the raw-to-notes
converter) has already run once against an earlier version of this folder (52 notes, all `draft`,
live in Supabase) — the files changed in this pass (02, 04, new 17-19) have not yet been re-run
through the converter; that's the next action.

| # | File | Domain | Retrieval | Priority for lawyer re-check |
|---|---|---|---|---|
| 01 | ftc-act-section-5-15-usc-45.md | Medical marketing | Direct fetch, verbatim | Low |
| 02 | ftc-health-products-compliance-guidance.md | Medical marketing | **Operator-supplied real PDF, verbatim** | Low — upgraded from search-synthesized |
| 03 | 16-cfr-255-endorsement-guides.md | Medical marketing | Direct fetch, verbatim | Low |
| 04 | fda-hbot-consumer-update.md | Medical marketing | **Operator-supplied real document, verbatim** | Low — upgraded from search-synthesized; still the single most directly applicable source for the two demo businesses |
| 05 | 21-cfr-801-device-labeling.md | Medical marketing | Direct fetch, verbatim (partial — §801.5 only) | Low |
| 06 | hipaa-privacy-rule-45-cfr-164.md | Patient privacy | Direct fetch, verbatim (partial) | Medium — open question: are either business a covered entity at all |
| 07 | ftc-health-breach-notification-rule-16-cfr-318.md | Patient privacy | Direct fetch, partial (missing §318.2 definitions) | Medium |
| 08 | tcpa-47-usc-227.md | Patient privacy / lead-contact | Direct fetch, verbatim | Low |
| 09 | can-spam-act-15-usc-7704.md | Patient privacy / lead-contact | Direct fetch, verbatim | Low |
| 10 | ftc-ai-claims-guidance.md | AI-visibility | Search-synthesized, URL confirmed real but unreachable | Low priority now — superseded as lead source by 17/18 |
| 11 | nist-ai-rmf.md | AI-visibility | Direct fetch, verbatim | Low |
| 12 | ca-bpc-17500-false-advertising.md | Medical marketing (CA) | Direct fetch, verbatim | Low |
| 13 | ca-bpc-17200-unfair-competition.md | Medical marketing (CA) | Direct fetch, verbatim | Low |
| 14 | ca-civil-code-56-cmia.md | Patient privacy (CA) | Direct fetch, verbatim (partial — 2 of 24 disclosure scenarios) | Medium |
| 15 | ca-civil-code-1798-ccpa-cpra.md | Patient privacy (CA) | Direct fetch, verbatim | Low |
| 16 | ca-hbot-facility-and-unlicensed-practice.md | Medical marketing (CA) | Mixed — see file | **High — corrects a speculative claim in the ingestion plan; §87897's HBOT-specific applicability unconfirmed** |
| 17 | ftc-v-workado-complaint.md | AI-visibility | **Operator-supplied real PDF, verbatim** | Low — real adjudicated matter, strong source |
| 18 | ftc-v-workado-decision-and-order.md | AI-visibility | **Operator-supplied real PDF, verbatim** | Low — real adjudicated matter, strong source |
| 19 | ftc-comment-copyright-office-ai.md | AI-visibility | **Operator-supplied real PDF, verbatim** | Low — also surfaces 5 more real, uningested source URLs for a future pass |
| 20 | ca-title22-oxygen-administration-and-nfpa99.md | Medical marketing (CA) | Direct fetch, verbatim | Medium — HBOT-specific applicability of §87897 still unconfirmed |

## 2026-08-15 upgrade note

The operator supplied 9 real documents (a Word/markdown export of an FDA letter, and 8 PDFs)
directly, closing the two highest-priority re-check flags from the first pass (files 02 and 04) and
adding a genuinely stronger AI-visibility source than existed before (a real, adjudicated FTC
enforcement matter — *FTC v. Workado, LLC, f/k/a Content At Scale AI*, Docket No. C-4822 — rather
than a single inaccessible blog post). File 10 is kept as a secondary reference, not removed, since
its URL is now independently confirmed real (cited in file 19's own footnotes) even though still
unreachable directly.

**Not yet re-run through the Layer 2 converter.** The 52 notes already in Supabase reflect the
*previous* versions of files 02 and 04 (search-synthesized) — they should be superseded by re-running
`ingest_raw_law.py`, which will add new notes from the upgraded content; the old, weaker notes from
the prior versions are not automatically removed and should be flagged for the lawyer to disregard in
favor of the newer, better-sourced ones once the converter runs again.

## Retrieval note, from the first pass

Direct fetches to fda.gov and most ftc.gov pages returned HTTP 403/404 from this environment's fetch
tool. Cornell Law School's Legal Information Institute (law.cornell.edu) proved a reliable verbatim
mirror for CFR/USC text when eCFR's own host redirected through an anti-bot gateway (item 03).

## California tier note

File 16 corrects a claim from the original ingestion plan: a search for a specific, named California
enforcement action against an unlicensed HBOT "wellness spa" turned up nothing concrete. Rather than
carry that speculative claim forward as if verified, it's flagged and replaced with the real,
confirmed regulatory framework.

## 2026-08-16 fixes — the citation-mismatch and fragment-note bugs, closed

Two real defects flagged since 2026-08-15, closed this pass:

1. **File 16 mixed two sources under one `**Source:**` line.** The converter only reads a file's
   *first* Source header and applies it to every quote extracted from that file — so quotes from the
   old §87897 (oxygen administration) section were mis-tagged with the §2052 (unlicensed practice of
   medicine) URL. Fixed by splitting: file 16 now covers §2052 only; file 20 (new) covers §87897 +
   NFPA 99. One source per file is now the enforced shape.
2. **File 15's numbered-list quotes fragmented on extraction.** The original `1. > "quote text` inline
   format meant the line-based parser never matched the numbered-list line as a blockquote start, so
   the *next* line (a bare continuation) got captured alone as an orphaned fragment (e.g. `"personal
   information..."` standing as its own note). Fixed by reformatting every item's quote onto its own
   blockquote line.

**The converter itself is now idempotent** (`ingest_raw_law.py`, 2026-08-16) — it checks existing
(body, source) pairs before writing and skips duplicates, closing the gap that caused the 189-note
duplication incident on 2026-08-15. Verified: re-running after these fixes correctly skipped all 19
unchanged files (80 notes) and wrote only the 6 genuinely new/corrected notes (5 from file 15, 1 from
file 20). 5 bad notes (4 CCPA fragments, 1 mis-cited §2052/§87897 note) removed directly from
Supabase. Final count: 91 notes, all still `draft`.

## Next

- Pull the 5 uningested FTC blog post URLs surfaced in file 19, especially "Watching the detectives"
  (July 2023) — directly on-topic for AI-detection-tool marketing claims.
- Run the good-faith-adversarial-review skill against files 15/16/20's new content before lawyer
  handoff — not yet done for this specific fix.
