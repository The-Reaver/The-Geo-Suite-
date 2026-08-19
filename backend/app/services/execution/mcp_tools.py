# SPEC: SPEC_CCC_M6_AGENTIC
"""MCP-style tool registration and approval-gated execution (EXE-6.3)."""
from __future__ import annotations

from typing import Any

from app.core.resilience import CircuitBreaker, CircuitOpenError
from app.services.worker.outbox import InMemoryDedupStore, InMemoryOutboxStore, handle_idempotent


_AUDIT: list[dict] = []


def register_tools(server_config: dict) -> dict:
    """EXE-6.3.1 — schemas with permission boundaries; no vendor SDK leakage."""
    server_config = server_config or {}
    tools = [
        {
            "name": "directory_submission",
            "permission": "execution:directory",
            "requires_approval": True,
            "description": "Enqueue a directory listing packet",
        },
        {
            "name": "content_optimization",
            "permission": "execution:cms",
            "requires_approval": True,
            "description": "Enqueue on-page/content diff",
        },
        {
            "name": "verification_window",
            "permission": "execution:read",
            "requires_approval": False,
            "description": "Compare before/after Sonar with intervals",
        },
    ]
    return {
        "status": "OK",
        "server": server_config.get("name") or "geo-execution",
        "tools": tools,
        "vendor_sdk_exposed": False,
        "reason": "tool schemas only — adapters behind gateways",
        # M7 llms.txt is NOT_RECOMMENDED — brand truth from workspace facts.
        "llms_txt_dependency": False,
        "brand_truth_source": "workspace_brand_facts",
    }


def enqueue_directory_submission(
    packet: dict,
    *,
    require_approval: bool = True,
    outbox: InMemoryOutboxStore | None = None,
    dedup: InMemoryDedupStore | None = None,
    gateway: Any = None,
    breaker: CircuitBreaker | None = None,
    approved: bool = False,
) -> dict:
    """EXE-6.3.2 — human approval default; audit log; idempotent apply."""
    if not packet:
        return {"status": "EMPTY", "reason": "packet missing"}
    if require_approval and not approved:
        entry = {
            "action": "directory_submission",
            "status": "AWAITING_APPROVAL",
            "packet_platform": (packet or {}).get("platform") or (packet.get("packet") or {}).get("platform"),
        }
        _AUDIT.append(entry)
        return {**entry, "reason": "human approval required before submit"}

    if gateway is not None and getattr(gateway, "configured", True) is False:
        return {"status": "AUTH_FAILED", "reason": "directory gateway credentials not configured"}

    outbox = outbox or InMemoryOutboxStore()
    dedup = dedup or InMemoryDedupStore()
    idem = (
        (packet or {}).get("idempotency_key")
        or f"dir:{(packet or {}).get('platform')}:{(packet or {}).get('name')}"
    )

    def _apply() -> dict:
        def _call() -> dict:
            if gateway is None:
                return {"status": "OK", "applied": True, "via": "fake_directory"}
            return gateway.submit(packet)

        if breaker is not None:
            try:
                return breaker.call(_call)
            except CircuitOpenError as exc:
                return {
                    "status": "CIRCUIT_OPEN",
                    "applied": False,
                    "reason": str(exc) or "circuit open",
                }
        return _call()

    result = handle_idempotent(dedup, idem, _apply)
    outbox.add({"type": "directory_submission", "idempotency_key": idem, "result": result})
    _AUDIT.append({"action": "directory_submission", "idempotency_key": idem, "result": result})
    return {
        "status": result.get("status", "OK"),
        "result": result,
        "idempotency_key": idem,
        "reason": "enqueued/applied via outbox idempotency",
    }


def enqueue_content_optimization(
    diff: dict,
    *,
    require_approval: bool = True,
    outbox: InMemoryOutboxStore | None = None,
    dedup: InMemoryDedupStore | None = None,
    approved: bool = False,
) -> dict:
    """EXE-6.3.3 — approval default; audit."""
    if not diff:
        return {"status": "EMPTY", "reason": "diff missing"}
    if require_approval and not approved:
        entry = {"action": "content_optimization", "status": "AWAITING_APPROVAL"}
        _AUDIT.append(entry)
        return {**entry, "reason": "human approval required"}
    outbox = outbox or InMemoryOutboxStore()
    dedup = dedup or InMemoryDedupStore()
    idem = (diff or {}).get("idempotency_key") or f"opt:{(diff or {}).get('page_id')}"

    def _apply() -> dict:
        return {"status": "OK", "applied": True, "diff_keys": list((diff or {}).keys())}

    result = handle_idempotent(dedup, idem, _apply)
    outbox.add({"type": "content_optimization", "idempotency_key": idem, "result": result})
    _AUDIT.append({"action": "content_optimization", "idempotency_key": idem, "result": result})
    return {"status": "OK", "result": result, "idempotency_key": idem}


def verification_window(action_id: str, sonar_before: dict, sonar_after: dict) -> dict:
    """EXE-6.3.4 — overlapping SOV CIs → INCONCLUSIVE, not a success badge."""
    before = sonar_before or {}
    after = sonar_after or {}
    for label, row in (("before", before), ("after", after)):
        if row.get("ci_lower") is None or row.get("ci_upper") is None or row.get("n") is None:
            return {
                "action_id": action_id,
                "status": "INSUFFICIENT_DATA",
                "reason": f"{label} Sonar metrics missing Wilson interval or n",
            }
    blo, bhi = float(before["ci_lower"]), float(before["ci_upper"])
    alo, ahi = float(after["ci_lower"]), float(after["ci_upper"])
    overlap = not (bhi < alo or ahi < blo)
    if overlap:
        return {
            "action_id": action_id,
            "status": "INCONCLUSIVE",
            "before": before,
            "after": after,
            "reason": "overlapping SOV confidence intervals — not a success badge",
        }
    direction = "up" if float(after.get("value") or 0) > float(before.get("value") or 0) else "down"
    return {
        "action_id": action_id,
        "status": "SEPARATED",
        "direction": direction,
        "before": before,
        "after": after,
        "reason": (
            "intervals separated — co-occurring observation after publish date; "
            "not a causal claim without M5-grade evidence"
        ),
    }


def learn_from_outcomes(outcomes: list[dict]) -> dict:
    """EXE-6.3.5 — may propose UNVALIDATED weights; never silently VALIDATED."""
    if not outcomes:
        return {
            "status": "EMPTY",
            "proposed_updates": [],
            "registry_write_status": None,
            "reason": "no outcomes",
        }
    proposed = []
    for o in outcomes:
        proposed.append(
            {
                "key": o.get("weight_key") or "execution_outcome_weight",
                "value": o.get("proposed_value"),
                "status": "PROPOSED_UNVALIDATED",
                "basis": o.get("basis") or "execution outcome sample",
            }
        )
    return {
        "status": "OK",
        "proposed_updates": proposed,
        "registry_write_status": "PROPOSED_UNVALIDATED",
        "validated_writes": 0,
        "reason": "proposals only — must not write VALIDATED into SOURCE_WEIGHT_REGISTRY",
    }


def audit_log() -> list[dict]:
    return list(_AUDIT)


def _reset_audit_for_tests() -> None:
    _AUDIT.clear()
