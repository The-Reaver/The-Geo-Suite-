"""SSRF guard and rate limit for POST /sales/audit-current — standalone battery twin.

Promoted 2026-08-08 from backend/tests/test_sales_preview_ssrf.py (pytest,
quarantined) into the run battery, per QUARANTINE.md rule 3: rewrite as a
standalone file under projects/geo_platform/tests/ (no `import pytest`, a
`__main__` runner that prints N/N), then delete the superseded pytest copy.
The prior GEO Brain Trust session left the SSRF fix's only proof in the
quarantined tree that ci_verify_geo.py never runs, so the fix passed nothing
the battery could see. This file closes that gap.

Proves Sentinel finding 1 (unauthenticated SSRF) is closed: every resolved
address is checked, DNS-rebinding included; localhost is blocked before
resolution; non-http schemes and malformed URLs are refused; and the
per-caller rate limit holds. No `import pytest`; monkeypatching is done by
hand with save/restore so the file runs as a plain script.
"""

import os
import socket
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (PROJ, os.path.join(PROJ, "backend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Placeholder env so importing the app package never reaches a live Supabase.
for _k, _v in {
    "SUPABASE_URL": "https://placeholder.supabase.co",
    "SUPABASE_ANON_KEY": "placeholder-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "placeholder-service-role-key",
}.items():
    os.environ.setdefault(_k, _v)

from app.routers import sales_preview as sp


def _fake_addrinfo(ip):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]


def _with_resolver(resolver, fn):
    """Run fn() with socket.getaddrinfo replaced, then restore it."""
    original = socket.getaddrinfo
    socket.getaddrinfo = resolver
    try:
        return fn()
    finally:
        socket.getaddrinfo = original


def test_public_https_url_allowed():
    ok, reason = _with_resolver(
        lambda host, port: _fake_addrinfo("93.184.216.34"),
        lambda: sp._is_public_http_url("https://example.com/"),
    )
    assert ok is True, f"a public https URL should be allowed, got reason {reason!r}"
    assert reason == "", f"an allowed URL should carry no reason, got {reason!r}"


def test_loopback_address_blocked():
    ok, reason = _with_resolver(
        lambda host, port: _fake_addrinfo("127.0.0.1"),
        lambda: sp._is_public_http_url("http://trusted-looking-name.example/"),
    )
    assert ok is False, "a hostname resolving to 127.0.0.1 must be blocked"
    assert "non-public" in reason, f"reason should name the non-public address, got {reason!r}"


def test_link_local_metadata_address_blocked():
    # 169.254.169.254 is the cloud metadata endpoint, the canonical SSRF target.
    ok, reason = _with_resolver(
        lambda host, port: _fake_addrinfo("169.254.169.254"),
        lambda: sp._is_public_http_url("http://trusted-looking-name.example/"),
    )
    assert ok is False, "the cloud metadata address must be blocked"
    assert "non-public" in reason, f"reason should name the non-public address, got {reason!r}"


def test_private_range_blocked():
    ok, reason = _with_resolver(
        lambda host, port: _fake_addrinfo("10.0.0.5"),
        lambda: sp._is_public_http_url("http://internal-service.example/"),
    )
    assert ok is False, "a hostname resolving into a private range must be blocked"
    assert "non-public" in reason, f"reason should name the non-public address, got {reason!r}"


def test_dns_rebinding_style_target_blocked():
    # A hostname with no obviously-internal spelling that simply resolves to a
    # private address. Only the resolved IP tells you, which is why we resolve.
    ok, reason = _with_resolver(
        lambda host, port: _fake_addrinfo("192.168.1.50"),
        lambda: sp._is_public_http_url("http://totally-normal-domain.example/"),
    )
    assert ok is False, "DNS-rebinding to a private address must be blocked"
    assert "non-public" in reason, f"reason should name the non-public address, got {reason!r}"


def test_localhost_hostname_blocked_before_resolution():
    def _should_not_be_called(host, port):
        raise AssertionError("localhost must be blocked before DNS resolution")

    ok, reason = _with_resolver(
        _should_not_be_called,
        lambda: sp._is_public_http_url("http://localhost:8000/admin"),
    )
    assert ok is False, "localhost must be refused on the literal-hostname denylist"


def test_non_http_scheme_blocked():
    ok, reason = sp._is_public_http_url("file:///etc/passwd")
    assert ok is False, "a file:// URL must be refused"
    assert "http" in reason.lower(), f"reason should mention the http-only rule, got {reason!r}"


def test_malformed_url_blocked():
    ok, reason = sp._is_public_http_url("not a url at all")
    assert ok is False, "a malformed URL must be refused"


def test_unresolvable_host_blocked():
    def _raise_gaierror(host, port):
        raise socket.gaierror("name or service not known")

    ok, reason = _with_resolver(
        _raise_gaierror,
        lambda: sp._is_public_http_url("http://this-domain-does-not-exist.invalid/"),
    )
    assert ok is False, "an unresolvable host must be refused"
    assert "resolve" in reason.lower(), f"reason should mention resolution, got {reason!r}"


def test_rate_limit_allows_calls_under_the_limit():
    sp._rate_limit_state.clear()
    for _ in range(sp._RATE_LIMIT_MAX_CALLS):
        sp._enforce_rate_limit("caller-a")  # must not raise


def test_rate_limit_blocks_calls_over_the_limit():
    sp._rate_limit_state.clear()
    for _ in range(sp._RATE_LIMIT_MAX_CALLS):
        sp._enforce_rate_limit("caller-b")
    try:
        sp._enforce_rate_limit("caller-b")
    except Exception as exc:  # HTTPException, imported inside the router module
        assert getattr(exc, "status_code", None) == 429, "over-limit call must be a 429"
    else:
        raise AssertionError("the call over the limit should have raised 429")


def test_rate_limit_is_per_caller_key():
    sp._rate_limit_state.clear()
    for _ in range(sp._RATE_LIMIT_MAX_CALLS):
        sp._enforce_rate_limit("caller-c")
    sp._enforce_rate_limit("caller-d")  # a different caller has its own bucket


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print("PASS  " + t.__name__)
            passed += 1
        except Exception as e:
            print("FAIL  " + t.__name__ + ": " + str(e))
    print(f"{passed}/{len(tests)} passed")
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if _run_all() else 1)
