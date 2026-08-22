import sys
import os

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ not in sys.path:
    sys.path.insert(0, PROJ)
BACKEND = os.path.join(PROJ, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

PLACEHOLDER_ENV = {
    "APP_ENV": "test",
    "APP_NAME": "platform-backend",
    "SUPABASE_URL": "https://placeholder.supabase.co",
    "SUPABASE_ANON_KEY": "placeholder-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "placeholder-service-role-key",
}
for key, value in PLACEHOLDER_ENV.items():
    os.environ.setdefault(key, value)

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def test_baseline_security_headers_present():
    # Real finding from an actual Nuclei scan against this app, 2026-08-22
    # -- this API set none of these. Guards the fix against a silent
    # regression (e.g. a future middleware reordering that drops it).
    res = client.get("/health")
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert res.headers.get("x-permitted-cross-domain-policies") == "none"
    assert res.headers.get("cross-origin-opener-policy") == "same-origin"
    assert "permissions-policy" in res.headers


def test_frame_headers_deliberately_absent():
    # Guards the OTHER half of the same decision: X-Frame-Options and
    # Content-Security-Policy are deliberately NOT set globally, because
    # Nova's own Site Generator preview modal (frontend/app/nova/
    # NovaShell.tsx, Slice D) legitimately frames the preview routes
    # cross-origin on purpose. A future change adding a blanket
    # frame-blocking header here would silently break that shipped
    # feature -- this test exists so that change fails loudly instead.
    res = client.get("/health")
    assert "x-frame-options" not in res.headers
    assert "content-security-policy" not in res.headers
