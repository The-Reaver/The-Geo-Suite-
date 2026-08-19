# Good-faith adversarial review — 2026-08-15 sourcing upgrade batch (40 notes, files 02/04/17/18/19)

> **This is an informal, good-faith adversarial review — not the fleet's formal Brain Trust
> process.** It does not produce a `STAG_BRAIN_TRUST_LEDGER.md` entry and did not go through
> Elijah's interview/vote structure. Treat it as an extra quality pass before human review, not as
> governance sign-off.

## Summary

40 notes reviewed, 3 independent seats, no cross-contamination between them. **No fabricated
quotes and no invented citations found anywhere in the batch** — every note traces to real text in
its raw_law file. The real findings are about **framing and duplication, not fabrication**: two
duplicate-fact pairs, one silently-edited fragment, one note whose "adjudicated" framing overstates
what a Complaint actually is, one note that mixes a verbatim quote with unlabeled editorial
commentary, and a batch-wide caveat that "verbatim" here means verified against the curated
raw_law file, not independently re-verified against the live government PDF (ftc.gov blocked all
three seats' own fetch attempts, same wall this environment hit all session).

## Findings, by item

### Duplicate pair 1 — `c94260b9c36243f9b18ba9522c8c6222` vs `039eef0031d64e4ca107316edc21d0e2`
**[Seat 1 — real problem]** Same underlying FTC "competent and reliable scientific evidence"
definition, captured twice. `c94260b9` is a truncated, silently-edited fragment (drops the
defining clause "'Competent and reliable scientific evidence' means," and silently capitalizes
"tests" → "Tests" with no ellipsis marking the edit — a fragment dressed up as a clean sentence).
`039eef00` is the complete, correctly-framed version. **Recommend dropping `c94260b9`.**

### Duplicate pair 2 — `9bd26bf68ff746e784bf38a94c1c9750` vs `2570c29e45404a85a919affadcc700e4`
**[Seat 1 — worth a second look]** Same "sufficient in quality and quantity" standard, captured
twice. `9bd26bf6` is truncated (at least ellipsis-marked, less severe than pair 1). `2570c29e` is
the complete version with its lead-in intact. **Recommend dropping `9bd26bf6`.**

### `2ded0ef2000c48728f267e0df06af145` — Section 5(a) violation statement
**[Seat 2 — real problem, framing]** Text is an exact match to the Complaint. But this Complaint
was resolved by consent — per the Decision and Order's own language (read directly this session,
not assumed), Workado "neither admits nor denies any of the allegations in the Complaint." Stating
the Section 5(a) violation as settled fact, with no "as alleged" framing, overstates what actually
happened. **This is a real accuracy issue in how I (not the note itself) described file 17 in its
own header — corrected below, see "Fixed in this pass."**

### `5843d77055494e67a62874faffdc63fa` through `b96d8d7ef5fd464a851b01a51e9bb79e` — Workado's alleged conduct (accuracy claims, training data, test results)
**[Seat 2 — real problem, same root cause as above]** These are the FTC's *allegations* about what
Workado did, not judicially confirmed facts (though the underlying numbers — 98.3% claimed vs.
53.2%/74.5% actual — are drawn from the developers' own published test results per the complaint,
which is a stronger evidentiary basis than a bare allegation, but still framed as allegation in the
source document). Same fix as above applies.

### `41075a4545cd464ca0ad918dbeeaf8af` vs `fbaad162885a49d798308b0621152cd2` — two different evidence standards
**[Seat 3 — worth a second look]** The Decision and Order defines "competent and reliable
evidence" (lower bar) but never separately defines "competent and reliable **scientific**
evidence" (a higher, FTC-precedent term of art) even though the operative prohibition
(`fbaad162`) invokes both. A reader could easily assume `41075a45`'s definition covers both terms
when it only covers one. Flag for the lawyer specifically — this is exactly the kind of
term-of-art gap that matters in a compliance library.

### `e77377ed00f44950b4fa1f1574d68bc0` — "Trained on blog posts..." contradiction note
**[Seat 3 — real problem]** Mixes a verbatim ad quote with an unlabeled editorial annotation
("Contradicted by the complaint's own finding, paragraph 11...") inside the same quoted unit.
Seat 3 could not verify "paragraph 11" independently (ftc.gov blocked their fetch, and the
raw_law file itself has no paragraph numbers). **Verified directly against the actual Complaint
PDF this session (I have the full text, not just the curated file): paragraph 11 does say exactly
this** — "The developers did not fine tune the AI Model using any non-academic content, such as
Wikipedia entries or blog posts." The citation is accurate, but the raw_law file doesn't carry
enough structure for anyone else to check that independently — a real gap, not a fabrication.
**Follow-up, not fixed this pass:** split this into a bare verbatim quote plus a separately-labeled
sourced note.

### `491f8f942524480e87859a8b0afd672e` — mandatory customer notice
**[Seat 3 — worth a second look, minor]** Reads as a voluntary first-person company statement
("We claimed... We've stopped...") with nothing in the note itself flagging this is FTC-*compelled*
corrective speech Workado was ordered to send, not a spontaneous admission. Context-loss risk if
ever surfaced standalone.

### `515fed3de1944e8abf7396b932cab85b` and `5843d77055494e67a62874faffdc63fa` — internal unmarked ellipses
**[Seat 2 — nitpick]** Both contain a mid-quote `...` splicing non-adjacent source sentences. The
elision is already present in the raw_law file (not introduced fresh by note extraction), so each
note is faithful to what's staged — flagged as a general practice note, not a defect in these two
specifically.

### Batch-wide caveat — verification chain stops one hop short of the primary source
**[Seat 2 and Seat 3, independently, same finding]** Every "no issue found" verdict in this review
means the note matches its raw_law markdown file — not that the raw_law file was independently
re-verified against the live FTC/FDA PDF by the reviewing seat. All three seats confirmed ftc.gov
blocks automated fetching (three fresh 403s during this review), matching this environment's own
experience all session. This isn't a defect that was found; it's an honest limit on what this
review can attest to, worth stating plainly to the lawyer rather than implying a stronger
verification chain than actually exists.

## Items with no findings (28 of 40)

All 5 FDA notes, 9 of 16 FTC guidance notes, 7 of 9 Complaint notes, 3 of 5 Decision and Order
notes, and all 5 Copyright Office comment notes — verified verbatim against their raw_law source
with no issue of any severity. Named explicitly rather than silently omitted: `3d631237`,
`7b23cdfd`, `f1c2fa4e`, `038617ec`, `3e311d27`, `ef9bdcee`, `4c722c7d`, `ea4e60fb`, `aafb2983`,
`1987f4c7`, `7727358`, `e44e4b3f`, `933d5115`, `b7447262`, `9aa49801`, `3172c5c8`, `e83dca03`,
`31186756`, `b42f6e59`, `7f32c5e6`, `0eab56f3`, `b96d8d7e`, `40e5c5d0`, `81aa9418`, `1c1c7055`,
`f70d4c51`, `66aac55b`, `920da584`, `00e1c04f`.

## Fixed in this pass

Corrected file 17's own header claim ("a real, adjudicated enforcement matter") to accurately
describe it as a Complaint resolved by consent order — Workado neither admitted nor denied the
allegations, per the Decision and Order's own language. This is a factual correction to my own
prior file-header claim, verified directly against text already read in full this session, not a
legal judgment call.

## Not fixed this pass, flagged for the lawyer / next session

- Drop or clearly subordinate the two truncated duplicate notes (`c94260b9`, `9bd26bf6`).
- Add paragraph numbers (or a direct pin-cite) to the raw_law Complaint file so citations like
  "paragraph 11" are independently checkable from the file alone.
- Consider whether the Knowledge Core's note schema needs a document-type field (complaint vs.
  consent order vs. final judgment vs. guidance) so downstream product surfaces can distinguish
  "alleged" from "established" automatically, rather than relying on each note's prose to carry
  that distinction.

---

> **This is an informal, good-faith adversarial review — not the fleet's formal Brain Trust
> process.** It does not produce a `STAG_BRAIN_TRUST_LEDGER.md` entry and did not go through
> Elijah's interview/vote structure. Treat it as an extra quality pass before human review, not as
> governance sign-off.
