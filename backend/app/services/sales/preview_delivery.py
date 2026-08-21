"""Sales Feature 3.3 — watermarked, expiring, non-indexable preview delivery.

In-memory store for offline/standalone tests. Operator wires a real host later.
No IP / precise geo stored. Compliance gate before issue.
"""
from __future__ import annotations

import hashlib
import re
import time
import uuid
from typing import Any

from ..compliance.compliance_checker import audit_site

# Module-level store so tests can exercise expiry without a database.
_PREVIEWS: dict[str, dict[str, Any]] = {}

DEFAULT_EXPIRES_H = 48
DEFAULT_URL_PREFIX = "/sales/preview"
WATERMARK_TEXT = "PREVIEW — NOT LIVE — DO NOT INDEX"
ROBOTS_HEADER = "noindex, nofollow"
HTTP_GONE = 410
HTTP_OK = 200
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404


def _now() -> float:
    return time.time()


def clear_preview_store() -> None:
    """Test helper — empty the in-memory preview map."""
    _PREVIEWS.clear()


def _rewrite_internal_links(html: str, *, preview_id: str, url_prefix: str, filenames: list[str]) -> str:
    """Rewrite site_engine.py's own flat-filename internal links
    (href="about.html", href="index.html#faq", ...) to absolute
    preview-scoped URLs.

    2026-08-20 bug fix: generate_site() always wrote a full, real
    multi-page site (index/about/privacy/accessibility/every service page)
    with real, working nav links between them -- but this module only ever
    captured and served index.html, so every one of those links 404'd for
    a rep or prospect. Those hrefs are relative and correct for a real
    deployed site (each page really does sit next to its siblings), but
    once every page is served from a shared
    /sales/preview/{preview_id}/page/{filename} path instead of its own
    directory, the same relative href no longer resolves to the right
    place -- so it's rewritten to an absolute preview-scoped URL instead,
    per page, at issue time.
    """
    for filename in filenames:
        target = f"{url_prefix}/{preview_id}/page/{filename}"

        def _replace(match: "re.Match[str]", _target: str = target) -> str:
            fragment = match.group(1) or ""
            return f'href="{_target}{fragment}"'

        html = re.sub(rf'href="{re.escape(filename)}(#[^"]*)?"', _replace, html)
    return html


def create_preview(
    site_artifact: dict,
    *,
    url_prefix: str = DEFAULT_URL_PREFIX,
    expires_h: int = DEFAULT_EXPIRES_H,
    clock: float | None = None,
) -> dict:
    """Issue a preview link after compliance screening.

    site_artifact carries "pages": {filename: raw_html}, with "index.html"
    required. Every page in "pages" -- not just index.html -- is screened
    by the compliance gate below (2026-08-21 fix: it used to check only
    index.html, back when that was the only page this module ever served)
    and, once cleared, stored and made servable through the
    /page/{filename} sub-route (routers/sales_preview.py's
    view_preview_page), with internal nav links rewritten to point there
    (see _rewrite_internal_links above) instead of 404ing.

    Back-compat: a caller still passing the old single-page {"html": ...}
    shape gets it treated as {"pages": {"index.html": ...}} -- no known
    caller does this anymore (both routers/sales_preview.py call sites
    pass "pages" now), but this keeps the function itself from silently
    breaking on the old shape rather than refusing clearly.
    """
    pages = site_artifact.get("pages")
    if not pages and site_artifact.get("html"):
        pages = {"index.html": site_artifact["html"]}
    pages = pages or {}

    html = pages.get("index.html") or ""
    if not html.strip():
        return {
            "ok": False,
            "status_code": HTTP_FORBIDDEN,
            "reason": "empty site artifact — nothing to preview",
        }

    # 2026-08-21, Opus 5 review: this used to screen index.html only --
    # correct back when index.html was the only page this module ever
    # served. The multi-page fix above (2026-08-20) made about.html,
    # privacy.html, accessibility.html, and every service-*.html publicly
    # servable too, and those pages render prospect-supplied free text
    # verbatim (service descriptions, credentials) that this gate never
    # saw. Every page is now screened; the whole preview is refused if any
    # one of them has a blocking finding, not just index.html.
    named: list[str] = []
    for page_content in pages.values():
        audit = audit_site(page_content or "", mode="publish")
        page_blocking = [
            f for f in (audit.get("findings") or [])
            if f.get("severity") == "error" or f.get("blocking")
        ]
        # Prefer explicit blocking list when present.
        if audit.get("blocking"):
            page_blocking = audit["blocking"]
        if audit.get("ok") is False or page_blocking:
            for item in page_blocking:
                if isinstance(item, dict):
                    named.append(item.get("rule") or item.get("id") or item.get("message"))
                else:
                    named.append(str(item))

    if named:
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

    filenames = list(pages.keys())
    pages_watermarked = {
        filename: (
            f"<!-- {WATERMARK_TEXT} -->\n"
            f"<meta name=\"robots\" content=\"{ROBOTS_HEADER}\">\n"
            f"{_rewrite_internal_links(content, preview_id=preview_id, url_prefix=url_prefix, filenames=filenames)}"
        )
        for filename, content in pages.items()
    }

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
        "html_watermarked": pages_watermarked.get("index.html", ""),
        "pages_watermarked": pages_watermarked,
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


def preview_status(preview_id: str, *, page: str | None = None, clock: float | None = None) -> dict:
    """Return status; past expiry → 410 Gone and no body render.

    page=None (or "index.html") returns the homepage, unchanged from before
    this module handled more than one page. Any other real filename
    create_preview() actually captured for this preview_id is servable too
    (routers/sales_preview.py's view_preview_page). An unknown page name on
    a real, unexpired preview returns its own 404, distinct from an unknown
    preview_id, so a caller can tell "this preview doesn't exist" from
    "this preview exists but has no page by that name."
    """
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

    page_name = page or "index.html"
    pages = record.get("pages_watermarked") or {}
    render = pages.get(page_name)
    if render is None:
        return {
            "ok": False,
            "status_code": HTTP_NOT_FOUND,
            "reason": f"this preview has no page named {page_name!r}",
        }

    return {
        "ok": True,
        "status_code": HTTP_OK,
        "preview_id": preview_id,
        "open_count": record["open_count"],
        "headers": record["headers"],
        "watermark": record["watermark"],
        "render": render,
        "expired": False,
        "reason": "preview active",
    }
