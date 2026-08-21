import sys
import os

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ not in sys.path:
    sys.path.insert(0, PROJ)
BACKEND = os.path.join(PROJ, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

import re
import uuid
from unittest.mock import patch, MagicMock

# Setup environment before loading app
PLACEHOLDER_ENV = {
    "APP_ENV": "test",
    "APP_NAME": "platform-backend",
    "SUPABASE_URL": "https://placeholder.supabase.co",
    "SUPABASE_ANON_KEY": "placeholder-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "placeholder-service-role-key",
}

for key, value in PLACEHOLDER_ENV.items():
    os.environ.setdefault(key, value)

from fastapi.testclient import TestClient
from app.main import app
from app.core.permissions import require_owner, require_sales_agent
import app.routers.sales_preview as sales_preview

client = TestClient(app)

# 2026-08-08 GEO Brain Trust closeout: the SSRF fix added two things to
# /sales/audit-current that this test predates and would otherwise fail on:
#   1. Depends(require_owner) — the route is no longer unauthenticated, so the
#      test overrides that dependency with a fake owner payload.
#   2. _is_public_http_url — a real socket.getaddrinfo SSRF guard, which would
#      hit the network (and reject example.com offline). It is patched to
#      allow the test URL; the guard's own behavior is proven exhaustively in
#      test_sales_preview_ssrf.py, not here.
# The mocked response also gains is_redirect=False, since the route now refuses
# server-issued redirects (a classic SSRF check bypass).

# A fixed, valid UUID string: 2026-08-09, /lead started deriving agent_id
# from payload["sub"] (must parse as a UUID) instead of trusting the request
# body. "owner-under-test" (the old placeholder here) would now 400 on that
# route, so every test that needs a real write uses this instead.
_TEST_OWNER_ID = "11111111-1111-1111-1111-111111111111"


def _fake_owner():
    return {"sub": _TEST_OWNER_ID, "app_metadata": {"role": "owner"}}


# 2026-08-16, Phase 0 of the sales-agent master panel build: audit-current,
# report, kit, lead, and my-prospects moved from require_owner to
# require_sales_agent (a strict superset -- owner/admin keep everything they
# had, sales_agent is newly allowed in). A distinct fake agent id/payload so
# tests can prove the widened role actually works, not just that owner still
# does.
_TEST_AGENT_ID = "22222222-2222-2222-2222-222222222222"


def _fake_sales_agent():
    return {"sub": _TEST_AGENT_ID, "app_metadata": {"role": "sales_agent"}}


def test_audit_current_success():
    class MockResponse:
        def __init__(self, text):
            self.text = text
            self.is_redirect = False
        def raise_for_status(self):
            pass

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def get(self, url):
            return MockResponse("<html><head></head><body><h1>Hello</h1><p>Some long text to pass the audit text length requirement. Some long text to pass the audit text length requirement.</p></body></html>")

    app.dependency_overrides[require_sales_agent] = _fake_owner
    sales_preview._rate_limit_state.clear()
    with patch("httpx.AsyncClient", new=MockAsyncClient), \
         patch.object(sales_preview, "_is_public_http_url", return_value=(True, "")):
        try:
            resp = client.post("/sales/audit-current", json={"url": "https://example.com"})
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200, f"an authorized, public-URL audit should be 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "score" in data
        assert "top_gaps" in data
        # 2026-08-16: was a Performance-only "performance_not_measured" flag;
        # generalized to disclose every not_measured category for this
        # single-page live path (Category 3 and part of 6 joined Category 5
        # once homepage_only stopped auto-zeroing artifacts never fetched).
        not_measured = data.get("not_measured")
        assert isinstance(not_measured, list) and "Technical Performance and Core Web Vitals" in not_measured, \
            "the dropped Performance category must be disclosed"
        assert "AI Crawler Access and llms.txt" in not_measured, \
            "single-page live audits must disclose Category 3 as not_measured, not auto-zeroed"
        assert data.get("preliminary") is True, \
            "client-facing readiness claims are paused per the 2026-08-16 operator ruling"

def test_audit_current_success_as_sales_agent():
    # 2026-08-16 Phase 0: proves the widened role itself works, not just that
    # the override key matches. A sales_agent-role payload, not owner/admin,
    # must reach the same 200 -- this is the whole point of require_sales_agent
    # existing instead of leaving the route on require_owner.
    class MockResponse:
        def __init__(self, text):
            self.text = text
            self.is_redirect = False
        def raise_for_status(self):
            pass

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def get(self, url):
            return MockResponse("<html><head></head><body><h1>Hello</h1><p>Some long text to pass the audit text length requirement. Some long text to pass the audit text length requirement.</p></body></html>")

    app.dependency_overrides[require_sales_agent] = _fake_sales_agent
    sales_preview._rate_limit_state.clear()
    with patch("httpx.AsyncClient", new=MockAsyncClient), \
         patch.object(sales_preview, "_is_public_http_url", return_value=(True, "")):
        try:
            resp = client.post("/sales/audit-current", json={"url": "https://example.com"})
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 200, \
            f"a sales_agent-role caller must reach this route, got {resp.status_code}: {resp.text}"


def test_audit_current_failure():
    class MockFailingClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def get(self, url):
            raise Exception("Connection error")

    app.dependency_overrides[require_sales_agent] = _fake_owner
    sales_preview._rate_limit_state.clear()
    with patch("httpx.AsyncClient", new=MockFailingClient), \
         patch.object(sales_preview, "_is_public_http_url", return_value=(True, "")):
        try:
            resp = client.post("/sales/audit-current", json={"url": "https://example.com"})
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 400, f"a failed fetch should be 400, got {resp.status_code}: {resp.text}"


def test_audit_current_requires_auth():
    # The whole point of Sentinel finding 1: this route must not be callable
    # without an authenticated owner. No dependency override here.
    app.dependency_overrides.clear()
    resp = client.post("/sales/audit-current", json={"url": "https://example.com"})
    assert resp.status_code in (401, 403), f"unauthenticated audit must be rejected, got {resp.status_code}"

def test_create_preview():
    # 2026-08-09 operator decision: preview_delivery.py is now authoritative
    # for /sales/preview, not a bare local filesystem path. This exercises
    # the real pipeline end to end — generate_preview() builds an actual
    # site, preview_delivery.create_preview() compliance-screens and issues
    # it — then follows the returned URL to confirm it is actually servable,
    # not just a 200 with an opaque id.
    # 2026-08-19: /preview moved from require_owner to require_sales_agent;
    # overriding the latter with an owner payload proves owner access is
    # unchanged by the widening (see test_create_preview_success_as_sales_agent
    # for proof the new role actually works, not just that owner still does).
    payload = {
        "business_name": "Test Biz",
        "subtype": "Plumber",
        "locality": "NY",
        "region": "NY",
        "street": "123 Main",
        "telephone": "555-0000",
        "postal_code": "10001",
        "domain": "test.com"
    }

    app.dependency_overrides[require_sales_agent] = _fake_owner
    try:
        resp = client.post("/sales/preview", json=payload)
        assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "preview_url" in data
        assert "/sales/preview/" in data["preview_url"], "preview_url must point at the real GET route, not the preview_delivery placeholder host"
        assert "preview.stag.local" not in data["preview_url"], "must not hand back preview_delivery's own placeholder host"
        assert "preview_id" in data
        assert "expires_at" in data
        assert "score" in data

        # The URL /sales/preview returns must actually be fetchable and
        # carry the noindex signal, not just look like one.
        view_resp = client.get(data["preview_url"])
        assert view_resp.status_code == 200, f"issued preview should be viewable, got {view_resp.status_code}"
        assert view_resp.headers.get("x-robots-tag") == "noindex, nofollow"
        assert "noindex" in view_resp.text
        assert "DEMO PREVIEW - NOT FOR PUBLICATION" in view_resp.text
    finally:
        app.dependency_overrides.clear()

def test_create_preview_success_as_sales_agent():
    # 2026-08-19: proves the widened role itself works on /preview, not just
    # that the override key matches -- mirrors
    # test_audit_current_success_as_sales_agent's pattern for the same reason.
    payload = {
        "business_name": "Test Biz",
        "subtype": "Plumber",
        "locality": "NY",
        "region": "NY",
        "street": "123 Main",
        "telephone": "555-0000",
        "postal_code": "10001",
        "domain": "test.com"
    }
    app.dependency_overrides[require_sales_agent] = _fake_sales_agent
    try:
        resp = client.post("/sales/preview", json=payload)
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200, \
        f"a sales_agent-role caller must reach this route, got {resp.status_code}: {resp.text}"


def test_create_preview_carries_rating_and_faqs_into_the_real_site():
    # 2026-08-20: BusinessFactsReq used to have no rating/same_as/faqs, so a
    # real prospect's own facts could never raise its generated site's score
    # -- only the fixed illustrative fixture could. Proves the fields
    # actually reach the rendered HTML, not just that a request carrying
    # them doesn't crash.
    payload = {
        "business_name": "Test Biz",
        "subtype": "Plumber",
        "locality": "NY",
        "region": "NY",
        "street": "123 Main",
        "telephone": "555-0000",
        "postal_code": "10001",
        "domain": "test.com",
        "rating": {"value": 4.8, "count": 213},
        "same_as": ["https://www.google.com/maps/place/test-biz"],
        "faqs": [{"question": "Do you offer emergency service?", "answer": "Yes, 24/7 dispatch."}],
    }
    app.dependency_overrides[require_sales_agent] = _fake_owner
    try:
        resp = client.post("/sales/preview", json=payload)
        assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
        view_resp = client.get(resp.json()["preview_url"])
        assert view_resp.status_code == 200
        html = view_resp.text
        assert '"ratingValue": "4.8"' in html, "the real rating must reach the JSON-LD, not be silently dropped"
        assert '"reviewCount": "213"' in html
        assert "www.google.com/maps/place/test-biz" in html, "same_as must reach the JSON-LD sameAs list"
        assert "Do you offer emergency service?" in html, "faqs must render as real visible content"
        assert "Yes, 24/7 dispatch." in html
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200, \
        f"a sales_agent-role caller must reach this route, got {resp.status_code}: {resp.text}"


def test_preview_internal_nav_links_actually_resolve():
    # 2026-08-20 bug fix: generate_site() always wrote a full, real
    # multi-page site (index/about/privacy/accessibility) with real internal
    # nav links between those pages, but preview_delivery.py only ever
    # captured and served index.html -- every one of those links 404'd for a
    # rep or prospect clicking through the previewed homepage. This proves
    # the fix by actually following the served links, not just asserting a
    # page dict shape. BusinessFactsReq has no `services` field, so this
    # path can't prove service-page resolution -- that's covered by
    # test_site_generator_example_internal_nav_links_resolve below, against
    # the illustrative fixture, which does have real services.
    payload = {
        "business_name": "Test Biz",
        "subtype": "Plumber",
        "locality": "NY",
        "region": "NY",
        "street": "123 Main",
        "telephone": "555-0000",
        "postal_code": "10001",
        "domain": "test.com",
    }
    app.dependency_overrides[require_sales_agent] = _fake_owner
    try:
        resp = client.post("/sales/preview", json=payload)
        assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
        home = client.get(resp.json()["preview_url"])
        assert home.status_code == 200

        hrefs = re.findall(r'href="(/sales/preview/[^"]+/page/[^"]+)"', home.text)
        assert hrefs, "expected at least one rewritten /page/ nav link on the homepage"
        # About/Privacy/Accessibility are always written by generate_site(),
        # even with no services on this facts shape.
        targets = {h.rsplit("/", 1)[-1] for h in hrefs}
        assert "about.html" in targets
        assert "privacy.html" in targets
        assert "accessibility.html" in targets

        for href in set(hrefs):
            page_resp = client.get(href)
            assert page_resp.status_code == 200, \
                f"internal nav link {href} must resolve, got {page_resp.status_code}"
    finally:
        app.dependency_overrides.clear()


def test_site_generator_example_internal_nav_links_resolve():
    # Same guard as the real-facts test above, against the illustrative
    # fixture, whose homepage carries the same About/Privacy/Accessibility
    # nav links. Also proves service-*.html pages -- which generate_site()
    # writes to disk but never links to from the homepage nav (confirmed by
    # reading site_engine.py directly: the services section renders <li>
    # name/description only, no per-service href) -- are still individually
    # servable through the new /page/ route now that every page the
    # generator writes is captured, not just index.html. The real-facts path above
    # can't prove this at all (BusinessFactsReq has no services field, so it
    # never generates service pages in the first place).
    app.dependency_overrides[require_owner] = _fake_owner
    try:
        resp = client.post("/sales/site-generator-example", json={})
        assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
        home = client.get(resp.json()["preview_url"])
        assert home.status_code == 200

        hrefs = re.findall(r'href="(/sales/preview/[^"]+/page/[^"]+)"', home.text)
        assert hrefs, "expected at least one rewritten /page/ nav link on the homepage"
        targets = {h.rsplit("/", 1)[-1] for h in hrefs}
        assert "about.html" in targets
        assert "privacy.html" in targets
        assert "accessibility.html" in targets

        for href in set(hrefs):
            page_resp = client.get(href)
            assert page_resp.status_code == 200, \
                f"internal nav link {href} must resolve, got {page_resp.status_code}"

        # Not linked from the homepage, but still a real page generate_site()
        # wrote for this fixture -- must resolve when fetched directly.
        preview_id = resp.json()["preview_id"]
        service_resp = client.get(f"/sales/preview/{preview_id}/page/service-hyperbaric-oxygen-therapy.html")
        assert service_resp.status_code == 200, \
            f"a real service page must resolve when fetched directly, got {service_resp.status_code}"
        assert "Hyperbaric Oxygen Therapy" in service_resp.text
    finally:
        app.dependency_overrides.clear()


def test_preview_unknown_page_name_returns_404():
    # A valid, unexpired preview_id with a fabricated page name must return a
    # real, distinct 404 -- not a crash, and not silently falling back to
    # index.html.
    payload = {
        "business_name": "Test Biz",
        "subtype": "Plumber",
        "locality": "NY",
        "region": "NY",
        "street": "123 Main",
        "telephone": "555-0000",
        "postal_code": "10001",
        "domain": "test.com",
    }
    app.dependency_overrides[require_sales_agent] = _fake_owner
    try:
        resp = client.post("/sales/preview", json=payload)
        assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
        preview_id = resp.json()["preview_id"]
    finally:
        app.dependency_overrides.clear()

    bad_resp = client.get(f"/sales/preview/{preview_id}/page/does-not-exist.html")
    assert bad_resp.status_code == 404, \
        f"an unknown page name on a real preview_id must 404, got {bad_resp.status_code}"


def test_preview_tempdir_is_cleaned_up_after_read():
    # generate_preview() (services/preview.py) builds its site under
    # tempfile.mkdtemp(prefix="preview_"), with no corresponding cleanup --
    # every real call to /sales/preview leaked a directory on disk. Proves
    # the shutil.rmtree() fix in create_preview() actually runs, against a
    # real path that existed before cleanup, not a mocked-away one.
    payload = {
        "business_name": "Test Biz",
        "subtype": "Plumber",
        "locality": "NY",
        "region": "NY",
        "street": "123 Main",
        "telephone": "555-0000",
        "postal_code": "10001",
        "domain": "test.com",
    }
    captured = {}
    real_rmtree = sales_preview.shutil.rmtree

    def spy_rmtree(path, *args, **kwargs):
        captured["path"] = str(path)
        captured["existed_before_cleanup"] = os.path.exists(path)
        return real_rmtree(path, *args, **kwargs)

    app.dependency_overrides[require_sales_agent] = _fake_owner
    try:
        with patch.object(sales_preview.shutil, "rmtree", side_effect=spy_rmtree):
            resp = client.post("/sales/preview", json=payload)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, resp.text
    assert captured.get("existed_before_cleanup") is True, \
        "rmtree must be called on a directory that actually existed -- proves it's cleaning up the real tempdir, not a no-op"
    assert "preview_" in captured.get("path", ""), \
        "must be cleaning up generate_preview()'s own preview_-prefixed mkdtemp directory"
    assert not os.path.exists(captured["path"]), \
        "the tempdir must actually be gone after the request completes"


def test_preview_tempdir_is_cleaned_up_even_when_generate_preview_raises():
    # 2026-08-21, Opus 5 review: the cleanup fix above only covered the
    # success path -- generate_preview() itself creates the directory (via
    # mkdtemp()) before it can fail, so if it raised partway through (or if
    # reading the generated pages afterward raised), the directory was
    # still orphaned with no way to recover its path. The router now owns
    # the tempdir and cleans it up in `finally`, so a failure inside
    # generate_preview() must not leak it.
    payload = {
        "business_name": "Test Biz",
        "subtype": "Plumber",
        "locality": "NY",
        "region": "NY",
        "street": "123 Main",
        "telephone": "555-0000",
        "postal_code": "10001",
        "domain": "test.com",
    }
    captured = {}
    real_rmtree = sales_preview.shutil.rmtree

    def spy_rmtree(path, *args, **kwargs):
        captured["path"] = str(path)
        captured["existed_before_cleanup"] = os.path.exists(path)
        return real_rmtree(path, *args, **kwargs)

    app.dependency_overrides[require_sales_agent] = _fake_owner
    try:
        with patch.object(sales_preview.shutil, "rmtree", side_effect=spy_rmtree), \
             patch.object(sales_preview, "generate_preview", side_effect=RuntimeError("boom")):
            resp = client.post("/sales/preview", json=payload)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 500, \
        f"a generate_preview() failure must surface as a real 500, got {resp.status_code}: {resp.text}"
    assert captured.get("existed_before_cleanup") is True, \
        "the router-owned tempdir must exist before cleanup even on the failure path"
    assert not os.path.exists(captured["path"]), \
        "the tempdir must still be cleaned up when generate_preview() raises, not just on success"


def test_compliance_gate_screens_every_page_not_just_index():
    # 2026-08-21, Opus 5 review: preview_delivery.create_preview() used to
    # run audit_site() against pages["index.html"] only -- correct back
    # when index.html was the only page this module ever served, but the
    # multi-page fix (2026-08-20) made every other page in "pages"
    # (about.html, privacy.html, accessibility.html, every service-*.html)
    # publicly servable too, all rendering prospect-supplied free text the
    # gate never saw. audit_site() is mocked directly here to prove the
    # *looping/aggregation* logic itself now covers every page, independent
    # of any one compliance rule's real detection behavior (real rule
    # coverage is exercised elsewhere in the compliance test suite).
    from app.services.sales import preview_delivery
    preview_delivery.clear_preview_store()

    def fake_audit_site(html, *, mode):
        if "RISKY" in html:
            return {"ok": False, "blocking": [{"rule": "marketing-unrescuable-guarantee-claim", "message": "risky"}]}
        return {"ok": True, "blocking": []}

    pages = {
        "index.html": "<html><body>clean homepage</body></html>",
        "service-example.html": "<html><body>RISKY service claim</body></html>",
    }
    with patch.object(preview_delivery, "audit_site", side_effect=fake_audit_site):
        result = preview_delivery.create_preview({"pages": pages})

    assert result["ok"] is False, "a blocking finding on a non-index page must refuse the whole preview"
    assert result["status_code"] == 403
    assert any("guarantee" in (r or "").lower() for r in result.get("rules", [])), \
        "the specific rule that blocked it must be named, even though it came from a non-index page"


def test_compliance_gate_still_passes_when_every_page_is_clean():
    from app.services.sales import preview_delivery
    preview_delivery.clear_preview_store()

    def fake_audit_site(html, *, mode):
        return {"ok": True, "blocking": []}

    pages = {
        "index.html": "<html><body>clean homepage</body></html>",
        "about.html": "<html><body>clean about page</body></html>",
    }
    with patch.object(preview_delivery, "audit_site", side_effect=fake_audit_site):
        result = preview_delivery.create_preview({"pages": pages})

    assert result["ok"] is True, "every page passing the gate must still let the preview issue normally"


def test_create_preview_requires_auth():
    # 2026-08-09 GEO Brain Trust Presentation Mode review, Sentinel finding:
    # this route carried zero authentication. No dependency override here.
    app.dependency_overrides.clear()
    resp = client.post("/sales/preview", json={"business_name": "Unauthed Biz"})
    assert resp.status_code in (401, 403), f"unauthenticated preview must be rejected, got {resp.status_code}"

def test_create_preview_blocked_by_compliance_gate():
    # 2026-08-09: a preview_delivery refusal (PHI/testimonial, marketing
    # claim, etc.) must surface as an honest 403 with the reason, not a
    # silent 200 or a generic 500. Mocked at the preview_delivery boundary
    # rather than trying to coax real testimonial HTML out of the site
    # generator — that gate's own rules are compliance_checker's concern,
    # proven in its own test coverage, not this route's.
    payload = {"business_name": "Test Biz", "subtype": "Plumber", "domain": "test.com"}
    app.dependency_overrides[require_sales_agent] = _fake_owner
    try:
        with patch.object(
            sales_preview,
            "issue_preview_delivery",
            return_value={
                "ok": False,
                "status_code": 403,
                "reason": "PHI rule: patient testimonial / identifier blocked preview",
            },
        ):
            resp = client.post("/sales/preview", json=payload)
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 403, f"a compliance-gate refusal must be 403, got {resp.status_code}"
    assert "PHI rule" in resp.json().get("detail", "")

def test_view_preview_unknown_returns_404():
    resp = client.get("/sales/preview/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404, f"an unknown preview_id should 404, got {resp.status_code}"

def test_rank_leads_requires_auth():
    app.dependency_overrides.clear()
    resp = client.post("/sales/rank-leads", json={"providers": []})
    assert resp.status_code in (401, 403), f"unauthenticated rank-leads must be rejected, got {resp.status_code}"

def test_lead_pipeline_requires_auth():
    app.dependency_overrides.clear()
    resp = client.post("/sales/lead-pipeline", json={"providers": []})
    assert resp.status_code in (401, 403), f"unauthenticated lead-pipeline must be rejected, got {resp.status_code}"

def test_pricing_tiers_returns_the_real_single_source_of_truth():
    # 2026-08-20: pricing used to be hardcoded identically in sales_kit.py
    # and NovaShell.tsx, kept in sync by hand. This is the one endpoint both
    # now read from (core/pricing.py).
    app.dependency_overrides[require_sales_agent] = _fake_sales_agent
    try:
        resp = client.get("/sales/pricing-tiers")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    names = [t["name"] for t in data["tiers"]]
    assert names == ["Starter", "Full-Service Growth", "Growth + Social"]
    assert [t["price"] for t in data["tiers"]] == [500, 2500, 4500]
    assert data["publish_threshold"] == 93

def test_pricing_tiers_requires_auth():
    app.dependency_overrides.clear()
    resp = client.get("/sales/pricing-tiers")
    assert resp.status_code in (401, 403), f"unauthenticated pricing-tiers must be rejected, got {resp.status_code}"

def test_save_lead():
    # 2026-08-09 operator decision: agent_id is no longer part of the request
    # body at all — it comes from the authenticated caller's own JWT.
    with patch("app.routers.sales_preview.get_supabase_admin") as mock_admin:
        mock_supabase = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()

        mock_admin.return_value = mock_supabase
        mock_supabase.table.return_value = mock_insert
        mock_insert.insert.return_value = mock_execute

        class MockResp:
            data = [{"id": str(uuid.uuid4())}]

        mock_execute.execute.return_value = MockResp()

        payload = {
            "business_name": "Test Lead",
            "contact_name": "John Doe",
            "contact_email": "john@example.com",
            "city": "NY",
            "current_score": 50,
            "preview_id": str(uuid.uuid4())
        }

        app.dependency_overrides[require_sales_agent] = _fake_owner
        try:
            resp = client.post("/sales/lead", json=payload)
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"

        # 2026-08-16: save_lead now also writes a compliance access-log entry
        # to "events" (via the same admin client), so .table() is called more
        # than once and insert() more than once -- assert_any_call / the
        # first insert call specifically, not the most recent one.
        mock_supabase.table.assert_any_call("prospects")
        inserted = mock_insert.insert.call_args_list[0][0][0]
        assert inserted["agent_id"] == _TEST_OWNER_ID, "agent_id must be the authenticated caller's own id"

def test_save_lead_ignores_client_supplied_agent_id():
    # The core of the operator's decision: even if a caller sends an
    # agent_id in the body (attempting to attribute a lead to someone else),
    # it must be dropped and the authenticated caller's id used instead.
    # LeadRequest no longer declares the field, so pydantic silently ignores
    # it — this proves that ignoring is total, not partial.
    with patch("app.routers.sales_preview.get_supabase_admin") as mock_admin:
        mock_supabase = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()

        mock_admin.return_value = mock_supabase
        mock_supabase.table.return_value = mock_insert
        mock_insert.insert.return_value = mock_execute

        class MockResp:
            data = [{"id": str(uuid.uuid4())}]

        mock_execute.execute.return_value = MockResp()

        spoofed_agent_id = str(uuid.uuid4())
        payload = {
            "agent_id": spoofed_agent_id,
            "business_name": "Test Lead",
            "current_score": 50,
            "preview_id": str(uuid.uuid4())
        }

        app.dependency_overrides[require_sales_agent] = _fake_owner
        try:
            resp = client.post("/sales/lead", json=payload)
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"

        # First insert() call is the prospects write; see the comment in
        # test_save_lead about the events access-log write that follows it.
        inserted = mock_insert.insert.call_args_list[0][0][0]
        assert inserted["agent_id"] != spoofed_agent_id, "a client-supplied agent_id must never reach the insert"
        assert inserted["agent_id"] == _TEST_OWNER_ID, "the authenticated caller's own id must be used instead"

def test_save_lead_without_preview_id_or_website_url():
    # 2026-08-16, Phase 1: preview_id was required even though the column
    # itself allows null -- a lead discovered via Prospecting and saved
    # directly never goes through /sales/preview first. Proves the relaxed
    # field actually works, not just that it type-checks.
    with patch("app.routers.sales_preview.get_supabase_admin") as mock_admin:
        mock_supabase = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()
        mock_admin.return_value = mock_supabase
        mock_supabase.table.return_value = mock_insert
        mock_insert.insert.return_value = mock_execute

        class MockResp:
            data = [{"id": str(uuid.uuid4())}]

        mock_execute.execute.return_value = MockResp()

        payload = {"business_name": "No Preview Yet", "current_score": 30}

        app.dependency_overrides[require_sales_agent] = _fake_owner
        try:
            resp = client.post("/sales/lead", json=payload)
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 200, f"expected 200 with no preview_id, got {resp.status_code}: {resp.text}"

        inserted = mock_insert.insert.call_args_list[0][0][0]
        assert inserted["preview_id"] is None
        assert inserted["website_url"] is None

def test_save_lead_stores_website_url():
    with patch("app.routers.sales_preview.get_supabase_admin") as mock_admin:
        mock_supabase = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()
        mock_admin.return_value = mock_supabase
        mock_supabase.table.return_value = mock_insert
        mock_insert.insert.return_value = mock_execute

        class MockResp:
            data = [{"id": str(uuid.uuid4())}]

        mock_execute.execute.return_value = MockResp()

        payload = {
            "business_name": "Has A Site",
            "current_score": 40,
            "website_url": "https://example.com/",
        }

        app.dependency_overrides[require_sales_agent] = _fake_owner
        try:
            resp = client.post("/sales/lead", json=payload)
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 200

        inserted = mock_insert.insert.call_args_list[0][0][0]
        assert inserted["website_url"] == "https://example.com/"

def test_save_lead_requires_auth():
    app.dependency_overrides.clear()
    payload = {
        "business_name": "Unauthed Lead",
        "current_score": 0,
        "preview_id": str(uuid.uuid4()),
    }
    resp = client.post("/sales/lead", json=payload)
    assert resp.status_code in (401, 403), f"unauthenticated lead write must be rejected, got {resp.status_code}"


def test_my_prospects_uses_user_scoped_client_not_admin():
    # 2026-08-16, Phase 0: the whole point of this route is that the
    # PROSPECTS query goes through get_user_client(token) -- the caller's own
    # JWT, so RLS is what actually decides what comes back -- never
    # get_supabase_admin(), which bypasses RLS entirely. Proving that
    # distinction is the one thing a unit test *can* prove without a live
    # Postgres; the real cross-agent isolation is proven by
    # tests/rls/test_sales_agent_prospect_isolation.py against a real
    # database, not here.
    #
    # 2026-08-16 addendum, compliance technical baseline: the route now also
    # writes an access-log event through the ADMIN client on purpose (an
    # audit trail an agent could suppress via their own RLS-scoped client
    # isn't a real audit trail) -- so admin IS called once, just never for
    # the prospects data itself. This test asserts that split, not "admin is
    # never called at all."
    with patch("app.routers.sales_preview.get_user_client") as mock_user_client, \
         patch("app.routers.sales_preview.get_supabase_admin") as mock_admin:
        mock_supabase = MagicMock()
        mock_select = MagicMock()
        mock_order = MagicMock()
        mock_user_client.return_value = mock_supabase
        mock_supabase.table.return_value = mock_select
        mock_select.select.return_value = mock_order
        mock_order.order.return_value = mock_order

        class MockResp:
            data = [{"id": "1", "business_name": "Real Prospect", "agent_id": _TEST_AGENT_ID}]

        mock_order.execute.return_value = MockResp()

        mock_admin_client = MagicMock()
        mock_admin.return_value = mock_admin_client

        app.dependency_overrides[require_sales_agent] = _fake_sales_agent
        try:
            resp = client.get(
                "/sales/my-prospects",
                headers={"Authorization": "Bearer fake-test-token"},
            )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json() == {"prospects": [{"id": "1", "business_name": "Real Prospect", "agent_id": _TEST_AGENT_ID}]}
        mock_user_client.assert_called_once_with("fake-test-token")
        # The user-scoped client, not admin, is what queried "prospects".
        mock_supabase.table.assert_called_once_with("prospects")
        # Admin was used, but only for the access-log write to "events".
        mock_admin_client.table.assert_called_once_with("events")


def test_my_prospects_requires_auth():
    app.dependency_overrides.clear()
    resp = client.get("/sales/my-prospects")
    assert resp.status_code in (401, 403), f"unauthenticated prospect list must be rejected, got {resp.status_code}"


def _mock_prospect_admin(existing_row):
    """Shared setup for the customize-endpoint tests: one admin client mock
    whose .table("prospects") supports both the ownership-check select and
    the update, as separate chains, plus whatever _log_prospect_access's own
    .table("events").insert(...) call needs."""
    mock_supabase = MagicMock()

    def table_side_effect(name):
        m = MagicMock()
        if name == "prospects":
            m.select.return_value.eq.return_value.execute.return_value = MagicMock(data=existing_row)
            m.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": "p1"}])
        return m

    mock_supabase.table.side_effect = table_side_effect
    return mock_supabase

_PROSPECT_ID = "33333333-3333-3333-3333-333333333333"

def test_customize_requires_auth():
    app.dependency_overrides.clear()
    resp = client.patch(
        f"/sales/prospects/{_PROSPECT_ID}/customize",
        json={"note": "x", "selected_gap_indices": [], "client_timestamp": "2026-08-16T12:00:00Z"},
    )
    assert resp.status_code in (401, 403), f"unauthenticated customize must be rejected, got {resp.status_code}"

def test_customize_unknown_prospect_404s():
    with patch("app.routers.sales_preview.get_supabase_admin", return_value=_mock_prospect_admin([])):
        app.dependency_overrides[require_sales_agent] = _fake_sales_agent
        try:
            resp = client.patch(
                f"/sales/prospects/{_PROSPECT_ID}/customize",
                json={"note": "x", "selected_gap_indices": [], "client_timestamp": "2026-08-16T12:00:00Z"},
            )
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 404

def test_customize_rejects_a_different_agents_prospect():
    other_agent = str(uuid.uuid4())
    with patch("app.routers.sales_preview.get_supabase_admin", return_value=_mock_prospect_admin([{"agent_id": other_agent, "customized_at": None}])):
        app.dependency_overrides[require_sales_agent] = _fake_sales_agent
        try:
            resp = client.patch(
                f"/sales/prospects/{_PROSPECT_ID}/customize",
                json={"note": "x", "selected_gap_indices": [], "client_timestamp": "2026-08-16T12:00:00Z"},
            )
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 403, "a prospect belonging to a different agent must be rejected, not silently written"

def test_customize_first_write_applies():
    with patch("app.routers.sales_preview.get_supabase_admin", return_value=_mock_prospect_admin([{"agent_id": _TEST_AGENT_ID, "customized_at": None}])):
        app.dependency_overrides[require_sales_agent] = _fake_sales_agent
        try:
            resp = client.patch(
                f"/sales/prospects/{_PROSPECT_ID}/customize",
                json={"note": "Loved the schema gap finding", "selected_gap_indices": [0, 2], "client_timestamp": "2026-08-16T12:00:00Z"},
            )
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["applied"] is True
        assert data["reason"] is None

def test_customize_stale_write_is_discarded_not_applied():
    # A newer customization already exists server-side (customized_at ahead
    # of the incoming client_timestamp) -- this must be discarded, not
    # silently overwrite the newer edit, per Celestina's last-write-wins design.
    with patch("app.routers.sales_preview.get_supabase_admin", return_value=_mock_prospect_admin([{
        "agent_id": _TEST_AGENT_ID, "customized_at": "2026-08-16T15:00:00+00:00",
    }])):
        app.dependency_overrides[require_sales_agent] = _fake_sales_agent
        try:
            resp = client.patch(
                f"/sales/prospects/{_PROSPECT_ID}/customize",
                json={"note": "an older, stale edit", "selected_gap_indices": [1], "client_timestamp": "2026-08-16T12:00:00Z"},
            )
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert data["applied"] is False
        assert data["reason"] == "stale"

def test_customize_newer_write_overwrites_older():
    with patch("app.routers.sales_preview.get_supabase_admin", return_value=_mock_prospect_admin([{
        "agent_id": _TEST_AGENT_ID, "customized_at": "2026-08-16T09:00:00+00:00",
    }])):
        app.dependency_overrides[require_sales_agent] = _fake_sales_agent
        try:
            resp = client.patch(
                f"/sales/prospects/{_PROSPECT_ID}/customize",
                json={"note": "a newer edit", "selected_gap_indices": [3], "client_timestamp": "2026-08-16T12:00:00Z"},
            )
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 200
        assert resp.json()["applied"] is True

def test_branded_report_carries_real_pillar_findings():
    # 2026-08-16: closes the report-renderer architecture gap named in
    # GEO_STATUS_AND_ROADMAP_2026-08-16.md section 3 -- proves end to end, through
    # the real HTTP route, that /sales/report's rendered HTML carries the same
    # AuditResult categories/fix_list the score came from, not a view that
    # discards them. A homepage with no structured data at all should produce a
    # real "Structured Data" pillar with real findings, and a real fix list --
    # not just a bare score with no pillar-by-pillar content behind it.
    class MockResponse:
        def __init__(self, text):
            self.text = text
            self.is_redirect = False
        def raise_for_status(self):
            pass

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def get(self, url):
            return MockResponse(
                "<html><head></head><body><h1>Hello</h1>"
                "<p>Some long text to pass the audit text length requirement. "
                "Some long text to pass the audit text length requirement.</p>"
                "</body></html>"
            )

    app.dependency_overrides[require_sales_agent] = _fake_sales_agent
    sales_preview._rate_limit_state.clear()
    with patch("httpx.AsyncClient", new=MockAsyncClient), \
         patch.object(sales_preview, "_is_public_http_url", return_value=(True, "")):
        try:
            resp = client.post("/sales/report", json={"url": "https://example.com"})
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
        html = resp.text
        assert "Pillar-by-pillar findings" in html, \
            "the branded report must render real per-category findings, not just a score"
        # This homepage has no JSON-LD, no Organization/WebSite schema -- the
        # engine's real Structured Data category must report that, and it must
        # show up as a genuine finding in the rendered document, not a stub.
        assert "Structured Data" in html or "Structured" in html, \
            "a real pillar section for structured data must appear"
        assert "NOT MEASURED" in html, \
            "this is a homepage-only live audit -- excluded categories must be labeled, not silently dropped"
        # 2026-08-16: the sectioned-report build wires real compliance findings
        # and the honest not-yet-available sections through this same route.
        assert "Governing framework" in html, \
            "a homepage with no lang attribute must trigger a real WCAG finding, rendered here"
        assert "Cross-reference against your own materials" in html, \
            "the sectioned report's honest not-yet-available section must appear"
        assert "Evidence-attribution triage" in html, \
            "the sectioned report's evidence-attribution section must appear, even if unpopulated"
        assert "Glossary" in html, "the sectioned report's glossary section must appear"
        assert "Prepared for" in html, "the sectioned report's cover details must appear"


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print("PASS  " + t.__name__)
            passed += 1
        except AssertionError as e:
            print("FAIL  " + t.__name__ + ": " + str(e))
        except Exception as e:
            print("FAIL  " + t.__name__ + ": " + str(e))
    print(f"\\n{passed}/{len(tests)} passed")
    return passed == len(tests)

if __name__ == "__main__":
    sys.exit(0 if _run_all() else 1)
