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

PAIRINGS = [T_INTER, T_FRAUNCES_INTER, T_SYSTEM]

def typography_for(seed: int) -> TypePairing:
    return PAIRINGS[(seed // 7) % len(PAIRINGS)]
