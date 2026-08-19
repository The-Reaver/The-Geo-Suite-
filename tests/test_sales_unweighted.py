"""Standalone tests for unweighted sales tools (schema / preview / proposal)."""
import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ not in sys.path:
    sys.path.insert(0, PROJ)
BACKEND = os.path.join(PROJ, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.services.platform_registry import render_claim  # noqa: E402
from app.services.sales.schema_inspector import (  # noqa: E402
    inspect_as_ai,
    inspect_proposed_jsonld,
    render_comparison,
)
from app.services.sales.preview_delivery import (  # noqa: E402
    clear_preview_store,
    create_preview,
    preview_status,
    record_open,
)
from app.services.sales.proposal_generator import build_proposal  # noqa: E402

COMPLIANT_HTML = """<!DOCTYPE html>
<html lang="en">
<head><title>Thrive HBOT Clinic</title>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"MedicalClinic","name":"Thrive HBOT",
 "telephone":"303-555-0100","url":"https://thrivehbot.com",
 "address":{"@type":"PostalAddress","streetAddress":"100 Main St"}}
</script>
</head>
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
</body>
</html>"""

PHI_HTML = """<!DOCTYPE html>
<html lang="en">
<head><title>Bad</title></head>
<body>
  <h1>Clinic</h1>
  <h2>Stories</h2>
  <div class="patient-story">
    <p>Mary Johnson says HBOT helped her autism symptoms.</p>
  </div>
  <a href="/accessibility-statement">Accessibility Statement</a>
</body>
</html>"""


def test_inspect_as_ai_none_is_empty_not_placeholder():
    result = inspect_as_ai(None)
    assert result["entities"] == []
    assert result["reason"] == "no website detected"
    # Fischman primary is now RESOLVED (Zenodo DOI); still no invented site data.
    assert result["fischman_claim"]["status"] == "RESOLVED"
    assert "61.7%" in result["fischman_claim"]["display"]


def test_inspect_reads_real_jsonld_and_proposed_cannot_invent_rating():
    current = inspect_as_ai(COMPLIANT_HTML)
    assert current["local_business"] is not None, current
    assert "name" in current["local_business"]["fields"]

    proposed = inspect_proposed_jsonld([{
        "@type": "MedicalClinic",
        "name": "Thrive HBOT",
        "telephone": "303-555-0100",
        "url": "https://thrivehbot.com",
    }])
    assert proposed["has_aggregate_rating"] is False
    assert "aggregateRating" not in proposed["fields"]
    # Diff: panel fields ⊆ artifact
    assert set(proposed["fields"]) <= {
        "name", "telephone", "url",
    }

    comparison = render_comparison(current, proposed)
    assert comparison["fabrication_check"]["aggregate_rating_invented"] is False


def test_withheld_statistic_renders_marker():
    claim = render_claim("claim_local_invisible_88")
    assert claim["status"] == "WITHHELD"
    assert "[statistic withheld" in claim["display"]
    resolved = render_claim("claim_ai_consumer_local_45")
    assert resolved["status"] == "RESOLVED"
    assert "45%" in resolved["display"] or resolved["number"] == "45%"
    fisch = render_claim("claim_fischman_schema_617")
    assert fisch["status"] == "RESOLVED"
    assert "doi.org/10.5281/zenodo.18728697" in fisch["primary_url"]
    graphite = render_claim("claim_ai_asking_share_28")
    assert graphite["status"] == "RESOLVED"
    assert graphite["number"] == "28%"
    blueprint_30 = render_claim("claim_search_share_ai_30")
    assert blueprint_30["status"] == "WITHHELD"


def test_preview_expiry_returns_410_and_no_render():
    clear_preview_store()
    issued = create_preview({"html": COMPLIANT_HTML}, expires_h=1, clock=1_000)
    assert issued["ok"] is True, issued
    pid = issued["preview_id"]
    active = preview_status(pid, clock=1_000)
    assert active["status_code"] == 200
    assert active["render"] is not None
    expired = preview_status(pid, clock=1_000 + 3600)
    assert expired["status_code"] == 410, expired
    assert expired["render"] is None
    assert "expired" in expired["reason"]


def test_record_open_stores_no_ip_or_precise_location():
    clear_preview_store()
    issued = create_preview({"html": COMPLIANT_HTML}, clock=2_000)
    result = record_open(
        issued["preview_id"],
        {
            "user_agent": "Mozilla/5.0 (iPhone)",
            "ip": "203.0.113.9",
            "ip_address": "203.0.113.9",
            "latitude": 39.7,
            "longitude": -104.9,
        },
    )
    assert result["ok"] is True, result
    keys = set(result["stored_event_keys"])
    assert "ip" not in keys and "ip_address" not in keys
    assert "latitude" not in keys and "longitude" not in keys
    assert "ua_class" in keys


def test_phi_testimonial_refuses_preview_naming_phi():
    clear_preview_store()
    result = create_preview({"html": PHI_HTML})
    assert result["ok"] is False, result
    assert result["status_code"] == 403
    joined = (result.get("reason") or "") + " " + " ".join(
        str(x) for x in (result.get("blocking") or result.get("rules") or [])
    )
    assert "phi" in joined.lower() or "testimonial" in joined.lower(), joined


def test_proposal_insufficient_data_stated_and_figures_exact():
    proposal = build_proposal(
        {"name": "Thrive HBOT", "city": "Denver", "service": "HBOT", "id": "t1"},
        {"verdict": "INSUFFICIENT_DATA", "cited_engines": 0, "seen_engines": 0},
        {"lost_lo": 1900, "lost_hi": 6400, "status": "ok", "assumptions": {"t": 400}},
        {"site_id": "site-1", "audit_score": 99, "screenshots": ["s1.png"]},
        tier="growth",
        pricing_tiers={"growth": {"monthly": 2500}},
        claim_ids=["claim_ai_consumer_local_45", "claim_near_me_visit_76"],
    )
    assert proposal["ok"] is True, proposal
    assert proposal["insufficient_data"] is True
    audit_section = next(s for s in proposal["sections"] if s["id"] == "audit")
    assert audit_section["body"]["insufficient_data_statement"]
    assert "INSUFFICIENT_DATA" in audit_section["body"]["insufficient_data_statement"]

    roi_section = next(s for s in proposal["sections"] if s["id"] == "roi")
    assert roi_section["body"]["lost_lo"] == 1900
    assert roi_section["body"]["lost_hi"] == 6400

    price_section = next(s for s in proposal["sections"] if s["id"] == "pricing")
    assert price_section["body"]["price"] == {"monthly": 2500}

    claims_section = next(s for s in proposal["sections"] if s["id"] == "claims")
    statuses = {c["claim_id"]: c["status"] for c in claims_section["body"]["claims"]}
    assert statuses["claim_ai_consumer_local_45"] == "RESOLVED"
    assert statuses["claim_near_me_visit_76"] == "WITHHELD"


def test_proposal_refuses_builder_default_price():
    result = build_proposal(
        {"name": "X"},
        {"verdict": "INVISIBLE"},
        {},
        {},
        tier="growth",
        pricing_tiers={},  # operator supplied nothing
    )
    assert result["ok"] is False
    assert "operator-configured" in result["reason"]


def _run_all():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print("PASS  " + t.__name__)
            passed += 1
        except AssertionError as e:
            print("FAIL  " + t.__name__ + ": " + str(e))
        except Exception as e:
            print("FAIL  " + t.__name__ + ": " + type(e).__name__ + " " + str(e))
    print(f"\n{passed}/{len(tests)} passed")
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if _run_all() else 1)
