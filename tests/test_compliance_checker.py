"""Standalone compliance checker tests for verify.py --geo battery.

No pytest — __main__ runner with real N/N. Asserts specific rule/finding strings.
"""
import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ not in sys.path:
    sys.path.insert(0, PROJ)
BACKEND = os.path.join(PROJ, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.services.compliance.compliance_checker import (  # noqa: E402
    audit_site,
    check_accessibility,
    check_citation_records,
    check_marketing_claims,
    check_phi_testimonials,
    DEFAULT_ABSOLUTE_GUARANTEE_TERMS,
    DEFAULT_HIGH_RISK_TERMS,
)
from app.schemas.compliance_schemas import CitationRecord, ClaimStrength  # noqa: E402


COMPLIANT_HTML = """<!DOCTYPE html>
<html lang="en">
<head><title>Thrive HBOT Clinic</title></head>
<body>
  <h1>Hyperbaric Oxygen Therapy</h1>
  <h2>Our Services</h2>
  <p>HBOT may help support recovery. Individual results may vary.</p>
  <img src="chamber.jpg" alt="HBOT chamber interior">
  <form>
    <label for="email">Email</label>
    <input id="email" type="email" name="email">
  </form>
  <a href="/about">About our clinic</a>
  <a href="/accessibility-statement">Accessibility Statement</a>
  <div class="testimonial" data-hipaa-authorized="true">
    <p>A satisfied patient shared positive experiences.</p>
  </div>
</body>
</html>"""

FAILING_HTML = """<!DOCTYPE html>
<html>
<head><title>Bad Clinic Site</title></head>
<body>
  <h1>HBOT Miracle Center</h1>
  <h3>Skip Level Heading</h3>
  <img src="hero.jpg">
  <p>Our HBOT cures autism and reverses aging for every patient.</p>
  <form><input type="text" name="phone"></form>
  <a href="#"></a>
  <p style="color: #cccccc; background-color: #ffffff;">Low contrast text here.</p>
  <div class="patient-story">
    <p>John Smith was diagnosed with autism and says HBOT changed his life.</p>
  </div>
</body>
</html>"""


def test_compliant_site_passes_publish():
    result = audit_site(COMPLIANT_HTML, mode="publish")
    assert result["ok"] is True, "Compliant site must pass publish gate"
    assert result["blocking"] == [], f"Expected no blocking findings, got {result['blocking']}"


def test_failing_site_blocks_publish_with_named_rules():
    result = audit_site(FAILING_HTML, mode="publish")
    assert result["ok"] is False, "Failing site must block publish"
    rules = {f["rule"] for f in result["blocking"]}
    assert "wcag-lang" in rules, "Missing lang must block with wcag-lang"
    assert "wcag-alt-text" in rules, "Missing alt must block with wcag-alt-text"
    assert "wcag-accessibility-statement" in rules, "Missing a11y statement must block"
    assert "marketing-unsubstantiated-claim" in rules, "Unsubstantiated claim must block"
    assert "phi-unauthorized-testimonial" in rules, "Unauthorized testimonial must block"
    assert len(result["blocking"]) >= 5, "One blocking finding per defect class minimum"


def test_failing_site_prospect_returns_gap_and_findings():
    result = audit_site(FAILING_HTML, mode="prospect")
    assert "compliance_gap_0_100" in result
    assert "findings" in result
    gap = result["compliance_gap_0_100"]
    assert gap >= 50, f"Failing site must have high compliance gap, got {gap}"
    rules = {f["rule"] for f in result["findings"]}
    assert "wcag-alt-text" in rules
    assert "marketing-unsubstantiated-claim" in rules
    assert "phi-unauthorized-testimonial" in rules


def test_compliant_prospect_low_gap():
    result = audit_site(COMPLIANT_HTML, mode="prospect")
    gap = result["compliance_gap_0_100"]
    assert gap <= 20, f"Compliant site should have low gap, got {gap}"


def test_high_risk_terms_is_parameter():
    text = "This product cures everything instantly."
    default_findings = check_marketing_claims(text)
    assert any("cures" in f["message"] for f in default_findings)

    custom = check_marketing_claims(text, high_risk_terms=["instantly"])
    assert any("instantly" in f["message"] for f in custom)

    no_match = check_marketing_claims(text, high_risk_terms=["not-in-text"])
    assert no_match == []


def test_default_high_risk_terms_documented():
    assert "autism" in DEFAULT_HIGH_RISK_TERMS
    assert "cure" in DEFAULT_HIGH_RISK_TERMS
    assert isinstance(DEFAULT_HIGH_RISK_TERMS, list)


def test_empty_input_fails_cleanly_publish():
    result = audit_site("", mode="publish")
    assert result["ok"] is False
    assert result["blocking"][0]["rule"] == "input-empty"


def test_empty_input_fails_cleanly_prospect():
    result = audit_site("", mode="prospect")
    assert result["compliance_gap_0_100"] == 100
    assert result["findings"][0]["rule"] == "input-empty"


def test_missing_path_fails_cleanly():
    result = audit_site("/nonexistent/path/to/site.html", mode="publish")
    assert result["ok"] is False
    assert "input-missing" in result["blocking"][0]["rule"]


def test_accessibility_score_branches():
    score_ok, findings_ok = check_accessibility(COMPLIANT_HTML)
    score_bad, findings_bad = check_accessibility(FAILING_HTML)
    assert score_ok > score_bad, "Compliant HTML must score higher than failing HTML"
    assert any(f["rule"] == "wcag-alt-text" for f in findings_bad)


def test_marketing_claim_with_disclaimer_passes():
    hedged = "HBOT may help with autism. Consult your physician. Results may vary."
    findings = check_marketing_claims(hedged)
    autism_findings = [f for f in findings if "autism" in f["message"]]
    assert autism_findings == [], f"Hedged claim should not flag: {findings}"


def test_absolute_guarantee_language_flags_even_with_disclaimer():
    # A nearby citation/disclaimer rescues an ordinary unsubstantiated
    # claim (see test above) but must NOT rescue a guarantee -- that is
    # the whole point of the net-impression rule: attribution distances
    # authorship, it does not un-say a certainty.
    text = (
        "This is a permanent treatment for chronic pain, per a 2015 study. "
        "Consult your physician. Results may vary. See citation [1]."
    )
    findings = check_marketing_claims(text)
    guarantee_findings = [
        f for f in findings if f["rule"] == "marketing-unrescuable-guarantee-claim"
    ]
    assert guarantee_findings, (
        f"'permanent treatment' must be flagged regardless of nearby "
        f"evidence markers: {findings}"
    )


def test_absolute_guarantee_terms_is_parameter_and_documented():
    text = "We provide a bespoke miracle-fix session."
    default_findings = check_marketing_claims(text)
    assert not any(
        f["rule"] == "marketing-unrescuable-guarantee-claim" for f in default_findings
    )

    custom = check_marketing_claims(text, absolute_guarantee_terms=["miracle-fix"])
    assert any(
        f["rule"] == "marketing-unrescuable-guarantee-claim" for f in custom
    ), custom

    assert "guaranteed" in DEFAULT_ABSOLUTE_GUARANTEE_TERMS
    assert isinstance(DEFAULT_ABSOLUTE_GUARANTEE_TERMS, list)


def test_phi_authorized_testimonial_passes():
    html = """<html lang="en"><body>
    <div class="testimonial" data-hipaa-authorized="true">
      <p>Jane Doe recovered from chronic pain.</p>
    </div></body></html>"""
    findings = check_phi_testimonials(html)
    assert findings == [], f"Authorized testimonial should pass: {findings}"


def test_phi_named_condition_flags():
    html = """<html lang="en"><body>
    <div class="patient-story">
      <p>Mary Johnson says HBOT helped her autism symptoms.</p>
    </div></body></html>"""
    findings = check_phi_testimonials(html)
    rules = {f["rule"] for f in findings}
    assert "phi-unauthorized-testimonial" in rules
    assert "phi-identifier-in-testimonial" in rules


def _valid_citation_record(**overrides):
    """A clean CitationRecord for tests to override one field at a time."""
    fields = dict(
        study_reference="Smith et al 2024, J Ortho, DOI:10.1000/xyz",
        claim_scope="local PRP injection reduces joint inflammation in the injected joint",
        limitation="Study only examined knee joints in adults 40-65; not generalized to other joints or ages",
        applicability_boundary="adult outpatients 40-65yo, single knee injection, 3mL dose",
        claim_strength=ClaimStrength.HEDGED_OPINION,
    )
    fields.update(overrides)
    return CitationRecord(**fields)


def test_citation_record_required_fields_enforced_at_construction():
    try:
        CitationRecord(
            study_reference="x", claim_scope="y", limitation="z",
        )  # missing applicability_boundary and claim_strength
        raise AssertionError("expected construction to fail on missing required fields")
    except Exception as e:
        assert not isinstance(e, AssertionError), str(e)


def test_citation_record_whitespace_only_field_rejected():
    try:
        _valid_citation_record(limitation="   ")
        raise AssertionError("expected construction to fail on whitespace-only limitation")
    except Exception as e:
        assert not isinstance(e, AssertionError), str(e)


def test_check_citation_records_empty_list_is_not_an_error():
    assert check_citation_records([]) == [], (
        "an empty citation-record list is the correct, honest state until "
        "Phase 2 supplies real lawyer-ratified content, not an error"
    )


def test_check_citation_records_clean_record_passes():
    findings = check_citation_records([_valid_citation_record()])
    assert findings == [], f"expected no findings for a clean record, got {findings}"


def test_check_citation_records_flags_placeholder_limitation():
    record = _valid_citation_record(limitation="N/A")
    findings = check_citation_records([record])
    rules = {f["rule"] for f in findings}
    assert "citation-placeholder-limitation" in rules, findings


def test_check_citation_records_flags_limitation_copied_from_scope():
    record = _valid_citation_record(
        claim_scope="PRP reduces inflammation",
        limitation="PRP reduces inflammation",
    )
    findings = check_citation_records([record])
    rules = {f["rule"] for f in findings}
    assert "citation-limitation-equals-scope" in rules, findings


def test_check_citation_records_flags_thin_establishment_claim_boundary():
    record = _valid_citation_record(
        claim_scope="Studies show HBOT treats chronic pain",
        applicability_boundary="adults",
        claim_strength=ClaimStrength.ESTABLISHMENT_CLAIM,
    )
    findings = check_citation_records([record])
    rules = {f["rule"] for f in findings}
    assert "citation-establishment-claim-thin-boundary" in rules, findings


def test_check_citation_records_establishment_claim_with_real_boundary_passes():
    record = _valid_citation_record(
        claim_scope="Studies show HBOT treats chronic pain",
        applicability_boundary="adult outpatients, 40 sessions, 2.0 ATA, chronic lower back pain only",
        claim_strength=ClaimStrength.ESTABLISHMENT_CLAIM,
    )
    findings = check_citation_records([record])
    assert findings == [], f"expected no findings for an adequately scoped establishment claim, got {findings}"


def test_check_citation_records_flags_local_evidence_stretched_to_systemic_claim():
    # The extrapolation failure: every real study cited tested a narrow,
    # local intervention, but the claim_scope stretches that into a
    # systemic/whole-body claim the evidence never tested.
    record = _valid_citation_record(
        claim_scope="local injection reduces pain and eliminates systemic inflammation",
    )
    findings = check_citation_records([record])
    rules = {f["rule"] for f in findings}
    assert "citation-scope-extrapolation" in rules, findings


def test_check_citation_records_local_only_claim_does_not_flag_extrapolation():
    # A claim that stays within what was actually studied must not be
    # flagged -- this check is about mismatch, not about the word "local"
    # or "systemic" appearing at all.
    record = _valid_citation_record(
        claim_scope="local injection reduces inflammation in the injected joint",
    )
    findings = check_citation_records([record])
    rules = {f["rule"] for f in findings}
    assert "citation-scope-extrapolation" not in rules, findings


def test_check_citation_records_not_wired_into_audit_site_yet():
    # Phase 1 only. audit_site() must be completely unaffected by this module
    # existing, since Phase 3 (not built yet) is what wires it in.
    result = audit_site(COMPLIANT_HTML, mode="publish")
    assert result["ok"] is True
    assert result["blocking"] == []
    rules_seen = {f.get("rule", "") for f in result.get("blocking", [])}
    assert not any(r.startswith("citation-") for r in rules_seen)


def test_marketing_and_phi_findings_carry_real_legal_basis():
    result = audit_site(FAILING_HTML, mode="prospect")
    findings_by_rule = {f["rule"]: f for f in result["findings"]}

    marketing = findings_by_rule["marketing-unsubstantiated-claim"]
    assert marketing["legal_basis"], "Marketing findings must cite real law"
    laws = {c["law"] for c in marketing["legal_basis"]}
    assert "FTC Act §5" in laws
    assert "FDA HBOT Consumer Update" in laws
    for c in marketing["legal_basis"]:
        assert c["citation"], f"Citation missing statute/reg cite: {c}"
        assert c["file"], f"Citation missing source file: {c}"

    phi = findings_by_rule["phi-unauthorized-testimonial"]
    assert phi["legal_basis"], "PHI findings must cite real law"
    phi_laws = {c["law"] for c in phi["legal_basis"]}
    assert "HIPAA Privacy Rule" in phi_laws


def test_accessibility_findings_have_no_fabricated_legal_basis():
    result = audit_site(FAILING_HTML, mode="prospect")
    wcag_findings = [f for f in result["findings"] if f["rule"].startswith("wcag-")]
    assert wcag_findings, "Failing site must produce wcag findings to test against"
    for f in wcag_findings:
        assert f["legal_basis"] == [], (
            "No real ADA/WCAG source file exists in raw_law/ yet; "
            "accessibility findings must not get an invented citation."
        )


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print("PASS  " + t.__name__)
            passed += 1
        except AssertionError as e:
            print("FAIL  " + t.__name__ + ": " + str(e))
        except Exception as e:
            print("FAIL  " + t.__name__ + ": " + str(e))
    print(f"\n{passed}/{len(tests)} passed")
    if passed < len(tests):
        sys.exit(1)


if __name__ == "__main__":
    _run_all()
