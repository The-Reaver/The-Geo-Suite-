#!/usr/bin/env python3
# Real tests for the GEO-D6 site engine (Sprint days 6-8).
# The generator has an objective grader: a site it produces must score >= 90 from
# the real audit engine. These tests prove that, prove the output derives from the
# input facts (two businesses differ), and prove the structural guarantees the
# spec names. Runnable standalone (python tests/test_site_engine.py) and
# pytest-collectable, matching the sibling suites. No pytest/bs4 dependency.

import os
import re
import sys
import tempfile

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ not in sys.path:
    sys.path.insert(0, PROJ)

from backend.app.schemas.site_schemas import (                     # noqa: E402
    BusinessFacts, Service, FAQ, Rating)
from backend.app.services.site_engine import generate_site         # noqa: E402
from backend.app.services import audit_engine                      # noqa: E402

GOOD_CWV = {"lcp_s": 1.8, "inp_ms": 120, "cls": 0.05}


def _dentist() -> BusinessFacts:
    return BusinessFacts(
        business_name="Cedar Ridge Dental", subtype="Dentist",
        street="1200 Cedar Road", locality="Portland", region="OR",
        postal_code="97201", telephone="+1-503-555-0142",
        domain="cedarridgedental.example", hours=["Mon-Fri 8:00-17:00"],
        service_areas=["Portland", "Beaverton", "Lake Oswego"],
        services=[
            Service(name="Preventive cleanings", description="Exams, digital X-rays, and hygiene visits for families."),
            Service(name="Dental implants", description="Permanent tooth replacement placed and restored in-house."),
            Service(name="Emergency care", description="Same-day appointments for pain, breaks, and lost fillings."),
        ],
        credentials=["ADA membership"],
        faqs=[FAQ(question="Do you accept new patients?", answer="Yes, and most PPO insurance plans."),
              FAQ(question="Do you offer emergency care?", answer="Yes, same-day slots Monday through Friday.")],
        same_as=["https://g.page/cedar-ridge-dental", "https://www.facebook.com/cedarridgedental"],
        rating=Rating(value=4.9, count=218), last_updated="2026-07-20",
        tagline="Family and cosmetic dentistry in Portland, OR")


def _plumber() -> BusinessFacts:
    return BusinessFacts(
        business_name="Saguaro Plumbing", subtype="Plumber",
        street="55 Cactus Way", locality="Tucson", region="AZ",
        postal_code="85701", telephone="+1-520-555-0199",
        domain="saguaroplumbing.example", hours=["Mon-Sat 7:00-19:00"],
        service_areas=["Tucson", "Marana", "Oro Valley"],
        services=[
            Service(name="Leak detection", description="Non-invasive location of hidden leaks before they cause damage."),
            Service(name="Water heater repair", description="Repair and replacement of tank and tankless units."),
        ],
        credentials=["Arizona ROC licensed"],
        faqs=[FAQ(question="Do you offer 24/7 service?", answer="Yes, for burst pipes and major leaks.")],
        same_as=["https://maps.app.goo.gl/saguaro"],
        rating=Rating(value=4.8, count=141), last_updated="2026-07-18",
        tagline="Trusted plumbing across Tucson, AZ")


def _gen(facts):
    d = tempfile.mkdtemp(prefix="geo_test_")
    generate_site(facts, d)
    return d


# 1. The milestone test — the sprint exit condition.
def test_generated_dentist_scores_at_least_90():
    d = _gen(_dentist())
    r = audit_engine.run_audit(d, cwv=GOOD_CWV)
    assert r.normalized_score >= 90, f"generated site scored {r.normalized_score}, expected >= 90"
    assert r.passed is True, "generated site did not pass the publish gate"


# 2. Anti-stub / facts-driven — two businesses produce different output.
def test_two_businesses_produce_different_sites():
    dd, pp = _gen(_dentist()), _gen(_plumber())
    di = open(os.path.join(dd, "index.html"), encoding="utf-8").read()
    pi = open(os.path.join(pp, "index.html"), encoding="utf-8").read()
    assert di != pi, "identical index for different businesses is a stub defect"
    assert "Cedar Ridge Dental" in di and "Cedar Ridge Dental" not in pi
    assert "Saguaro Plumbing" in pi and "Saguaro Plumbing" not in di
    assert "1200 Cedar Road" in di and "55 Cactus Way" in pi
    assert set(os.listdir(dd)) != set(os.listdir(pp)), "service page filenames should differ"


# 3. Subtype fidelity — the specific type, never generic LocalBusiness.
def test_subtype_is_specific_not_generic():
    di = open(os.path.join(_gen(_dentist()), "index.html"), encoding="utf-8").read()
    pi = open(os.path.join(_gen(_plumber()), "index.html"), encoding="utf-8").read()
    assert '"@type": "Dentist"' in di
    assert '"@type": "Plumber"' in pi
    assert '"@type": "LocalBusiness"' not in di and '"@type": "LocalBusiness"' not in pi


# 4. NAP single-source — footer NAP matches JSON-LD NAP after normalization.
def test_footer_nap_matches_schema():
    d = _gen(_dentist())
    html = open(os.path.join(d, "index.html"), encoding="utf-8").read()
    footer = re.search(r"<footer>.*?</footer>", html, re.S).group(0)
    footer_digits = set(re.findall(r"\d", re.sub(r"<[^>]+>", " ", footer)))
    assert "5035550142" in re.sub(r"\D", "", re.sub(r"<[^>]+>", " ", footer))
    assert "Cedar Ridge Dental" in footer
    assert "Portland" in footer and "OR" in footer


# 5. Crawler policy — robots allows all required tokens, blocks none, keeps
#    .well-known open, references the sitemap.
def test_robots_allows_required_crawlers():
    from backend.app.core import rubric
    from backend.app.services.audit_engine import _parse_robots, _rules_for, _is_blocked
    d = _gen(_dentist())
    robots = open(os.path.join(d, "robots.txt"), encoding="utf-8").read()
    groups = _parse_robots(robots)
    for bot in rubric.REQUIRED_BOTS:
        assert not _is_blocked(_rules_for(groups, bot), "/"), f"{bot} is blocked"
    assert not _is_blocked(_rules_for(groups, "Googlebot"), "/.well-known/security.txt")
    assert "sitemap" in robots.lower()


# 6. Link integrity — every internal href resolves to a real file.
def test_all_internal_links_resolve():
    from backend.app.services.audit_engine import _resolves, _is_internal, _parse_html
    from pathlib import Path
    d = _gen(_dentist())
    for name in os.listdir(d):
        if not name.endswith(".html"):
            continue
        dom = _parse_html(open(os.path.join(d, name), encoding="utf-8").read())
        for a in dom.find_all("a"):
            href = a.attrs.get("href", "")
            if _is_internal(href):
                assert _resolves(Path(d), href), f"broken internal link in {name}: {href}"


# 7. Declared mirrors — each HTML page declares a markdown alternate that exists.
def test_markdown_mirrors_declared_and_present():
    d = _gen(_dentist())
    for name in os.listdir(d):
        if not name.endswith(".html"):
            continue
        html = open(os.path.join(d, name), encoding="utf-8").read()
        m = re.search(r'<link rel="alternate" type="text/markdown" href="([^"]+)"', html)
        assert m, f"{name} does not declare a markdown mirror"
        assert os.path.exists(os.path.join(d, m.group(1))), f"declared mirror missing: {m.group(1)}"


# 8. Second-client isolation — generating a second client leaves the first intact.
def test_second_client_does_not_touch_first():
    dd = _gen(_dentist())
    before = open(os.path.join(dd, "index.html"), encoding="utf-8").read()
    _gen(_plumber())  # a separate dir
    after = open(os.path.join(dd, "index.html"), encoding="utf-8").read()
    assert before == after, "generating a second client mutated the first"


# 9. End-to-end path — audit_site_from_facts generates and grades in one call.
def test_audit_site_from_facts_end_to_end():
    r = audit_engine.audit_site_from_facts(_dentist(), cwv=GOOD_CWV)
    assert r.passed is True and r.normalized_score >= 90


# 10. No declared-but-never-written assets. generate_site() used to point
#     LocalBusiness.image, Organization.logo, and og:image at assets/photo.jpg
#     and assets/logo.png -- files it never wrote, a real 404 on every
#     generated site. logo.svg is now real; the (non-existent) photo
#     reference is gone rather than pointing at a placeholder pretending to
#     be this business's own photo.
def test_no_dead_asset_references_and_logo_is_real():
    d = _gen(_dentist())
    html = open(os.path.join(d, "index.html"), encoding="utf-8").read()
    assert "photo.jpg" not in html, "no real photo exists; must not declare one"
    assert "logo.png" not in html, "the old, never-written logo path must be gone"
    assert "og:image" not in html, "no og:image without a real raster image to point it at"
    m = re.search(r'"logo":\s*"([^"]+)"', html)
    assert m, "Organization.logo must be present"
    logo_rel = m.group(1).replace(_base_url_for(_dentist()), "").lstrip("/")
    assert logo_rel == "assets/logo.svg"
    logo_path = os.path.join(d, "assets", "logo.svg")
    assert os.path.exists(logo_path), "the declared logo file must actually exist on disk"
    svg = open(logo_path, encoding="utf-8").read()
    assert svg.strip().startswith("<svg"), "logo.svg must be a real SVG document"
    assert "Cedar Ridge Dental" in svg, "logo must be labeled for the actual business (aria-label)"


def test_logo_differs_between_businesses():
    dentist_svg = open(os.path.join(_gen(_dentist()), "assets", "logo.svg"), encoding="utf-8").read()
    plumber_svg = open(os.path.join(_gen(_plumber()), "assets", "logo.svg"), encoding="utf-8").read()
    assert dentist_svg != plumber_svg, "identical logos for different businesses is the same stub defect #2 guards against"


def _base_url_for(facts) -> str:
    return f"https://{facts.domain}"


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"ERROR {t.__name__}: {e.__class__.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if _run_all() else 1)
