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

# 2026-08-21, Slice C.1: grew from 8 to 20 palettes per the operator's
# explicit correction ("this library of templates, palettes, type
# pairings need to be vast"). Two new options per existing named family
# (2->4 real choices each), plus two general-purpose entries that only
# ever surface through the `else` catch-all. Every ink/bg pair below was
# verified against this module's own contrast_ratio() before being added
# -- weakest margin is Sky at 13.93, well clear of the 4.5 floor
# assert_wcag() enforces on the whole list below.
#
# 2026-08-21, Opus 5 review of the first cut of this slice found two
# real defects, both fixed in the values below:
# 1. assert_wcag() only ever checked ink/bg -- every template's primary
#    CTA button/band renders background:var(--accent);color:#fff, and 5
#    of the 12 new accents (Mint, Olive, Amber, Sky, Indigo) shipped that
#    pairing below WCAG's 3:1 floor for large-scale UI text (Mint
#    measured 2.54:1). accent/accent_dark for those five are now real
#    Tailwind-scale darker steps (e.g. emerald-700/800 for Mint), each
#    independently re-verified at white/accent >= 4.6 -- comfortably
#    clear of both the 3:1 floor assert_wcag() now enforces and the
#    stricter 4.5:1 normal-text bar, not just barely passing.
# 2. Terracotta was Orange's own ramp shifted one step darker (identical
#    ink and accent_soft, accent == Orange's accent_dark) -- not a
#    genuinely new option. Redesigned as a real muted clay/rust tone
#    (accent saturation ~0.47 vs. Orange's ~0.90 at a similar hue angle
#    -- the same "muted earthy tone vs. vivid saturated tone" distinction
#    real design systems use), with its own ink/bg/accent_soft, none
#    shared with Orange.

# Dental/Medical, additional options
P_MINT = Palette("Mint", "#F7FDFB", "#FFFFFF", "#06281F", "#3F6B5C", "#DCEEE7",
                 "#047857", "#065F46", "#D1FAE5", "#34D399", "#047857", "#B45309")

P_INDIGO = Palette("Indigo", "#F5F6FF", "#FFFFFF", "#1E1B4B", "#4C4A75", "#E0E1FA",
                   "#4F46E5", "#4338CA", "#E0E7FF", "#818CF8", "#4F46E5", "#B45309")

# Home Services, additional options
P_AMBER = Palette("Amber", "#FFFBF5", "#FFFFFF", "#431E07", "#7C4A1B", "#FDEBD3",
                  "#B45309", "#92400E", "#FEF3C7", "#F59E0B", "#B45309", "#D97706")

P_CHARCOAL = Palette("Charcoal", "#FAFAFA", "#FFFFFF", "#171717", "#52525B", "#E4E4E7",
                     "#27272A", "#18181B", "#F4F4F5", "#52525B", "#27272A", "#B45309")

# Legal/Finance, additional options
P_BURGUNDY = Palette("Burgundy", "#FBF7F7", "#FFFFFF", "#2D0A0F", "#6B2530", "#F0DEDF",
                     "#881337", "#4C0519", "#FFE4E6", "#BE123C", "#881337", "#B45309")

P_FOREST = Palette("Forest", "#F6F9F6", "#FFFFFF", "#0B2818", "#355E42", "#DCEBE0",
                   "#166534", "#14532D", "#DCFCE7", "#22C55E", "#166534", "#B45309")

# Beauty/Salon, additional options
P_LAVENDER = Palette("Lavender", "#FAF8FF", "#FFFFFF", "#2E1065", "#5B21B6", "#EDE7FB",
                     "#9333EA", "#7E22CE", "#F3E8FF", "#C084FC", "#9333EA", "#B45309")

P_BLUSH = Palette("Blush", "#FFF8F8", "#FFFFFF", "#4A1015", "#8B4A52", "#FCE4E6",
                  "#DB2777", "#BE185D", "#FCE7F3", "#F472B6", "#DB2777", "#B45309")

# Food/Restaurant, additional options
P_OLIVE = Palette("Olive", "#FBFBF3", "#FFFFFF", "#292B12", "#565A2B", "#E9EAD4",
                  "#4D7C0F", "#3F6212", "#ECFCCB", "#84CC16", "#4D7C0F", "#B45309")

P_TERRACOTTA = Palette("Terracotta", "#FDF6F0", "#FFFFFF", "#3D1E0F", "#6B4A3A", "#EDE0D5",
                       "#8B4B32", "#6B3623", "#F0DFD2", "#A0623F", "#8B4B32", "#B45309")

# General-purpose -- no named industry family maps to these; they only
# ever surface through palette_for()'s `else` branch, widening the
# fallback instead of adding a 6th named family.
P_SKY = Palette("Sky", "#F0F9FF", "#FFFFFF", "#0C2A3D", "#3B6478", "#DEF0FA",
               "#0369A1", "#075985", "#E0F2FE", "#38BDF8", "#0369A1", "#B45309")

P_STONE = Palette("Stone", "#FAFAF9", "#FFFFFF", "#1C1917", "#57534E", "#E7E5E4",
                  "#78716C", "#57534E", "#F5F5F4", "#A8A29E", "#78716C", "#B45309")

# 2026-08-22, Slice 4 (grow palettes/type pairings further, cheap
# dimension first per operator direction -- new templates, the expensive
# bespoke half, stay their own separate slice). One new option per each
# of the 5 named families (4->5 each), 20->25 total. Every hue chosen to
# clear the SAME distinctness bar `test_palette_family_members_are_
# visually_distinct` already enforces (hue delta >=8deg OR sat delta
# >=0.15 from every other member of its own family) -- verified
# numerically against that exact formula before being locked in here,
# not eyeballed, learning from Slice C.1's Terracotta-was-Orange's-own-
# ramp defect. All three assert_wcag() checks (ink/bg>=4.5, white-on-
# accent>=3.0, accent/bg>=3.0) verified the same way; weakest margin is
# Champagne's white/accent at 4.10 (comfortably clear of the 3.0 floor,
# not just barely passing -- Champagne's first draft measured 3.25,
# tightened before committing rather than shipped at a bare pass).
#
# 2026-08-22, Opus 5 review: the first draft's accent_soft values were
# mid-grey tints (HLS lightness ~0.76-0.88, most at low saturation),
# breaking this registry's own established convention -- all 20
# pre-existing palettes use a near-white pastel tint (lightness
# ~0.89-0.94, saturation mostly 0.80-1.00). No live WCAG violation
# resulted (every real accent_soft usage across all 9 templates pairs it
# with --accent-dark or --ink, never --muted, and both pairings measured
# safe even with the mid-grey values), but the values looked generated
# by a different rule than the rest of the registry -- regenerated at
# lightness 0.91/saturation 0.85 (matching the established pattern) and
# re-verified: accent_dark/accent_soft and ink/accent_soft both stay
# comfortably >=5.9 for all five (weakest is Champagne's accent_dark/
# accent_soft at 5.92), not just barely passing.
P_CYAN = Palette("Cyan", "#FAFCFD", "#FFFFFF", "#0E2025", "#4E6D74", "#DEEAED",
                 "#0C7B97", "#06566B", "#D5F4FC", "#26B5D9", "#0C7B97", "#B45309")

P_DENIM = Palette("Denim", "#FAFAFD", "#FFFFFF", "#0E1225", "#4E5474", "#DEE0ED",
                  "#2E419E", "#1F2E7A", "#D5DBFC", "#6977BF", "#2E419E", "#B45309")

P_PLUM = Palette("Plum", "#FCFAFD", "#FFFFFF", "#210E25", "#6E4E74", "#EBDEED",
                 "#62206F", "#401249", "#F5D5FC", "#9546A4", "#62206F", "#B45309")

P_CHAMPAGNE = Palette("Champagne", "#FDFCFA", "#FFFFFF", "#251F0E", "#746B4E", "#EDE9DE",
                      "#977A20", "#715A14", "#FCF2D5", "#C4A74F", "#977A20", "#B45309")

P_BASIL = Palette("Basil", "#FAFDFA", "#FFFFFF", "#0E2512", "#4E7454", "#DEEDE0",
                  "#206F2D", "#12491C", "#D5FCDB", "#46A456", "#206F2D", "#B45309")


PALETTES = [
    P_TEAL, P_BLUE, P_RED, P_STEEL, P_NAVY, P_ROSE, P_ORANGE, P_SLATE,
    P_MINT, P_INDIGO, P_AMBER, P_CHARCOAL, P_BURGUNDY, P_FOREST,
    P_LAVENDER, P_BLUSH, P_OLIVE, P_TERRACOTTA, P_SKY, P_STONE,
    P_CYAN, P_DENIM, P_PLUM, P_CHAMPAGNE, P_BASIL,
]

# 2026-08-21, Opus 5 review (round 3) of the industry-aware template
# selection slice: engine.py's template_for() used to duplicate this
# module's subtype-keyword branches verbatim in a second copy, to keep
# template family and palette family "coherent" (the same business never
# gets a Legal-family palette paired with a Beauty-family template).
# That coherence guarantee had zero real enforcement -- mutation-proven:
# adding one keyword to only ONE of the two copies left the entire
# 407-test suite green, since nothing actually compared the two
# classifications against each other. Extracted here as the single
# source of truth both modules call, so the two branch chains can no
# longer drift apart at all -- not just "tested to not drift," genuinely
# impossible to drift, since there is only one copy of the logic left.
INDUSTRY_FAMILY_DENTAL_MEDICAL = "dental_medical"
INDUSTRY_FAMILY_HOME_SERVICES = "home_services"
INDUSTRY_FAMILY_LEGAL_FINANCE = "legal_finance"
INDUSTRY_FAMILY_BEAUTY_SALON = "beauty_salon"
INDUSTRY_FAMILY_FOOD_RESTAURANT = "food_restaurant"
INDUSTRY_FAMILY_GENERAL = "general"

def industry_family_for(subtype: str) -> str:
    subtype = subtype.lower() if subtype else ""
    if "dent" in subtype or "medical" in subtype or "physician" in subtype or "vet" in subtype:
        return INDUSTRY_FAMILY_DENTAL_MEDICAL
    if "plumb" in subtype or "hvac" in subtype or "electric" in subtype or "repair" in subtype or "contractor" in subtype:
        return INDUSTRY_FAMILY_HOME_SERVICES
    if "law" in subtype or "attorney" in subtype or "finance" in subtype or "estate" in subtype:
        return INDUSTRY_FAMILY_LEGAL_FINANCE
    if "salon" in subtype or "beauty" in subtype or "spa" in subtype:
        return INDUSTRY_FAMILY_BEAUTY_SALON
    if "food" in subtype or "restaurant" in subtype or "cafe" in subtype:
        return INDUSTRY_FAMILY_FOOD_RESTAURANT
    return INDUSTRY_FAMILY_GENERAL

# 2026-08-22, Slice 4: each named family grew from 4 to 5 real options,
# appended (not inserted) so the family's own existing index order isn't
# reshuffled. That does NOT mean existing businesses keep their existing
# palette, though -- an earlier version of this comment claimed it did,
# which an Opus 5 review disproved by direct measurement: palette_for()
# is `family[seed % len(family)]`, so growing the modulus 4->5 remaps
# every seed >= 4 to a different index than before (only seed values 0-3
# themselves are unaffected -- real seeds, derived from business name +
# domain hashing, are essentially uniform, not small sequential
# integers). Measured directly: only 20% of 10,000 sampled seeds keep
# their pre-Slice-4 palette in the dental_medical family, and 10 of 12
# businesses in this file's own test_variation_across_businesses fixture
# get a different palette after this change (7 of those 10 land on one
# of the OLD 4 options, not even the new one). This is the same
# tradeoff every prior registry-growth slice in this codebase already
# carried (C.1's 8->20 grow, and the industry-aware-selection slice
# itself, both remapped existing seeds the same way) -- not a new
# regression Slice 4 introduced, just one this comment previously
# described inaccurately. Sites are regenerated from current facts on
# each real run, not persisted as "this business = this palette," so
# this churn has no live-data consequence; flagging honestly rather than
# leaving the disproven claim in place.
_PALETTE_FAMILIES = {
    INDUSTRY_FAMILY_DENTAL_MEDICAL: [P_TEAL, P_BLUE, P_MINT, P_INDIGO, P_CYAN],
    INDUSTRY_FAMILY_HOME_SERVICES: [P_RED, P_STEEL, P_AMBER, P_CHARCOAL, P_DENIM],
    INDUSTRY_FAMILY_LEGAL_FINANCE: [P_NAVY, P_SLATE, P_BURGUNDY, P_FOREST, P_PLUM],
    INDUSTRY_FAMILY_BEAUTY_SALON: [P_ROSE, P_TEAL, P_LAVENDER, P_BLUSH, P_CHAMPAGNE],
    INDUSTRY_FAMILY_FOOD_RESTAURANT: [P_ORANGE, P_RED, P_OLIVE, P_TERRACOTTA, P_BASIL],
}

def palette_for(subtype: str, seed: int) -> Palette:
    family = _PALETTE_FAMILIES.get(industry_family_for(subtype), PALETTES)
    return family[seed % len(family)]

def assert_wcag():
    for p in PALETTES:
        # body ink vs bg
        assert contrast_ratio(p.ink, p.bg) >= 4.5, f"Palette {p.name} fails body contrast"
        # 2026-08-21, Opus 5 review of Slice C.1: both of these were
        # previously unchecked -- this line was commented out from the
        # start, and white-on-accent was never checked at all. Every
        # template's primary CTA button/band renders
        # background:var(--accent);color:#fff, so a palette whose accent
        # doesn't clear WCAG's 3:1 floor for large-scale UI text against
        # both white and its own bg ships an unreadable button, not just
        # a theoretical risk (5 of the first 12 new palettes did exactly
        # this before being fixed).
        assert contrast_ratio("#FFFFFF", p.accent) >= 3.0, \
            f"Palette {p.name} fails white-on-accent button-text contrast"
        assert contrast_ratio(p.accent, p.bg) >= 3.0, f"Palette {p.name} fails large-text accent contrast"

assert_wcag()
