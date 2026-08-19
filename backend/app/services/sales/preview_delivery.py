"""Sales Feature 3.3 — watermarked, expiring, non-indexable preview delivery.

In-memory store for offline/standalone tests. Operator wires a real host later.
No IP / precise geo stored. Compliance gate before issue.
"""
from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any

from ..compliance.compliance_checker import audit_site

# Module-level store so tests can exercise expiry without a database.
_PREVIEWS: dict[str, dict[str, Any]] = {}

DEFAULT_EXPIRES_H = 48
WATERMARK_TEXT = "PREVIEW — NOT LIVE — DO NOT INDEX"
ROBOTS_HEADER = "noindex, nofollow"
HTTP_GONE = 410
HTTP_OK = 200
HTTP_FORBIDDEN = 403


def _now() -> float:
    return time.time()


def clear_preview_store() -> None:
    """Test helper — empty the in-memory preview map."""
    _PREVIEWS.clear()


def create_preview(
    site_artifact: dict,
    *,
    expires_h: int = DEFAULT_EXPIRES_H,
    clock: float | None = None,
) -> dict:
    """Issue a preview link after compliance screening."""
    html = site_artifact.get("html") or ""
    if not html.strip():
        return {
            "ok": False,
            "status_code": HTTP_FORBIDDEN,
            "reason": "empty site artifact — nothing to preview",
        }

    audit = audit_site(html, mode="publish")
    blocking = [
        f for f in (audit.get("findings") or [])
        if f.get("severity") == "error" or f.get("blocking")
    ]
    # Prefer explicit blocking list when present.
    if audit.get("blocking"):
        blocking = audit["blocking"]
    if audit.get("ok") is False or blocking:
        named = []
        for item in blocking:
            if isinstance(item, dict):
                named.append(item.get("rule") or item.get("id") or item.get("message"))
            else:
                named.append(str(item))
        # PHI testimonials are the named refusal the spec requires.
        phi_hit = any(
            "phi" in (n or "").lower() or "testimonial" in (n or "").lower()
            for n in named
        )
        reason = (
            "PHI rule: patient testimonial / identifier blocked preview"
            if phi_hit
            else "compliance gate refused preview"
        )
        return {
            "ok": False,
            "status_code": HTTP_FORBIDDEN,
            "reason": reason,
            "blocking": named,
            "rules": named,
        }

    # 2026-08-09: UUID4, not a token_urlsafe string. This module is now wired
    # into app/routers/sales_preview.py, where the id flows into LeadRequest
    # .preview_id and the prospects.preview_id column — both typed as UUID.
    # A token_urlsafe string would fail Pydantic validation and the Postgres
    # insert once a lead references a real preview. UUID4 carries more
    # entropy than the 12 bytes used before (122 bits vs. 96), so this is not
    # a regression in unguessability, and it matches the UUID convention
    # used for every other id in this schema (users, clients, prospects).
    preview_id = str(uuid.uuid4())
    issued = clock if clock is not None else _now()
    expires_at = issued + max(1, int(expires_h)) * 3600
    token = hashlib.sha256(preview_id.encode("utf-8")).hexdigest()[:16]
    record = {
        "preview_id": preview_id,
        "token": token,
        "issued_at": issued,
        "expires_at": expires_at,
        "expires_h": expires_h,
        "watermark": WATERMARK_TEXT,
        "headers": {
            "X-Robots-Tag": ROBOTS_HEADER,
        },
        "robots_txt_disallow": "/preview/",
        "html_watermarked": (
            f"<!-- {WATERMARK_TEXT} -->\n"
            f"<meta name=\"robots\" content=\"{ROBOTS_HEADER}\">\n"
            f"{html}"
        ),
        "opens": [],
        "open_count": 0,
        # Never store clinic production host as preview host.
        "preview_host": "preview.stag.local",
        "production_domain_forbidden": True,
    }
    _PREVIEWS[preview_id] = record
    return {
        "ok": True,
        "status_code": HTTP_OK,
        "preview_id": preview_id,
        "url": f"https://preview.stag.local/preview/{preview_id}",
        "expires_at": expires_at,
        "headers": record["headers"],
        "watermark": WATERMARK_TEXT,
        "reason": "preview issued after compliance screen",
    }


def record_open(preview_id: str, request_meta: dict | None = None) -> dict:
    """Record an open. Stores count, timestamps, coarse UA class — never IP."""
    record = _PREVIEWS.get(preview_id)
    if record is None:
        return {"ok": False, "status_code": 404, "reason": "unknown preview_id"}

    meta = dict(request_meta or {})
    # Strip forbidden keys even if a caller passes them.
    for forbidden in ("ip", "ip_address", "client_ip", "geo", "lat", "lon",
                      "latitude", "longitude", "precise_location"):
        meta.pop(forbidden, None)

    ua = (meta.get("user_agent") or meta.get("ua") or "").lower()
    if "mobile" in ua or "android" in ua or "iphone" in ua:
        ua_class = "mobile"
    elif "bot" in ua or "spider" in ua:
        ua_class = "bot"
    elif ua:
        ua_class = "desktop"
    else:
        ua_class = "unknown"

    event = {
        "ts": _now(),
        "ua_class": ua_class,
    }
    record["opens"].append(event)
    record["open_count"] = len(record["opens"])
    stored_keys = set(event.keys())
    return {
        "ok": True,
        "preview_id": preview_id,
        "open_count": record["open_count"],
        "stored_event_keys": sorted(stored_keys),
        "reason": "open recorded without IP or precise location",
    }


def preview_status(preview_id: str, *, clock: float | None = None) -> dict:
    """Return status; past expiry → 410 Gone and no body render."""
    record = _PREVIEWS.get(preview_id)
    if record is None:
        return {"ok": False, "status_code": 404, "reason": "unknown preview_id"}
    now = clock if clock is not None else _now()
    if now >= record["expires_at"]:
        return {
            "ok": False,
            "status_code": HTTP_GONE,
            "reason": "preview expired",
            "render": None,
            "expired": True,
        }
    return {
        "ok": True,
        "status_code": HTTP_OK,
        "preview_id": preview_id,
        "open_count": record["open_count"],
        "headers": record["headers"],
        "watermark": record["watermark"],
        "render": record["html_watermarked"],
        "expired": False,
        "reason": "preview active",
    }
