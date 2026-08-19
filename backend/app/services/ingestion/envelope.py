# SPEC: SPEC_CCC_M1_INGESTION
"""Domain envelope for all ingestion gateways — no vendor objects escape."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


STATUSES = (
    "OK",
    "EMPTY",
    "RATE_LIMITED",
    "AUTH_FAILED",
    "TIMEOUT",
    "BLOCKED",
    "VENDOR_ERROR",
    "BUDGET_EXHAUSTED",
)


@dataclass
class GatewayEnvelope:
    status: str
    data: Any = None
    error: str | None = None
    vendor: str = ""
    model_id: str | None = None
    requested_at: str | None = None
    latency_ms: float | None = None
    cost_units: float = 0.0
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "data": self.data,
            "error": self.error,
            "vendor": self.vendor,
            "model_id": self.model_id,
            "requested_at": self.requested_at,
            "latency_ms": self.latency_ms,
            "cost_units": self.cost_units,
            **self.extra,
        }


class IngestionError(Exception):
    """Domain exception — never wrap a raw vendor exception for callers."""

    def __init__(self, status: str, message: str):
        self.status = status
        super().__init__(message)
