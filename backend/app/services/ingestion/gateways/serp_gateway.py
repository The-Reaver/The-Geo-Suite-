# SPEC: SPEC_CCC_M1_INGESTION
"""Offline-fake SERP gateway — no vendor SDK imports."""
from __future__ import annotations

from ..envelope import GatewayEnvelope, IngestionError


def fetch_serp(query: str, *, geo: str | None = None, fake: dict | None = None) -> dict:
    """Return domain envelope. Live keys are operator-owned; tests inject `fake`."""
    if fake is not None:
        status = fake.get("status", "OK")
        return GatewayEnvelope(
            status=status,
            data=fake.get("data"),
            error=fake.get("error"),
            vendor=fake.get("vendor", "fake_serp"),
            model_id=fake.get("model_id"),
            requested_at=fake.get("requested_at"),
            latency_ms=fake.get("latency_ms", 0),
            cost_units=float(fake.get("cost_units") or 0),
        ).as_dict()
    # Unconfigured = honest AUTH_FAILED, not empty OK.
    return GatewayEnvelope(
        status="AUTH_FAILED",
        data=None,
        error="serp credentials not configured",
        vendor="unconfigured",
    ).as_dict()
