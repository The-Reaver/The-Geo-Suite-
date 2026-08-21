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
    template = TEMPLATES[seed % len(TEMPLATES)]
    hero_style = "gradient"

    return Theme(template=template, palette=palette, typography=type_pairing, hero_style=hero_style)
