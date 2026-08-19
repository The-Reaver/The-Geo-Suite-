"""
The AI-Search Readiness rubric — the single source of truth.

Encoded once here, verbatim from `geo_platform_build/reference/GEO-optimization-standards.md`
(section "The 0 to 100 AI-Search Readiness rubric") and cross-checked against
`CRAWLER_INTELLIGENCE.md` section 3 for the documented-vs-hypothesis split.

2026-08-16, RUBRIC_WEIGHT_SOURCING_TRACE_2026-08-16.md Phase 1: `CRAWLER_INTELLIGENCE.md`
lives at the outer `stag` repo root (one level above this `geo_platform` repo's own
root), not inside this repo — a prior trace pass searching only within this repo
concluded the file didn't exist anywhere, which is wrong; it exists and every
section/subsection citation below and in audit_engine.py was verified against its
real content on 2026-08-16 and is accurate (real primary-source citations per
operator: OpenAI, Anthropic, Google, Perplexity, Apple, Microsoft, Common Crawl —
see its own section 5). Path noted here so the next reader doesn't re-run that
search and reach the same wrong conclusion.

Nothing else in the codebase may define category weights, tier bands, the publish
threshold, or the required-crawler list. If the reference document changes, change it
here and let the tests (`test_audit_engine.test_rubric_integrity`) catch drift.
"""
from __future__ import annotations

# --- Categories and weights (must sum to 100) --------------------------------
# (id, name, weight, tier_label)
#   tier_label is the category's dominant evidence tier for the report header:
#     "documented"  — operator-published or mechanically verifiable
#     "hypothesis"  — third-party inference only, no operator documentation
# Category 3 is documented overall but its llms.txt sub-check is a hypothesis; that
# split is handled per sub-check inside the engine, not here.
# Category 1 was re-tagged "hypothesis" on 2026-08-16, per a Brain Trust finding
# (Oluwole's seat, audit-engine trustworthiness review): CRAWLER_INTELLIGENCE.md
# section 3 places schema.org's effect on AI-answer citation in Tier 2, hypotheses
# under test, not documented fact — yet 13 of Category 1's 20 points (subtype
# specificity, Organization/WebSite presence, Service/FAQPage, @id linking, sameAs)
# rested entirely on that unproven claim while counted as "documented." Only the
# mechanically-verifiable sub-checks (valid JSON-LD parse, required NAP fields — 7
# of 20 points) are genuinely documented; the rest is now tagged and excluded from
# documented_subtotal per sub-check inside the engine, same pattern as Category 3.
CATEGORIES: list[tuple[int, str, int, str]] = [
    (1, "Structured Data and Schema", 20, "hypothesis"),
    (2, "Semantic HTML and Content Structure (GEO-SFE)", 20, "hypothesis"),
    (3, "AI Crawler Access and llms.txt", 12, "documented"),
    (4, "Entity Consistency and Off-Page Authority", 13, "documented"),
    (5, "Technical Performance and Core Web Vitals", 15, "documented"),
    (6, "Data Integrity", 10, "documented"),
    (7, "Actual AI Citation Presence", 10, "documented"),
]

CATEGORY_WEIGHT: dict[int, int] = {c[0]: c[2] for c in CATEGORIES}
CATEGORY_NAME: dict[int, str] = {c[0]: c[1] for c in CATEGORIES}
CATEGORY_TIER: dict[int, str] = {c[0]: c[3] for c in CATEGORIES}

TOTAL_WEIGHT = sum(c[2] for c in CATEGORIES)  # 100

# --- Tier bands (inclusive lower, inclusive upper) ---------------------------
TIER_BANDS: list[tuple[int, int, str]] = [
    (0, 39, "Poor"),
    (40, 59, "Needs Work"),
    (60, 79, "Strong"),
    (80, 100, "AI-Optimized"),
]

# --- Publish gate ------------------------------------------------------------
# Raised from 90 to 93 by direct operator ruling, 2026-08-08 GEO Brain Trust
# review, Question 1: "our gate should be 93 minimum and it should be an
# impeccable, scientific, mathematical, journalism framework... if we cannot
# give reliability in our rankings and how we come to the educated
# recommendations we give our clients, then we are FRAUDS." This overrode a
# 3-3-1 table vote split. The mechanical threshold change lands here; the
# larger ask, tracing every category weight above to a cited source or a
# stated confidence interval instead of the "internal GEO market and
# best-practice scan" GEO-optimization-standards.md currently cites, is
# still open and owned by Bink and Oluwole.
PUBLISH_THRESHOLD = 93  # normalized_score must be >= this to publish

# --- Client-facing claims pause, operator ruling 2026-08-16 -------------------
# Direct operator decision, GEO Suite session 2026-08-16 (Oluwole's ask, Brain
# Trust review on audit-engine trustworthiness): client-facing "AI-Search
# Readiness" claims pause until (a) Category 1's documented-vs-hypothesis tagging
# is corrected (done this same session, see the CATEGORIES comment above) AND
# (b) the rubric weight-sourcing gap above (open since 2026-08-08) is actually
# closed with a cited source or stated confidence interval, not just a re-tag.
# (a) is done; (b) is NOT done — this flag stays True until the operator or a
# future session closes (b) for real. Callers that present a score to a client
# (sales/report routes, the Nova demo) must check this and show the audit as
# preliminary/internal rather than a finished client-facing readiness claim.
AI_SEARCH_READINESS_CLAIMS_PAUSED = True

# --- Evidence tiers, named so sub-checks can tag themselves ------------------
DOCUMENTED = "documented"
HYPOTHESIS = "hypothesis"


# --- Crawler access authority (from CRAWLER_INTELLIGENCE.md sections 2 & 4) ---
# Every retrieval-search and user-triggered-fetcher token that a generated site
# must permit. Blocking any of these costs AI visibility.
REQUIRED_BOTS: tuple[str, ...] = (
    "OAI-SearchBot",
    "ChatGPT-User",
    "PerplexityBot",
    "Perplexity-User",
    "Claude-SearchBot",
    "Claude-User",
    "Googlebot",
    "Bingbot",
    "Applebot",
)

# The subset that fetches the instant a real person asks about the business.
# CRAWLER_INTELLIGENCE.md 1.2 / 4.2: blocking one of these is a hard fail of the
# crawler-access category, not a deduction — robots.txt cannot even control them,
# and blocking (via WAF) destroys the citation moment.
USER_TRIGGERED_FETCHERS: tuple[str, ...] = (
    "ChatGPT-User",
    "Perplexity-User",
    "Claude-User",
)

# Generic subtype that must NOT be used on its own — AI engines weight it far less.
GENERIC_LOCALBUSINESS = "LocalBusiness"


def tier_for(score: int, passed: bool | None = None) -> str:
    """Return the tier band label for a 0-100 score.

    The reference rubric's top band starts at 80 but the publish threshold is 93,
    so a site can legitimately sit in the "AI-Optimized" band and still be blocked
    (e.g. 87). Presenting "AI-Optimized" on a blocked site is misleading to an
    owner, so when `passed` is supplied and False the label carries the
    qualifier. Never report a band without its publish status.
    """
    label = "Poor" if score < 0 else "AI-Optimized"
    for lo, hi, band in TIER_BANDS:
        if lo <= score <= hi:
            label = band
            break
    if passed is False and score < PUBLISH_THRESHOLD:
        return f"{label} (below publish threshold)"
    return label


def assert_rubric_integrity() -> None:
    """Fail loudly if the encoded rubric ever drifts from a valid 100-point split."""
    if TOTAL_WEIGHT != 100:
        raise ValueError(f"rubric weights sum to {TOTAL_WEIGHT}, not 100")
    ids = [c[0] for c in CATEGORIES]
    if ids != list(range(1, 8)):
        raise ValueError(f"rubric category ids must be 1..7, got {ids}")
