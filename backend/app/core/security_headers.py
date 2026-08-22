"""
Baseline HTTP security headers, added 2026-08-22 in direct response to a
real Nuclei scan against this app's own local instance (part of the new
standing "point ZAP/Nuclei at every deploy" practice -- see
.github/workflows/security-scan.yml). The scan's own top finding, first
run: this API set none of the standard hardening headers at all.

Deliberately does NOT set X-Frame-Options / frame-ancestors or a
Content-Security-Policy here, even though Nuclei flagged both missing --
verified this app has two real reasons neither can be a safe blanket
default:
  1. The Site Generator preview routes (sales_preview.py's view_preview /
     view_preview_page) are deliberately framed cross-origin, on purpose,
     by Nova's own in-app preview modal (frontend/app/nova/NovaShell.tsx,
     Slice D, 2026-08-22) -- Nova's frontend and this backend are separate
     Railway services on different origins. A blanket DENY/SAMEORIGIN or a
     restrictive frame-ancestors would break that feature outright, the
     same day it shipped.
  2. Those same preview pages load Google Fonts live via @import
     (site_design/typography.py) and render inline <style> blocks by
     design (site_engine.py) -- a naive strict CSP would break their own
     rendering, not just a hypothetical attack surface.
Framing/CSP hardening for the preview routes specifically is a real,
separately-scoped follow-up (an explicit frame-ancestors allowing only
the known frontend origin, and a CSP tuned to the real font/style sources)
-- not invented here to avoid shipping a header that looks complete but
quietly breaks a feature that already went through its own review.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Permitted-Cross-Domain-Policies": "none",
    # Conservative default: no camera/mic/geolocation/payment from any
    # context. Nothing in this API needs any of them.
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    # Cross-Origin-Opener-Policy governs window.opener relationships for
    # popups, not iframe framing -- safe alongside the preview iframe's
    # allow-popups sandbox above, unlike X-Frame-Options/CSP would be.
    "Cross-Origin-Opener-Policy": "same-origin",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for name, value in _HEADERS.items():
            response.headers.setdefault(name, value)
        return response
