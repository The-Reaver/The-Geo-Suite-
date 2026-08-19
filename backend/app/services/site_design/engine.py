import hashlib
import collections
from typing import Any
from . import palettes
from . import typography
from .templates import editorial_minimal, split_modern, bold_cinematic

Theme = collections.namedtuple("Theme", ["template", "palette", "typography", "hero_style"])

TEMPLATES = [
    editorial_minimal.TemplateEditorialMinimal,
    split_modern.TemplateSplitModern,
    bold_cinematic.TemplateBoldCinematic
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
    
    has_photos = getattr(facts, "has_photos", False)
    if has_photos:
        template = TEMPLATES[seed % len(TEMPLATES)]
        hero_style = "photo-led"
    else:
        # Bias towards minimal/gradient
        minimal_templates = [editorial_minimal.TemplateEditorialMinimal, split_modern.TemplateSplitModern]
        template = minimal_templates[seed % len(minimal_templates)]
        hero_style = "gradient"
        
    return Theme(template=template, palette=palette, typography=type_pairing, hero_style=hero_style)
