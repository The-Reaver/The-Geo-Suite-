"""Reports router — the real reporting/alerting/export logic that had no
HTTP surface at all.

2026-08-20: `dashboard.py` had only one function (`category_pillars`)
reachable from any router (via `/sales/report`); its other three functions
(`executive_summary`, `engine_breakdown`, `competitive_view`,
`split_trend_at_model_boundary`), all of `export.py`, and all of
`alerting.py` were real, tested code with zero HTTP surface -- nobody could
trigger them from the live app.

Every function here is a pure, stateless transform over a caller-supplied
payload (a `client`/`view`/`window`/`competitors` dict) -- none of them read
from this app's own persisted data model, which is exactly how
`export_report` (already wired into `/sales/report`'s export path) already
works. This app has no persisted multi-engine/competitor/trend-history data
model of its own (the client-dashboard tables that would carry one were
explicitly deferred out of v1 scope during the repo split) -- these routes
don't invent one. They expose real, honest-refusal logic (CI enforcement,
forbidden-causal-language scrubbing, interval-separation gating) to whatever
caller has the shaped data to send it, same contract the functions already
had as plain Python calls.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.permissions import require_sales_agent
from app.services.reporting import alerting, dashboard
from app.services.reporting.export import api_payload, apply_white_label, export_report

router = APIRouter(prefix="/reports", tags=["reports"])


class ClientWindowRequest(BaseModel):
    client: dict[str, Any]
    window: dict[str, Any]


class CompetitiveViewRequest(BaseModel):
    client: dict[str, Any]
    competitors: list[dict[str, Any]] = []


class TrendSegmentsRequest(BaseModel):
    points: list[dict[str, Any]]


class AlertsRequest(BaseModel):
    client: dict[str, Any]
    current: dict[str, Any]
    previous: dict[str, Any]


class ExportRequest(BaseModel):
    view: dict[str, Any]
    fmt: str = "html"
    branding: Optional[dict[str, Any]] = None


class WhiteLabelRequest(BaseModel):
    view: dict[str, Any]
    branding: dict[str, Any]


class ApiPayloadRequest(BaseModel):
    view: dict[str, Any]


@router.post("/executive-summary")
async def executive_summary(request: ClientWindowRequest, payload: dict = Depends(require_sales_agent)):
    """RPT-8.1.1 without M5 attribution panels -- see dashboard.py's own
    docstring. M5 (Granger/VARMAX-style causal attribution) keys are
    explicitly absent, never zeroed, when not computed."""
    return dashboard.executive_summary(request.client, request.window)


@router.post("/engine-breakdown")
async def engine_breakdown(request: ClientWindowRequest, payload: dict = Depends(require_sales_agent)):
    return dashboard.engine_breakdown(request.client, request.window)


@router.post("/competitive-view")
async def competitive_view(request: CompetitiveViewRequest, payload: dict = Depends(require_sales_agent)):
    return dashboard.competitive_view(request.client, request.competitors)


@router.post("/trend-segments")
async def trend_segments(request: TrendSegmentsRequest, payload: dict = Depends(require_sales_agent)):
    """Splits a trend series at every model-version boundary -- comparing
    scores across an underlying model change is exactly the kind of
    causal-looking-but-isn't comparison this app refuses to present as one
    continuous line."""
    return {"segments": dashboard.split_trend_at_model_boundary(request.points)}


@router.post("/alerts")
async def alerts(request: AlertsRequest, payload: dict = Depends(require_sales_agent)):
    """Hallucination + SOV-change alerts, both gated: hallucination fires at
    n=1 (never wait for a bigger sample on a factual error), SOV-change
    requires non-overlapping confidence intervals and n>=5 on both sides.
    Every alert body is scrubbed of forbidden causal language
    (dashboard.FORBIDDEN_CAUSAL) before it's returned."""
    return {"alerts": alerting.evaluate_alerts(request.client, request.current, request.previous)}


@router.post("/weekly-digest")
async def weekly_digest(request: ClientWindowRequest, payload: dict = Depends(require_sales_agent)):
    return alerting.weekly_digest(request.client, request.window)


@router.post("/export")
async def export(request: ExportRequest, payload: dict = Depends(require_sales_agent)):
    """fmt='html' is real (branded, print-ready). fmt='json' is real. fmt='pdf'
    raises NotImplementedError -- no real PDF-rendering pipeline exists in
    this repo yet (use fmt='html' and print-to-PDF). _assert_exportable's
    honesty refusals (empty limitations, sampled metrics missing CI bounds)
    run before any format branch, so no format can skip them."""
    try:
        content = export_report(request.view, request.fmt, request.branding)
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    media_type = {"html": "text/html", "json": "application/json"}.get(request.fmt, "text/plain")
    from fastapi.responses import Response

    return Response(content=content, media_type=media_type)


@router.post("/white-label")
async def white_label(request: WhiteLabelRequest, payload: dict = Depends(require_sales_agent)):
    """Applies branding without ever stripping the honesty fields
    (methodology/limitations/metrics/weights_status) -- see
    export.apply_white_label's own comment."""
    return apply_white_label(request.view, request.branding)


@router.post("/api-payload")
async def api_payload_route(request: ApiPayloadRequest, payload: dict = Depends(require_sales_agent)):
    """A view's metrics/limitations/methodology as structured JSON -- never
    flattens a sampled metric to a bare scalar (api_payload refuses that)."""
    try:
        return api_payload(request.view)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
