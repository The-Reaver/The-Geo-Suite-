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
# 3b. _SCHEMA_MAP-derived subtypes must be recognized as specific LocalBusiness
#     subtypes by the real audit engine, not just present as a JSON-LD string.
#     audit_engine.py's own _LOCAL_BUSINESS_SUBTYPES allowlist is a second,
#     independently-maintained list of the same schema.org subtypes site_engine.py's
#     _SCHEMA_MAP/_HUMAN can emit -- these two lists had drifted (missing
#     "NailSalon"/"DaySpa"), so a real "Nail Salon" business fell back to the
#     generic-node path (is_specific_subtype=False), cascading into ~9 failed
#     Entity Consistency checks and a 76 score instead of ~99. Guards against
#     that specific drift recurring for the two _SCHEMA_MAP override entries.
def test_schema_map_override_subtypes_score_well():
    for name, subtype, domain in [
        ("Glamour Nail Bar", "Nail Salon", "glamour-nail-bar.example"),
        ("Serenity Med Spa", "Med Spa", "serenity-med-spa.example"),
    ]:
        facts = BusinessFacts(
            business_name=name, subtype=subtype,
            street="10 Beauty Ave", locality="Austin", region="TX",
            postal_code="78701", telephone="+1-512-555-0100", domain=domain,
            hours=["Mon-Fri 9:00-18:00"], service_areas=["Austin"],
            services=[
                Service(name="Signature service", description="A real, specific service with a genuine, informative description of what is offered."),
                Service(name="Second service", description="A second real, distinct service with its own genuine, informative description of the offering."),
            ],
            credentials=["Licensed professional"],
            faqs=[FAQ(question="What should I expect?", answer="A clear, professional experience tailored to your needs."),
                  FAQ(question="How do I book?", answer="Call or visit our website to schedule an appointment.")],
            same_as=["https://g.page/example-business"],
            rating=Rating(value=4.7, count=88), last_updated="2026-08-21",
            tagline="Example")
        d = _gen(facts)
        r = audit_engine.run_audit(d, cwv=GOOD_CWV)
        assert r.normalized_score >= 93, (
            f"{subtype} scored {r.normalized_score}, expected >= 93 "
            "-- likely a _LOCAL_BUSINESS_SUBTYPES/_SCHEMA_MAP drift regression"
        )
        assert r.passed is True


# 3c. Opening prose formatting -- no double commas / double spaces.
#     Found while manually verifying Slice 1's new industry-aware prose
#     (site_prose.py): p1_html's f-string already appends "," after
#     open_clause (which itself ends "... in {locality}, {region}"), so
#     every one of the 12 prose variants' p1_rest previously ALSO started
#     with a leading comma -- pre-existing (confirmed via diff against the
#     prior hardcoded template, which had the same bug), but far more
#     visible now that real, varied prose renders it. Separately,
#     _human() double-spaced any subtype that already contains a space
#     before a capital letter and isn't a literal _HUMAN key (e.g.
#     "Hair Salon" -> "hair  salon"), since its space-insertion regex
#     doesn't check for an existing space.
def test_opening_prose_has_no_double_commas_or_spaces():
    for subtype in ("Dentist", "Hair Salon", "Nail Salon", "Med Spa", "Auto Repair", "Real Estate"):
        facts = BusinessFacts(
            business_name="Example Business", subtype=subtype,
            street="1 Main St", locality="Portland", region="OR",
            postal_code="97201", telephone="+1-503-555-0142",
            domain=f"{subtype.lower().replace(' ', '-')}.example",
            hours=["Mon-Fri 8:00-17:00"], service_areas=["Portland", "Beaverton"],
            services=[Service(name="Signature Service", description="A real service description.")],
            same_as=["https://g.page/example"], rating=Rating(value=4.8, count=100),
            last_updated="2026-08-21", tagline="Example")
        html = open(os.path.join(_gen(facts), "index.html"), encoding="utf-8").read()
        idx = html.find("</script>")
        # Strip HTML comments and tags entirely (not to a space) so adjacent
        # inline elements collapse the same way a browser renders them --
        # e.g. "...OR,</strong>, serving..." must be checked as "OR,,",
        # which a naive space-substitution (or checking raw markup) would
        # miss since the two commas sit on either side of a closing tag.
        visible = re.sub(r"<!--.*?-->", "", html[idx:], flags=re.S)
        visible = re.sub(r"<[^>]+>", "", visible)
        assert ",," not in visible, f"{subtype}: double comma in rendered prose"
        low = visible.lower()
        assert "  salon" not in low and "  spa" not in low and "  repair" not in low and "  estate" not in low, (
            f"{subtype}: double space in rendered _human() text"
        )


def test_footer_nap_matches_schema():
    d = _gen(_dentist())
    html = open(os.path.join(d, "index.html"), encoding="utf-8").read()
    # 2026-08-21, Opus 5 review of Slice C.3: every template now applies
    # its own class to the shared <footer> tag site_engine.py emits
    # (previously classless, so every template's own footer CSS silently
    # matched nothing) -- match any <footer ...> opening tag, not just a
    # bare one, so this test doesn't couple to which template rendered it.
    footer = re.search(r"<footer[^>]*>.*?</footer>", html, re.S).group(0)
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


# 11. No dead font references. typography.py used to declare @font-face src
#     pointing at /assets/fonts/*.woff2 -- files no code ever wrote, a dead
#     reference on every generated site waiting on a "static asset pipeline"
#     that was never built. Now loads the same families from Google Fonts'
#     real, live CSS API instead of a local path nothing produces.
def test_no_dead_font_references():
    d = _gen(_dentist())
    html = open(os.path.join(d, "index.html"), encoding="utf-8").read()
    assert "assets/fonts" not in html, "must not reference a local font path nothing writes"
    assert ".woff2" not in html, "must not declare a local woff2 file that doesn't exist on disk"
    assert not os.path.exists(os.path.join(d, "assets", "fonts")), "no fonts dir should be created if nothing real is vendored into it"


# 12. Site Generator robustness push, Slice A: the real rating already
#     computed for JSON-LD's aggregateRating (_build_jsonld) used to be
#     the only place it appeared -- .rating/.stars CSS existed, unused, in
#     every template. Proves the number is now actually visible in the
#     rendered body, not just machine-readable, and that the trust band
#     reflects the real facts (locality, rating, review count).
def test_rating_is_visibly_rendered_not_just_in_jsonld():
    d = _gen(_dentist())
    html = open(os.path.join(d, "index.html"), encoding="utf-8").read()
    # 2026-08-21, Opus 5 review: the previous version of this test checked
    # for the digits "4.9"/"218" anywhere in the body after the JSON-LD
    # script tag -- but _stats_band_html's own trust-band text also
    # contains those exact digits, so the test could not fail even if the
    # rating <div> itself were empty, wrong, or fabricated (confirmed via
    # mutation testing: hardcoding the filled-star count to 5 regardless of
    # the real value still passed). Every assertion below is anchored
    # inside the rating element itself.
    m = re.search(r'<div class="rating">(.*?)</div>', html, re.S)
    assert m, "the real rating must render somewhere visible, not only in JSON-LD"
    rating_block = m.group(0)
    assert 'class="stars"' in rating_block
    assert 'aria-hidden="true"' in rating_block, "the decorative star glyphs must be hidden from screen readers"
    assert "★★★★★" in rating_block, "a 4.9 rating must round to 5 filled stars, not a hardcoded or wrong count"
    assert "☆" not in rating_block, "a 4.9 rating must not show any empty stars"
    assert "4.9" in rating_block, "the exact real rating value must be visible inside the rating element"
    assert "218" in rating_block and "reviews" in rating_block, \
        "the exact real review count must be visible inside the rating element"

    assert 'class="band"' in html, "a real rating must produce a visible trust band"
    assert "Trusted across Portland" in html, "the trust band must use the business's real locality"
    assert "&middot;" in html, "the trust band's separator must render as a real middle dot"
    assert "&amp;middot;" not in html, "the &middot; entity must not be double-escaped into literal text"


def test_rating_omitted_entirely_when_none():
    # No fabricated placeholder rating, ever -- same honesty gate
    # _build_jsonld's own aggregateRating already applies.
    facts = BusinessFacts(
        business_name="No Rating Yet LLC", subtype="GeneralContractor",
        street="1 First St", locality="Boise", region="ID",
        postal_code="83701", telephone="+1-208-555-0100",
        domain="noratingyet.example")
    d = _gen(facts)
    html = open(os.path.join(d, "index.html"), encoding="utf-8").read()
    assert 'class="rating"' not in html, "must never fabricate a rating when there isn't one"
    assert 'class="stars"' not in html
    assert 'class="band"' not in html, "the trust band is rating-gated -- no rating means no band"


def test_rating_omitted_when_zero_reviews():
    # 2026-08-21, Opus 5 review: count=0 wasn't gated -- a "4.9 stars"
    # badge and trust band could render with zero real reviews behind it,
    # the same fabrication risk (a claim with nothing real to back it) the
    # None-rating gate above already exists to prevent.
    facts = _dentist().model_copy(update={"rating": Rating(value=4.9, count=0)})
    d = _gen(facts)
    html = open(os.path.join(d, "index.html"), encoding="utf-8").read()
    assert 'class="rating"' not in html, "a rating with zero reviews behind it must not render a trust badge"
    assert 'class="stars"' not in html
    assert 'class="band"' not in html, "a rating with zero reviews behind it must not render a trust band"


def test_rating_schema_rejects_invalid_values():
    # 2026-08-21, Opus 5 review: Rating.value/count were unconstrained, so
    # a corrupted upstream value (a bad DB row, a malformed API payload)
    # could reach round() in _rating_html as NaN/Infinity -- a real 500 --
    # or render visibly wrong output (more than 5 filled stars for
    # value > 5, scientific notation for an absurd value, a negative star
    # count). A real rating is always 0-5 stars with a non-negative review
    # count; this is now a schema guarantee, not an assumption the
    # renderer has to defend against on its own.
    for bad_value in (float("nan"), float("inf"), float("-inf"), 5.1, -0.1, 123456789.0):
        try:
            Rating(value=bad_value, count=10)
            raise AssertionError(f"Rating accepted an invalid value: {bad_value!r}")
        except ValueError:
            pass
    try:
        Rating(value=4.9, count=-1)
        raise AssertionError("Rating accepted a negative review count")
    except ValueError:
        pass
    # Real, valid ratings must still work.
    r = Rating(value=4.9, count=218)
    assert r.value == 4.9 and r.count == 218


# 13. Site Generator robustness push, Slice B: a real location section --
#     the mandatory NAP fields already rendered in the footer, plus a real
#     no-API-key Google Maps directions link (no maps API key is
#     configured anywhere in this codebase, so an embedded map isn't
#     honestly buildable), plus the real business hours already computed
#     for JSON-LD's openingHoursSpecification but never shown to a
#     visitor until now.
def test_location_is_visibly_rendered_with_directions_and_hours():
    d = _gen(_dentist())
    html = open(os.path.join(d, "index.html"), encoding="utf-8").read()
    # 2026-08-21, Opus 5 review: the footer's own pre-existing NAP text
    # already contains this business's street/city/state/zip, so asserting
    # those strings appear anywhere in `body` passed even with a
    # completely empty <address> block -- caught by mutation testing.
    # Anchor every assertion inside the <address>...</address> block
    # itself so this test can only pass if that specific element is real.
    addr_match = re.search(r'<address>(.*?)</address>', html, re.S)
    assert addr_match, "a real address block must render"
    addr = addr_match.group(1)
    assert "1200 Cedar Road" in addr, "the real street address must be visible inside <address>"
    assert "Portland" in addr and "OR" in addr and "97201" in addr, "the real city/state/zip must be visible inside <address>"
    m = re.search(r'<a class="directions-link" href="([^"]+)"', html)
    assert m, "a real directions link must render"
    href = m.group(1)
    assert "www.google.com/maps/search" in href, "the directions link must be a real, no-API-key maps deep link"
    assert "Cedar%20Ridge%20Dental" in href, "the directions link must be built from this business's own real name, not a placeholder"
    assert "1200%20Cedar%20Road" in href, "the directions link must be built from this business's own real street, not a placeholder"
    body = html.split("</script>")[-1]
    assert "Mon-Fri 8:00-17:00" in body, "the real, exact hours string must be visible, not reparsed/reformatted"


def test_blank_hours_entries_are_filtered_not_rendered_as_empty_bullets():
    # 2026-08-21, Opus 5 review: f.hours truthiness alone ("if f.hours:")
    # let a list of only whitespace/blank strings (a realistic result of a
    # rep pasting a textarea with a trailing newline) through, rendering a
    # visible "Hours" heading over an empty, meaningless list. Real entries
    # must still render; an all-blank list must be treated as no hours at
    # all, same honesty gate as the genuinely-empty-list case.
    facts = _dentist().model_copy(update={"hours": ["", "   ", "Mon-Fri 8:00-17:00"]})
    d = _gen(facts)
    html = open(os.path.join(d, "index.html"), encoding="utf-8").read()
    assert "<li></li>" not in html, "a blank hours entry must not render as an empty bullet"
    assert "<li>  </li>" not in html and "<li>   </li>" not in html
    assert "Mon-Fri 8:00-17:00" in html, "a real hours entry alongside blank ones must still render"

    all_blank = _dentist().model_copy(update={"hours": ["", "  \t "]})
    d2 = _gen(all_blank)
    html2 = open(os.path.join(d2, "index.html"), encoding="utf-8").read()
    assert 'class="hours-list"' not in html2, "an hours list containing only blank strings must render as no hours at all"
    assert "<h3>Hours</h3>" not in html2


# 2026-08-21, Slice 2 (hero visual restructuring): _highlights_html
# replaces the second hero paragraph with a real, fact-derived component
# (services/areas/credentials) -- never fabricated. Anchored inside
# class="highlights" specifically (not the whole page), same lesson as
# test_location_is_visibly_rendered_with_directions_and_hours above --
# service/credential text already appears elsewhere on the page (prose,
# services list), so a whole-page substring check could pass even with a
# broken or empty highlights component.
def _highlights_span(html: str) -> str:
    m = re.search(r'<div class="highlights"[^>]*>(.*?)</div>', html, re.S)
    assert m, "a real highlights component must render"
    return m.group(1)


def test_highlights_content_is_real_and_correctly_gated():
    d = _gen(_dentist())
    html = open(os.path.join(d, "index.html"), encoding="utf-8").read()
    hl = _highlights_span(html)
    # _dentist() has 3 services, 3 service areas, 1 credential -- all three
    # kinds of highlight should be present.
    assert "Preventive cleanings" in hl and "Dental implants" in hl and "Emergency care" in hl, (
        "3 or fewer services should be listed by name, not summarized"
    )
    assert "3 areas served" in hl
    assert "ADA membership" in hl

    # No services at all -> the same honest fallback phrase svc_phrase
    # already uses elsewhere on the page, never an empty/missing item.
    no_services = _dentist().model_copy(update={"services": []})
    d2 = _gen(no_services)
    html2 = open(os.path.join(d2, "index.html"), encoding="utf-8").read()
    hl2 = _highlights_span(html2)
    assert "a full range of services" in hl2

    # More than 3 services -> summarized by count, not an unbounded list.
    many_services = _dentist().model_copy(update={"services": [
        Service(name=f"Service {i}", description="A real description.") for i in range(5)
    ]})
    d3 = _gen(many_services)
    html3 = open(os.path.join(d3, "index.html"), encoding="utf-8").read()
    hl3 = _highlights_span(html3)
    assert "5 services offered" in hl3
    assert "Service 0" not in hl3, "more than 3 services must be summarized, not listed"

    # No service areas / no credentials -> those items are omitted
    # entirely, never a fabricated placeholder.
    bare = _dentist().model_copy(update={"service_areas": [], "credentials": []})
    d4 = _gen(bare)
    html4 = open(os.path.join(d4, "index.html"), encoding="utf-8").read()
    hl4 = _highlights_span(html4)
    assert "served" not in hl4
    assert "ADA membership" not in hl4
    # The services item is unconditional -- still present with nothing else.
    assert "Preventive cleanings" in hl4


# 2026-08-21, Opus 5 review round 2 of Slice 2: the original test above
# never exercised the escaping path, the credentials-truncated-to-2
# boundary, or plural/singular area-count wording -- mutation-proven:
# removing _esc() entirely, widening creds[:2] to creds[:9], and changing
# "s if area_count != 1" to a hardcoded "s" all passed the full suite
# clean. Each gets its own targeted test below.
def test_highlights_escapes_html_in_service_and_credential_names():
    payload = '<img src=x onerror=alert(1)>"'
    facts = _dentist().model_copy(update={
        "services": [Service(name=payload, description="A real description.")],
        "credentials": [payload],
    })
    d = _gen(facts)
    html = open(os.path.join(d, "index.html"), encoding="utf-8").read()
    hl = _highlights_span(html)
    # "onerror=" as literal text is expected and fine once escaped -- the
    # real check is that no live "<img" TAG (an unescaped opening angle
    # bracket immediately followed by the tag name) reached the page.
    assert "<img" not in hl, "unescaped markup reached the highlights component"
    assert "&lt;img" in hl, "the service/credential name must still be visibly present, just escaped"
    assert hl.count("&lt;img") == 2, "both the service name and the credential must be escaped"


def test_highlights_credentials_truncated_to_first_two():
    facts = _dentist().model_copy(update={
        "credentials": ["Alpha Certification", "Beta License", "Gamma Accreditation"]
    })
    d = _gen(facts)
    html = open(os.path.join(d, "index.html"), encoding="utf-8").read()
    hl = _highlights_span(html)
    assert "Alpha Certification" in hl and "Beta License" in hl
    assert "Gamma Accreditation" not in hl, "more than 2 credentials must be truncated, not all listed"


def test_highlights_area_count_singular_vs_plural():
    one_area = _dentist().model_copy(update={"service_areas": ["Portland"]})
    d = _gen(one_area)
    html = open(os.path.join(d, "index.html"), encoding="utf-8").read()
    hl = _highlights_span(html)
    assert "1 area served" in hl, "exactly one area must use singular wording"
    assert "1 areas served" not in hl

    two_areas = _dentist().model_copy(update={"service_areas": ["Portland", "Beaverton"]})
    d2 = _gen(two_areas)
    html2 = open(os.path.join(d2, "index.html"), encoding="utf-8").read()
    hl2 = _highlights_span(html2)
    assert "2 areas served" in hl2, "more than one area must use plural wording"


def test_highlights_services_boundary_exactly_three_vs_four():
    three = _dentist().model_copy(update={"services": [
        Service(name=f"Svc {i}", description="A real description.") for i in range(3)
    ]})
    d = _gen(three)
    html = open(os.path.join(d, "index.html"), encoding="utf-8").read()
    hl = _highlights_span(html)
    assert "Svc 0" in hl and "Svc 1" in hl and "Svc 2" in hl, "exactly 3 services must still be listed by name"
    assert "3 services offered" not in hl

    four = _dentist().model_copy(update={"services": [
        Service(name=f"Svc {i}", description="A real description.") for i in range(4)
    ]})
    d2 = _gen(four)
    html2 = open(os.path.join(d2, "index.html"), encoding="utf-8").read()
    hl2 = _highlights_span(html2)
    assert "4 services offered" in hl2, "4 services must cross over to the count summary"
    assert "Svc 0" not in hl2


def test_highlights_has_real_list_aria_roles_and_accessible_name():
    d = _gen(_dentist())
    html = open(os.path.join(d, "index.html"), encoding="utf-8").read()
    m = re.search(r'<div class="highlights"([^>]*)>', html)
    assert m, "a real highlights div must render"
    container_attrs = m.group(1)
    assert 'role="list"' in container_attrs, "the highlights container must carry role=list"
    assert 'aria-label="Highlights"' in container_attrs, "the highlights container must have an accessible name"
    hl = _highlights_span(html)
    assert hl.count('role="listitem"') == hl.count("<span"), (
        "every highlight item must carry role=listitem, matching the container's role=list"
    )


def test_highlights_clips_unbounded_service_and_credential_names():
    # Service/credential names are free text with no length cap on
    # BusinessFacts -- an adversarially long name must not be allowed to
    # inflate this component's word count without bound, since that
    # measurably erodes the audit rubric's emphasis-density headroom.
    long_name = "A Very Long And Overly Descriptive Service Name That Goes On And On"
    facts = _dentist().model_copy(update={
        "services": [Service(name=long_name, description="A real description.")],
        "credentials": ["An Equally Long And Overly Descriptive Professional Credential Title"],
    })
    d = _gen(facts)
    html = open(os.path.join(d, "index.html"), encoding="utf-8").read()
    hl = _highlights_span(html)
    for span in re.findall(r'<span role="listitem">(.*?)</span>', hl, re.S):
        assert len(span) <= 61, f"highlight item not clipped, {len(span)} chars: {span!r}"
    assert "…" in hl, "a clipped item must end with an ellipsis, not be silently cut off"


# 2026-08-21, Opus 5 review of Slice 2: p1_html's <p> tag never carried
# class="lede" -- 7 of the 9 templates style the hero paragraph
# EXCLUSIVELY through a ".hero .lede"/".hero p.lede" CSS rule, so it
# matched nothing on any real generated page, ever. The hero paragraph
# rendered at each template's default wide `.wrap` measure (up to
# 1120px) instead of the intended ~52ch narrow reading width and muted
# color -- the actual "shorter, more scannable lede" this slice exists to
# deliver never took visual effect. Checked against REAL per-template
# render_index output (design_engine.TEMPLATES, same facts, real blocks
# from _index_main -- not the synthetic _index_blocks() fixture other
# design-variation tests use, since that fixture hardcodes a classless
# "<p>p1</p>" that would hide this exact regression).
def test_hero_paragraph_carries_lede_class_across_all_templates():
    from backend.app.services.site_engine import _F as _FactsWrapper, _index_main, _head

    facts = _dentist()
    f = _FactsWrapper(facts)
    base = f"https://{facts.domain}"
    blocks = _index_main(f, base)
    blocks["head"] = _head(f, base, base + "/", "Title", "Desc", "index.md", "{}")
    blocks["title"] = "Title"

    pal = design_engine.palettes.palette_for(facts.subtype, 0)
    typ = design_engine.typography.typography_for(0)
    for tmpl in design_engine.TEMPLATES:
        theme = design_engine.Theme(template=tmpl, palette=pal, typography=typ, hero_style="gradient")
        html = tmpl.render_index(f, base, theme, blocks)
        assert 'class="lede"' in html, f"{tmpl.name}: hero paragraph is missing class=\"lede\""


def test_hours_omitted_when_none_but_address_and_directions_remain():
    # Hours default to [] and must stay honestly gated -- never a
    # fabricated "call for hours" placeholder. The address and directions
    # link are unconditional (NAP fields are mandatory), so they must
    # still render even with no hours at all.
    facts = BusinessFacts(
        business_name="No Hours Yet LLC", subtype="GeneralContractor",
        street="1 First St", locality="Boise", region="ID",
        postal_code="83701", telephone="+1-208-555-0100",
        domain="nohoursyet.example")
    d = _gen(facts)
    html = open(os.path.join(d, "index.html"), encoding="utf-8").read()
    assert 'class="hours-list"' not in html, "must never fabricate hours when none were given"
    assert "<h3>Hours</h3>" not in html
    assert "<address>" in html, "the address must still render with no hours present"
    assert 'class="directions-link"' in html, "the directions link must still render with no hours present"


# 2026-08-21, Opus 5 review of the Slice 1 prose commit (c792e83) found 9
# real bugs; the tests below lock in each fix. The review also prompted a
# direct XSS/injection re-verification that surfaced a much broader,
# genuinely severe, PRE-EXISTING vulnerability (unescaped business_name in
# every template's <h1>/nav-brand, and a real </script> breakout via the
# JSON-LD block) -- neither introduced by this session's prose work, both
# fixed in the same pass since they were found while verifying the
# reviewer's narrower anchor-text finding.

from backend.app.services.site_engine import _human, _loc                 # noqa: E402
from backend.app.services import site_prose                               # noqa: E402
from backend.app.services.site_design import engine as design_engine      # noqa: E402


def _facts(**overrides):
    base = dict(
        business_name="Example Business", subtype="Dentist",
        street="100 Main St", locality="Portland", region="OR",
        postal_code="97201", telephone="+1-503-555-0142", domain="example.example",
        hours=["Mon-Fri 8:00-17:00"], service_areas=["Portland", "Beaverton"],
        services=[Service(name="Signature Service", description="A real service description.")],
        same_as=["https://g.page/example"], rating=Rating(value=4.8, count=100),
        last_updated="2026-08-21", tagline="Example")
    base.update(overrides)
    return BusinessFacts(**base)


# 11. Every prose variant's emphasized clause starts a NEW sentence (p2_a
#     always ends ". " before it) and must be capitalized -- all 12 were
#     lowercase before the review, rendering "...anything. getting the
#     diagnosis right..." on every generated homepage.
def test_em_clause_is_always_capitalized():
    for fam_name, fns in site_prose._FAMILIES.items():
        for fn in fns:
            _, _, _, _, p2_a, em_clause, _, _, about_em, _ = fn(
                "Example Business", "example business", "Portland, OR",
                "Portland", "Signature Service", "")
            assert p2_a.rstrip().endswith("."), f"{fam_name}/{fn.__name__}: p2_a must end a sentence"
            assert em_clause[0].isupper(), f"{fam_name}/{fn.__name__}: em_clause must start capitalized, got {em_clause[:30]!r}"


# 12. Real, end-to-end proof (not just the raw string) that the capitalized
#     em_clause actually reaches the rendered page.
def test_rendered_page_never_starts_a_sentence_lowercase_after_a_period():
    for subtype in ("Dentist", "Attorney", "Restaurant", "Hair Salon"):
        facts = _facts(subtype=subtype, domain=f"{subtype.lower().replace(' ','-')}-cap.example")
        html = open(os.path.join(_gen(facts), "index.html"), encoding="utf-8").read()
        for m in re.finditer(r"<em>(.)", html):
            assert m.group(1).isupper(), f"{subtype}: <em> clause starts lowercase: {m.group(0)!r}"


# 13. _general_1's about paragraph used to read "...are what clients bring
#     up first when they refer someone else matter more than any single
#     project" -- two finite verbs with no punctuation between them.
def test_general_1_about_paragraph_is_grammatical():
    _, _, _, _, _, _, _, about_a, about_em, about_b = site_prose._general_1(
        "Example Business", "example business", "Portland, OR", "Portland", "Signature Service", "")
    full = about_a + about_em + about_b
    assert " else matter " not in full, "still has the two-finite-verbs grammar break"
    assert about_b.lstrip().startswith(","), "about_b must continue about_em as one clause, not start a new one"


# 14. _human() must resolve _SCHEMA_MAP override keys ("HVAC", "Auto
#     Repair", "Real Estate") to their real, authored _HUMAN values instead
#     of mangling them via the regex fallback ("h v a c", "a auto repair").
def test_human_resolves_schema_map_keys_correctly():
    for subtype, expected in [
        ("HVAC", "heating and cooling company"),
        ("Auto Repair", "auto repair shop"),
        ("Real Estate", "real estate agency"),
        ("Hair Salon", "hair salon"),
        ("Nail Salon", "nail salon"),
        ("Med Spa", "med spa"),
    ]:
        assert _human(subtype) == expected, f"_human({subtype!r}) = {_human(subtype)!r}, expected {expected!r}"


# 15. site_prose.py's <a href="about.html">about {business_name}...</a>
#     interpolates business_name INSIDE the anchor's own visible text.
#     _esc_inline() used to treat the whole "<a ...>...</a>" match as a
#     pre-approved token and append it unescaped, leaving that inner text
#     -- including business_name -- injectable, even though every other
#     occurrence of business_name on the page was correctly escaped.
def test_anchor_inner_text_is_escaped_not_just_the_tag_structure():
    payload = "Acme <img src=x onerror=alert(1)> Dental"
    facts = _facts(business_name=payload, domain="anchor-injection.example")
    html = open(os.path.join(_gen(facts), "index.html"), encoding="utf-8").read()
    assert "<img src=x onerror=" not in html, "raw payload survived inside the about.html anchor text"
    assert "about.html\">about Acme &lt;img" in html, "anchor tag structure must still be literal, only its text escaped"


# 16. A genuinely severe, pre-existing, fleet-wide bug found while
#     verifying finding #15 above: every one of the 9 templates'
#     render_index()/render_about()/render_service()/render_privacy()
#     interpolated facts.business_name (and most, facts.locality) directly
#     into <h1> and the nav-brand replacement with ZERO escaping -- a real,
#     live, stored-XSS vector via business_name on every generated
#     homepage, present since these templates were first written.
def test_h1_and_nav_never_render_business_name_unescaped_across_all_templates():
    payload = "Acme <img src=x onerror=alert(document.domain)> Dental"
    seen_templates = set()
    for subtype in ("Dentist", "Plumber", "Attorney", "Hair Salon", "Restaurant", "MovingCompany"):
        for i in range(40):
            facts = _facts(business_name=payload, subtype=subtype,
                            domain=f"h1-xss-{subtype.lower().replace(' ','')}-{i}.example")
            theme = design_engine.select_theme(facts)
            seen_templates.add(theme.template.name)
            d = _gen(facts)
            html = open(os.path.join(d, "index.html"), encoding="utf-8").read()
            body_start = html.find("<body")
            body = re.sub(r"<style.*?</style>", "", html[body_start:], flags=re.S)
            assert "<img src=x onerror=" not in body, (
                f"{subtype} on template {theme.template.name}: unescaped business_name in visible body"
            )
    assert len(seen_templates) == 9, f"only exercised {len(seen_templates)}/9 templates: {seen_templates}"


# 17. A real, exploitable </script> breakout: a business_name containing a
#     literal "</script>" survived verbatim into the JSON-LD block, and a
#     browser's HTML parser treats that substring as the REAL closing tag
#     of the JSON-LD <script>, letting whatever follows (a real <script>
#     tag, in this reproduction) execute as live markup.
def test_jsonld_cannot_be_used_to_break_out_of_its_script_tag():
    payload = "Acme</script><script>alert(document.domain)</script>Dental"
    facts = _facts(business_name=payload, domain="jsonld-breakout.example")
    html = open(os.path.join(_gen(facts), "index.html"), encoding="utf-8").read()
    assert "</script><script>alert" not in html, "business_name broke out of the JSON-LD <script> tag"
    import json
    start = html.find('<script type="application/ld+json">') + len('<script type="application/ld+json">')
    end = html.find("</script>", start)
    parsed = json.loads(html[start:end])
    biz = next(n for n in parsed["@graph"] if n.get("@id", "").endswith("#business"))
    assert biz["name"] == payload, "JSON-LD must still round-trip to the real business name"


# 18. BusinessFacts.region has no min_length -- an empty region used to
#     produce visible double-comma/double-space artifacts ("in London, ,",
#     "London,  00000") in 10+ separate places across this file (titles,
#     meta descriptions, the visible <address> block, the accessibility
#     page, the about page, footer NAP, markdown mirrors). All now route
#     through one shared _loc() helper.
def test_empty_region_never_produces_double_comma_or_space_anywhere():
    facts = _facts(business_name="No Region LLC", subtype="Plumber",
                    locality="London", region="", postal_code="00000",
                    domain="no-region.example")
    d = _gen(facts)
    for name in os.listdir(d):
        path = os.path.join(d, name)
        if not (name.endswith(".html") or name.endswith(".md")):
            continue
        text = open(path, encoding="utf-8").read()
        for line in text.split("\n"):
            stripped = line.strip()
            assert "London,  " not in stripped, f"{name}: double space after London: {stripped[:120]!r}"
            assert "London, ," not in stripped, f"{name}: double comma after London: {stripped[:120]!r}"
    assert _loc(facts) == "London"


# 19. The industry_family_for() classifier used by palette/template
#     selection is deliberately coarse ("estate" -> legal_finance, "spa"/
#     "salon" -> beauty_salon) -- correct for color/layout, but prose
#     asserts specific professional facts. A "Real Estate" business landing
#     in legal_finance's prose literally said "direct access to the
#     attorney handling your case"; "Nail Salon"/"Med Spa" landing in
#     beauty_salon's hair-specific prose said "what your hair or skin can
#     actually support" and offered "a color correction." Neither business
#     type does either. A dedicated prose-only refinement (_prose_family_for)
#     routes these to their own real_estate/nail_spa families instead.
def test_real_estate_and_nail_salon_never_get_wrong_industry_prose_claims():
    forbidden = {
        "Real Estate": {"attorney", "law firm", "counsel", "legal", "case", "filed", "filings", "matter"},
        "Nail Salon": {"hair", "stylist", "haircut", "trim"},
        "Med Spa": {"hair", "stylist", "haircut", "trim"},
    }

    def visible_text(html):
        body_start = html.find("<body")
        body = html[body_start:] if body_start != -1 else html
        body = re.sub(r"<style.*?</style>", "", body, flags=re.S)
        body = re.sub(r"<script.*?</script>", "", body, flags=re.S)
        body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
        body = re.sub(r"<[^>]+>", " ", body)
        return body.lower()

    for subtype, bad_words in forbidden.items():
        for i in range(10):
            facts = _facts(subtype=subtype,
                            domain=f"wrong-industry-{subtype.lower().replace(' ','')}-{i}.example")
            html = open(os.path.join(_gen(facts), "index.html"), encoding="utf-8").read()
            text = visible_text(html)
            for w in bad_words:
                assert not re.search(r"\b" + re.escape(w) + r"\b", text), (
                    f"{subtype} seed {i}: forbidden word {w!r} found -- wrong-industry prose claim"
                )


# 20. Real, direct assertion that Real Estate/Nail Salon/Med Spa actually
#     reach their own dedicated families (not silently absorbed into the
#     general fallback, which would also pass test 19 vacuously).
def test_real_estate_and_nail_salon_route_to_their_own_families():
    assert site_prose._prose_family_for("Real Estate") == "real_estate"
    assert site_prose._prose_family_for("Nail Salon") == "nail_spa"
    assert site_prose._prose_family_for("Med Spa") == "nail_spa"
    # sanity: genuine legal/beauty subtypes still route to their real families
    assert site_prose._prose_family_for("Attorney") == "legal_finance"
    assert site_prose._prose_family_for("Hair Salon") == "beauty_salon"


# 2026-08-21, Opus 5 review round 2 (of commit b386c3e, the fix for round
# 1's 9 findings) found 5 more real bugs -- 2 critical (the XSS fixes from
# round 1 were incomplete: _esc_inline still emitted an attacker-controlled
# <a> OPENING tag raw when business_name contained its own anchor before
# the real about.html one; facts.telephone was unescaped in the nav "Call
# {phone}" text on 7 of 9 templates), 1 crash regression the round-1 fix
# introduced (_ANCHOR_RE.match() returning None -> AttributeError -> 500
# on an unpaired "<a"), 1 industry-misclassification gap inherited from a
# collision this codebase's own tests already document ("Spanish
# Restaurant" -> nail_spa via "spa" inside "Spanish"), and 1 _loc()
# truthiness bug (whitespace-only region reproduced the same artifacts
# empty region was fixed for). All fixed via a root-cause redesign
# (site_prose.py's anchor is now a sentinel marker, never literal HTML,
# eliminating the whole "detect a trusted vs. attacker anchor at runtime"
# problem) rather than another patch on the same fragile approach.

def test_attacker_anchor_in_business_name_cannot_form_a_real_tag():
    payload = 'Acme<a href="javascript:alert(1)" onmouseover="alert(document.domain)">CLICK</a>Dental'
    facts = _facts(business_name=payload, domain="attacker-anchor.example")
    html = open(os.path.join(_gen(facts), "index.html"), encoding="utf-8").read()
    # a REAL, HTML-parseable attacker tag needs a literal, unescaped "<a " --
    # substring presence of the escaped text elsewhere is not exploitable.
    assert not re.search(r'<a href="javascript:alert\(1\)"[^>]*onmouseover', html), (
        "a real, parseable attacker <a> tag survived"
    )
    # the one real about.html anchor must still render correctly
    assert '<a href="about.html">about Acme' in html


def test_unpaired_anchor_tag_in_business_name_does_not_crash_generation():
    # 2026-08-21, Opus review round 3: str hashing is PYTHONHASHSEED-
    # randomized, so a domain built from hash(payload) selected a
    # different, randomly-varying template/palette on every run -- a
    # template-specific crash would only have been caught probabilistically
    # and would not have been reproducible. A fixed, enumerated domain is
    # deterministic across runs.
    for i, payload in enumerate(('Acme <a b>c</a><a d Dental', 'A</a><a b', '<a x>y</a><a z')):
        facts = _facts(business_name=payload, domain=f"unpaired-anchor-case-{i}.example")
        _gen(facts)  # must not raise


def test_telephone_is_escaped_in_nav_call_link_across_all_templates():
    payload_phone = '+1-555-0100"><script>alert(document.domain)</script>'
    seen = set()
    for subtype in ("Dentist", "Plumber", "Attorney", "Hair Salon", "Restaurant", "MovingCompany"):
        for i in range(40):
            facts = _facts(subtype=subtype, telephone=payload_phone,
                            domain=f"tel-xss-{subtype.lower().replace(' ','')}-{i}.example")
            theme = design_engine.select_theme(facts)
            seen.add(theme.template.name)
            html = open(os.path.join(_gen(facts), "index.html"), encoding="utf-8").read()
            body_start = html.find("<body")
            body = re.sub(r"<style.*?</style>", "", html[body_start:], flags=re.S)
            assert "<script>alert(document.domain)</script>" not in body, (
                f"{subtype} on {theme.template.name}: telephone injection in nav"
            )
    assert len(seen) == 9, f"only exercised {len(seen)}/9 templates: {seen}"


def test_known_substring_collisions_route_to_the_correct_prose_family():
    # Both documented in tests/test_site_design_variation.py as accepted
    # collisions for palette/template selection -- but wrong for prose.
    assert site_prose._prose_family_for("Spanish Restaurant") == "food_restaurant"
    assert site_prose._prose_family_for("Spanish Cafe") == "food_restaurant"
    assert site_prose._prose_family_for("Corvette Repair") == "home_services"
    # genuine veterinary/legal/beauty subtypes must still route correctly
    assert site_prose._prose_family_for("VeterinaryCare") == "dental_medical"
    assert site_prose._prose_family_for("Veterinary Clinic") == "dental_medical"
    assert site_prose._prose_family_for("Real Estate") == "real_estate"
    assert site_prose._prose_family_for("Nail Salon") == "nail_spa"


def test_dent_repair_never_gets_dental_prose():
    # 2026-08-21, Opus review round 5 (finding #2): \bdent (no closing \b)
    # matched the standalone word "dent" in "Paintless Dent Repair" -- a
    # common real auto-body subtype -- which suppressed BOTH the repair
    # override and the safety net, so it kept dental_medical wholesale.
    for subtype in ("Paintless Dent Repair", "Dent Repair", "Hail Dent Repair",
                     "Mobile Dent Repair"):
        assert site_prose._prose_family_for(subtype) == "home_services", subtype
    # Real dental subtypes must be unaffected by the narrower marker.
    for subtype in ("Dentist", "DentalClinic", "Dental Lab", "Dentures Studio"):
        assert site_prose._prose_family_for(subtype) == "dental_medical", subtype

    facts = _facts(subtype="Paintless Dent Repair", business_name="Straighten Up Auto",
                    domain="dent-repair-real.example")
    html = open(os.path.join(_gen(facts), "index.html"), encoding="utf-8").read()
    body_start = html.find("<body")
    text = re.sub(r"<[^>]+>", " ", html[body_start:]).lower()
    for w in ("patient", "clinical", "treatment plan"):
        assert not re.search(r"\b" + re.escape(w) + r"\b", text), f"found forbidden word {w!r}"


def test_estate_planning_never_gets_real_estate_agency_prose():
    # 2026-08-21, Opus review round 5 (finding #3): a bare "estate" (no
    # "law"/"attorney") used to be treated as sufficient real-estate
    # evidence on its own -- "Estate Planning", a common legal-practice
    # subtype, got brokerage prose ("comparable sales", "yard sign")
    # instead of its real legal-services prose.
    assert site_prose._prose_family_for("Estate Planning") == "legal_finance"
    assert site_prose._prose_family_for("Estate Sale Company") == "legal_finance"
    # Real real-estate subtypes must still redirect correctly.
    assert site_prose._prose_family_for("Real Estate") == "real_estate"
    assert site_prose._prose_family_for("RealEstateAgent") == "real_estate"
    assert site_prose._prose_family_for("Real Estate Agent") == "real_estate"

    facts = _facts(subtype="Estate Planning", business_name="Cedar Trust Law",
                    domain="estate-planning-real.example")
    html = open(os.path.join(_gen(facts), "index.html"), encoding="utf-8").read()
    body_start = html.find("<body")
    text = re.sub(r"<[^>]+>", " ", html[body_start:]).lower()
    for w in ("comparable sales", "yard sign", "listing", "buyers and sellers"):
        assert w not in text, f"found forbidden phrase {w!r}"


def test_veterinarian_still_gets_dental_medical_prose():
    # 2026-08-21, Opus review round 5 (finding #5): the marker only checked
    # "\bvets?\b|\bveterinary\b" -- missed "Veterinarian", the more natural
    # English noun and a real regression from the commit under review
    # (before it, VeterinaryCare-style subtypes resolved via the coarse
    # classifier alone with no marker to miss).
    assert site_prose._prose_family_for("Veterinarian Clinic") == "dental_medical"
    assert site_prose._prose_family_for("VeterinarianClinic") == "dental_medical"


def test_first_gbp_rejects_non_http_schemes_and_wrong_hosts():
    # 2026-08-21, Opus review round 5 (finding #1, HIGH): _first_gbp used
    # to substring-match the whole URL string against known GBP hostnames
    # with no scheme or host check -- "javascript:alert(1)//g.page"
    # matched "g.page" as a plain substring and rendered as a live,
    # clickable javascript: link in the footer, reproduced end to end
    # through the real /sales/preview route and past the compliance gate.
    from app.services.site_engine import _first_gbp

    malicious = [
        "javascript:alert(document.domain)//g.page",
        "javascript:alert(1)//maps.app.goo.gl",
        "data:text/html,<script>alert(1)</script>#g.page",
        "//g.page/evil",  # protocol-relative, no real scheme
        "ftp://g.page/not-http",
        "https://evil.example/g.page",  # "g.page" only in the path, wrong host
        "https://evil.example/?u=google.com/maps",  # substring in query, wrong host
    ]
    for u in malicious:
        assert _first_gbp([u]) is None, f"should have rejected {u!r}"

    good = [
        "https://g.page/cedar-ridge-dental",
        "http://business.google.com/some-listing",
        "https://maps.app.goo.gl/saguaro",
        "https://www.google.com/maps/place/Cedar+Ridge",
        "https://google.com/maps?q=cedar+ridge",
    ]
    for u in good:
        assert _first_gbp([u]) == u, f"should have accepted {u!r}"

    # A malicious entry ahead of a real one must not shadow it -- the real
    # one should still be found.
    assert _first_gbp(["javascript:alert(1)//g.page", "https://g.page/real"]) == "https://g.page/real"


def test_same_as_javascript_url_never_reaches_rendered_footer():
    # The raw URL legitimately still appears inside the JSON-LD `sameAs`
    # array (declarative structured data, never executed by a browser) --
    # the real risk is only the rendered, clickable <a href> in the
    # footer, so isolate the check to the body content after </script>.
    facts = _facts(same_as=["javascript:alert(document.domain)//g.page"],
                    domain="javascript-same-as.example")
    html = open(os.path.join(_gen(facts), "index.html"), encoding="utf-8").read()
    script_end = html.rfind("</script>")
    body = html[script_end:]
    assert "javascript:" not in body, "javascript: URL reached the rendered page as a link"
    assert "See our reviews on Google" not in body, (
        "a GBP link rendered even though the only same_as entry was rejected"
    )


def test_spanish_restaurant_never_gets_nail_salon_prose():
    facts = _facts(subtype="Spanish Restaurant", business_name="Casa Iberia",
                    domain="spanish-restaurant-real.example")
    html = open(os.path.join(_gen(facts), "index.html"), encoding="utf-8").read()
    body_start = html.find("<body")
    text = re.sub(r"<[^>]+>", " ", html[body_start:]).lower()
    for w in ("nail", "sterilized", "technician", "cuticle"):
        assert not re.search(r"\b" + w + r"\b", text), f"found forbidden word {w!r}"


def test_whitespace_only_region_never_produces_double_comma_or_space():
    facts = _facts(business_name="No Region LLC", subtype="Plumber",
                    locality="London", region="   ", postal_code="00000",
                    domain="whitespace-region.example")
    assert _loc(facts) == "London"
    d = _gen(facts)
    for name in os.listdir(d):
        path = os.path.join(d, name)
        if not (name.endswith(".html") or name.endswith(".md")):
            continue
        for line in open(path, encoding="utf-8").read().split("\n"):
            stripped = line.strip()
            assert "London,  " not in stripped, f"{name}: double space: {stripped[:120]!r}"
            assert "London, ," not in stripped, f"{name}: double comma: {stripped[:120]!r}"


# 2026-08-21, Opus 5 review round 3 (of commit e8b97ef, the fix for round
# 2's 5 findings) found 3 more real bugs, 2 of them in that commit's own
# fixes: the sentinel-marker scheme e8b97ef introduced to fix the anchor-
# injection bug was itself forgeable (business_name could contain the
# literal sentinel bytes and inject its own fake anchor, and any stray
# \x01 broke assets/logo.svg's XML validity via a separate path); the
# word-boundary regex rewrite (also from e8b97ef) didn't allow plural
# forms, so "Corvette Repairs"/"Estates Agency"/"Spanish Restaurants" all
# fell through the very guards meant to catch their singular forms; and
# the _loc() strip fix created a new divergence between the visible page
# (region omitted) and the JSON-LD address (region still raw). Fixed by
# removing the marker/sentinel design entirely (the "read more" link's
# text is now a genuinely separate return value, never signaled in-band)
# plus stripping control characters at the real intake boundary
# (BusinessFacts itself) rather than trusting no renderer downstream ever
# needs to defend against them.

def test_control_characters_are_stripped_from_business_name_at_intake():
    facts = _facts(business_name="Acme \x01ABOUT_LINK_OPEN\x01 Dental",
                    domain="control-char-intake.example")
    assert "\x01" not in facts.business_name
    d = _gen(facts)
    html = open(os.path.join(d, "index.html"), encoding="utf-8").read()
    assert "\x01" not in html
    import xml.etree.ElementTree as ET
    logo = open(os.path.join(d, "assets", "logo.svg"), encoding="utf-8").read()
    ET.fromstring(logo)  # must not raise ParseError


def test_business_name_cannot_forge_extra_anchor_tags_via_sentinel_bytes():
    baseline = _facts(business_name="Riverside Family Dental", domain="anchor-baseline.example")
    baseline_html = open(os.path.join(_gen(baseline), "index.html"), encoding="utf-8").read()
    baseline_count = baseline_html.count('<a href="about.html">')

    for payload in (
        'Acme \x01ABOUT_LINK_OPEN\x01<script>alert(1)</script>\x01ABOUT_LINK_CLOSE\x01 Dental',
        'Acme \x01ABOUT_LINK_OPEN\x01 Dental',
    ):
        facts = _facts(business_name=payload, domain=f"anchor-forgery-{abs(len(payload))}.example")
        html = open(os.path.join(_gen(facts), "index.html"), encoding="utf-8").read()
        assert html.count('<a href="about.html">') == baseline_count, (
            f"forged anchor tag count for payload {payload!r}"
        )


def test_known_collisions_survive_pluralization():
    for subtype, expected in [
        ("Spanish Restaurant", "food_restaurant"),
        ("Spanish Restaurants", "food_restaurant"),
        ("Spanish Cafes", "food_restaurant"),
        ("Corvette Repair", "home_services"),
        ("Corvette Repairs", "home_services"),
        ("Real Estate", "real_estate"),
        ("Estates Agency", "real_estate"),
        ("Real Estates Group", "real_estate"),
        ("Nail Salon", "nail_spa"),
        ("Nails Salon", "nail_spa"),
        ("Day Spas", "nail_spa"),
    ]:
        got = site_prose._prose_family_for(subtype)
        assert got == expected, f"{subtype!r} -> {got!r}, expected {expected!r}"


def test_jsonld_address_region_matches_visible_page_omission():
    facts = _facts(business_name="No Region LLC", subtype="Plumber",
                    locality="London", region="   ", postal_code="00000",
                    domain="jsonld-region-consistency.example")
    html = open(os.path.join(_gen(facts), "index.html"), encoding="utf-8").read()
    import json
    start = html.find('<script type="application/ld+json">') + len('<script type="application/ld+json">')
    end = html.find("</script>", start)
    parsed = json.loads(html[start:end])
    biz = next(n for n in parsed["@graph"] if n.get("@id", "").endswith("#business"))
    assert "addressRegion" not in biz["address"], (
        "whitespace-only region must be omitted from JSON-LD, matching the visible page"
    )


# 2026-08-21, Opus 5 review round 4 (of commit 453755c, the fix for round
# 3's 3 findings) found 4 more real bugs -- the control-character
# sanitization round 3 added was bypassed entirely by the one real,
# externally-reachable route (POST /sales/preview validates through a
# separate, hand-maintained model that never inherited the new
# validators), the control-character regex missed two XML-forbidden
# noncharacters (U+FFFE/U+FFFF) and lone UTF-16 surrogates (a real,
# remote-triggerable 500), and the false-industry-claim collision class
# was still open for any word not on the two specific override lists
# ("Spanish Tapas Bar" still got hair-salon prose, "Corvette Restoration"
# still got dental prose). Fixed by reusing the same stripping helper on
# the router's own model, widening the character class, and adding a
# general safety net that falls back to industry-neutral prose whenever a
# family has no real word-level support at all, rather than trying to
# enumerate every possible synonym.

def test_sales_preview_business_facts_req_strips_control_chars():
    from app.routers.sales_preview import BusinessFactsReq
    req = BusinessFactsReq(business_name="Acme\x01Dental Co", subtype="Dentist\x01",
                            locality="Portland\x01", domain="test.example")
    assert "\x01" not in req.business_name
    assert "\x01" not in req.subtype
    assert "\x01" not in req.locality


def test_control_char_stripping_covers_noncharacters_and_surrogates():
    facts = _facts(business_name="Acme" + chr(0xFFFE) + "Dental",
                    domain="noncharacter-fffe.example")
    assert chr(0xFFFE) not in facts.business_name
    d = _gen(facts)
    import xml.etree.ElementTree as ET
    logo = open(os.path.join(d, "assets", "logo.svg"), encoding="utf-8").read()
    ET.fromstring(logo)  # must not raise

    facts2 = _facts(business_name="Acme" + chr(0xFFFF) + "Dental",
                     domain="noncharacter-ffff.example")
    assert chr(0xFFFF) not in facts2.business_name

    facts3 = _facts(business_name="Acme" + chr(0xD800) + "Dental",
                     domain="lone-surrogate.example")
    assert chr(0xD800) not in facts3.business_name
    _gen(facts3)  # must not raise UnicodeEncodeError


def test_false_industry_claims_closed_for_untested_synonym_collisions():
    # "Spanish Tapas Bar" / "Corvette Restoration" contain neither
    # "restaurant"/"cafe" nor "repair" literally, so the two specific
    # overrides never fire -- must fall back to safe, general prose
    # instead of the coarse classifier's accidental beauty_salon/
    # dental_medical guess.
    assert site_prose._prose_family_for("Spanish Tapas Bar") == "general"
    assert site_prose._prose_family_for("Corvette Restoration") == "general"
    # 2026-08-21, Opus review round 5 (finding #4): coarse lands on
    # legal_finance ("law" inside "Flawless") with no real word support
    # there, but "nails" IS real, unambiguous beauty-salon evidence in the
    # same string -- the safety net now checks every family's marker, not
    # just the (wrong) coarse guess's, so this correctly resolves to
    # nail_spa instead of settling for generic prose.
    assert site_prose._prose_family_for("Flawless Nails Studio") == "nail_spa"

    facts = _facts(subtype="Spanish Tapas Bar", business_name="Casa Iberia",
                    domain="spanish-tapas-real.example")
    html = open(os.path.join(_gen(facts), "index.html"), encoding="utf-8").read()
    body_start = html.find("<body")
    text = re.sub(r"<[^>]+>", " ", html[body_start:]).lower()
    for w in ("hair", "stylist", "nail", "sterilized"):
        assert not re.search(r"\b" + w + r"\b", text), f"found forbidden word {w!r}"


def test_safety_net_does_not_regress_real_pascalcase_schema_types():
    # PascalCase schema keys (site_engine.py's own _HUMAN dict) have no
    # internal spaces -- a naive \bmedical\b never matches inside the
    # lowercased "medicalclinic". Every one of these must still route to
    # its real family, not fall back to "general".
    #
    # 2026-08-21, Opus review round 5 (finding #6): the original version of
    # this test derived its own skip condition from
    # palettes.industry_family_for() -- part of the classification chain
    # under test -- and only asserted `!= "general"`, never the actual
    # correct family. Mutation-proven: it would still pass if HairSalon
    # started returning "food_restaurant", and would go vacuous (zero real
    # assertions) if industry_family_for() itself regressed to
    # always-general. Hardcoded the real expected family per key instead.
    expected = {
        "Dentist": "dental_medical",
        "MedicalClinic": "dental_medical",
        "Physician": "dental_medical",
        "VeterinaryCare": "dental_medical",
        "Plumber": "home_services",
        "HVACBusiness": "home_services",
        "Electrician": "home_services",
        "AutoRepair": "home_services",
        "RoofingContractor": "home_services",
        "GeneralContractor": "home_services",
        "Attorney": "legal_finance",
        "RealEstateAgent": "real_estate",
        "HairSalon": "beauty_salon",
        "BeautySalon": "beauty_salon",
        "Restaurant": "food_restaurant",
    }
    from app.services.site_engine import _HUMAN
    for key, want in expected.items():
        assert key in _HUMAN, f"{key!r} no longer a real schema key -- update this test's map"
        got = site_prose._prose_family_for(key)
        assert got == want, f"{key!r} -> {got!r}, expected {want!r}"


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
