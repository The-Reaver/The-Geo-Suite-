import hashlib
import collections
from typing import Any
from . import palettes
from . import typography
from .templates import (
    editorial_minimal, split_modern, bold_cinematic, trust_panel, boutique_editorial,
    framed_gallery, directory_listing, timeline_flow, compact_utility,
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
# industry-aware templates."). Mirrors palette_for()'s exact
# subtype-detection branches (same keywords, same branch order) so a
# business always gets a COHERENT pairing -- never a Legal-family
# palette paired with a Beauty-family template for the same business.
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
DENTAL_MEDICAL_TEMPLATES = [
    trust_panel.TemplateTrustPanel, timeline_flow.TemplateTimelineFlow,
    editorial_minimal.TemplateEditorialMinimal, split_modern.TemplateSplitModern,
]
HOME_SERVICES_TEMPLATES = [
    directory_listing.TemplateDirectoryListing, compact_utility.TemplateCompactUtility,
    bold_cinematic.TemplateBoldCinematic, split_modern.TemplateSplitModern,
]
LEGAL_FINANCE_TEMPLATES = [
    trust_panel.TemplateTrustPanel, timeline_flow.TemplateTimelineFlow,
    compact_utility.TemplateCompactUtility, editorial_minimal.TemplateEditorialMinimal,
]
BEAUTY_SALON_TEMPLATES = [
    boutique_editorial.TemplateBoutiqueEditorial, framed_gallery.TemplateFramedGallery,
    bold_cinematic.TemplateBoldCinematic, editorial_minimal.TemplateEditorialMinimal,
]
FOOD_RESTAURANT_TEMPLATES = [
    boutique_editorial.TemplateBoutiqueEditorial, framed_gallery.TemplateFramedGallery,
    bold_cinematic.TemplateBoldCinematic, split_modern.TemplateSplitModern,
]

def template_for(subtype: str, seed: int):
    subtype = subtype.lower() if subtype else ""
    if "dent" in subtype or "medical" in subtype or "physician" in subtype or "vet" in subtype:
        family = DENTAL_MEDICAL_TEMPLATES
    elif "plumb" in subtype or "hvac" in subtype or "electric" in subtype or "repair" in subtype or "contractor" in subtype:
        family = HOME_SERVICES_TEMPLATES
    elif "law" in subtype or "attorney" in subtype or "finance" in subtype or "estate" in subtype:
        family = LEGAL_FINANCE_TEMPLATES
    elif "salon" in subtype or "beauty" in subtype or "spa" in subtype:
        family = BEAUTY_SALON_TEMPLATES
    elif "food" in subtype or "restaurant" in subtype or "cafe" in subtype:
        family = FOOD_RESTAURANT_TEMPLATES
    else:
        family = TEMPLATES
    # Decorrelated from palette_for()'s own seed % len(family): several
    # named families have identically-sized (4-item) template and
    # palette lists, and plain seed % 4 for both would put template and
    # palette choice in perfect lockstep within a family (index 0 always
    # pairs the same palette with the same template). typography_for()
    # already solves the analogous problem with seed // 7; // 13 here is
    # a different divisor so all three selections vary independently.
    return family[(seed // 13) % len(family)]

def select_theme(facts: Any) -> Theme:
    seed = compute_seed(facts)

    palette = palettes.palette_for(getattr(facts, "subtype", ""), seed)
    type_pairing = typography.typography_for(seed)

    # 2026-08-20: this used to gate template choice on facts.has_photos --
    # a field that doesn't exist on the real BusinessFacts schema and is
    # never set anywhere in the real backend (only ever True in test
    # fixtures). That meant every real, production-generated site took the
    # `else` branch and bold_cinematic was never actually reachable, no
    # matter what business it was generating for. No real photo-ingestion
    # pipeline exists in this codebase, so there's no honest signal to gate
    # on -- select from all three templates unconditionally so the visual
    # variety they were built for is real, not theoretical. hero_style
    # stays "gradient" (the only value any template's CSS actually renders
    # differently for) until a real photo pipeline exists to justify a
    # "photo-led" hero.
    template = template_for(getattr(facts, "subtype", ""), seed)
    hero_style = "gradient"

    return Theme(template=template, palette=palette, typography=type_pairing, hero_style=hero_style)
