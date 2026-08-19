# SPEC: SPEC_CCC_M1_INGESTION
"""Crawl gateway offline fake — BLOCKED ≠ ABSENT."""
from __future__ import annotations

from ..envelope import GatewayEnvelope


def fetch_page(url: str, *, fake: dict | None = None) -> dict:
    if fake is not None:
        return GatewayEnvelope(
            status=fake.get("status", "OK"),
            data=fake.get("data"),
            error=fake.get("error"),
            vendor=fake.get("vendor", "fake_crawl"),
            requested_at=fake.get("requested_at"),
            latency_ms=fake.get("latency_ms", 0),
        ).as_dict()
    return GatewayEnvelope(
        status="AUTH_FAILED",
        error="crawl credentials/proxy not configured",
        vendor="unconfigured",
    ).as_dict()
