import collections

TypePairing = collections.namedtuple("TypePairing", [
    "name", "display_family", "body_family", "css"
])

# 2026-08-20: this used to point @font-face src at /assets/fonts/*.woff2 --
# files no code anywhere in this repo ever writes, a dead reference (404)
# on every generated site, waiting on a "static asset pipeline" that was
# never built. No such pipeline exists (confirmed: no font-vendoring code
# anywhere in this codebase), so rather than keep declaring local files
# that don't exist, load the same real families from Google Fonts' CSS API
# -- a live, working, standard approach for a generated site with no build
# step of its own, not a placeholder. @import must be the first rule in a
# stylesheet; this string is always injected first by
# templates/__init__.py::_inject_css, so that holds.

CSS_INTER_INTER = (
    "@import url('https://fonts.googleapis.com/css2"
    "?family=Inter:wght@400;600&display=swap');"
)

CSS_FRAUNCES_INTER = (
    "@import url('https://fonts.googleapis.com/css2"
    "?family=Fraunces:wght@600&family=Inter:wght@400;600&display=swap');"
)

T_INTER = TypePairing(
    "Inter",
    display_family="'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    body_family="'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    css=CSS_INTER_INTER
)

T_FRAUNCES_INTER = TypePairing(
    "Fraunces + Inter",
    display_family="'Fraunces', Georgia, serif",
    body_family="'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    css=CSS_FRAUNCES_INTER
)

T_SYSTEM = TypePairing(
    "System UI",
    display_family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    body_family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    css=""
)

# 2026-08-21, Slice C.1: grew from 3 to 8 pairings per the operator's
# explicit correction ("this library of templates, palettes, type
# pairings need to be vast"). Each family/URL verified live against
# Google Fonts' real CSS API before being added (curl, HTTP 200, real
# @font-face output) -- same rigor as the original font-pipeline fix,
# not names trusted from memory.

CSS_PLAYFAIR_SOURCE = (
    "@import url('https://fonts.googleapis.com/css2"
    "?family=Playfair+Display:wght@600;700&family=Source+Sans+3:wght@400;600&display=swap');"
)

CSS_SPACE_GROTESK_INTER = (
    "@import url('https://fonts.googleapis.com/css2"
    "?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;600&display=swap');"
)

CSS_DM_SERIF_WORK = (
    "@import url('https://fonts.googleapis.com/css2"
    "?family=DM+Serif+Display:wght@400&family=Work+Sans:wght@400;600&display=swap');"
)

CSS_POPPINS_NUNITO = (
    "@import url('https://fonts.googleapis.com/css2"
    "?family=Poppins:wght@500;700&family=Nunito+Sans:wght@400;600&display=swap');"
)

CSS_IBM_PLEX = (
    "@import url('https://fonts.googleapis.com/css2"
    "?family=IBM+Plex+Serif:wght@500;700&family=IBM+Plex+Sans:wght@400;600&display=swap');"
)

T_PLAYFAIR_SOURCE = TypePairing(
    "Playfair Display + Source Sans 3",
    display_family="'Playfair Display', Georgia, serif",
    body_family="'Source Sans 3', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    css=CSS_PLAYFAIR_SOURCE
)

T_SPACE_GROTESK_INTER = TypePairing(
    "Space Grotesk + Inter",
    display_family="'Space Grotesk', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    body_family="'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    css=CSS_SPACE_GROTESK_INTER
)

T_DM_SERIF_WORK = TypePairing(
    "DM Serif Display + Work Sans",
    display_family="'DM Serif Display', Georgia, serif",
    body_family="'Work Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    css=CSS_DM_SERIF_WORK
)

T_POPPINS_NUNITO = TypePairing(
    "Poppins + Nunito Sans",
    display_family="'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    body_family="'Nunito Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    css=CSS_POPPINS_NUNITO
)

T_IBM_PLEX = TypePairing(
    "IBM Plex Serif + IBM Plex Sans",
    display_family="'IBM Plex Serif', Georgia, serif",
    body_family="'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    css=CSS_IBM_PLEX
)

PAIRINGS = [
    T_INTER, T_FRAUNCES_INTER, T_SYSTEM,
    T_PLAYFAIR_SOURCE, T_SPACE_GROTESK_INTER, T_DM_SERIF_WORK,
    T_POPPINS_NUNITO, T_IBM_PLEX,
]

def typography_for(seed: int) -> TypePairing:
    return PAIRINGS[(seed // 7) % len(PAIRINGS)]
