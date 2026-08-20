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

from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.core.permissions import require_owner
import app.services.site_pipeline as site_pipeline

client = TestClient(app)

_TEST_OWNER_ID = "11111111-1111-1111-1111-111111111111"


def _fake_owner():
    return {"sub": _TEST_OWNER_ID, "app_metadata": {"role": "owner"}}


_GOOD_FACTS = {
    "business_name": "Cedar Ridge Dental",
    "subtype": "Dentist",
    "street": "1200 Cedar Road",
    "locality": "Portland",
    "region": "OR",
    "postal_code": "97201",
    "country": "US",
    "telephone": "+1-503-555-0142",
    "domain": "cedarridgedental.example",
    "hours": ["Mon-Fri 8:00-17:00"],
    "service_areas": ["Portland", "Beaverton", "Lake Oswego"],
    "services": [
        {"name": "Preventive cleanings", "description": "Exams, digital X-rays, and hygiene visits for families."},
        {"name": "Dental implants", "description": "Permanent tooth replacement placed and restored in-house."},
    ],
    "credentials": ["ADA membership"],
    "faqs": [{"question": "Do you accept new patients?", "answer": "Yes, and most PPO insurance plans."}],
    "same_as": ["https://g.page/cedar-ridge-dental"],
    "rating": {"value": 4.9, "count": 218},
    "last_updated": "2026-07-20",
    "tagline": "Family and cosmetic dentistry in Portland, OR",
}


# 2026-08-20: site_pipeline.generate_and_store() used to unconditionally
# generate_site()+run_audit() itself even though this route had already done
# exactly that a few lines earlier to decide pass/fail -- every successful
# publish silently paid for both twice. Proves the real HTTP path now only
# generates and audits once.
def test_publish_generates_and_audits_only_once():
    real_generate_site = site_pipeline.generate_site
    real_run_audit = site_pipeline.run_audit

    calls = {"generate_site": 0, "run_audit": 0}

    def counting_generate_site(*args, **kwargs):
        calls["generate_site"] += 1
        return real_generate_site(*args, **kwargs)

    def counting_run_audit(*args, **kwargs):
        calls["run_audit"] += 1
        return real_run_audit(*args, **kwargs)

    app.dependency_overrides[require_owner] = _fake_owner
    try:
        with patch.object(site_pipeline, "generate_site", side_effect=counting_generate_site), \
             patch.object(site_pipeline, "run_audit", side_effect=counting_run_audit):
            resp = client.post("/sites/33333333-3333-3333-3333-333333333333/audit", json={"facts": _GOOD_FACTS})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["passed"] is True
    assert data["score"] >= 90

    # site_pipeline.generate_site is only called on the site_dir=None
    # fallback path -- the real route always supplies site_dir, so it must
    # be zero here, not just "less than before".
    assert calls["generate_site"] == 0, "generate_and_store must reuse the caller's already-generated site, not regenerate"
    assert calls["run_audit"] == 0, "generate_and_store must reuse the caller's already-computed audit, not re-audit"


if __name__ == "__main__":
    test_publish_generates_and_audits_only_once()
    print("PASS  test_publish_generates_and_audits_only_once")
