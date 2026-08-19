# SPEC: SPEC_CCC_M9_ADMIN
"""Multi-brand workspaces, RBAC, budgets, Path A data-flow map (ADM-9.2)."""
from __future__ import annotations

from typing import Any

from .admin_registry import (
    BUDGET_ALERT_FRACTION,
    BUDGET_EXHAUST_FRACTION,
    ROLES,
    WEIGHTS_STATUS,
)

# In-process store for offline/admin scaffolding (swap for DB later).
_WORKSPACES: dict[str, dict] = {}
_RBAC: dict[str, list[dict]] = {}


def create_workspace(brand: dict) -> dict:
    """ADM-9.2.1 — isolated workspace per brand; no merged fake metrics."""
    brand = brand or {}
    wid = str(brand.get("workspace_id") or brand.get("id") or "").strip()
    if not wid:
        return {
            "status": "INSUFFICIENT_BRAND_DATA",
            "workspace": None,
            "reason": "missing workspace_id/id",
        }
    name = brand.get("name") or brand.get("brand_name")
    if not name:
        return {
            "status": "INSUFFICIENT_BRAND_DATA",
            "workspace": None,
            "reason": "missing brand name",
        }
    ws = {
        "workspace_id": wid,
        "name": name,
        "agency_id": brand.get("agency_id"),
        "domains": list(brand.get("domains") or []),
        "aliases": list(brand.get("aliases") or []),
        "engines": list(brand.get("engines") or []),
        "competitors": list(brand.get("competitors") or []),
        "prompt_clusters": list(brand.get("prompt_clusters") or []),
        "weights_status": WEIGHTS_STATUS,
    }
    _WORKSPACES[wid] = ws
    _RBAC.setdefault(wid, [])
    return {"status": "OK", "workspace": dict(ws), "reason": "workspace created"}


def list_workspaces(*, agency_id: str | None = None) -> list[dict]:
    rows = list(_WORKSPACES.values())
    if agency_id is not None:
        rows = [w for w in rows if w.get("agency_id") == agency_id]
    # Honest empty — never invent placeholder tenants.
    return [dict(w) for w in rows]


def configure_rbac(workspace_id: str, grants: list[dict]) -> dict:
    """ADM-9.2.2 — deny-by-default; roles Admin/Analyst/Viewer/Client."""
    if workspace_id not in _WORKSPACES:
        return {
            "status": "NOT_FOUND",
            "grants": [],
            "reason": f"workspace {workspace_id!r} does not exist",
        }
    accepted: list[dict] = []
    rejected: list[dict] = []
    for g in grants or []:
        role = g.get("role")
        principal = g.get("principal") or g.get("user_id")
        if role not in ROLES:
            rejected.append({"grant": g, "reason": f"unknown role {role!r} — deny-by-default"})
            continue
        if not principal:
            rejected.append({"grant": g, "reason": "missing principal — deny-by-default"})
            continue
        accepted.append(
            {
                "workspace_id": workspace_id,
                "principal": principal,
                "role": role,
                # Client = white-label portal read only
                "permissions": (
                    ["read:portal"]
                    if role == "Client"
                    else ["read", "write"] if role in ("Admin", "Analyst") else ["read"]
                ),
            }
        )
    _RBAC[workspace_id] = accepted
    return {
        "status": "OK" if not rejected else "PARTIAL",
        "grants": accepted,
        "rejected": rejected,
        "reason": "deny-by-default RBAC applied",
    }


def budget_status(workspace_id: str, usage: dict, caps: dict) -> dict:
    """ADM-9.2.3 — alert 80%/100%; never invent spend; never silently shrink n."""
    usage = usage or {}
    caps = caps or {}
    engines: dict[str, dict] = {}
    any_exhausted = False
    any_alert = False
    for engine, cap in caps.items():
        try:
            cap_f = float(cap)
        except (TypeError, ValueError):
            engines[engine] = {
                "status": "INVALID_CAP",
                "reason": f"cap for {engine} is not numeric",
            }
            continue
        used_raw = usage.get(engine)
        if used_raw is None:
            engines[engine] = {
                "status": "UNKNOWN_USAGE",
                "used": None,
                "cap": cap_f,
                "remaining_fraction": None,
                "reason": "usage not reported — not invented as 0 spend",
            }
            continue
        try:
            used = float(used_raw)
        except (TypeError, ValueError):
            engines[engine] = {
                "status": "INVALID_USAGE",
                "reason": f"usage for {engine} is not numeric",
            }
            continue
        if cap_f <= 0:
            engines[engine] = {
                "status": "INVALID_CAP",
                "used": used,
                "cap": cap_f,
                "reason": "cap must be positive",
            }
            continue
        frac = used / cap_f
        remaining = max(0.0, 1.0 - frac)
        if frac >= BUDGET_EXHAUST_FRACTION:
            any_exhausted = True
            engines[engine] = {
                "status": "BUDGET_EXHAUSTED",
                "used": used,
                "cap": cap_f,
                "remaining_fraction": remaining,
                "throttle": True,
                "reason": "100% cap reached — non-critical queries must refuse",
            }
        elif frac >= BUDGET_ALERT_FRACTION:
            any_alert = True
            engines[engine] = {
                "status": "BUDGET_ALERT",
                "used": used,
                "cap": cap_f,
                "remaining_fraction": remaining,
                "throttle": False,
                "reason": "80% alert threshold",
            }
        else:
            engines[engine] = {
                "status": "OK",
                "used": used,
                "cap": cap_f,
                "remaining_fraction": remaining,
                "throttle": False,
                "reason": "under alert threshold",
            }

    overall = "OK"
    if any_exhausted:
        overall = "BUDGET_EXHAUSTED"
    elif any_alert:
        overall = "BUDGET_ALERT"
    elif not engines:
        overall = "EMPTY"

    return {
        "workspace_id": workspace_id,
        "status": overall,
        "engines": engines,
        "throttle": any_exhausted,
        "reason": (
            "budget exhausted — refuse non-critical queries; never shrink n_iterations"
            if any_exhausted
            else "budget status computed from reported usage only"
        ),
    }


def path_a_data_flow() -> dict:
    """Static versioned Path A map — Path B nodes deferred / this module."""
    return {
        "version": "path_a_v1",
        "weights_status": WEIGHTS_STATUS,
        "nodes": [
            {"id": "M1", "label": "Ingestion", "status": "LIVE"},
            {"id": "M2", "label": "Sonar", "status": "LIVE"},
            {"id": "M3", "label": "Citation Influence", "status": "LIVE"},
            {"id": "M4", "label": "Footprint", "status": "LIVE"},
            {"id": "M8", "label": "Reporting", "status": "LIVE"},
            {"id": "Sales", "label": "Sales suite", "status": "LIVE"},
            {"id": "weights", "label": "weights registry", "status": "LIVE"},
            {"id": "M5", "label": "Econometric", "status": "DEFERRED"},
            {"id": "M6", "label": "Agentic", "status": "DEFERRED"},
            {"id": "M9", "label": "Admin", "status": "THIS_MODULE"},
        ],
        "edges": [
            {"from": "M1", "to": "M2"},
            {"from": "M2", "to": "M3"},
            {"from": "M2", "to": "M4"},
            {"from": "M3", "to": "M4"},
            {"from": "weights", "to": "M4"},
            {"from": "M4", "to": "M8"},
            {"from": "M8", "to": "Sales"},
        ],
        # Explicit non-claims — M5 Granger is not a live edge.
        "absent_edges": [
            {"from": "M8", "to": "M5", "reason": "Granger/VARMAX panels ABSENT until M5 MEASURED"},
            {"from": "M5", "to": "M8", "reason": "no live econometric edge"},
        ],
        "reason": "Path A data-flow only; Path B modules are DEFERRED/THIS_MODULE nodes",
    }


def _reset_store_for_tests() -> None:
    """Test helper — clear in-memory workspaces."""
    _WORKSPACES.clear()
    _RBAC.clear()
