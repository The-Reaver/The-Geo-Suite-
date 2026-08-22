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
#
# 2026-08-22, Slice 4: grew 20->25 (one new option per named family,
# cheap dimension grown first per operator direction -- new templates
# stay their own separate, bespoke slice). Thresholds raised to the real
# measured values (25 total, 5 per family within range(8), empirically
# re-confirmed, not assumed) rather than left at the old floor.
def test_palette_library_has_real_variety():
    assert len(palettes.PALETTES) >= 25, \
        f"expected >= 25 palettes, got {len(palettes.PALETTES)}"
    names = [p.name for p in palettes.PALETTES]
    assert len(names) == len(set(names)), f"duplicate palette names: {names}"
    accents = [p.accent for p in palettes.PALETTES]
    assert len(accents) == len(set(accents)), f"duplicate accent colors: {accents}"

    representative_subtypes = ["Dentist", "Plumber", "Attorney", "Hair Salon", "Restaurant"]
    for subtype in representative_subtypes:
        seen = {palettes.palette_for(subtype, seed).name for seed in range(8)}
        assert len(seen) >= 5, \
            f"{subtype}'s industry family must resolve to >= 5 distinct palettes, got {seen}"


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


# 2026-08-21, Opus 5 review of the previous fix commit: this originally
# resolved a :hover rule's inherited size/weight via _selector_base(),
# which returns only the FIRST whitespace token of a selector -- correct
# for a single compound token like ".dir-call:hover" (base ".dir-call"),
# but wrong for a DESCENDANT :hover selector like "X Y:hover", where it
# resolves to the ancestor "X" instead of the real un-hovered self "X Y".
# Proven by mutation to produce both a false negative (a real violation
# hidden because the unrelated ancestor happens to declare a large
# font-size) and a false positive (a compliant rule flagged because the
# ancestor declares no font-size at all, even though "X Y" itself does).
# Now resolves the exact un-hovered self first (the same selector text
# with only its own trailing pseudo-class stripped), falling back to
# _selector_base()'s ancestor lookup only if that misses.
def _self_without_pseudo(selector: str) -> str:
    return re.sub(r":[a-zA-Z-]+$", "", selector.strip()).strip()


def _resolve_size_weight(selector: str, decl: str, rules_by_selector: dict):
    self_sel = _self_without_pseudo(selector)
    fallback_decl = rules_by_selector.get(self_sel, "")
    if not fallback_decl and self_sel != selector:
        fallback_decl = rules_by_selector.get(_selector_base(selector), "")
    size = _declared_px(decl, "font-size")
    if size == 0.0 and selector != self_sel:
        size = _declared_px(fallback_decl, "font-size")
    if "font-weight" in decl.replace(" ", "").lower():
        weight = _declared_weight(decl)
    elif selector != self_sel:
        weight = _declared_weight(fallback_decl)
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
#
# 2026-08-22, Opus 5 review of Slice 4: this dict was NOT updated when
# Slice 4 added a 5th member to each family, leaving all 5 new palettes
# (Cyan/Denim/Plum/Champagne/Basil) completely outside this guard --
# despite a code comment elsewhere (palettes.py) claiming they'd been
# "chosen to clear the SAME distinctness bar `test_palette_family_
# members_are_visually_distinct` already enforces," which was false for
# this exact reason. Mutation-proven real gap, not theoretical: swapping
# Cyan's accent for Teal's own accent_dark (hue delta 0.7deg, sat delta
# 0.009 -- a literal reconstruction of the historical Terracotta defect)
# still passed the full suite before this fix. Now included.
def test_palette_family_members_are_visually_distinct():
    families = {
        "Dentist": ["Teal", "Blue", "Mint", "Indigo", "Cyan"],
        "Plumber": ["Red", "Steel", "Amber", "Charcoal", "Denim"],
        "Attorney": ["Navy", "Slate", "Burgundy", "Forest", "Plum"],
        "Hair Salon": ["Rose", "Teal", "Lavender", "Blush", "Champagne"],
        "Restaurant": ["Orange", "Red", "Olive", "Terracotta", "Basil"],
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


# 2026-08-22, Slice 4: grew 8->11 pairings. Thresholds raised to the
# real measured values -- all 11 confirmed reachable within range(80)
# before locking this in, not assumed from the old 8-pairing figure.
def test_typography_library_has_real_variety():
    assert len(typography.PAIRINGS) >= 11, \
        f"expected >= 11 type pairings, got {len(typography.PAIRINGS)}"
    names = [t.name for t in typography.PAIRINGS]
    assert len(names) == len(set(names)), f"duplicate type pairing names: {names}"
    seen = {typography.typography_for(seed).name for seed in range(80)}
    assert len(seen) >= 11, f"expected all 11 pairings to be reachable via typography_for(), got {seen}"


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
    # up in this specific fixed 12-business list -- raised to >=6,
    # matching what's actually observed, not the full registry size, so
    # this doesn't become flaky against an unchanging small sample. Slice
    # C.4 grew the registry to 9; 7 of those 9 showed up -- raised to
    # >=7.
    #
    # 2026-08-21, industry-aware template selection: re-measured directly
    # after select_theme() stopped being subtype-blind for template
    # choice (each business here now only ever reaches its own real
    # industry family's 4 templates, not any of the 9) -- still exactly
    # 7 distinct templates observed across this same fixed list, so the
    # >=7 floor holds without needing to change. Deliberately NOT naming
    # which 2 of the 9 don't land here: that's a function of the exact
    # seed-derivation internals (compute_seed/hashing choices), which
    # already changed once this same slice (a round-3 Opus 5 review found
    # this comment's own earlier "Directory Listing and Timeline Flow"
    # detail had gone stale the moment _template_seed() replaced the old
    # `// 13` divisor -- the actual pair is now different) -- a detail
    # this comment shouldn't have to keep re-verifying on every future
    # change to how seeds map to indices.
    # 2026-08-22, Slice 4: palettes_seen re-measured after growing each
    # family to 5 members -- 11 of the (now 25) palettes actually land
    # across this same fixed 12-business list. Locked in at >=9, not the
    # full observed 11: an Opus 5 review flagged that >=11 against a
    # hard ceiling of 12 businesses leaves zero slack (this list has
    # exactly one known collision, Teal appearing twice) -- any future,
    # unrelated seed-derivation tweak that creates one more collision
    # would fail this test for no real reason, the same flakiness this
    # test's own comment above already warns about. >=9 preserves real
    # margin while still meaningfully raised from the pre-Slice-4 floor
    # of >=4. templates_seen is untouched by this slice (templates
    # aren't part of it) and holds at >=7.
    assert len(templates_seen) >= 7, f"Expected >= 7 templates, got {len(templates_seen)}: {templates_seen}"
    assert len(palettes_seen) >= 9, f"Expected >= 9 palettes, got {len(palettes_seen)}: {palettes_seen}"


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
#
# 2026-08-21, industry-aware template selection sub-slice: select_theme()
# is no longer subtype-blind for template choice -- "Plumber" only ever
# reaches the Home Services family now, which neither of these two
# templates belongs to. Switched each target to a real subtype from its
# own actual family (Trust Panel -> Dental/Medical, Boutique Editorial ->
# Beauty/Salon), matching engine.py's own family assignments exactly
# rather than a blind subtype every template used to share.
def test_new_c2_templates_are_reachable_for_real_facts():
    for target, subtype in (("Trust Panel", "Dentist"), ("Boutique Editorial", "Hair Salon")):
        found = False
        for i in range(200):
            f = _F(business_name=f"Business {i}", domain=f"biz{i}.example", subtype=subtype)
            theme = engine.select_theme(f)
            if theme.template.name == target:
                found = True
                break
        assert found, f"{target} must be reachable for real facts (subtype={subtype!r})"


# 2026-08-21, Slice C.3: same guarantee for the second batch of new
# templates.
#
# 2026-08-21, industry-aware template selection sub-slice: switched each
# target to a real subtype from its own family (Framed Gallery ->
# Food/Restaurant; Directory Listing stays on "Plumber" -- Home Services
# is its only family, and it was already reachable through it).
def test_new_c3_templates_are_reachable_for_real_facts():
    for target, subtype in (("Framed Gallery", "Restaurant"), ("Directory Listing", "Plumber")):
        found = False
        for i in range(200):
            f = _F(business_name=f"Business {i}", domain=f"biz{i}.example", subtype=subtype)
            theme = engine.select_theme(f)
            if theme.template.name == target:
                found = True
                break
        assert found, f"{target} must be reachable for real facts (subtype={subtype!r})"


# 2026-08-21, Slice C.4: same guarantee for the third batch of new
# templates.
#
# 2026-08-21, industry-aware template selection sub-slice: switched
# Timeline Flow to a real subtype from one of its own families
# (Dental/Medical or Legal/Finance -- "Plumber" reaches neither); Compact
# Utility stays on "Plumber" since Home Services is one of its real
# families.
def test_new_c4_templates_are_reachable_for_real_facts():
    for target, subtype in (("Timeline Flow", "Attorney"), ("Compact Utility", "Plumber")):
        found = False
        for i in range(200):
            f = _F(business_name=f"Business {i}", domain=f"biz{i}.example", subtype=subtype)
            theme = engine.select_theme(f)
            if theme.template.name == target:
                found = True
                break
        assert found, f"{target} must be reachable for real facts (subtype={subtype!r})"


# 2026-08-21, industry-aware template selection sub-slice: proves "vast
# per industry" is real, not just "at least one template exists per
# family" -- every one of the 5 named families' own 4 templates is
# independently reachable for a real subtype belonging to that family,
# AND that no template outside that family is ever selected for it.
#
# 2026-08-21, Opus 5 review found this test's first draft was vacuous in
# two ways, both fixed here:
# 1. expected_names was derived from engine.py's own family lists (the
#    exact code under test), making the assertion tautological --
#    mutation-proven to still pass 407/407 even when a family was
#    narrowed to a single template repeated 4 times. Now hardcoded
#    independently, so a real narrowing shows up as a real mismatch.
# 2. The check was `seen_names >= expected_names` (a superset check,
#    "did we see at least these"), which says nothing about whether a
#    FOREIGN template also got selected -- mutation-proven to still pass
#    407/407 with template_for() reverted entirely to the pre-slice blind
#    TEMPLATES[seed % 9], since a blind selector still eventually
#    surfaces every family's own names too, just alongside 5 others. Now
#    asserts every single selection is IN the family (fails fast on the
#    first foreign template) and that all 4 real ones are eventually
#    seen -- together this is real containment, not just presence.
def test_every_named_family_has_real_variety():
    families = {
        "Dentist": {"Trust Panel", "Timeline Flow", "Editorial Minimal", "Split Modern"},
        "Plumber": {"Directory Listing", "Compact Utility", "Bold Cinematic", "Split Modern"},
        "Attorney": {"Trust Panel", "Timeline Flow", "Compact Utility", "Editorial Minimal"},
        "Hair Salon": {"Boutique Editorial", "Framed Gallery", "Bold Cinematic", "Editorial Minimal"},
        "Restaurant": {"Boutique Editorial", "Framed Gallery", "Bold Cinematic", "Split Modern"},
    }
    for subtype, expected_names in families.items():
        seen_names = set()
        for i in range(400):
            f = _F(business_name=f"Business {i}", domain=f"biz{i}.example", subtype=subtype)
            theme = engine.select_theme(f)
            assert theme.template.name in expected_names, (
                f"subtype={subtype!r} selected {theme.template.name!r}, which is outside "
                f"its own family {expected_names} -- template selection must stay confined "
                "to the business's real industry family"
            )
            seen_names.add(theme.template.name)
        assert seen_names == expected_names, (
            f"subtype={subtype!r}'s family must reach all 4 of its own templates, "
            f"only reached {seen_names} of {expected_names}"
        )


# 2026-08-21, industry-aware template selection sub-slice: a subtype that
# doesn't match any of the 5 named families (e.g. a mover) must still be
# able to reach any of the 9 templates -- the same guarantee every
# business had before template selection became industry-aware, now
# scoped to only the businesses actually outside a named family.
#
# 2026-08-21, Opus 5 review (round 3): this test's expected_names was
# derived from engine.TEMPLATES itself -- the same tautology already
# fixed in test_every_named_family_has_real_variety(), left unfixed here.
# Mutation-proven: removing a template from TEMPLATES entirely (a real
# regression -- the fallback pool for every non-family business silently
# shrinks) still passed 407/407, including this test, since both the
# expected set and the observed set shrink together. Hardcoded
# independently of engine.py so a real registry shrink is now caught.
def test_general_fallback_still_reaches_all_nine_templates():
    expected_names = {
        "Editorial Minimal", "Split Modern", "Bold Cinematic", "Trust Panel",
        "Boutique Editorial", "Framed Gallery", "Directory Listing",
        "Timeline Flow", "Compact Utility",
    }
    seen_names = set()
    for i in range(400):
        f = _F(business_name=f"Business {i}", domain=f"biz{i}.example", subtype="Moving Company")
        theme = engine.select_theme(f)
        assert theme.template.name in expected_names, (
            f"general fallback selected {theme.template.name!r}, which isn't one of the "
            f"9 registered templates -- {expected_names}"
        )
        seen_names.add(theme.template.name)
    assert seen_names == expected_names, (
        f"general fallback must reach all 9 templates, only reached {seen_names}"
    )


# 2026-08-21, Opus 5 review (round 3): the design intent -- "a business
# always gets a coherent pairing, never a Legal-family palette with a
# Beauty-family template" -- was genuinely unenforced before
# palettes.industry_family_for() was extracted as the single shared
# classifier both palette_for() and template_for() now call (previously
# each module carried its own copy of the same keyword branches, and
# mutation-proven a keyword added to only one copy left the whole suite
# green). This pins the observable guarantee directly, against
# HARDCODED expected sets -- NOT derived from engine._TEMPLATE_FAMILIES /
# palettes._PALETTE_FAMILIES, the exact self-referential tautology
# already caught and fixed once in this same file
# (test_every_named_family_has_real_variety, test_general_fallback_
# still_reaches_all_nine_templates). Confirmed the danger is real, not
# theoretical: an earlier draft of this exact test derived its expected
# sets from those live dicts and a swap-two-families mutation (a real
# kind of copy/paste mistake, not a contrived one) passed cleanly,
# because the test's own "expected" value and the code under test read
# from the identical mutated source.
# 2026-08-22, Slice 4: each family's expected palette set grew by its
# one new member (the templates side is untouched -- this slice didn't
# add templates). Still hardcoded independently of engine.py's own
# family dicts, per the round-3 review finding this guards against
# (deriving "expected" from the live code under test makes the coherence
# check tautological -- mutation-proven to pass even with a
# swapped-family bug).
def test_template_and_palette_family_selection_stay_coherent():
    expected = {
        "dental_medical": (
            {"Trust Panel", "Timeline Flow", "Editorial Minimal", "Split Modern"},
            {"Teal", "Blue", "Mint", "Indigo", "Cyan"},
        ),
        "home_services": (
            {"Directory Listing", "Compact Utility", "Bold Cinematic", "Split Modern"},
            {"Red", "Steel", "Amber", "Charcoal", "Denim"},
        ),
        "legal_finance": (
            {"Trust Panel", "Timeline Flow", "Compact Utility", "Editorial Minimal"},
            {"Navy", "Slate", "Burgundy", "Forest", "Plum"},
        ),
        "beauty_salon": (
            {"Boutique Editorial", "Framed Gallery", "Bold Cinematic", "Editorial Minimal"},
            {"Rose", "Teal", "Lavender", "Blush", "Champagne"},
        ),
        "food_restaurant": (
            {"Boutique Editorial", "Framed Gallery", "Bold Cinematic", "Split Modern"},
            {"Orange", "Red", "Olive", "Terracotta", "Basil"},
        ),
    }
    subtype_to_family = {
        "Dentist": "dental_medical", "Physician": "dental_medical", "VeterinaryCare": "dental_medical",
        "Plumber": "home_services", "HVAC": "home_services", "Electrician": "home_services", "Contractor": "home_services",
        "Attorney": "legal_finance", "Law Firm": "legal_finance", "Real Estate": "legal_finance",
        "Hair Salon": "beauty_salon", "Beauty Spa": "beauty_salon",
        "Restaurant": "food_restaurant", "Cafe": "food_restaurant",
        # Deliberately adversarial subtypes with known substring-collision
        # risk, inherited from the original keyword design (not
        # introduced by this slice) -- confirming they land in the same
        # (mis-triggered) family on both sides, not just "some" family.
        "Spanish Restaurant": "beauty_salon",  # "spa" substring in "Spanish"
        "Corvette Repair": "dental_medical",   # "vet" substring in "Corvette"
    }
    for subtype, family_key in subtype_to_family.items():
        expected_template_names, expected_palette_names = expected[family_key]
        for i in range(30):
            f = _F(business_name=f"Business {i}", domain=f"biz{i}.example", subtype=subtype)
            theme = engine.select_theme(f)
            assert theme.template.name in expected_template_names, (
                f"subtype={subtype!r} (expected family={family_key!r}): template "
                f"{theme.template.name!r} isn't in this family's own template list "
                f"{expected_template_names}"
            )
            assert theme.palette.name in expected_palette_names, (
                f"subtype={subtype!r} (expected family={family_key!r}): palette "
                f"{theme.palette.name!r} isn't in this family's own palette list "
                f"{expected_palette_names}"
            )

    # "Moving Company" and "" match none of the 5 named families --
    # confirm both template and palette land in the general fallback
    # (the full 9-template / 25-palette pool), also against a hardcoded
    # set, not TEMPLATES/PALETTES themselves.
    #
    # 2026-08-22, Slice 4: added the 5 new palette names (Cyan, Denim,
    # Plum, Champagne, Basil) to this hardcoded set -- they're only
    # reachable through their own named family OR this general fallback,
    # same as every other palette added in Slice C.1.
    all_template_names = {
        "Editorial Minimal", "Split Modern", "Bold Cinematic", "Trust Panel",
        "Boutique Editorial", "Framed Gallery", "Directory Listing",
        "Timeline Flow", "Compact Utility",
    }
    all_palette_names = {
        "Teal", "Blue", "Red", "Steel", "Navy", "Rose", "Orange", "Slate",
        "Mint", "Indigo", "Amber", "Charcoal", "Burgundy", "Forest",
        "Lavender", "Blush", "Olive", "Terracotta", "Sky", "Stone",
        "Cyan", "Denim", "Plum", "Champagne", "Basil",
    }
    for subtype in ("Moving Company", ""):
        for i in range(30):
            f = _F(business_name=f"Business {i}", domain=f"biz{i}.example", subtype=subtype)
            theme = engine.select_theme(f)
            assert theme.template.name in all_template_names
            assert theme.palette.name in all_palette_names


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
def _index_blocks(rating_html: str, stats_band: str, location_html: str = "",
                   highlights_html: str = "") -> dict:
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
        "highlights_html": highlights_html,
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


def _find_hero_el(dom):
    for el in dom.iter():
        if "hero" in el.attrs.get("class", ""):
            return el
    return None


# 2026-08-21, Slice 2 (hero visual restructuring): the hero used to stack
# both p1_html and p2_html -- two full prose paragraphs -- reading as a
# wall of text. p2_html now relocates to its own section right after the
# hero (mirroring bold_cinematic.py's pre-existing, already-shipping
# split), across all 9 templates, real DOM-checked -- not just "present
# on the page somewhere", which a plain substring check can't tell apart
# from "still inside the hero".
def test_p2_relocated_outside_hero_across_all_templates():
    f = _F(business_name="Acme Plumbing", domain="acme.com", subtype="Plumber",
           telephone="555-0100", locality="Austin")
    blocks = _index_blocks("", "")
    pal = palettes.palette_for("Plumber", 0)
    typ = engine.typography.typography_for(0)
    for tmpl in engine.TEMPLATES:
        theme = Theme(template=tmpl, palette=pal, typography=typ, hero_style="gradient")
        html = tmpl.render_index(f, "https://acme.com", theme, blocks)
        dom = audit_engine._parse_html(html)
        hero = _find_hero_el(dom)
        assert hero is not None, f"{tmpl.name}: no element with 'hero' in its class"
        assert "p1" in hero.text(), f"{tmpl.name}: p1_html is missing from the hero"
        assert "p2" not in hero.text(), f"{tmpl.name}: p2_html is still inside the hero"
        assert "p2" in dom.text(), f"{tmpl.name}: p2_html was dropped from the page entirely, not just relocated"


# 2026-08-21, Slice 2: highlights_html (services/areas/credentials, real
# facts only -- see site_engine.py's _highlights_html) is the real
# component meant to replace the lost second hero paragraph. Present on
# every template; inside the hero for 8 of 9, inside Trust Panel's own
# sidebar for the one template whose established pattern is to route
# every real trust fact there instead.
def test_highlights_render_and_are_correctly_placed():
    f = _F(business_name="Acme Plumbing", domain="acme.com", subtype="Plumber",
           telephone="555-0100", locality="Austin")
    highlights = '<div class="highlights"><span role="listitem">3 services offered</span></div>'
    blocks = _index_blocks("", "", highlights_html=highlights)
    pal = palettes.palette_for("Plumber", 0)
    typ = engine.typography.typography_for(0)
    for tmpl in engine.TEMPLATES:
        theme = Theme(template=tmpl, palette=pal, typography=typ, hero_style="gradient")
        html = tmpl.render_index(f, "https://acme.com", theme, blocks)
        assert 'class="highlights"' in html, f"{tmpl.name} dropped the highlights component"
        dom = audit_engine._parse_html(html)
        hero = _find_hero_el(dom)
        assert hero is not None, f"{tmpl.name}: no element with 'hero' in its class"
        if tmpl.name == "Trust Panel":
            assert "3 services offered" not in hero.text(), (
                "Trust Panel: highlights must route to the sidebar, not the narrow hero column"
            )
            assert 'class="sidebar"' in html and "3 services offered" in html, (
                "Trust Panel: highlights must still render somewhere real (the sidebar)"
            )
        else:
            assert "3 services offered" in hero.text(), (
                f"{tmpl.name}: highlights_html must render inside the hero"
            )


def test_highlights_omitted_gracefully_when_blocks_key_missing():
    # _index_blocks's own default ("") mirrors a real business with no
    # services/areas/credentials data reaching _highlights_html -- but
    # _highlights_html itself always returns a real <div> (the services
    # fallback phrase guarantees that), so the ONLY way this key is empty
    # is a caller (or an older cached blocks dict) that never set it at
    # all -- confirms every template's blocks.get("highlights_html") gate
    # degrades safely rather than raising a KeyError.
    f = _F(business_name="Acme Plumbing", domain="acme.com", subtype="Plumber",
           telephone="555-0100", locality="Austin")
    blocks = _index_blocks("", "")
    del blocks["highlights_html"]
    pal = palettes.palette_for("Plumber", 0)
    typ = engine.typography.typography_for(0)
    for tmpl in engine.TEMPLATES:
        theme = Theme(template=tmpl, palette=pal, typography=typ, hero_style="gradient")
        html = tmpl.render_index(f, "https://acme.com", theme, blocks)
        assert 'class="highlights"' not in html, f"{tmpl.name} fabricated highlights with no real data"


# 2026-08-21, Slice C.2: a template being reachable and rendering the
# right blocks doesn't prove it actually clears the real 90-point audit
# gate -- proves both new templates do, generating a real, complete site
# (not synthetic blocks) through generate_site() with facts chosen to
# actually hash to each new template, exactly like
# test_bold_cinematic_is_reachable_for_real_facts finds a real seed
# rather than forcing the template directly.
def _assert_templates_pass_real_audit_gate(template_subtypes: dict):
    # 2026-08-21: this file's own bare-bones _F() fixture (same_as=[], no
    # rating -- used elsewhere in this file only to prove business
    # names/subtypes render, never to prove a score) does NOT clear the
    # real 90-point gate regardless of template -- confirmed the first
    # version of the C.2 test failed with those exact facts on Trust
    # Panel for that reason, nothing to do with the template itself. A
    # real site needs real sameAs/rating data to pass, same as
    # test_site_engine.py's _dentist()/_plumber() fixtures already
    # supply.
    #
    # 2026-08-21, industry-aware template selection sub-slice: this used
    # to take a bare set of template names and search for all of them
    # under one shared subtype ("Plumber") -- broke the moment
    # select_theme() became subtype-aware, since a batched set can span
    # multiple real families (e.g. Trust Panel is Dental/Medical,
    # Boutique Editorial is Beauty/Salon; no single subtype reaches
    # both). Now takes {template_name: real_subtype_from_its_own_family}
    # and searches each independently with its own correct subtype.
    GOOD_CWV = {"lcp_s": 1.8, "inp_ms": 120, "cls": 0.05}
    for target, subtype in template_subtypes.items():
        found = False
        for i in range(200):
            f = _F(
                business_name=f"Business {i}", domain=f"biz{i}.example", subtype=subtype,
                locality="Austin", region="TX", postal_code="78701", country="US",
                telephone="555-0100", street="123 Main St",
                # 2026-08-21, Opus 5 review: this content used to be
                # hardcoded plumbing-specific text ("Fixing leaks",
                # "Quality plumbing", g.page/example-plumbing) regardless
                # of which real subtype/family was under test -- harmless
                # to the audit score (which doesn't grade topical
                # relevance) but genuinely incoherent once the subtype
                # here can be Dentist/Attorney/Hair Salon/Restaurant.
                # Kept industry-neutral instead.
                services=[types.SimpleNamespace(name="Great service", description="We do it well.")],
                service_areas=["Austin"],
                same_as=["https://g.page/example"],
                hours=["Mon-Fri 8:00-17:00"], faqs=[],
                credentials=["Licensed"], last_updated="2026-07-25",
                tagline="Quality service",
                rating=types.SimpleNamespace(value=4.9, count=218),
            )
            theme = engine.select_theme(f)
            if theme.template.name != target:
                continue
            found = True
            with tempfile.TemporaryDirectory() as tmp:
                generate_site(f, tmp)
                r = audit_engine.run_audit(tmp, cwv=GOOD_CWV)
                assert r.passed is True, f"{target} scored {r.normalized_score}, expected to pass"
            break
        assert found, f"never found a seed landing on {target!r} (subtype={subtype!r})"


def test_new_c2_templates_pass_the_real_audit_gate():
    _assert_templates_pass_real_audit_gate({"Trust Panel": "Dentist", "Boutique Editorial": "Hair Salon"})


# 2026-08-21, Slice C.3: same guarantee for the second batch of new
# templates.
def test_new_c3_templates_pass_the_real_audit_gate():
    _assert_templates_pass_real_audit_gate({"Framed Gallery": "Restaurant", "Directory Listing": "Plumber"})


# 2026-08-21, Site Generator Slice 3: real, licensing-free hero-background
# pattern wired into 7 of the 9 templates -- deliberately skipped for
# Boutique Editorial (narrow single-column magazine layout, no full-bleed
# hero box to put a background image behind) and Compact Utility (its own
# documented design intent is zero accent-color background fill anywhere,
# "safe by construction" -- a decorative pattern would contradict that).
_HERO_BG_WIRED_TEMPLATES = {
    "Editorial Minimal": "Dentist", "Split Modern": "Plumber", "Bold Cinematic": "Electrician",
    "Trust Panel": "Attorney", "Framed Gallery": "Restaurant", "Directory Listing": "HVACBusiness",
    "Timeline Flow": "Dentist",
}
_HERO_BG_SKIPPED_TEMPLATES = {"Boutique Editorial": "Hair Salon", "Compact Utility": "GeneralContractor"}


def _find_facts_for_template(target, subtype):
    for i in range(200):
        f = _F(
            business_name=f"Business {i}", domain=f"biz{i}.example", subtype=subtype,
            locality="Austin", region="TX", postal_code="78701", country="US",
            telephone="555-0100", street="123 Main St",
            services=[types.SimpleNamespace(name="Great service", description="We do it well.")],
            service_areas=["Austin"], same_as=["https://g.page/example"],
            hours=["Mon-Fri 8:00-17:00"], faqs=[], credentials=["Licensed"],
            last_updated="2026-07-25", tagline="Quality service",
            rating=types.SimpleNamespace(value=4.9, count=218),
        )
        if engine.select_theme(f).template.name == target:
            return f
    return None


def _hero_selector_and_rule(css: str, template_name: str) -> tuple:
    """Finds the real .hero/.hero-in RULE BLOCK a template's own CSS
    declares -- not just whether some CSS text substring floats anywhere
    in the stylesheet. Returns (selector, rule_body) or (None, None).

    2026-08-21, Opus 5 review of the first version of this slice's tests:
    mutation-proven broken. Renaming a template's real selector to
    `.hero-DEADSELECTOR` (so the background rule matches nothing in the
    actual rendered markup) still left the old test green, because it
    only checked whether the marker STRING appeared anywhere in the
    `<style>` block -- exactly the "CSS rule matches nothing real" defect
    class this session has already found and fixed at least 4 times
    elsewhere (footer/FAQ/lede/menu-price). This helper instead parses
    real selector -> declaration-block pairs (same technique the
    generalized WCAG scanner elsewhere in this file already uses for the
    identical reason) so a test can assert the background rule lives
    inside the selector that's actually used in the rendered HTML.

    2026-08-21, Opus 5 review round 2: the first version of this helper
    did its own regex directly against the raw CSS, comments included --
    mutation-proven still broken. Deleting the real background rule but
    leaving a comment that happens to quote the old rule text (a CSS
    comment ships verbatim into the rendered <style> block, exactly the
    same fact that caused the trust_panel.py collision this same slice
    already found and fixed once) left the test green. Reuses the shared
    _parse_css_rules() (comment-stripped) instead of re-deriving a second,
    weaker parser -- the exact fix pattern this file already has on hand
    for this defect class."""
    selector = ".hero-in" if template_name == "Split Modern" else ".hero"
    for raw_selector, body in _parse_css_rules(css):
        if _selector_base(raw_selector) == selector and raw_selector.strip() == selector:
            return selector, body
    return None, None


def test_hero_bg_asset_is_wired_into_the_7_templates_that_should_use_it():
    marker = "background-image:url('assets/hero-bg.svg')"
    for target, subtype in _HERO_BG_WIRED_TEMPLATES.items():
        f = _find_facts_for_template(target, subtype)
        assert f is not None, f"never found a seed landing on {target!r}"
        with tempfile.TemporaryDirectory() as tmp:
            generate_site(f, tmp)
            assert os.path.exists(os.path.join(tmp, "assets", "hero-bg.svg")), \
                f"{target}: hero-bg.svg asset was not written"
            index = open(os.path.join(tmp, "index.html"), encoding="utf-8").read()
            # The real selector must exist in this page's own CSS AND
            # actually be present in the rendered body markup (proves the
            # rule matches something real, not a dead/renamed selector).
            selector, rule = _hero_selector_and_rule(index, target)
            assert selector is not None, f"{target}: no real {selector!r} rule found in this page's own CSS at all"
            assert marker in rule, f"{target}: {selector!r} rule exists but doesn't declare the hero-bg background"
            body_class = selector.lstrip(".")
            assert f'class="{body_class}"' in index or f'class="wrap {body_class}"' in index or f' {body_class}"' in index, \
                f"{target}: {selector!r} is declared in CSS but that class never appears in the rendered body"


def test_hero_bg_is_not_wired_into_the_2_templates_that_deliberately_skip_it():
    marker = "background-image:url('assets/hero-bg.svg')"
    for target, subtype in _HERO_BG_SKIPPED_TEMPLATES.items():
        f = _find_facts_for_template(target, subtype)
        assert f is not None, f"never found a seed landing on {target!r}"
        with tempfile.TemporaryDirectory() as tmp:
            generate_site(f, tmp)
            index = open(os.path.join(tmp, "index.html"), encoding="utf-8").read()
            assert marker not in index, \
                f"{target}: this template deliberately doesn't use the hero background -- CSS marker should not appear"
            # The asset is still written unconditionally for every site (a
            # real, deterministic file, not a stub) even if this template's
            # own CSS doesn't reference it.
            assert os.path.exists(os.path.join(tmp, "assets", "hero-bg.svg"))


def test_hero_bg_actually_differs_between_two_real_generated_businesses():
    # 2026-08-21, Opus 5 review: mutation-proven the unit-level determinism
    # test alone is not enough -- hardcoding compute_seed(f) to always
    # return 0 (every real business gets byte-identical hero art) left the
    # full 477-test suite green, because nothing exercised the real
    # generate_site() -> compute_seed() -> _hero_bg_svg() path end to end.
    # This is the same "anti-stub" guarantee already proven for logo.svg
    # ("two different businesses get two different logos"), applied here.
    dentist = _F(
        business_name="Cedar Ridge Dental", domain="cedarridgedental.example", subtype="Dentist",
        locality="Portland", region="OR", postal_code="97201", country="US",
        telephone="555-0100", street="1200 Cedar Road",
        services=[types.SimpleNamespace(name="Cleanings", description="Real cleanings.")],
        service_areas=["Portland"], same_as=["https://g.page/example"],
        hours=["Mon-Fri 8:00-17:00"], faqs=[], credentials=["ADA membership"],
        last_updated="2026-07-25", tagline="Family dentistry",
        rating=types.SimpleNamespace(value=4.9, count=218),
    )
    plumber = _F(
        business_name="Saguaro Plumbing", domain="saguaroplumbing.example", subtype="Plumber",
        locality="Tucson", region="AZ", postal_code="85701", country="US",
        telephone="555-0199", street="55 Cactus Way",
        services=[types.SimpleNamespace(name="Leak repair", description="Real leak repair.")],
        service_areas=["Tucson"], same_as=["https://g.page/example2"],
        hours=["Mon-Sat 7:00-19:00"], faqs=[], credentials=["Licensed"],
        last_updated="2026-07-18", tagline="Trusted plumbing",
        rating=types.SimpleNamespace(value=4.8, count=141),
    )
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        generate_site(dentist, d1)
        generate_site(plumber, d2)
        svg1 = open(os.path.join(d1, "assets", "hero-bg.svg"), encoding="utf-8").read()
        svg2 = open(os.path.join(d2, "assets", "hero-bg.svg"), encoding="utf-8").read()
        assert svg1 != svg2, "two different real businesses produced byte-identical hero backgrounds"
        # 2026-08-21, self-caught while mutation-testing this very fix:
        # pinning the seed passed into _hero_bg_svg to a constant (the
        # exact mutation this test exists to catch) still left this
        # assertion green, because theme.palette is computed by a
        # SEPARATE call to compute_seed(f) inside select_theme() -- a
        # dentist and a plumber land on different palette FAMILIES
        # regardless of what seed _hero_bg_svg itself receives, so color
        # alone made the two files differ even with the real bug present.
        # Extracts the circle cx/cy/r values specifically (purely
        # seed-derived layout, independent of which fill color the
        # palette contributes) so this test can't be satisfied by color
        # variation alone -- it has to prove the LAYOUT itself moved.
        positions1 = re.findall(r'cx="(\d+)" cy="(\d+)" r="(\d+)"', svg1)
        positions2 = re.findall(r'cx="(\d+)" cy="(\d+)" r="(\d+)"', svg2)
        assert positions1 and positions2, "expected real circle positions in both generated patterns"
        assert positions1 != positions2, \
            "two different real businesses produced the same circle layout -- only color varied, seed is not reaching the layout"


def test_hero_bg_svg_is_deterministic_and_varies_between_businesses():
    from app.services.site_engine import _hero_bg_svg
    p = palettes.PALETTES[0]
    a = _hero_bg_svg(12345, p)
    b = _hero_bg_svg(12345, p)
    c = _hero_bg_svg(99999, p)
    assert a == b, "same seed must produce the same pattern"
    assert a != c, "different seeds must produce different patterns"
    import xml.etree.ElementTree as ET
    ET.fromstring(a)  # real, well-formed XML, not just a string that looks like SVG


def test_hero_bg_uses_one_group_opacity_not_per_shape_opacity():
    # 2026-08-21, Opus 5 review: per-shape opacity composites additively
    # where circles overlap (1-(1-a)^N for N same-colored layers), so
    # "each shape is faint" does NOT mean "the pattern is faint" -- a real
    # generated site (Dentist -> Timeline Flow + Mint) hit an effective
    # ~0.35 alpha from 3 overlapping circles and dropped .hero .lede
    # (var(--muted) on the composited background) to 4.458:1, below the
    # real AA floor. Fixed architecturally: every circle is fully opaque,
    # and ONE <g opacity="..."> wraps the whole pattern -- group opacity is
    # a single post-composite fade, so the maximum effective opacity
    # anywhere in the pattern is exactly the group's own value, regardless
    # of circle count or overlap. This test locks in the MECHANISM (no
    # per-shape opacity survives), not just the value range -- a
    # regression back to per-shape opacity would fail this even if it
    # happened to pick "safe-looking" individual numbers.
    from app.services.site_engine import _hero_bg_svg, _HERO_BG_MIN_GROUP_OPACITY, _HERO_BG_MAX_GROUP_OPACITY
    for seed in range(30):
        svg = _hero_bg_svg(seed, palettes.PALETTES[0])
        assert "<circle" in svg, f"seed {seed}: expected real <circle> elements in the generated SVG"
        # No circle element carries its own opacity attribute -- that's
        # the actual mechanism fix, not just a value-range coincidence.
        for circle_tag in re.findall(r"<circle[^/]*/>", svg):
            assert "opacity=" not in circle_tag, f"seed {seed}: a <circle> still carries its own opacity: {circle_tag!r}"
        group_opacities = [float(x) for x in re.findall(r'<g opacity="([\d.]+)"', svg)]
        assert len(group_opacities) == 1, f"seed {seed}: expected exactly one group-level opacity, found {group_opacities}"
        go = group_opacities[0]
        assert _HERO_BG_MIN_GROUP_OPACITY <= go <= _HERO_BG_MAX_GROUP_OPACITY, \
            f"seed {seed}: group opacity {go} outside the verified-safe range"


def test_hero_bg_composited_contrast_clears_wcag_aa_on_every_real_palette():
    # 2026-08-21: the real, load-bearing safety test. Computes the ACTUAL
    # alpha-composited background color (bg mixed with accent/accent_soft
    # at the group opacity) using the same source-over compositing math
    # browsers use, then checks real contrast_ratio() (the same function
    # palettes.assert_wcag() itself uses) for text colors that actually
    # render inside a hero-bg-wired hero (var(--ink) for h1, var(--muted)
    # for .lede/rating text, and var(--gold) for the star-rating glyphs)
    # against that composited background, across all 20 real palettes, at
    # BOTH ends of the real opacity range this generator can produce.
    #
    # 2026-08-21, Opus 5 review round 2: the first version of this test
    # only checked ink/muted -- gold was reasoned out of scope because
    # several palettes already fail gold/bg at baseline (zero pattern
    # involved) and this test's job was never to fix a pre-existing gap.
    # That reasoning stopped short: 13 of 20 palettes DO clear 4.5:1 on
    # gold/bg at baseline, and the pattern was regressing every one of
    # them below 4.5 (reachable in 32 real template/palette pairs).
    # Checking gold ONLY where a palette's own baseline (zero pattern)
    # already clears 4.5:1 is the right scope: it holds this slice to not
    # making anything WORSE than it already was, without asserting a bar
    # (gold/bg >= 4.5 universally) this codebase has never actually held
    # and that isn't this slice's defect to fix.
    from app.services.site_engine import _HERO_BG_MIN_GROUP_OPACITY, _HERO_BG_MAX_GROUP_OPACITY

    def _mix(bg_hex, fg_hex, alpha):
        bg = tuple(int(bg_hex.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
        fg = tuple(int(fg_hex.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
        out = tuple(round(bg[c] * (1 - alpha) + fg[c] * alpha) for c in range(3))
        return "#%02X%02X%02X" % out

    baseline_gold_pass = {p.name for p in palettes.PALETTES if palettes.contrast_ratio(p.gold, p.bg) >= 4.5}

    failures = []
    for p in palettes.PALETTES:
        for opacity in (_HERO_BG_MIN_GROUP_OPACITY, _HERO_BG_MAX_GROUP_OPACITY):
            for fill in (p.accent, p.accent_soft):
                composited_bg = _mix(p.bg, fill, opacity)
                checks = [(p.ink, "ink"), (p.muted, "muted")]
                if p.name in baseline_gold_pass:
                    checks.append((p.gold, "gold"))
                for text_color, label in checks:
                    cr = palettes.contrast_ratio(text_color, composited_bg)
                    if cr < 4.5:
                        failures.append(f"{p.name}/{label} on {fill} @ {opacity}: {cr:.3f}")
    assert not failures, "real WCAG AA violations from the hero background pattern: " + "; ".join(failures)


# 2026-08-21, Slice C.4: same guarantee for the third batch of new
# templates.
def test_new_c4_templates_pass_the_real_audit_gate():
    _assert_templates_pass_real_audit_gate({"Timeline Flow": "Attorney", "Compact Utility": "Plumber"})


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
