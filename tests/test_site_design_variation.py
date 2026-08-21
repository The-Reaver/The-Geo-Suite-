"""Standalone design-variation test for verify.py battery.

Tests determinism, variation, WCAG contrast, and template coverage of the
site_design engine. No pytest — standalone-runnable with a __main__ runner.
"""
import os
import sys
import types
import tempfile

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ not in sys.path:
    sys.path.insert(0, PROJ)
BACKEND = os.path.join(PROJ, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.services.site_engine import generate_site
from app.services.site_design import engine, palettes
from app.services.site_design.engine import Theme


def _F(**kwargs):
    return types.SimpleNamespace(**kwargs)


GOOD_CWV = {"lcp_s": 1.8, "inp_ms": 120, "cls": 0.05}


def test_deterministic_seed_generation():
    f1 = _F(business_name="Acme Plumbing", domain="acme.com", subtype="Plumber")
    f2 = _F(business_name="Acme Plumbing", domain="acme.com", subtype="Plumber")
    f3 = _F(business_name="Zen Dental", domain="zen.com", subtype="Dentist")

    assert engine.compute_seed(f1) == engine.compute_seed(f2), "Same facts must give same seed"
    assert engine.compute_seed(f1) != engine.compute_seed(f3), "Different facts must give different seed"


def test_palettes_wcag_contrast():
    for seed in range(20):
        p = palettes.palette_for("Hair Salon", seed)

        def luminance(hex_col):
            hex_col = hex_col.lstrip("#")
            if len(hex_col) == 3:
                hex_col = "".join(c + c for c in hex_col)
            r, g, b = (int(hex_col[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

            def srgb(c):
                return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

            return 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b)

        l1, l2 = luminance(p.ink), luminance(p.bg)
        bright, dark = max(l1, l2), min(l1, l2)
        cr = (bright + 0.05) / (dark + 0.05)
        assert cr >= 4.5, f"Contrast {cr:.2f} < 4.5 for ink={p.ink} bg={p.bg}"


def test_variation_across_businesses():
    businesses = [
        ("Alpha Dental", "alpha.com", "Dentist"),
        ("Beta Plumbers", "beta.com", "Plumber"),
        ("Gamma Legal", "gamma.com", "Attorney"),
        ("Delta Foods", "delta.com", "Restaurant"),
        ("Epsilon Spa", "epsilon.com", "BeautySalon"),
        ("Zeta Hair", "zeta.com", "Hair Salon"),
        ("Eta Real Estate", "eta.com", "Real Estate"),
        ("Theta Repair", "theta.com", "Auto Repair"),
        ("Iota Heating", "iota.com", "HVAC"),
        ("Kappa Vet", "kappa.com", "VeterinaryCare"),
        ("Lambda Movers", "lambda.com", "MovingCompany"),
        ("Mu Nails", "mu.com", "Nail Salon"),
    ]

    templates_seen = set()
    palettes_seen = set()

    # No has_photos here on purpose -- that field doesn't exist on the real
    # BusinessFacts schema (see test_bold_cinematic_is_reachable_for_real_facts
    # below for why that matters), so this must prove variation under the
    # same shape of facts select_theme() actually gets in production.
    for name, domain, subtype in businesses:
        f = _F(business_name=name, domain=domain, subtype=subtype)
        theme = engine.select_theme(f)
        templates_seen.add(str(theme.template))
        palettes_seen.add(theme.palette.name)

    assert len(templates_seen) >= 3, f"Expected >= 3 templates, got {len(templates_seen)}: {templates_seen}"
    assert len(palettes_seen) >= 4, f"Expected >= 4 palettes, got {len(palettes_seen)}: {palettes_seen}"


# 2026-08-20: has_photos is not a field on the real BusinessFacts schema and
# is never set anywhere in the real backend -- only ever True in test
# fixtures. select_theme() used to gate template choice on it, so every real,
# production-generated site silently took the "no photos" branch and never
# reached bold_cinematic, no matter what business it was generating for.
# This proves bold_cinematic is genuinely reachable now, using facts shaped
# exactly like what select_theme() gets for a real site (no has_photos at
# all), not facts hand-crafted to exercise a code path that never runs live.
def test_bold_cinematic_is_reachable_for_real_facts():
    found = False
    for i in range(200):
        f = _F(business_name=f"Business {i}", domain=f"biz{i}.example", subtype="Plumber")
        theme = engine.select_theme(f)
        if theme.template.name == "Bold Cinematic":
            found = True
            break
    assert found, "Bold Cinematic must be reachable for facts with no has_photos field at all"


def test_generate_site_with_variations():
    f = _F(
        business_name="Acme Plumbing",
        domain="acme.com",
        subtype="Plumber",
        locality="Austin",
        region="TX",
        postal_code="78701",
        country="US",
        telephone="555-0100",
        street="123 Main St",
        services=[types.SimpleNamespace(name="Fixing leaks", description="We fix them.")],
        service_areas=["Austin"],
        same_as=[],
        hours=["Mon-Fri 8-5"],
        faqs=[],
        credentials=[],
        last_updated="2026-07-25",
        tagline="Quality plumbing",
        has_photos=False
    )
    with tempfile.TemporaryDirectory() as tmp:
        generate_site(f, tmp)
        assert os.path.exists(os.path.join(tmp, "index.html")), "index.html missing"
        with open(os.path.join(tmp, "index.html")) as fh:
            html = fh.read()
            assert "Acme Plumbing" in html, "Business name missing from HTML"


# 2026-08-20: split_modern/bold_cinematic's render_service (and, through it,
# render_about/render_privacy) used to import and call editorial_minimal's
# own render_service directly -- which injects *editorial_minimal's own*
# CSS_BASE via its own _apply_css, not the calling template's. A "Split
# Modern" or "Bold Cinematic" home page linked to every interior page
# rendered in Editorial Minimal's CSS entirely, a real theme break on every
# click past the homepage, not just "less varied." Forces each template
# directly (bypassing hash-based selection) rather than hunting for facts
# that happen to hash to each one.
# Genuinely unique to each template's own CSS_BASE -- editorial_minimal and
# split_modern both legitimately use the `header.site` selector, so that
# string can't distinguish them; verified unique via grep before picking.
_CSS_MARKER = {
    "editorial_minimal": ".call-btn",
    "split_modern": ".hero-in",
    "bold_cinematic": "header.nav",
}


def test_interior_pages_use_their_own_templates_css():
    f = _F(business_name="Acme Plumbing", domain="acme.com", subtype="Plumber",
           telephone="555-0100")
    blocks = {
        "head": "<!DOCTYPE html><html><head><style></style></head>",
        "nav": '<nav aria-label="Primary"><a href="index.html">Home</a></nav>',
        "footer": '<footer class="site">footer</footer>',
        "content": "<h1>Test Service</h1><p>content</p>",
        "cookie": '<div id="cookie-consent"></div>',
    }
    pal = palettes.palette_for("Plumber", 0)
    typ = engine.typography.typography_for(0)
    for tmpl in engine.TEMPLATES:
        theme = Theme(template=tmpl, palette=pal, typography=typ, hero_style="gradient")
        for page_fn, page_name in ((tmpl.render_service, "service"), (tmpl.render_about, "about"),
                                    (tmpl.render_privacy, "privacy")):
            html = page_fn(f, "https://acme.com", theme, blocks)
            own_marker = _CSS_MARKER[tmpl.name.lower().replace(" ", "_")]
            assert own_marker in html, f"{tmpl.name}'s {page_name} page missing its own CSS marker {own_marker!r}"
            for other_name, other_marker in _CSS_MARKER.items():
                if other_marker == own_marker:
                    continue
                assert other_marker not in html, (
                    f"{tmpl.name}'s {page_name} page leaked {other_name}'s CSS marker {other_marker!r} "
                    "-- interior pages must stay in their own theme"
                )


# 2026-08-20, Site Generator robustness push Slice A: site_engine.py now
# threads real rating_html/stats_band content into blocks -- proves every
# template actually renders them when present, and none of the three
# fabricates them when facts carry no rating (rating_html/stats_band are
# empty strings in that case, mirroring site_engine.py's own gate).
#
# 2026-08-21, Slice B: extended with location_html (real address + a real
# no-API-key directions link -- always present, unlike rating_html/
# stats_band, since NAP fields are mandatory on BusinessFacts) so both
# slices' cross-template coverage share one blocks builder.
def _index_blocks(rating_html: str, stats_band: str, location_html: str = "") -> dict:
    return {
        "head": "<!DOCTYPE html><html><head><style></style></head>",
        "nav": '<nav aria-label="Primary"><a href="index.html">Home</a></nav>',
        "footer": '<footer class="site">footer</footer>',
        "p1_html": "<p>p1</p>",
        "p2_html": "<p>p2</p>",
        "services_block": "<h2>Services</h2><ul><li>Item</li></ul>",
        "areas_block": "",
        "about_block": "<section><h2>About</h2></section>",
        "faq_block": "",
        "rating_html": rating_html,
        "stats_band": stats_band,
        "location_html": location_html,
        "cookie": '<div id="cookie-consent"></div>',
    }


_LOCATION_HTML = (
    '<section aria-label="Location and hours"><h2>Location &amp; hours in Austin</h2>'
    '<address>123 Main St<br>Austin, TX 78701</address>'
    '<p><a class="directions-link" href="https://www.google.com/maps/search/?api=1&amp;query=Acme%20Plumbing">'
    'Get directions</a></p></section>'
)


def test_rating_and_stats_band_render_across_all_templates():
    f = _F(business_name="Acme Plumbing", domain="acme.com", subtype="Plumber",
           telephone="555-0100", locality="Austin")
    blocks = _index_blocks(
        '<div class="rating"><span class="stars" aria-hidden="true">★★★★★</span>4.9 (218 reviews)</div>',
        '<div class="band"><div><h2>Trusted across Austin</h2></div></div>',
    )
    pal = palettes.palette_for("Plumber", 0)
    typ = engine.typography.typography_for(0)
    for tmpl in engine.TEMPLATES:
        theme = Theme(template=tmpl, palette=pal, typography=typ, hero_style="gradient")
        html = tmpl.render_index(f, "https://acme.com", theme, blocks)
        assert 'class="rating"' in html, f"{tmpl.name} dropped the rating block"
        assert 'class="stars"' in html, f"{tmpl.name} dropped the star markup"
        assert 'class="band"' in html, f"{tmpl.name} dropped the trust band"


def test_rating_and_stats_band_omitted_when_blank():
    f = _F(business_name="Acme Plumbing", domain="acme.com", subtype="Plumber",
           telephone="555-0100", locality="Austin")
    # location_html is real here (unlike rating/stats) -- proves the two
    # slices' honesty gates are independent: no rating doesn't mean no
    # location, since NAP fields are mandatory and rating is optional.
    blocks = _index_blocks("", "", _LOCATION_HTML)
    pal = palettes.palette_for("Plumber", 0)
    typ = engine.typography.typography_for(0)
    for tmpl in engine.TEMPLATES:
        theme = Theme(template=tmpl, palette=pal, typography=typ, hero_style="gradient")
        html = tmpl.render_index(f, "https://acme.com", theme, blocks)
        assert 'class="rating"' not in html, f"{tmpl.name} must not fabricate a rating block when none is given"
        assert 'class="band"' not in html, f"{tmpl.name} must not fabricate a trust band when none is given"
        assert 'class="directions-link"' in html, f"{tmpl.name} dropped a real location block that was actually given"


# 2026-08-21, Slice B: proves every template renders the real location
# section (address + directions link) when given, mirroring Slice A's
# rating/stats-band coverage above.
def test_location_renders_across_all_templates():
    f = _F(business_name="Acme Plumbing", domain="acme.com", subtype="Plumber",
           telephone="555-0100", locality="Austin")
    blocks = _index_blocks("", "", _LOCATION_HTML)
    pal = palettes.palette_for("Plumber", 0)
    typ = engine.typography.typography_for(0)
    for tmpl in engine.TEMPLATES:
        theme = Theme(template=tmpl, palette=pal, typography=typ, hero_style="gradient")
        html = tmpl.render_index(f, "https://acme.com", theme, blocks)
        assert "<address>" in html, f"{tmpl.name} dropped the address block"
        assert 'class="directions-link"' in html, f"{tmpl.name} dropped the directions link"


# ---------------------------------------------------------------------------
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
