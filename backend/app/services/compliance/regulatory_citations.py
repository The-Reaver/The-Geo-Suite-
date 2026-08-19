"""regulatory_citations.py

Maps compliance-checker finding rules to the real, sourced law text backing
them, drawn from knowledge_core/feeds/regulatory/raw_law/ (20 files, direct
-fetch or operator-supplied primary sources -- see that folder's
MANIFEST.md for retrieval method and provenance of each one).

Every citation here points at real statute/regulation/guidance text. None
of it is a legal conclusion about any specific business: each source file
in raw_law/ is explicitly marked "Verification status: Not yet
lawyer-reviewed," and that caveat carries through to every citation
returned here. This surfaces *what law a finding relates to*, not a ruling
that a business violates it -- the same separation check_citation_records()
already enforces for citation records generally (see the module docstring
on compliance_checker.py).

wcag-* (accessibility) rules intentionally have no entries: no ADA/WCAG
legal-text file has been through the same real-retrieval process as the 20
files here, so none is cited, matching this project's own rule that an
unsourced claim is labeled as such rather than filled in.
"""
from __future__ import annotations

RAW_LAW_DIR = "knowledge_core/feeds/regulatory/raw_law"

_MARKETING_CITATIONS: list[dict] = [
    {
        "law": "FTC Act §5",
        "citation": "15 U.S.C. §45(a)",
        "file": "01-ftc-act-section-5-15-usc-45.md",
        "source_url": "https://www.law.cornell.edu/uscode/text/15/45",
        "relevance": "Prohibits unfair or deceptive acts or practices in commerce -- the core federal authority behind unsubstantiated health claims.",
    },
    {
        "law": "FTC Health Products Compliance Guidance",
        "citation": "FTC Health Products Compliance Guidance (Dec. 2022)",
        "file": "02-ftc-health-products-compliance-guidance.md",
        "source_url": None,
        "relevance": "FTC's own guidance on substantiating health-related product claims.",
    },
    {
        "law": "FDA HBOT Consumer Update",
        "citation": 'FDA, "Hyperbaric Oxygen Therapy: Get the Facts" (Aug. 25, 2025 letter to health care providers)',
        "file": "04-fda-hbot-consumer-update.md",
        "source_url": "https://www.fda.gov/medical-devices/letters-health-care-providers/follow-instructions-safe-use-hyperbaric-oxygen-therapy-devices-letter-health-care-providers",
        "relevance": "Lists the only conditions FDA has cleared HBOT to treat; the single most directly applicable source for any HBOT marketing claim.",
    },
    {
        "law": "16 CFR Part 255 — Endorsement Guides",
        "citation": "16 C.F.R. Part 255",
        "file": "03-16-cfr-255-endorsement-guides.md",
        "source_url": None,
        "relevance": "Governs testimonials and endorsements used in marketing -- relevant to PHI-testimonial findings as well as marketing-claim findings.",
    },
    {
        "law": "21 CFR §801.5 — Device Labeling",
        "citation": "21 C.F.R. §801.5",
        "file": "05-21-cfr-801-device-labeling.md",
        "source_url": None,
        "relevance": "Federal device-labeling adequate-directions-for-use requirement.",
    },
    {
        "law": "Cal. Bus. & Prof. Code §17500 — False Advertising Law",
        "citation": "Cal. Bus. & Prof. Code §17500",
        "file": "12-ca-bpc-17500-false-advertising.md",
        "source_url": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=BPC&sectionNum=17500",
        "relevance": "California's state-level false-advertising statute -- a misdemeanor, not just a civil exposure.",
    },
    {
        "law": "Cal. Bus. & Prof. Code §17200 — Unfair Competition Law",
        "citation": "Cal. Bus. & Prof. Code §17200",
        "file": "13-ca-bpc-17200-unfair-competition.md",
        "source_url": None,
        "relevance": "California's broad unfair-competition statute, frequently paired with §17500 claims.",
    },
    {
        "law": "Cal. Bus. & Prof. Code §2052 — Unlicensed Practice of Medicine",
        "citation": "Cal. Bus. & Prof. Code §2052",
        "file": "16-ca-hbot-facility-and-unlicensed-practice.md",
        "source_url": None,
        "relevance": "California-specific: the source file flags applicability to non-medical HBOT facilities as an open question, not settled.",
    },
    {
        "law": "Cal. Code Regs. tit. 22 / NFPA 99 — Oxygen Administration",
        "citation": "Cal. Code Regs. tit. 22 + NFPA 99",
        "file": "20-ca-title22-oxygen-administration-and-nfpa99.md",
        "source_url": None,
        "relevance": "HBOT-specific facility/safety standard; source file flags applicability to a given HBOT business as still unconfirmed.",
    },
]

_PHI_CITATIONS: list[dict] = [
    {
        "law": "HIPAA Privacy Rule",
        "citation": "45 C.F.R. §164.502",
        "file": "06-hipaa-privacy-rule-45-cfr-164.md",
        "source_url": "https://www.law.cornell.edu/cfr/text/45/164.502",
        "relevance": "General use/disclosure standard for protected health information. Source file flags an open, unresolved question: whether a given HBOT business even qualifies as a HIPAA \"covered entity\" at all.",
    },
    {
        "law": "FTC Health Breach Notification Rule",
        "citation": "16 C.F.R. Part 318",
        "file": "07-ftc-health-breach-notification-rule-16-cfr-318.md",
        "source_url": None,
        "relevance": "Applies to health data held by entities NOT covered by HIPAA -- the more likely applicable rule if a business isn't a HIPAA covered entity.",
    },
    {
        "law": "Cal. Civil Code §56 — Confidentiality of Medical Information Act (CMIA)",
        "citation": "Cal. Civ. Code §56 et seq.",
        "file": "14-ca-civil-code-56-cmia.md",
        "source_url": None,
        "relevance": "California's own medical-information confidentiality statute, broader than HIPAA in some respects.",
    },
    {
        "law": "Cal. Civil Code §1798 — CCPA/CPRA",
        "citation": "Cal. Civ. Code §1798.100 et seq.",
        "file": "15-ca-civil-code-1798-ccpa-cpra.md",
        "source_url": None,
        "relevance": "California's general consumer-privacy statute; applies alongside CMIA for California-based patients.",
    },
]

_RULE_PREFIX_MAP: dict[str, list[dict]] = {
    "marketing-": _MARKETING_CITATIONS,
    "phi-": _PHI_CITATIONS,
    # citation-* findings (check_citation_records()) are substantiation and
    # net-impression questions -- the same FTC Act §5 / Endorsement Guides
    # authority as marketing-* findings, just checked against a structured
    # CitationRecord instead of raw page text.
    "citation-": _MARKETING_CITATIONS,
}


def citations_for_rule(rule: str) -> list[dict]:
    """Return the real, sourced law citations relevant to a finding's rule.

    Every citation traces to a specific file in raw_law/ (see that folder's
    MANIFEST.md) -- direct-fetch or operator-supplied primary-source text,
    each explicitly marked not yet lawyer-reviewed. This surfaces what law
    a check relates to, never a claim that the business violates it.

    wcag-* rules and anything else with no mapped prefix return [] rather
    than a guessed citation.
    """
    for prefix, citations in _RULE_PREFIX_MAP.items():
        if rule.startswith(prefix):
            return citations
    return []
