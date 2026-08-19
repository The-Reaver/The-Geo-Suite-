import collections

def _luminance(hex_color: str) -> float:
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = "".join(c+c for c in hex_color)
    r, g, b = (int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    
    def adjust(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    
    return 0.2126 * adjust(r) + 0.7152 * adjust(g) + 0.0722 * adjust(b)

def contrast_ratio(hex1: str, hex2: str) -> float:
    l1 = _luminance(hex1)
    l2 = _luminance(hex2)
    bright = max(l1, l2)
    dark = min(l1, l2)
    return (bright + 0.05) / (dark + 0.05)

# A Palette contains the tokens needed by all templates.
Palette = collections.namedtuple("Palette", [
    "name", "bg", "surface", "ink", "muted", "line",
    "accent", "accent_dark", "accent_soft", "grad_start", "grad_end", "gold"
])

# Define the base palettes pre-checked for WCAG AA
# Dental/Medical (Teal/Blue)
P_TEAL = Palette("Teal", "#FBFBF9", "#FFFFFF", "#0A0F0D", "#5B6660", "#EAEBE6", 
                 "#0E9488", "#0B6E64", "#E7F1EE", "#2DD4BF", "#0E9488", "#C08A2D")

P_BLUE = Palette("Blue", "#F8FAFC", "#FFFFFF", "#0F172A", "#475569", "#E2E8F0",
                 "#2563EB", "#1D4ED8", "#DBEAFE", "#60A5FA", "#2563EB", "#D97706")

# Home Services (Bold Red/Steel)
P_RED = Palette("Red", "#FAFAFA", "#FFFFFF", "#171717", "#525252", "#E5E5E5",
                "#DC2626", "#B91C1C", "#FEE2E2", "#F87171", "#DC2626", "#D97706")

P_STEEL = Palette("Steel", "#F8FAFC", "#FFFFFF", "#0F172A", "#475569", "#E2E8F0",
                  "#475569", "#334155", "#F1F5F9", "#94A3B8", "#475569", "#D97706")

# Legal/Finance (Navy/Gold)
P_NAVY = Palette("Navy", "#F8FAFC", "#FFFFFF", "#020617", "#334155", "#E2E8F0",
                 "#0F172A", "#020617", "#F1F5F9", "#334155", "#0F172A", "#B45309")

# Beauty/Salon (Warm/Elegant)
P_ROSE = Palette("Rose", "#FFF1F2", "#FFFFFF", "#2A1215", "#881337", "#FFE4E6",
                 "#E11D48", "#BE123C", "#FFE4E6", "#FB7185", "#E11D48", "#D97706")

# Food/Restaurant (Warm)
P_ORANGE = Palette("Orange", "#FFF7ED", "#FFFFFF", "#431407", "#7C2D12", "#FFEDD5",
                   "#EA580C", "#C2410C", "#FFEDD5", "#FB923C", "#EA580C", "#B45309")

# Professional/Neutral
P_SLATE = Palette("Slate", "#F8FAFC", "#FFFFFF", "#0F172A", "#475569", "#E2E8F0",
                  "#334155", "#1E293B", "#F1F5F9", "#64748B", "#334155", "#D97706")


PALETTES = [P_TEAL, P_BLUE, P_RED, P_STEEL, P_NAVY, P_ROSE, P_ORANGE, P_SLATE]

def palette_for(subtype: str, seed: int) -> Palette:
    subtype = subtype.lower() if subtype else ""
    if "dent" in subtype or "medical" in subtype or "physician" in subtype or "vet" in subtype:
        family = [P_TEAL, P_BLUE]
    elif "plumb" in subtype or "hvac" in subtype or "electric" in subtype or "repair" in subtype or "contractor" in subtype:
        family = [P_RED, P_STEEL]
    elif "law" in subtype or "attorney" in subtype or "finance" in subtype or "estate" in subtype:
        family = [P_NAVY, P_SLATE]
    elif "salon" in subtype or "beauty" in subtype or "spa" in subtype:
        family = [P_ROSE, P_TEAL]
    elif "food" in subtype or "restaurant" in subtype or "cafe" in subtype:
        family = [P_ORANGE, P_RED]
    else:
        family = PALETTES
    return family[seed % len(family)]

def assert_wcag():
    for p in PALETTES:
        # body ink vs bg
        assert contrast_ratio(p.ink, p.bg) >= 4.5, f"Palette {p.name} fails body contrast"
        # large text accent vs bg (optional but good practice)
        # assert contrast_ratio(p.accent, p.bg) >= 3.0, f"Palette {p.name} fails large contrast"

assert_wcag()
