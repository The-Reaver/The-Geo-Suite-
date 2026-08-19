# SPEC: SPEC_CCC_M1_INGESTION
"""LLM ingest — identical prompts; default n=20 recorded on observations."""
from __future__ import annotations

from .gateways.llm_gateway import multi_model_identical

DEFAULT_N_ITERATIONS = 20  # registry seed; Track B may change — recorded on each obs


def run_stability_sample(
    prompt: str,
    engines: list[str],
    *,
    n_iterations: int | None = None,
    fakes_by_iter: list[dict] | None = None,
) -> dict:
    n = int(n_iterations if n_iterations is not None else DEFAULT_N_ITERATIONS)
    iterations = []
    for i in range(n):
        fake = (fakes_by_iter or [None] * n)[i] if fakes_by_iter else None
        batch = multi_model_identical(prompt, engines, fakes=fake)
        if not batch.get("prompt_identical"):
            return {
                "status": "VENDOR_ERROR",
                "error": "prompt identity failure",
                "n_iterations": n,
            }
        iterations.append(batch)
    return {
        "status": "OK",
        "n_iterations": n,
        "prompt": prompt,
        "iterations": iterations,
        "reason": "n_iterations recorded for downstream intervals",
    }


def assert_budget(remaining: float, cost: float) -> dict:
    if remaining < cost:
        return {
            "status": "BUDGET_EXHAUSTED",
            "allowed": False,
            "reason": "run would exceed configured ceiling",
            "remaining": remaining,
            "cost": cost,
        }
    return {
        "status": "OK",
        "allowed": True,
        "remaining_after": remaining - cost,
    }
