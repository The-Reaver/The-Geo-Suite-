# SPEC: SPEC_CCC_M1_INGESTION
"""Offline-fake LLM gateway — identical prompt assertion for multi-model."""
from __future__ import annotations

from ..envelope import GatewayEnvelope


def complete_prompt(
    prompt: str,
    *,
    engine: str,
    model_id: str | None = None,
    fake: dict | None = None,
) -> dict:
    if fake is not None:
        return GatewayEnvelope(
            status=fake.get("status", "OK"),
            data=fake.get("data"),
            error=fake.get("error"),
            vendor=engine,
            model_id=fake.get("model_id") or model_id,
            requested_at=fake.get("requested_at"),
            latency_ms=fake.get("latency_ms", 0),
            cost_units=float(fake.get("cost_units") or 0),
        ).as_dict()
    return GatewayEnvelope(
        status="AUTH_FAILED",
        data=None,
        error=f"{engine} credentials not configured",
        vendor=engine,
        model_id=model_id,
    ).as_dict()


def multi_model_identical(prompt: str, engines: list[str], *, fakes: dict | None = None) -> dict:
    """Fail the batch if prompts would differ — callers pass one prompt string."""
    if not prompt:
        return {
            "status": "VENDOR_ERROR",
            "error": "empty prompt",
            "results": {},
        }
    # Textual identity is guaranteed by single `prompt` arg; record it.
    results = {}
    fakes = fakes or {}
    for eng in engines:
        results[eng] = complete_prompt(prompt, engine=eng, fake=fakes.get(eng))
    return {
        "status": "OK",
        "prompt": prompt,
        "prompt_identical": True,
        "results": results,
    }
