# SPEC: SPEC_CCC_M1_INGESTION
"""Analytics gateway offline fake — collect only; no M5 attribution."""
from __future__ import annotations

from ..envelope import GatewayEnvelope


def fetch_analytics(*, fake: dict | None = None) -> dict:
    if fake is not None:
        env = GatewayEnvelope(
            status=fake.get("status", "OK"),
            data=fake.get("data"),
            error=fake.get("error"),
            vendor=fake.get("vendor", "fake_analytics"),
        ).as_dict()
        # Heuristic may be stored but must be flagged unvalidated.
        if isinstance(env.get("data"), dict) and "ai_referral_confidence" in env["data"]:
            env["data"] = dict(env["data"])
            env["data"]["attribution_surfacing"] = "FORBIDDEN_UNDER_PATH_A"
        return env
    return GatewayEnvelope(
        status="AUTH_FAILED",
        error="analytics credentials not configured",
        vendor="unconfigured",
    ).as_dict()
