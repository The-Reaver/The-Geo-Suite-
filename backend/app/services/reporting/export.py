# SPEC: SPEC_CCC_M8_REPORTING
"""White-label + export — intervals and limitations are non-optional."""
from __future__ import annotations

import json
from typing import Any


def apply_white_label(view: dict, branding: dict) -> dict:
    view = dict(view or {})
    branding = branding or {}
    themed = dict(view)
    themed["branding"] = {
        "logo": branding.get("logo"),
        "colors": branding.get("colors"),
        "domain": branding.get("domain"),
    }
    # May not strip honesty fields.
    for key in ("methodology", "limitations", "metrics", "weights_status"):
        if key in view:
            themed[key] = view[key]
    if "methodology" not in themed:
        themed["methodology"] = {"show_your_work": True}
    if "limitations" not in themed or not themed["limitations"]:
        themed["limitations"] = list(view.get("limitations") or [])
    # Preserve UNVALIDATED tags inside methodology
    meth = dict(themed.get("methodology") or {})
    if view.get("methodology", {}).get("weights_status"):
        meth["weights_status"] = view["methodology"]["weights_status"]
    themed["methodology"] = meth
    return themed


def _assert_exportable(view: dict) -> None:
    limitations = (view or {}).get("limitations") or []
    if not limitations:
        raise ValueError("export refuses empty limitations block")
    metrics = (view or {}).get("metrics") or {}
    if isinstance(metrics, dict):
        items = metrics.values()
    else:
        items = metrics
    for m in items:
        if not isinstance(m, dict):
            continue
        if m.get("kind", "sampled") != "sampled":
            continue
        if m.get("status") != "MEASURED":
            continue
        if m.get("ci_lower") is None or m.get("ci_upper") is None:
            name = m.get("name") or "metric"
            raise ValueError(f"export refuses metric '{name}' missing interval")


def export_report(view: dict, fmt: str, branding: dict | None = None) -> bytes:
    _assert_exportable(view)
    if fmt == "html":
        # Branded, charted, print-ready document (GEO Brain Trust item 7).
        # The honesty refusals above run first, so no format can skip them.
        from .render_html import render_report_html

        return render_report_html(view, branding).encode("utf-8")
    if fmt == "pdf":
        # 2026-08-20: this used to raise NotImplementedError -- there was no
        # real render pipeline in this repo. The branded report HTML
        # (render_html.py) is pure static markup with inline-SVG charts and
        # no <script>/canvas -- no JS execution is needed to lay it out, so
        # a full headless browser (Playwright/Chromium) isn't required
        # either; WeasyPrint renders real HTML+CSS straight to PDF bytes
        # with a much smaller, well-known Debian dependency (just the Pango
        # stack -- verified against this package's actual native bindings,
        # not guessed) than a browser would add to the production image.
        from .render_html import render_report_html
        from weasyprint import HTML

        html = render_report_html(view, branding)
        return HTML(string=html).write_pdf()
    payload = {
        "format": fmt,
        "view": view,
        "methodology": view.get("methodology"),
        "limitations": view.get("limitations"),
    }
    if fmt == "json":
        return json.dumps(payload, indent=2).encode("utf-8")
    # Minimal text export for genuinely unrecognized formats.
    lines = [
        f"REPORT ({fmt})",
        f"limitations: {view.get('limitations')}",
        f"methodology: {view.get('methodology')}",
        f"metrics: {view.get('metrics')}",
    ]
    return "\n".join(lines).encode("utf-8")


def api_payload(view: dict) -> dict:
    metrics = (view or {}).get("metrics") or {}
    # Never flatten to scalars.
    out_metrics = {}
    if isinstance(metrics, dict):
        for k, m in metrics.items():
            if isinstance(m, dict):
                out_metrics[k] = {
                    "value": m.get("value"),
                    "ci_lower": m.get("ci_lower"),
                    "ci_upper": m.get("ci_upper"),
                    "n": m.get("n"),
                    "status": m.get("status"),
                }
            else:
                raise ValueError("api_payload refuses scalar metrics")
    return {
        "metrics": out_metrics,
        "limitations": view.get("limitations") or [],
        "methodology": view.get("methodology") or {},
    }
