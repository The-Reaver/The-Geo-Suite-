"""Standalone design-variation test for verify.py battery.

Tests determinism, variation, WCAG contrast, and template coverage of the
site_design engine. No pytest — standalone-runnable with a __main__ runner.
"""
import os
import re
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
from app.services import audit_engine
from app.services.site_design import engine, palettes, typography
from app.services.site_design.templates import (
    editorial_minimal, split_modern, bold_cinematic, trust_panel, boutique_editorial,
    framed_gallery, directory_listing, timeline_flow, compact_utility,
)
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


# 2026-08-21, Slice C.1: grew the palette library from 8 to 20 and the
# typography library from 3 to 8, per the operator's explicit correction
# ("this library of templates, palettes, type pairings need to be vast").
# assert_wcag() (palettes.py, runs at import time) is still the
# authoritative contrast gate for every entry; these lock in the actual
# size/variety so a future edit can't silently shrink the library back
# down without a test noticing.
#
# 2026-08-21, Opus 5 review of the first cut of this slice: this test
# originally compared .name only -- a color-identical clone (different
# name, same hex values) would have passed, and did in mutation testing.
# Now also asserts every accent hex is unique, and a sibling test below
# independently re-verifies both WCAG checks and genuine visual
# distinctness within each family, so a future weakening of
# assert_wcag() or a near-duplicate palette can't slip through with only
# assert_wcag() itself as the sole gate.
def test_palette_library_has_real_variety():
    assert len(palettes.PALETTES) >= 20, \
        f"expected >= 20 palettes, got {len(palettes.PALETTES)}"
    names = [p.name for p in palettes.PALETTES]
    assert len(names) == len(set(names)), f"duplicate palette names: {names}"
    accents = [p.accent for p in palettes.PALETTES]
    assert len(accents) == len(set(accents)), f"duplicate accent colors: {accents}"

    representative_subtypes = ["Dentist", "Plumber", "Attorney", "Hair Salon", "Restaurant"]
    for subtype in representative_subtypes:
        seen = {palettes.palette_for(subtype, seed).name for seed in range(8)}
        assert len(seen) >= 4, \
            f"{subtype}'s industry family must resolve to >= 4 distinct palettes, got {seen}"


def _luminance(hex_color):
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

    def srgb(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b)


def _contrast(hex1, hex2):
    l1, l2 = _luminance(hex1), _luminance(hex2)
    bright, dark = max(l1, l2), min(l1, l2)
    return (bright + 0.05) / (dark + 0.05)


def _hue_sat(hex_color):
    import colorsys
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h * 360, s


# 2026-08-21, Opus 5 review of Slice C.1: assert_wcag() only ever checked
# ink/bg, and only for palettes actually reachable through this module's
# own PALETTES list -- but no test independently re-verified the white-
# on-accent button contrast every template's primary CTA relies on
# (background:var(--accent);color:#fff). 5 of the first 12 new palettes
# shipped that pairing below WCAG's 3:1 floor (Mint measured 2.54:1)
# before being fixed; this test re-implements the check independently
# (mirroring test_palettes_wcag_contrast's own reimplementation style for
# ink/bg) over the FULL 20-palette list, not just the 4 reachable via one
# subtype, so a future weakening of assert_wcag() can't silently regress
# this.
def test_all_palettes_pass_button_text_contrast_independently():
    for p in palettes.PALETTES:
        cr = _contrast("#FFFFFF", p.accent)
        assert cr >= 3.0, f"{p.name}: white text on accent {p.accent} is {cr:.2f}, below the 3:1 floor"


def _css_rule(css: str, selector: str) -> str:
    import re
    m = re.search(re.escape(selector) + r"\{([^}]*)\}", css)
    assert m, f"selector {selector!r} not found"
    return m.group(1)


def _declared_px(rule: str, prop: str) -> float:
    import re
    m = re.search(re.escape(prop) + r":\s*([\d.]+)px", rule)
    return float(m.group(1)) if m else 0.0


def _declared_weight(rule: str, prop: str = "font-weight") -> int:
    import re
    m = re.search(re.escape(prop) + r":\s*(\d+)", rule)
    return int(m.group(1)) if m else 400  # CSS default is 400 (normal)


# 2026-08-21, Opus 5 review of Slice C.2: editorial_minimal.py and
# boutique_editorial.py both render their trust band as white text
# directly on var(--accent) (split_modern/bold_cinematic use the fixed,
# always-dark var(--dark) instead, and trust_panel uses dark text on a
# light accent-soft tint -- neither is affected). White-on-accent only
# clears WCAG's 3:1 floor (assert_wcag(), palettes.py) -- a bar that's
# only valid for large-scale text. .band .sub was rendering at 16-17px
# normal weight, nowhere near large text, so 2 of the 20 palettes (Teal
# 3.74:1, Orange 3.56:1) genuinely failed the real 4.5:1 normal-text bar
# their actual font size required. Every affected selector's declared
# font-size/font-weight must now genuinely clear WCAG's large-text
# threshold (>=24px at any weight, or >=18.66px bold) so relying on the
# 3:1 floor is honest, not incidental.
def test_band_white_text_on_accent_qualifies_as_large_text():
    for mod in (editorial_minimal, boutique_editorial):
        css = mod.CSS_BASE
        for selector in (".band h2", ".band .sub"):
            rule = _css_rule(css, selector)
            size = _declared_px(rule, "font-size")
            weight = _declared_weight(rule)
            qualifies = size >= 24 or (size >= 18.66 and weight >= 700)
            assert qualifies, (
                f"{mod.__name__} {selector}: {size}px/{weight} does not qualify as WCAG "
                f"large text, so it needs 4.5:1 contrast, not the 3:1 floor assert_wcag() checks"
            )


def _parse_css_rules(css: str):
    # Strip /* ... */ comments first -- several templates put explanatory
    # comments between related rules (e.g. between ".band" and ".band h2"),
    # and without this the naive brace-scanning regex below captures the
    # comment text as part of the NEXT rule's "selector," which then fails
    # to startswith() match against its real, uncommented selector string.
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    return re.findall(r'([^{}]+)\{([^{}]*)\}', css)


def _selector_base(selector: str) -> str:
    sel = selector.strip().split()[0]
    return sel.split(":")[0]


# 2026-08-21, Opus 5 review of Slice C.3: the test above only ever checked
# 2 hardcoded modules (editorial_minimal/boutique_editorial) and 2
# hardcoded selectors (.band h2/.band .sub) -- a scope narrow enough that
# the exact same defect class (white text on var(--accent) below the WCAG
# large-text threshold) slipped through undetected in this same C.3 commit,
# in directory_listing.py's brand-new .dir-call and .mobile-call-bar a
# rules. This generalizes the guard across every template's full CSS_BASE
# and every selector, present and future, instead of a hand-picked list.
#
# Only a rule whose OWN declaration block sets color:#fff, and whose
# background -- either declared directly on that same selector, or on its
# "base" selector (the first compound/descendant token, e.g. ".dir-call"
# for ".dir-call:hover") -- is exactly var(--accent), is checked. The
# substring match "background:var(--accent)" deliberately does not
# false-positive against "--accent-soft"/"--accent-dark": the exact
# variable name's closing paren immediately follows "accent", which only
# ever occurs for the literal `--accent` custom property.
#
# 2026-08-21, Opus 5 review of the footer/contrast fix commit: this test
# originally skipped every :hover selector outright, reasoning that a
# :hover rule "often doesn't redeclare font-size, relying on inheritance
# from the base rule" -- but that's exactly backwards as a reason to
# SKIP: a :hover rule that inherits its size FROM the base rule is
# real CSS cascade behavior (both rules match the same hovered element;
# properties the :hover rule doesn't redeclare keep the base rule's
# value), not something this checker can't know. The blanket skip was a
# 100% false-negative filter -- every one of the 4 rules it excused
# (.call-btn:hover, .dir-call:hover, .tl-call:hover, .call-pill:hover,
# each inheriting 14-15px/600 from their un-hovered base rule) was a real
# live bug. Now resolved instead of skipped: a :hover rule's own
# font-size/font-weight take priority if declared, else fall back to its
# base selector's declared value.
#
# A selector is also skipped if a MORE SPECIFIC descendant selector (e.g.
# ".band h2" for ".band") exists in the same file and itself declares a
# color -- that descendant rule governs whatever real text renders inside
# it, so the ancestor's own color is just an inheritance fallback, never
# itself the color actual text renders in. This is a real, structural
# case, not a loophole: site_engine.py's _stats_band_html() always wraps
# its real text in child elements (h2/.sub), never directly under
# class="band", so ".band"'s own "color:#fff" never reaches the page
# un-overridden. Confirmed by first running this test without the
# exclusion and finding it flagged exactly that -- a container reset, not
# a rendered-text bug -- while still correctly catching the real
# .dir-call/.mobile-call-bar bugs this test exists to guard, neither of
# which has any such descendant override.
def _has_color_overriding_descendant(selector: str, rules) -> bool:
    prefix = selector.strip() + " "
    for other_sel, other_decl in rules:
        other_sel = other_sel.strip()
        if other_sel.startswith(prefix) and "color:" in other_decl.replace(" ", "").lower():
            return True
    return False


def _rules_by_selector_merged(rules):
    # 2026-08-21, Opus 5 review: a plain {sel: decl for sel, decl in rules}
    # dict comprehension is last-write-wins on the WHOLE decl string --
    # editorial_minimal.py declares ".band" twice (once at top level, once
    # inside a @media block, e.g. ".band{padding:32px}"), and the second,
    # narrower declaration was silently replacing the first, dropping
    # "background:var(--accent)" from what base-selector lookups could
    # see. Real CSS cascade merges same-selector rules property-by-
    # property (last value per property wins, not last rule wins
    # wholesale); this approximates that safely for our purposes by
    # concatenating every declaration block seen for a selector, so a
    # property mentioned in an earlier rule is never lost just because a
    # later, narrower rule for the same selector doesn't redeclare it.
    merged = {}
    for sel, decl in rules:
        sel = sel.strip()
        merged[sel] = (merged[sel] + ";" + decl) if sel in merged else decl
    return merged


def _resolve_size_weight(selector: str, decl: str, rules_by_selector: dict):
    base = _selector_base(selector)
    base_decl = rules_by_selector.get(base, "")
    size = _declared_px(decl, "font-size")
    if size == 0.0 and selector != base:
        size = _declared_px(base_decl, "font-size")
    if "font-weight" in decl.replace(" ", "").lower():
        weight = _declared_weight(decl)
    elif selector != base:
        weight = _declared_weight(base_decl)
    else:
        weight = _declared_weight(decl)
    return size, weight


def test_no_white_on_accent_text_below_the_wcag_large_text_threshold():
    modules = [editorial_minimal, split_modern, bold_cinematic, trust_panel,
               boutique_editorial, framed_gallery, directory_listing,
               timeline_flow, compact_utility]
    for mod in modules:
        css = mod.CSS_BASE
        rules = _parse_css_rules(css)
        rules_by_selector = _rules_by_selector_merged(rules)
        for selector, decl in rules:
            selector = selector.strip()
            if "color:#fff" not in decl.replace(" ", "").lower():
                continue
            base = _selector_base(selector)
            base_decl = rules_by_selector.get(base, "")
            bg_here = "background:var(--accent)" in decl.replace(" ", "").lower()
            bg_base = "background:var(--accent)" in base_decl.replace(" ", "").lower()
            if not (bg_here or bg_base):
                continue
            if _has_color_overriding_descendant(selector, rules):
                continue
            size, weight = _resolve_size_weight(selector, decl, rules_by_selector)
            qualifies = size >= 24 or (size >= 18.66 and weight >= 700)
            assert qualifies, (
                f"{mod.__name__} {selector!r}: white text on var(--accent) at "
                f"{size}px/{weight} does not qualify as WCAG large text"
            )


# 2026-08-21, Opus 5 review of Slice C.1: caught a real near-duplicate
# hex-uniqueness alone can't detect -- Terracotta was Orange's own accent
# ramp shifted one step darker (same hue, same high saturation), not a
# genuinely new option. Within each named industry family, every pair of
# palettes must differ in hue by >= 8 degrees or in saturation by >= 0.15
# -- the same "muted earthy tone vs. vivid saturated tone" distinction a
# hex-only uniqueness check would miss.
def test_palette_family_members_are_visually_distinct():
    families = {
        "Dentist": ["Teal", "Blue", "Mint", "Indigo"],
        "Plumber": ["Red", "Steel", "Amber", "Charcoal"],
        "Attorney": ["Navy", "Slate", "Burgundy", "Forest"],
        "Hair Salon": ["Rose", "Teal", "Lavender", "Blush"],
        "Restaurant": ["Orange", "Red", "Olive", "Terracotta"],
    }
    by_name = {p.name: p for p in palettes.PALETTES}
    for subtype, names in families.items():
        pals = [by_name[n] for n in names]
        for i in range(len(pals)):
            for j in range(i + 1, len(pals)):
                h1, s1 = _hue_sat(pals[i].accent)
                h2, s2 = _hue_sat(pals[j].accent)
                hue_delta = min(abs(h1 - h2), 360 - abs(h1 - h2))
                sat_delta = abs(s1 - s2)
                assert hue_delta >= 8 or sat_delta >= 0.15, (
                    f"{pals[i].name} and {pals[j].name} (both in the {subtype!r} family) "
                    f"are too visually similar: hue delta {hue_delta:.1f}, sat delta {sat_delta:.2f}"
                )


def test_typography_library_has_real_variety():
    assert len(typography.PAIRINGS) >= 8, \
        f"expected >= 8 type pairings, got {len(typography.PAIRINGS)}"
    names = [t.name for t in typography.PAIRINGS]
    assert len(names) == len(set(names)), f"duplicate type pairing names: {names}"
    seen = {typography.typography_for(seed).name for seed in range(80)}
    assert len(seen) >= 8, f"expected all 8 pairings to be reachable via typography_for(), got {seen}"


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

    # 2026-08-21, Slice C.2: raised from >=3 to >=5 -- all 5 registered
    # templates were observed across this exact business list at the
    # time. Slice C.3 grew the registry to 7, but only 6 of those 7 show
    # up in this specific fixed 12-business list (Split Modern doesn't,
    # just by chance of the hash distribution over this exact set) --
    # raised to >=6, matching what's actually observed, not the full
    # registry size, so this doesn't become flaky against an unchanging
    # small sample. Slice C.4 grew the registry to 9; 7 of those 9 show up
    # in this same fixed list (Bold Cinematic and Compact Utility don't,
    # again just by chance of the hash distribution over this exact set)
    # -- raised to >=7, same "observed, not registry size" reasoning.
    assert len(templates_seen) >= 7, f"Expected >= 7 templates, got {len(templates_seen)}: {templates_seen}"
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


# 2026-08-21, Slice C.2: proves both new templates are actually reachable
# through the real, unconditional select_theme() modulo -- same
# reachability guarantee test_bold_cinematic_is_reachable_for_real_facts
# already established for the third template.
def test_new_c2_templates_are_reachable_for_real_facts():
    for target in ("Trust Panel", "Boutique Editorial"):
        found = False
        for i in range(200):
            f = _F(business_name=f"Business {i}", domain=f"biz{i}.example", subtype="Plumber")
            theme = engine.select_theme(f)
            if theme.template.name == target:
                found = True
                break
        assert found, f"{target} must be reachable for real facts"


# 2026-08-21, Slice C.3: same guarantee for the second batch of new
# templates.
def test_new_c3_templates_are_reachable_for_real_facts():
    for target in ("Framed Gallery", "Directory Listing"):
        found = False
        for i in range(200):
            f = _F(business_name=f"Business {i}", domain=f"biz{i}.example", subtype="Plumber")
            theme = engine.select_theme(f)
            if theme.template.name == target:
                found = True
                break
        assert found, f"{target} must be reachable for real facts"


# 2026-08-21, Slice C.4: same guarantee for the third batch of new
# templates.
def test_new_c4_templates_are_reachable_for_real_facts():
    for target in ("Timeline Flow", "Compact Utility"):
        found = False
        for i in range(200):
            f = _F(business_name=f"Business {i}", domain=f"biz{i}.example", subtype="Plumber")
            theme = engine.select_theme(f)
            if theme.template.name == target:
                found = True
                break
        assert found, f"{target} must be reachable for real facts"


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
    # 2026-08-21, Slice C.2: two new templates, verified unique the same
    # way -- grepped across every template file before picking.
    "trust_panel": "header.clinic",
    "boutique_editorial": "header.boutique",
    # 2026-08-21, Slice C.3: same again.
    "framed_gallery": "header.frame-top",
    "directory_listing": "header.directory",
    # 2026-08-21, Slice C.4: same again.
    "timeline_flow": "header.timeline-top",
    "compact_utility": "header.utility",
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


# 2026-08-21, Opus 5 review of Slice C.3: site_engine.py's _footer()
# returns a bare, classless <footer> tag -- every template's own
# footer.<name>{...} CSS rule was silently matching nothing, on every
# generated site, for every template, since the very first one. Went
# undetected because test_interior_pages_use_their_own_templates_css's
# own synthetic blocks["footer"] fixture already had a class baked in
# by hand ('<footer class="site">footer</footer>' above), unlike the
# real site_engine.py output -- this uses the real, classless shape
# instead, so it can only pass if the template genuinely adds its own
# class.
def test_every_template_adds_its_own_class_to_the_shared_footer():
    f = _F(business_name="Acme Plumbing", domain="acme.com", subtype="Plumber",
           telephone="555-0100", locality="Austin")
    real_footer = "  <footer>\n    <p>Acme Plumbing</p>\n  </footer>"
    blocks = {
        "head": "<!DOCTYPE html><html><head><style></style></head>",
        "nav": '<nav aria-label="Primary"><a href="index.html">Home</a></nav>',
        "footer": real_footer,
        "p1_html": "<p>p1</p>",
        "p2_html": "<p>p2</p>",
        "services_block": '<h2 id="services">Services</h2><ul><li>Item</li></ul>',
        "areas_block": "",
        "about_block": "<section><h2>About</h2></section>",
        "faq_block": "",
        "rating_html": "",
        "stats_band": "",
        "location_html": "",
        "cookie": '<div id="cookie-consent"></div>',
    }
    pal = palettes.palette_for("Plumber", 0)
    typ = engine.typography.typography_for(0)
    interior_blocks = dict(blocks, content="<h1>Test Service</h1><p>content</p>")
    for tmpl in engine.TEMPLATES:
        theme = Theme(template=tmpl, palette=pal, typography=typ, hero_style="gradient")
        html = tmpl.render_index(f, "https://acme.com", theme, blocks)
        assert re.search(r'<footer class="[^"]+">', html), \
            f"{tmpl.name}'s render_index must add its own class to the real, classless <footer> _footer() emits"
        assert "<footer>\n" not in html, f"{tmpl.name}'s render_index left the shared footer classless"

        service_html = tmpl.render_service(f, "https://acme.com", theme, interior_blocks)
        assert re.search(r'<footer class="[^"]+">', service_html), \
            f"{tmpl.name}'s render_service must add its own class to the real, classless <footer> _footer() emits"
        assert "<footer>\n" not in service_html, f"{tmpl.name}'s render_service left the shared footer classless"


# 2026-08-21, Opus 5 review of the footer/contrast fix commit: found that
# site_engine.py's real faq_block output (plain <h3>/<p> pairs, never
# <details>/<summary>) never matched any of the 9 templates' own
# .faq/details/summary/summary::after accordion CSS -- the identical "CSS
# rule matches nothing real" defect class as the footer bug, still shipped
# in the two brand-new C.4 templates. Fixed via a shared _wrap_faq()
# helper (templates/__init__.py). This proves the fix directly against
# real, site_engine.py-shaped faq_block markup (not a placeholder), and
# that no template drops or mangles the real question/answer text while
# converting it.
def test_every_template_renders_real_faq_accordion_markup():
    f = _F(business_name="Acme Plumbing", domain="acme.com", subtype="Plumber",
           telephone="555-0100", locality="Austin")
    real_faq_block = (
        '    <section id="faq" aria-label="Frequently asked questions">\n'
        '      <h2>Frequently asked questions</h2>\n'
        '      <h3>Do you offer emergency service?</h3>\n'
        '      <p>Yes, 24/7.</p>\n'
        '      <h3>Are you licensed?</h3>\n'
        '      <p>Yes, fully licensed and insured.</p>\n'
        '    </section>'
    )
    blocks = {
        "head": "<!DOCTYPE html><html><head><style></style></head>",
        "nav": '<nav aria-label="Primary"><a href="index.html">Home</a></nav>',
        "footer": "  <footer>\n    <p>Acme Plumbing</p>\n  </footer>",
        "p1_html": "<p>p1</p>",
        "p2_html": "<p>p2</p>",
        "services_block": '<h2 id="services">Services</h2><ul><li>Item</li></ul>',
        "areas_block": "",
        "about_block": "<section><h2>About</h2></section>",
        "faq_block": real_faq_block,
        "rating_html": "",
        "stats_band": "",
        "location_html": "",
        "cookie": '<div id="cookie-consent"></div>',
    }
    pal = palettes.palette_for("Plumber", 0)
    typ = engine.typography.typography_for(0)
    for tmpl in engine.TEMPLATES:
        theme = Theme(template=tmpl, palette=pal, typography=typ, hero_style="gradient")
        html = tmpl.render_index(f, "https://acme.com", theme, blocks)
        assert "<details>" in html and "<summary>" in html, \
            f"{tmpl.name} must render real <details>/<summary> FAQ accordion markup, not flat <h3>/<p>"
        assert "Do you offer emergency service?" in html, \
            f"{tmpl.name} dropped or mangled the real FAQ question text"
        assert "Yes, fully licensed and insured." in html, \
            f"{tmpl.name} dropped or mangled the real FAQ answer text"
        assert html.count("<details>") == 2, \
            f"{tmpl.name} rendered {html.count('<details>')} FAQ accordion items, expected 2"


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


# 2026-08-21, Slice C.2: a template being reachable and rendering the
# right blocks doesn't prove it actually clears the real 90-point audit
# gate -- proves both new templates do, generating a real, complete site
# (not synthetic blocks) through generate_site() with facts chosen to
# actually hash to each new template, exactly like
# test_bold_cinematic_is_reachable_for_real_facts finds a real seed
# rather than forcing the template directly.
def _assert_templates_pass_real_audit_gate(template_names):
    # 2026-08-21: this file's own bare-bones _F() fixture (same_as=[], no
    # rating -- used elsewhere in this file only to prove business
    # names/subtypes render, never to prove a score) does NOT clear the
    # real 90-point gate regardless of template -- confirmed the first
    # version of the C.2 test failed with those exact facts on Trust
    # Panel for that reason, nothing to do with the template itself. A
    # real site needs real sameAs/rating data to pass, same as
    # test_site_engine.py's _dentist()/_plumber() fixtures already
    # supply.
    GOOD_CWV = {"lcp_s": 1.8, "inp_ms": 120, "cls": 0.05}
    remaining = set(template_names)
    for i in range(200):
        if not remaining:
            break
        f = _F(
            business_name=f"Business {i}", domain=f"biz{i}.example", subtype="Plumber",
            locality="Austin", region="TX", postal_code="78701", country="US",
            telephone="555-0100", street="123 Main St",
            services=[types.SimpleNamespace(name="Fixing leaks", description="We fix them.")],
            service_areas=["Austin"],
            same_as=["https://g.page/example-plumbing"],
            hours=["Mon-Fri 8:00-17:00"], faqs=[],
            credentials=["Texas licensed"], last_updated="2026-07-25",
            tagline="Quality plumbing",
            rating=types.SimpleNamespace(value=4.9, count=218),
        )
        theme = engine.select_theme(f)
        if theme.template.name not in remaining:
            continue
        remaining.discard(theme.template.name)
        with tempfile.TemporaryDirectory() as tmp:
            generate_site(f, tmp)
            r = audit_engine.run_audit(tmp, cwv=GOOD_CWV)
            assert r.passed is True, f"{theme.template.name} scored {r.normalized_score}, expected to pass"
    assert not remaining, f"never found a seed landing on: {remaining}"


def test_new_c2_templates_pass_the_real_audit_gate():
    _assert_templates_pass_real_audit_gate({"Trust Panel", "Boutique Editorial"})


# 2026-08-21, Slice C.3: same guarantee for the second batch of new
# templates.
def test_new_c3_templates_pass_the_real_audit_gate():
    _assert_templates_pass_real_audit_gate({"Framed Gallery", "Directory Listing"})


# 2026-08-21, Slice C.4: same guarantee for the third batch of new
# templates.
def test_new_c4_templates_pass_the_real_audit_gate():
    _assert_templates_pass_real_audit_gate({"Timeline Flow", "Compact Utility"})


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
