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

2026-08-20: added _AI_VISIBILITY_CITATIONS and _LEAD_CONTACT_CITATIONS,
covering raw_law/'s remaining 7 files (08, 09, 10, 11, 17, 18, 19) that had
zero citation-list entries at all until now. Same honesty rule applies in
reverse here: these are mapped under ai-claims-* and lead-contact-* rule
prefixes that compliance_checker.py does not emit any findings for yet --
there is no TCPA/CAN-SPAM consent check or AI-claims-marketing check in
that module today. citations_for_rule() returning real data for a prefix
with no live caller isn't dead weight -- it's ready the moment that check
gets written, same as every other citation list here, just staged ahead of
the code that will consume it instead of behind it.
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

_LEAD_CONTACT_CITATIONS: list[dict] = [
    {
        "law": "TCPA — Telephone Consumer Protection Act",
        "citation": "47 U.S.C. §227(b)(1)",
        "file": "08-tcpa-47-usc-227.md",
        "source_url": "https://www.law.cornell.edu/uscode/text/47/227",
        "relevance": "Restricts autodialed/prerecorded calls and texts to cell phones without prior express consent -- directly relevant once outbound lead-contact features text or call a prospect.",
    },
    {
        "law": "CAN-SPAM Act",
        "citation": "15 U.S.C. §7704(a)",
        "file": "09-can-spam-act-15-usc-7704.md",
        "source_url": "https://www.law.cornell.edu/uscode/text/15/7704",
        "relevance": "Prohibits false or misleading header information and deceptive subject lines in commercial email -- relevant to any outbound lead-contact email.",
    },
]

_AI_VISIBILITY_CITATIONS: list[dict] = [
    {
        "law": 'FTC Business Guidance — "Keep your AI claims in check"',
        "citation": "FTC Business Blog (Feb. 2023)",
        "file": "10-ftc-ai-claims-guidance.md",
        "source_url": "https://www.ftc.gov/business-guidance/blog/2023/02/keep-your-ai-claims-check",
        "relevance": "FTC staff guidance applying FTC Act §5's unfair-or-deceptive standard specifically to AI marketing claims; secondary to the Workado matter (files 17-18) per that file's own note -- a real, adjudicated matter is a stronger source than blog commentary.",
    },
    {
        "law": "NIST AI Risk Management Framework (AI RMF 1.0)",
        "citation": "NIST AI RMF 1.0",
        "file": "11-nist-ai-rmf.md",
        "source_url": "https://www.nist.gov/itl/ai-risk-management-framework",
        "relevance": "Voluntary, non-binding federal AI-governance reference framework, not a source of legal liability on its own -- cited as context, not authority.",
    },
    {
        "law": "FTC v. Workado, LLC (f/k/a Content At Scale AI) — Complaint",
        "citation": "FTC Docket No. C-4822 (File No. 232-3092)",
        "file": "17-ftc-v-workado-complaint.md",
        "source_url": "https://www.ftc.gov/legal-library/browse/cases-proceedings/2323092-content-scale-ai",
        "relevance": "Real FTC enforcement action alleging unsubstantiated AI-detection-accuracy claims -- allegation only, not an adjudicated finding (Workado neither admitted nor denied); directly analogous to any AI-accuracy claim GEO Suite or a client makes.",
    },
    {
        "law": "FTC v. Workado, LLC (f/k/a Content At Scale AI) — Decision and Order",
        "citation": "FTC Docket No. C-4822 (File No. 232-3092)",
        "file": "18-ftc-v-workado-decision-and-order.md",
        "source_url": "https://www.ftc.gov/system/files/ftc_gov/pdf/ContentatScaleAI-DecisionandOrder.pdf",
        "relevance": "The binding order resolving the Workado matter: no representation about AI-detection effectiveness without competent and reliable substantiating evidence -- the general FTC Act §5 standard applied concretely to an AI-accuracy claim.",
    },
    {
        "law": 'FTC Comment to the U.S. Copyright Office, "Artificial Intelligence and Copyright"',
        "citation": "U.S. Copyright Office Docket No. 2023-6",
        "file": "19-ftc-comment-copyright-office-ai.md",
        "source_url": "https://www.ftc.gov/system/files/ftc_gov/pdf/p241200_ftc_comment_to_copyright_office.pdf",
        "relevance": "FTC's own stated position that there is no AI exemption from existing consumer-protection law -- broader competition/policy framing, not a new binding rule.",
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
    # 2026-08-20: no lead-contact-* or ai-claims-* finding exists in
    # compliance_checker.py yet -- these two prefixes stage real citations
    # ahead of the checks that will eventually emit them, same honesty
    # tradeoff as wcag-*'s empty list above, just in the other direction.
    "lead-contact-": _LEAD_CONTACT_CITATIONS,
    "ai-claims-": _AI_VISIBILITY_CITATIONS,
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
