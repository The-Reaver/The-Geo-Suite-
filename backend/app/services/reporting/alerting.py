# SPEC: SPEC_CCC_M8_REPORTING
"""Alerting with interval-separation gate; hallucination CRITICAL at n=1."""
from __future__ import annotations

from typing import Any

from ..sonar.alert_gates import evaluate_sov_drop_alert
from .dashboard import FORBIDDEN_CAUSAL


def _has_causal_verb(text: str) -> bool:
    lowered = (text or "").lower()
    return any(p in lowered for p in FORBIDDEN_CAUSAL)


def hallucination_alert(verification: dict) -> dict | None:
    verification = verification or {}
    if verification.get("status") != "HALLUCINATION":
        return None
    severity = verification.get("severity") or "HIGH"
    body = (
        f"Observed claim status HALLUCINATION on field "
        f"{verification.get('field')}: {verification.get('claim_text')}"
    )
    if _has_causal_verb(body):
        body = "Observed hallucination finding; see verification record."
    return {
        "type": "hallucination",
        "severity": severity,
        "fire": True,
        "n": 1,
        "body": body,
        "reason": "medical_or_fact_hallucination_n1",
        "intervals": None,
    }


def sov_change_alert(before: dict, after: dict) -> dict | None:
    before = before or {}
    after = after or {}
    n_b = int(before.get("n") or 0)
    n_a = int(after.get("n") or 0)
    prev_ci = (before.get("ci_lower"), before.get("ci_upper"))
    curr_ci = (after.get("ci_lower"), after.get("ci_upper"))
    if None in prev_ci or None in curr_ci:
        return {
            "type": "sov_change",
            "fire": False,
            "reason": "missing_intervals",
            "body": "SOV alert suppressed: intervals required",
        }
    result = evaluate_sov_drop_alert(
        prev_point=float(before.get("value") or 0),
        curr_point=float(after.get("value") or 0),
        prev_ci=(float(prev_ci[0]), float(prev_ci[1])),
        curr_ci=(float(curr_ci[0]), float(curr_ci[1])),
        drop_pp_threshold=10.0,
    )
    # evaluate_sov_drop_alert already encodes overlap + threshold; also enforce n≥5
    if n_b < 5 or n_a < 5:
        return {
            "type": "sov_change",
            "fire": False,
            "reason": "insufficient_sample",
            "body": "SOV alert suppressed: n<5",
            "intervals": {"before": prev_ci, "after": curr_ci},
        }
    body = (
        f"SOV point moved from {before.get('value')} to {after.get('value')}; "
        f"intervals before={prev_ci} after={curr_ci}."
    )
    if result.get("fire") and _has_causal_verb(body):
        body = "SOV intervals separated; co-occurring observations only."
    return {
        "type": "sov_change",
        "fire": bool(result.get("fire")),
        "reason": result.get("reason"),
        "body": body,
        "intervals": {"before": prev_ci, "after": curr_ci},
    }


def competitor_activity_alert(deltas: dict) -> dict | None:
    deltas = deltas or {}
    if not deltas.get("events"):
        return None
    # Co-occurrence only — no causal verbs.
    events = deltas["events"]
    body = (
        "Co-occurring observation: "
        + "; ".join(str(e) for e in events)
        + " (concurrent with visibility window; not asserted as cause)."
    )
    if _has_causal_verb(body):
        raise ValueError("competitor alert body contains forbidden causal verb")
    return {
        "type": "competitor_activity",
        "fire": True,
        "reason": "co_occurring_observation",
        "body": body,
    }


def stability_alert(csi_before, csi_after) -> dict | None:
    if csi_before is None or csi_after is None:
        return {
            "type": "stability",
            "fire": False,
            "reason": "insufficient_sample",
            "body": "CSI unavailable in one or both periods",
        }
    drop = float(csi_before) - float(csi_after)
    if drop < 10:
        return {
            "type": "stability",
            "fire": False,
            "reason": "below_threshold",
            "body": "CSI change below alert threshold",
        }
    body = (
        f"CSI moved from {csi_before} to {csi_after}. "
        f"Suggested review: re-check schema freshness markers (evidence only; no promised effect)."
    )
    if _has_causal_verb(body):
        body = "CSI declined across the window; review freshness markers."
    return {
        "type": "stability",
        "fire": True,
        "reason": "csi_drop",
        "body": body,
    }


def evaluate_alerts(client: dict, current: dict, previous: dict) -> list[dict]:
    alerts: list[dict] = []
    hall = hallucination_alert((current or {}).get("verification") or {})
    if hall:
        alerts.append(hall)
    sov = sov_change_alert(
        (previous or {}).get("sov") or {},
        (current or {}).get("sov") or {},
    )
    if sov:
        alerts.append(sov)
    return alerts


def weekly_digest(client: dict, window: dict) -> dict:
    return {
        "client": (client or {}).get("name"),
        "window": window,
        "alerts": (client or {}).get("alerts") or [],
        "limitations": ["Digest summarises alerts; it does not assert causes."],
    }
