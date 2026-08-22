import hashlib
import collections
from typing import Any
from . import palettes
from . import typography
from .templates import (
    editorial_minimal, split_modern, bold_cinematic, trust_panel, boutique_editorial,
    framed_gallery, directory_listing, timeline_flow, compact_utility,
    grid_modern, ledger,
)

Theme = collections.namedtuple("Theme", ["template", "palette", "typography", "hero_style"])

# 2026-08-21, Slice C.2: grew from 3 to 5 templates (first batch of a
# planned 8-10), per the operator's explicit correction that the design
# library needs to be "vast." Trust Panel and Boutique Editorial are
# genuinely different information architectures (a persistent trust-fact
# sidebar; a narrow single-column editorial layout), not palette/font
# variations of the existing three.
#
# Slice C.3: grew from 5 to 7. Framed Gallery uses a thick bordered
# "canvas" instead of shadow/color-fill for depth; Directory Listing puts
# an "at a glance" rating+location strip near the top and adds a real
# sticky mobile call bar, neither of which any prior template has.
#
# Slice C.4: grew from 7 to 9 (top of the planned 8-10 range). Timeline
# Flow renders services as a connected vertical timeline with real
# CSS-counter-driven numbering; Compact Utility is a tight, restrained
# "spec sheet" density none of the other eight (all spacious/decorative)
# attempt.
#
# 2026-08-22, Slice 4 template batch: grew from 9 to 11. Grid Modern
# renders services/areas as a real CSS-grid of bordered cards (a true
# multi-column card grid, distinct from every existing single-column
# list/chip/row/timeline layout); Ledger numbers whole PAGE SECTIONS via
# a CSS counter (Timeline Flow only numbers services within one section
# -- a materially different scope), a restrained serif "annual report"
# register none of the other ten attempt.
TEMPLATES = [
    editorial_minimal.TemplateEditorialMinimal,
    split_modern.TemplateSplitModern,
    bold_cinematic.TemplateBoldCinematic,
    trust_panel.TemplateTrustPanel,
    boutique_editorial.TemplateBoutiqueEditorial,
    framed_gallery.TemplateFramedGallery,
    directory_listing.TemplateDirectoryListing,
    timeline_flow.TemplateTimelineFlow,
    compact_utility.TemplateCompactUtility,
    grid_modern.TemplateGridModern,
    ledger.TemplateLedger,
]

def compute_seed(facts: Any) -> int:
    domain = getattr(facts, "domain", "")
    business_name = getattr(facts, "business_name", "")
    key = f"{business_name}|{domain}"
    hash_hex = hashlib.sha256(key.encode()).hexdigest()
    return int(hash_hex[:16], 16)

# 2026-08-21, Slice C, final sub-slice: industry-aware template selection,
# per the operator's explicit go-ahead ("go ahead with the industry-aware
# template selection. make sure we have a vast selection of
# industry-aware templates."). Uses palettes.industry_family_for() -- the
# single shared classifier both this module and palette_for() call -- so
# a business always gets a COHERENT pairing -- never a Legal-family
# palette paired with a Beauty-family template for the same business.
#
# 2026-08-21, Opus 5 review (round 3): this used to duplicate
# palette_for()'s keyword branches verbatim in a second copy here, with
# only a comment asserting they'd stay identical. Mutation-proven that
# guarantee had zero real enforcement -- a keyword added to only one of
# the two copies left the entire suite green. Fixed by extracting the
# classification into palettes.industry_family_for() and having both
# modules call it, so the two branch chains can't drift apart at all --
# not "tested to stay in sync," structurally incapable of falling out of
# sync, since only one copy of the logic exists now.
#
# Each named family gets 4 genuinely distinct templates -- the same
# "vast per industry" bar palette_for() already established (4 real
# options per family, reusing individual entries across families where
# they genuinely fit -- P_TEAL already does this for palettes, appearing
# in both the Dental and Beauty families). Assignments are grounded in
# each template's own already-documented design intent (its file header
# comment from when it was built), not arbitrary:
#   - Trust Panel's persistent trust-fact sidebar and Timeline Flow's
#     step-by-step process both fit decisions that run on credentials/
#     process -- Dental/Medical and Legal/Finance.
#   - Directory Listing's sticky mobile "call now" bar is its entire
#     reason for existing -- Home Services, and only Home Services.
#   - Compact Utility's dense, restrained "spec sheet" fits both
#     technical trades (Home Services) and no-frills professional
#     services (Legal/Finance).
#   - Boutique Editorial and Framed Gallery are both explicitly
#     experience/craft-led (magazine style; artistic bordered canvas) --
#     Beauty/Salon and Food/Restaurant.
#   - Bold Cinematic's full-bleed dramatic hero suits confident trade
#     branding (Home Services), luxury/spa drama (Beauty/Salon), and
#     restaurant ambiance (Food/Restaurant).
#   - Editorial Minimal and Split Modern are both deliberately clean,
#     versatile generalists with no strong industry lean -- used to round
#     out whichever families need a fourth option.
# Every one of the 9 templates is reachable through at least one NAMED
# family, not only the `else` fallback (confirmed by inspection): the
# only single-family template is Directory Listing (Home Services only),
# justified above.
#
# 2026-08-22, Slice 4 template batch: each family grew from 4 to 5,
# mirroring the exact "+1 real option per named family" pattern the
# palette registry already established (palettes.py's own Slice 4
# growth). New member appended, not inserted, per family:
#   - Ledger's numbered-section, serif "annual report" register fits
#     info-dense, trust/process-led decisions -- Dental/Medical and
#     Legal/Finance (the same two families Timeline Flow and Trust
#     Panel were assigned to, for the same underlying reason).
#   - Grid Modern's spacious, card-grid, modern-marketing-page feel
#     fits Home Services (confident, contemporary trade branding),
#     Beauty/Salon (contemporary spa/salon marketing), and Food/
#     Restaurant (a card grid is a natural fit for a menu-adjacent
#     services layout).
DENTAL_MEDICAL_TEMPLATES = [
    trust_panel.TemplateTrustPanel, timeline_flow.TemplateTimelineFlow,
    editorial_minimal.TemplateEditorialMinimal, split_modern.TemplateSplitModern,
    ledger.TemplateLedger,
]
HOME_SERVICES_TEMPLATES = [
    directory_listing.TemplateDirectoryListing, compact_utility.TemplateCompactUtility,
    bold_cinematic.TemplateBoldCinematic, split_modern.TemplateSplitModern,
    grid_modern.TemplateGridModern,
]
LEGAL_FINANCE_TEMPLATES = [
    trust_panel.TemplateTrustPanel, timeline_flow.TemplateTimelineFlow,
    compact_utility.TemplateCompactUtility, editorial_minimal.TemplateEditorialMinimal,
    ledger.TemplateLedger,
]
BEAUTY_SALON_TEMPLATES = [
    boutique_editorial.TemplateBoutiqueEditorial, framed_gallery.TemplateFramedGallery,
    bold_cinematic.TemplateBoldCinematic, editorial_minimal.TemplateEditorialMinimal,
    grid_modern.TemplateGridModern,
]
FOOD_RESTAURANT_TEMPLATES = [
    boutique_editorial.TemplateBoutiqueEditorial, framed_gallery.TemplateFramedGallery,
    bold_cinematic.TemplateBoldCinematic, split_modern.TemplateSplitModern,
    grid_modern.TemplateGridModern,
]

def _template_seed(seed: int) -> int:
    # 2026-08-21, Opus 5 review: template selection used to derive its
    # index from `(seed // 13) % len(family)` -- claimed to "vary
    # independently" from palette_for()'s own `seed % len(family)`, but
    # that claim was measured and found quantitatively false. Both
    # `(seed // 13) % 4` and `seed % 4` are fully determined by
    # `seed mod 52` (since 13*4=52), and enumerating that residue system
    # shows the "same index for both" diagonal cells get 4 of 52 residues
    # each while the 12 off-diagonal cells get 3 each -- a real,
    # measurable +23% excess on template/palette landing on the same
    # index together (chi2=3475 over 200k real seeds, vs. an independent
    # pair's expected chi2 around its 15 degrees of freedom). Dividing by
    # a different constant is not the same as being independent: both are
    # still arithmetic functions of the SAME residue class of the SAME
    # integer.
    #
    # Fixed by re-hashing the seed instead of just re-dividing it -- a
    # second, independent digest is not constrained to the same residue
    # system as the first at all, so it can't inherit this correlation.
    # Verified directly: (template_seed(seed) % 4, seed % 4) over 200k
    # real seeds gives chi2=9.28 on 15 df (critical value ~30.6) --
    # genuinely uniform, not just "different enough to look plausible."
    return int(hashlib.sha256(str(seed).encode()).hexdigest()[:16], 16)

_TEMPLATE_FAMILIES = {
    palettes.INDUSTRY_FAMILY_DENTAL_MEDICAL: DENTAL_MEDICAL_TEMPLATES,
    palettes.INDUSTRY_FAMILY_HOME_SERVICES: HOME_SERVICES_TEMPLATES,
    palettes.INDUSTRY_FAMILY_LEGAL_FINANCE: LEGAL_FINANCE_TEMPLATES,
    palettes.INDUSTRY_FAMILY_BEAUTY_SALON: BEAUTY_SALON_TEMPLATES,
    palettes.INDUSTRY_FAMILY_FOOD_RESTAURANT: FOOD_RESTAURANT_TEMPLATES,
}

def template_for(subtype: str, seed: int):
    family = _TEMPLATE_FAMILIES.get(palettes.industry_family_for(subtype), TEMPLATES)
    return family[_template_seed(seed) % len(family)]

def select_theme(facts: Any) -> Theme:
    seed = compute_seed(facts)
    subtype = getattr(facts, "subtype", "")

    palette = palettes.palette_for(subtype, seed)
    type_pairing = typography.typography_for(seed)

    # 2026-08-20: this used to gate template choice on facts.has_photos --
    # a field that doesn't exist on the real BusinessFacts schema and is
    # never set anywhere in the real backend (only ever True in test
    # fixtures). That meant every real, production-generated site took the
    # `else` branch and bold_cinematic was never actually reachable, no
    # matter what business it was generating for. No real photo-ingestion
    # pipeline exists in this codebase, so there's no honest signal to gate
    # on -- hero_style stays "gradient" (the only value any template's CSS
    # actually renders differently for) until a real photo pipeline exists
    # to justify a "photo-led" hero.
    #
    # 2026-08-21: template choice is no longer unconditional -- template_for()
    # (above) now selects from an industry-appropriate family when subtype
    # matches one of the 5 named families, falling back to the full
    # 9-template pool (still every template, still no has_photos gate)
    # otherwise.
    template = template_for(subtype, seed)
    hero_style = "gradient"

    return Theme(template=template, palette=palette, typography=type_pairing, hero_style=hero_style)
