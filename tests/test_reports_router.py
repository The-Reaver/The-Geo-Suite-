"""Tests for /reports/* -- dashboard.py/alerting.py/export.py's real logic,
which had zero HTTP surface until this router existed.
"""
import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ not in sys.path:
    sys.path.insert(0, PROJ)
BACKEND = os.path.join(PROJ, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

PLACEHOLDER_ENV = {
    "APP_ENV": "test",
    "APP_NAME": "geo-suite-backend",
    "SUPABASE_URL": "https://placeholder.supabase.co",
    "SUPABASE_ANON_KEY": "placeholder-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "placeholder-service-role-key",
}
for key, value in PLACEHOLDER_ENV.items():
    os.environ.setdefault(key, value)

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.core.permissions import require_sales_agent  # noqa: E402

client = TestClient(app)


def _fake_sales_agent():
    return {"sub": "11111111-1111-1111-1111-111111111111", "role": "sales_agent", "app_metadata": {"role": "sales_agent"}}


def _authed():
    app.dependency_overrides[require_sales_agent] = _fake_sales_agent


def test_reports_require_auth():
    app.dependency_overrides.clear()
    resp = client.post("/reports/executive-summary", json={"client": {}, "window": {}})
    assert resp.status_code in (401, 403), f"unauthenticated executive-summary must be rejected, got {resp.status_code}"


def test_executive_summary_omits_m5_keys():
    _authed()
    try:
        resp = client.post("/reports/executive-summary", json={
            "client": {"name": "Acme Clinic", "metrics": {"sov": 0.4}},
            "window": {"start": "2026-07-01", "end": "2026-07-28"},
        })
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["client"] == "Acme Clinic"
    for banned in ("granger", "varmax", "attribution_waterfall", "roi_irf"):
        assert banned not in data, f"M5 key must be absent, not present: {banned}"


def test_engine_breakdown_and_competitive_view():
    _authed()
    try:
        resp1 = client.post("/reports/engine-breakdown", json={
            "client": {"engines": {"chatgpt": {"cited": True}}}, "window": {"start": "a", "end": "b"},
        })
        resp2 = client.post("/reports/competitive-view", json={
            "client": {"name": "Acme"}, "competitors": [{"name": "Rival Clinic"}],
        })
    finally:
        app.dependency_overrides.clear()
    assert resp1.status_code == 200 and resp1.json()["engines"]["chatgpt"]["cited"] is True
    assert resp2.status_code == 200 and resp2.json()["competitors"][0]["name"] == "Rival Clinic"


def test_trend_segments_splits_on_model_boundary():
    _authed()
    try:
        resp = client.post("/reports/trend-segments", json={"points": [
            {"t": 1, "model_id": "gpt-4o-2024", "v": 0.1},
            {"t": 2, "model_id": "gpt-4o-2024", "v": 0.2},
            {"t": 3, "model_id": "gpt-4o-2025", "v": 0.25},
        ]})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200, resp.text
    segments = resp.json()["segments"]
    assert len(segments) == 2 and len(segments[0]) == 2 and len(segments[1]) == 1


def test_alerts_hallucination_fires_at_n1_and_is_causal_language_free():
    _authed()
    try:
        resp = client.post("/reports/alerts", json={
            "client": {"name": "Acme"},
            "current": {"verification": {
                "status": "HALLUCINATION", "field": "phone", "severity": "HIGH",
                "claim_text": "wrong number",
            }},
            "previous": {},
        })
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200, resp.text
    alerts = resp.json()["alerts"]
    # evaluate_alerts always evaluates both alert types -- an empty "previous"
    # sov correctly yields a suppressed (fire: False) sov_change alert
    # alongside the real hallucination one, not just the hallucination alone.
    by_type = {a["type"]: a for a in alerts}
    assert by_type["hallucination"]["fire"] is True and by_type["hallucination"]["n"] == 1
    assert by_type["sov_change"]["fire"] is False and by_type["sov_change"]["reason"] == "missing_intervals"
    for banned in ("root cause", "caused by", "drove the drop"):
        assert banned not in by_type["hallucination"]["body"]


def test_export_html_and_pdf_not_implemented():
    _authed()
    view = {"metrics": {}, "limitations": ["controlled sample"]}
    try:
        html_resp = client.post("/reports/export", json={"view": view, "fmt": "html"})
        pdf_resp = client.post("/reports/export", json={"view": view, "fmt": "pdf"})
    finally:
        app.dependency_overrides.clear()
    assert html_resp.status_code == 200, html_resp.text
    assert "text/html" in html_resp.headers["content-type"]
    assert pdf_resp.status_code == 501, "fmt=pdf must be an honest 501, not a mislabeled 200"


def test_export_refuses_empty_limitations():
    _authed()
    try:
        resp = client.post("/reports/export", json={"view": {"metrics": {}, "limitations": []}, "fmt": "json"})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 400, f"empty limitations must be refused, got {resp.status_code}"


def test_white_label_keeps_honesty_fields():
    _authed()
    try:
        resp = client.post("/reports/white-label", json={
            "view": {"limitations": ["x"], "methodology": {"weights_status": "UNVALIDATED"}},
            "branding": {"logo": "l", "colors": ["#000"]},
        })
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["limitations"] == ["x"]
    assert data["methodology"]["weights_status"] == "UNVALIDATED"


def test_api_payload_refuses_scalar_metrics():
    _authed()
    try:
        resp = client.post("/reports/api-payload", json={"view": {"metrics": {"sov": 0.4}}})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 400, f"scalar metrics must be refused, got {resp.status_code}"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print("PASS  " + t.__name__)
            passed += 1
        except AssertionError as e:
            print("FAIL  " + t.__name__ + ": " + str(e))
    print(f"\n{passed}/{len(tests)} passed")
    if passed < len(tests):
        sys.exit(1)
