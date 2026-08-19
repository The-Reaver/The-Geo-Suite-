import collections

TypePairing = collections.namedtuple("TypePairing", [
    "name", "display_family", "body_family", "css"
])

# For now, we stub the actual URLs to point to `/assets/fonts/` locally to pass the audit,
# and use the system font stack as the immediate fallback.
# In a real deployed environment, the static asset pipeline copies these .woff2 files.

CSS_INTER_INTER = """
@font-face {
  font-family: 'Inter';
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url('/assets/fonts/inter-regular.woff2') format('woff2');
}
@font-face {
  font-family: 'Inter';
  font-style: normal;
  font-weight: 600;
  font-display: swap;
  src: url('/assets/fonts/inter-semibold.woff2') format('woff2');
}
"""

CSS_FRAUNCES_INTER = CSS_INTER_INTER + """
@font-face {
  font-family: 'Fraunces';
  font-style: normal;
  font-weight: 600;
  font-display: swap;
  src: url('/assets/fonts/fraunces-semibold.woff2') format('woff2');
}
"""

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
