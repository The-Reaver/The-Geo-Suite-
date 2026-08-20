from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import httpx
import ipaddress
import socket
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

from app.core import pricing, rubric
from app.core.permissions import require_owner, require_sales_agent, security
from app.core.supabase_client import get_supabase_admin, get_user_client
from app.services.audit_engine import run_audit
from app.services.dashboard_panels import build_lead_pipeline, render_lead_pipeline_html
from app.schemas.site_schemas import FAQ, Rating
from app.services.preview import generate_preview
from app.services.sales.preview_delivery import (
    create_preview as issue_preview_delivery,
    preview_status,
    record_open,
)

router = APIRouter(prefix="/sales", tags=["sales"])

# --- SSRF guard for /audit-current --------------------------------------
# 2026-08-08 GEO Brain Trust review, Sentinel finding 1: this route fetched
# any caller-supplied URL with zero auth and zero validation, a textbook
# unauthenticated SSRF (cloud metadata endpoints, internal services). Every
# resolved address is checked, not just the literal hostname, to close the
# DNS-rebinding gap a hostname-only denylist would leave open. Redirects are
# not followed, since validating the first URL and then following a redirect
# to an internal address is the classic bypass for this exact check.

_BLOCKED_HOSTNAMES = {"localhost", "metadata.google.internal"}


def _is_public_http_url(url: str) -> tuple[bool, str]:
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Malformed URL."

    if parsed.scheme not in ("http", "https"):
        return False, "Only http and https URLs are allowed."
    if not parsed.hostname:
        return False, "URL has no hostname."

    hostname = parsed.hostname.lower()
    if hostname in _BLOCKED_HOSTNAMES:
        return False, "This host is not allowed."

    try:
        addrinfo = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False, "Could not resolve host."

    if not addrinfo:
        return False, "Could not resolve host."

    for family, _type, _proto, _canonname, sockaddr in addrinfo:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False, "Could not validate a resolved address."
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False, "This URL resolves to a non-public address and cannot be audited."

    return True, ""


# --- Rate limiting for /audit-current ------------------------------------
# In-process, per-caller token bucket. Deliberately simple: no new dependency,
# no shared state across workers. Good enough to stop single-process abuse of
# an endpoint that now does an outbound fetch per call; a multi-worker deploy
# should move this to a shared store (Redis) instead of raising the limit.
_RATE_LIMIT_WINDOW_SECONDS = 60
_RATE_LIMIT_MAX_CALLS = 10
_rate_limit_state: Dict[str, List[float]] = {}


def _enforce_rate_limit(key: str) -> None:
    now = time.monotonic()
    window_start = now - _RATE_LIMIT_WINDOW_SECONDS
    calls = [t for t in _rate_limit_state.get(key, []) if t > window_start]
    if len(calls) >= _RATE_LIMIT_MAX_CALLS:
        raise HTTPException(
            status_code=429,
            detail="Too many audit requests. Try again in a minute.",
        )
    calls.append(now)
    _rate_limit_state[key] = calls

class AuditCurrentRequest(BaseModel):
    url: str

class ReportRequest(BaseModel):
    url: str
    client_name: str = ""
    price: Optional[float] = None

# 2026-08-20: BusinessFactsReq used to have no rating/same_as/faqs at all, so
# a real prospect's facts could never reach generate_preview() with enough
# substance to score fairly -- see site_generator_example()'s docstring below
# for why that gap existed. Added the three fields the site engine and
# ILLUSTRATIVE_HBOT_EXAMPLE (a real BusinessFacts instance) already carry,
# reusing site_schemas.py's own Rating/FAQ types rather than redefining them.
# Every other field keeps its existing default so this stays backward
# compatible with the partial payloads test_sales_preview.py already sends
# (e.g. test_create_preview_requires_auth posts only business_name).
class BusinessFactsReq(BaseModel):
    business_name: str
    subtype: str = ""
    locality: str = ""
    region: str = ""
    street: str = ""
    telephone: str = ""
    postal_code: str = ""
    domain: str = ""
    rating: Optional[Rating] = None
    same_as: List[str] = []
    faqs: List[FAQ] = []

class RankLeadsRequest(BaseModel):
    providers: List[Dict[str, Any]]
    # Optional map of provider name -> {accessibility_gap, visibility_gap}.
    # Absent gaps leave a lead provisional rather than assuming a clean site.
    audits: Optional[Dict[str, Dict[str, float]]] = None


class LeadRequest(BaseModel):
    # 2026-08-09 operator decision: agent_id is deliberately not a field here.
    # See the comment on save_lead() below — it is always taken from the
    # authenticated caller's own JWT, never from the request body.
    business_name: str
    contact_name: Optional[str] = ""
    contact_email: Optional[str] = ""
    city: Optional[str] = ""
    current_score: int
    # 2026-08-16, Phase 1 of the offline build: preview_id relaxed to
    # Optional. It was required even though the prospects.preview_id column
    # itself has no NOT NULL constraint — a lead discovered via Prospecting
    # and saved directly (the real flow "Sync for the field" depends on
    # having data to sync) never goes through /sales/preview first, so
    # forcing a preview_id blocked that path entirely.
    preview_id: Optional[UUID] = None
    # New: the business's real site URL, so a saved lead has something for
    # /sales/kit to generate a Sales Kit against later. Migration
    # 20260816000000_prospects_website_url.sql. Nullable -- a lead saved
    # without a confirmed URL yet stays valid, "Sync for the field" just
    # skips kit-generation for it.
    website_url: Optional[str] = None

@router.post("/audit-current")
async def audit_current(
    request: AuditCurrentRequest,
    payload: dict = Depends(require_sales_agent),
):
    is_public, reason = _is_public_http_url(request.url)
    if not is_public:
        raise HTTPException(status_code=400, detail=reason)

    rate_limit_key = str(payload.get("sub") or payload.get("email") or "unknown")
    _enforce_rate_limit(rate_limit_key)

    try:
        # follow_redirects=False on purpose: validating the request URL and
        # then following a server-issued redirect to an internal address is
        # the standard bypass for the check above. A caller whose target
        # legitimately redirects gets a clear 400 and can resubmit the final
        # URL directly.
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            response = await client.get(request.url)
            if response.is_redirect:
                raise HTTPException(
                    status_code=400,
                    detail="URL redirected. Submit the final destination URL directly.",
                )
            response.raise_for_status()
            html = response.text
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch url: {str(e)}")

    with tempfile.TemporaryDirectory(prefix="geo_audit_") as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "index.html").write_text(html, encoding="utf-8")
        result = run_audit(tmpdir, homepage_only=True)

    return {
        "score": result.normalized_score,
        "top_gaps": result.fix_list[:5] if result.fix_list else [],
        "not_measured": result.not_measured,
        "not_measured_note": (
            "This live preview only fetches the homepage, so " +
            ", ".join(result.not_measured) +
            " are not measured and are excluded from the score above — not "
            "assumed to pass."
        ),
        # 2026-08-16 operator ruling: client-facing "AI-Search Readiness" claims
        # pause until the rubric weight-sourcing gap is closed. See
        # rubric.AI_SEARCH_READINESS_CLAIMS_PAUSED.
        "preliminary": rubric.AI_SEARCH_READINESS_CLAIMS_PAUSED,
        "preliminary_note": (
            "This score is preliminary and internal-use only — the rubric's "
            "category weights are not yet traced to a cited source or "
            "confidence interval (open since 2026-08-08). Do not present as a "
            "finished client-facing readiness claim until this is closed."
        ) if rubric.AI_SEARCH_READINESS_CLAIMS_PAUSED else None,
    }

@router.post("/report", response_class=HTMLResponse)
async def branded_report(
    request: ReportRequest,
    payload: dict = Depends(require_sales_agent),
):
    """Audit the submitted URL live and render the branded, print-ready report
    (score gauge, Value & Savings, methodology, limitations). Same SSRF guard,
    rate limit and redirect policy as /audit-current — this route also does an
    outbound fetch per call. Honest: the score is measured, never fabricated;
    the value figures are shown as published market ranges with a methodology
    note, and Performance is disclosed as excluded from this live path."""
    is_public, reason = _is_public_http_url(request.url)
    if not is_public:
        raise HTTPException(status_code=400, detail=reason)

    rate_limit_key = str(payload.get("sub") or payload.get("email") or "unknown")
    _enforce_rate_limit(rate_limit_key)

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            response = await client.get(request.url)
            if response.is_redirect:
                raise HTTPException(
                    status_code=400,
                    detail="URL redirected. Submit the final destination URL directly.",
                )
            response.raise_for_status()
            html_text = response.text
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch url: {str(e)}")

    with tempfile.TemporaryDirectory(prefix="geo_report_") as tmpdir:
        (Path(tmpdir) / "index.html").write_text(html_text, encoding="utf-8")
        result = run_audit(tmpdir, homepage_only=True)

    from app.services.compliance.compliance_checker import audit_site as audit_compliance
    from app.services.reporting.dashboard import category_pillars
    from app.services.reporting.render_html import render_report_html

    # 2026-08-16: real WCAG / marketing-claim / PHI-testimonial findings from
    # the same fetched HTML the score came from -- feeds the report's
    # "Governing framework" section. Structural check, not a legal
    # determination; the renderer's own disclosure text says so on every render.
    compliance_result = audit_compliance(html_text, mode="prospect")

    score = result.normalized_score
    price = request.price
    savings = (
        [max(0.0, 24000.0 - price), max(0.0, 83500.0 - price)]
        if price is not None
        else None
    )
    limitations = [
        f"{name} is not measured by this live path and is excluded from the score."
        for name in result.not_measured
    ] + [
        "The score reflects the pages fetched at audit time and can change as the site changes.",
    ]
    if rubric.AI_SEARCH_READINESS_CLAIMS_PAUSED:
        # 2026-08-16 operator ruling: pause client-facing "AI-Search Readiness"
        # claims until the rubric weight-sourcing gap (open since 2026-08-08)
        # is closed. This report still shows the real score — it's the framing
        # as a finished readiness claim that's paused, not the audit itself.
        limitations.append(
            "PRELIMINARY: this rubric's category weights are not yet traced to "
            "a cited source or confidence interval. Treat this report as "
            "internal/preliminary, not a finished AI-Search Readiness claim."
        )
    view = {
        "client": request.client_name or (urlparse(request.url).hostname or "Client"),
        "score": score,
        # 2026-08-16: real pillar-by-pillar findings and the prioritized fix
        # list, sourced directly from the same AuditResult the score came from
        # (dashboard.category_pillars is the merge point — see
        # GEO_STATUS_AND_ROADMAP_2026-08-16.md section 3 for the gap this closes).
        # Not a placeholder: every finding and fix line is real engine output.
        "categories": category_pillars(result),
        "fix_list": result.fix_list,
        "compliance_findings": compliance_result.get("findings", []),
        "report_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "methodology": {
            "Method": "Live crawl of the submitted URL, scored on the seven-category AI-Search rubric.",
            "Engines": "ChatGPT, Perplexity, Gemini, Google AI Overviews",
            "weights_status": "UNVALIDATED",
        },
        "limitations": limitations,
        "value": {
            "agency_range": [24000, 83500],
            "price": price,
            "savings_range": savings,
            "note": (
                "Comparison prices are published market ranges for equivalent "
                "medical-practice services (AI-search audit, custom site, schema/SEO, "
                "WCAG remediation, visibility monitoring, marketing-claim review), "
                "not a quote for any specific competing offer."
            ),
        },
    }
    return HTMLResponse(content=render_report_html(view))


class KitRequest(BaseModel):
    url: str
    business_name: str = ""

@router.post("/kit", response_class=HTMLResponse)
async def sales_kit(
    request: KitRequest,
    payload: dict = Depends(require_sales_agent),
):
    """The Sales Kit: one printable packet combining a real live audit
    ('before') with a real, freshly-audited generated-site proof point
    ('after', an illustrative example — never claimed to be this business's
    actual future site) and pricing. Same SSRF guard, rate limit and redirect
    policy as /audit-current and /report. 2026-08-16, built for the investor
    demo per the operator's decision to scope Sales Kit minimal-but-real."""
    is_public, reason = _is_public_http_url(request.url)
    if not is_public:
        raise HTTPException(status_code=400, detail=reason)

    rate_limit_key = str(payload.get("sub") or payload.get("email") or "unknown")
    _enforce_rate_limit(rate_limit_key)

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            response = await client.get(request.url)
            if response.is_redirect:
                raise HTTPException(
                    status_code=400,
                    detail="URL redirected. Submit the final destination URL directly.",
                )
            response.raise_for_status()
            html_text = response.text
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch url: {str(e)}")

    with tempfile.TemporaryDirectory(prefix="geo_kit_") as tmpdir:
        (Path(tmpdir) / "index.html").write_text(html_text, encoding="utf-8")
        result = run_audit(tmpdir, homepage_only=True)

    from app.services.reporting.sales_kit import render_sales_kit_html

    name = request.business_name or (urlparse(request.url).hostname or "Prospect")
    return HTMLResponse(content=render_sales_kit_html(
        business_name=name,
        before_score=result.normalized_score,
        before_gaps=result.fix_list,
        before_not_measured=result.not_measured,
    ))


@router.get("/pricing-tiers")
async def pricing_tiers(payload: dict = Depends(require_sales_agent)):
    """The same real tiers the Sales Kit renders (core/pricing.py), so the
    live Nova pricing panel reads from one source instead of a second
    hand-synced copy in TypeScript. Also hands back the publish-gate
    threshold so the frontend doesn't hardcode "93" separately either."""
    return {"tiers": pricing.PRICING_TIERS, "publish_threshold": rubric.PUBLISH_THRESHOLD}


@router.post("/site-generator-example")
async def site_generator_example(
    request: Request,
    payload: dict = Depends(require_owner),
):
    """Site Generator, wired to the real, already-built pipeline it had never
    been connected to (site_engine.generate_site -> the real audit engine ->
    the real compliance-gated, 48h-expiring preview link). 2026-08-16, for
    the investor/conference demo.

    Reuses `sales_kit.ILLUSTRATIVE_HBOT_EXAMPLE` — the same illustrative
    fixture the Sales Kit's "after" example uses — as a reliable, zero-input
    fallback: no live prospect data required, always the same real, cached
    score. `BusinessFactsReq` (below) has since gained `rating`/`same_as`/
    `faqs`, so a rep with an already-audited prospect selected should call
    `/preview` with that prospect's real facts instead and get their actual
    generated site, not this fixture — the frontend picks between the two
    (see frontend/app/nova/site-generator/route.ts). This route stays as the
    guaranteed-good path for when no real prospect is in context yet."""
    from app.services.reporting.sales_kit import ILLUSTRATIVE_HBOT_EXAMPLE
    from app.services.site_engine import generate_site

    with tempfile.TemporaryDirectory(prefix="geo_sitegen_") as tmpdir:
        out = Path(tmpdir)
        generate_site(ILLUSTRATIVE_HBOT_EXAMPLE, out)
        result = run_audit(out)  # not homepage_only — real robots.txt/sitemap.xml exist here
        html = (out / "index.html").read_text(encoding="utf-8")

    delivery = issue_preview_delivery({"html": html})
    if not delivery.get("ok"):
        raise HTTPException(
            status_code=delivery.get("status_code", 403),
            detail=delivery.get("reason", "preview could not be issued"),
        )

    preview_url = str(request.url_for("view_preview", preview_id=delivery["preview_id"]))
    return {
        "preview_url": preview_url,
        "preview_id": delivery["preview_id"],
        "expires_at": delivery["expires_at"],
        "score": result.normalized_score,
        "passed": result.passed,
    }


# --- Auth for /preview, /rank-leads, /lead-pipeline, /lead ---------------
# 2026-08-09 GEO Brain Trust Presentation Mode review, Sentinel finding: these
# four routes carried zero authentication while /audit-current and /report
# (same router, same file) were already gated behind require_owner. /lead is
# the severe case — it performs a real write to the prospects table through
# get_supabase_admin() (the service-role client, which bypasses row-level
# security) from fully unauthenticated, caller-supplied JSON, including an
# arbitrary agent_id. Closed by requiring the same owner/admin auth already
# established elsewhere in this file, not a new access-control concept.
#
# Two residuals flagged in that review, both since resolved by operator
# decision (2026-08-09):
#   1. Which preview mechanism is authoritative: preview_delivery.py, not a
#      bare local filesystem path. See create_preview() below.
#   2. Whether /lead's agent_id should be locked to the caller: yes. See
#      LeadRequest and save_lead() below — agent_id is no longer a client-
#      supplied field at all.

# 2026-08-19 operator decision: /preview was the one route in this file left
# on require_owner after the 2026-08-16 sales_agent widening (which moved
# audit-current, report, kit, lead, and my-prospects to require_sales_agent).
# A rep's own pitch flow calls audit-current then preview back to back --
# leaving preview owner-only meant every non-owner rep's wizard 403'd right
# after the audit step succeeded. require_sales_agent is a strict superset
# (owner/admin keep everything they had); this widens, narrows nothing.
@router.post("/preview")
async def create_preview(
    facts: BusinessFactsReq,
    request: Request,
    payload: dict = Depends(require_sales_agent),
):
    """Generate a demo site for a prospect, then issue it through the
    compliance-gated, expiring preview mechanism, not as a bare local
    filesystem path. generate_preview() still does the real site build and
    live audit score; its output HTML is now piped through
    preview_delivery.create_preview() for the 48h TTL, the PHI/testimonial
    compliance gate, and the noindex/nofollow watermark. A blocked preview
    (e.g. an unauthorized testimonial) returns 403 with the specific rule
    that blocked it, not a silent 200."""
    try:
        result = generate_preview(facts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    index_path = Path(result.out_dir) / "index.html"
    html = index_path.read_text(encoding="utf-8") if index_path.exists() else ""

    delivery = issue_preview_delivery({"html": html})
    if not delivery.get("ok"):
        raise HTTPException(
            status_code=delivery.get("status_code", 403),
            detail=delivery.get("reason", "preview could not be issued"),
        )

    # preview_delivery.py's own "url" field points at a fixed placeholder
    # host (preview.stag.local) — that module's docstring says the operator
    # wires a real host later. Building the actual reachable URL from this
    # request instead, so what gets handed to a prospect isn't a link that
    # 404s.
    preview_url = str(request.url_for("view_preview", preview_id=delivery["preview_id"]))

    return {
        "preview_url": preview_url,
        "preview_id": delivery["preview_id"],
        "expires_at": delivery["expires_at"],
        "score": result.score,
        "breakdown": result.fix_list,
    }


@router.get("/preview/{preview_id}")
async def view_preview(preview_id: str, request: Request):
    """Serve a previously issued preview link.

    Deliberately NOT behind require_owner, unlike every other route in this
    file: this is the one link in the whole flow a prospect with no STAG
    account has to be able to open, the same share-link model
    preview_delivery.py was built for. The unguessable preview_id (a UUID4,
    122 bits of entropy) is the access control. Every response carries
    X-Robots-Tag: noindex, nofollow, and the link is self-expiring — 410
    Gone with no body once past its 48h TTL, not a link that stays live
    forever.

    Not done here (flagged, not fixed): no rate limit on this route. The
    preview_id space is large enough that brute-forcing it is not practical,
    but a scraper with a leaked id could still hit this repeatedly; the same
    per-caller limiter used on /audit-current doesn't apply cleanly to an
    unauthenticated route and would need its own design.
    """
    status = preview_status(preview_id)
    if not status.get("ok"):
        raise HTTPException(
            status_code=status.get("status_code", 404),
            detail=status.get("reason", "not found"),
        )

    record_open(preview_id, {"user_agent": request.headers.get("user-agent", "")})

    return HTMLResponse(content=status["render"], headers=status.get("headers") or {})

@router.post("/rank-leads")
async def rank_prospect_leads(
    request: RankLeadsRequest,
    payload: dict = Depends(require_owner),
):
    """Rank a prospect list for the sales dashboard. Read-only: scoring never
    writes to or mutates a provider record."""
    panel = build_lead_pipeline(request.providers, request.audits)
    return panel


@router.post("/lead-pipeline", response_class=HTMLResponse)
async def lead_pipeline_html(
    request: RankLeadsRequest,
    payload: dict = Depends(require_owner),
):
    """Sales/admin HTML surface for the ranked lead pipeline.

    Read-only. Empty provider list renders an honest empty state, not a
    fabricated ranking.
    """
    panel = build_lead_pipeline(request.providers, request.audits)
    return render_lead_pipeline_html(panel)


def _log_prospect_access(event_type: str, agent_id: str, extra: dict | None = None) -> None:
    """Append-only access-log entry for the compliance technical baseline
    (2026-08-16 operator ruling: HIPAA + CCPA-style data-privacy law + a more
    formal extension of the existing WCAG/FTC/PHI posture). Always written
    through the admin client, from server code the agent cannot influence --
    an audit trail an agent could edit or suppress isn't one. Best-effort:
    a logging failure must never block the real operation it's logging, so
    this swallows its own errors rather than raising into the caller."""
    try:
        get_supabase_admin().table("events").insert({
            "client_id": None,
            "event_type": event_type,
            "payload": {"agent_id": agent_id, **(extra or {})},
        }).execute()
    except Exception:
        pass


@router.post("/lead")
async def save_lead(
    lead: LeadRequest,
    payload: dict = Depends(require_sales_agent),
):
    """Save a prospect lead. agent_id is always the authenticated caller's
    own id, taken from the verified JWT's sub claim, never from the request
    body (2026-08-09 operator decision, closing the residual noted when
    auth was added to this route: a caller could previously attribute a
    lead to any agent_id it liked)."""
    try:
        agent_id = UUID(str(payload.get("sub")))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Authenticated user id is not a valid UUID; cannot attribute this lead.",
        )

    supabase = get_supabase_admin()
    data = {
        "agent_id": str(agent_id),
        "business_name": lead.business_name,
        "contact_name": lead.contact_name,
        "contact_email": lead.contact_email,
        "city": lead.city,
        "current_score": lead.current_score,
        "preview_id": str(lead.preview_id) if lead.preview_id else None,
        "website_url": lead.website_url,
    }
    resp = supabase.table("prospects").insert(data).execute()
    if not resp.data:
        raise HTTPException(status_code=500, detail="Failed to insert lead")
    _log_prospect_access("prospect.created", str(agent_id), {"prospect_id": resp.data[0].get("id")})
    return {"status": "success", "lead": resp.data[0]}


def _bearer_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    return credentials.credentials


@router.get("/my-prospects")
async def my_prospects(
    payload: dict = Depends(require_sales_agent),
    token: str = Depends(_bearer_token),
):
    """List the calling agent's own saved prospects.

    2026-08-16, Phase 0 of the sales-agent master panel build: the
    `prospects` table (migrated 2026-07-25, RLS enabled 2026-08-09 per
    `prospects_select` in supabase/migrations/20260809000000_prospects_rls_policies.sql)
    has been write-only since it was created -- save_lead() inserts through
    the service-role client, which bypasses RLS entirely, and nothing has
    ever read it back. That means the RLS policy ("agents see their own
    leads, operators see every lead") has never actually been exercised by
    any real request. This route is the read half: it uses get_user_client()
    with the caller's own JWT, not the admin client, so RLS is the thing
    actually deciding what comes back -- not an application-level filter
    that could drift from the policy. No agent_id filter is applied here in
    Python; if one ever shows up, that would mean RLS silently stopped
    doing its job, not that this code needs to do RLS's job for it."""
    supabase = get_user_client(token)
    resp = supabase.table("prospects").select("*").order("created_at", desc=True).execute()
    rows = resp.data or []
    _log_prospect_access("prospect.accessed", str(payload.get("sub")), {"action": "list", "count": len(rows)})
    return {"prospects": rows}


class CustomizeRequest(BaseModel):
    note: str = ""
    selected_gap_indices: List[int] = []
    # Client-generated, not server now() -- the whole point of Phase 2's
    # write-side offline sync is resolving a queued offline edit against
    # whatever the server already has once it finally syncs. See
    # OFFLINE_ARCHITECTURE_BRAIN_TRUST_2026-08-16.md section D.
    client_timestamp: datetime


@router.patch("/prospects/{prospect_id}/customize")
async def customize_prospect(
    prospect_id: UUID,
    body: CustomizeRequest,
    payload: dict = Depends(require_sales_agent),
):
    """Save an agent's Sales Kit customization for one prospect -- a note
    and which gaps to highlight. Phase 2 of the offline build
    (OFFLINE_ARCHITECTURE_BRAIN_TRUST_2026-08-16.md section F), and the
    *original* Sales Kit customization ask the sales-agent master-panel
    review's Q1 carried, now built offline-aware from the start.

    Last-write-wins, keyed by the client-generated `client_timestamp`, per
    Celestina's finding D: the realistic conflict surface is narrow (the
    same agent editing the same prospect from two devices, or a stale
    queued write racing a newer one) -- not a CRDT, which would be
    over-engineering for one text field and one small index array. A write
    older than what's already stored is discarded, not silently applied
    over newer data, and the caller is told so honestly rather than getting
    back an ambiguous 200.

    Ownership checked explicitly here through the admin client rather than
    relying on RLS for the write: the original prospects RLS migration
    deliberately defines no insert/update/delete policy ("no client-side
    role should ever write this table directly"), so this route is that
    policy's application-layer equivalent for this one specific write."""
    try:
        agent_id = UUID(str(payload.get("sub")))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Authenticated user id is not a valid UUID.")

    supabase = get_supabase_admin()
    existing = supabase.table("prospects").select("agent_id, customized_at").eq("id", str(prospect_id)).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Prospect not found.")
    row = existing.data[0]
    if str(row.get("agent_id")) != str(agent_id):
        raise HTTPException(status_code=403, detail="This prospect belongs to a different agent.")

    incoming = body.client_timestamp
    if incoming.tzinfo is None:
        incoming = incoming.replace(tzinfo=timezone.utc)

    existing_customized_at = row.get("customized_at")
    if existing_customized_at:
        existing_dt = datetime.fromisoformat(str(existing_customized_at).replace("Z", "+00:00"))
        if existing_dt >= incoming:
            _log_prospect_access("prospect.customize_discarded_stale", str(agent_id), {
                "prospect_id": str(prospect_id),
                "incoming_timestamp": incoming.isoformat(),
                "existing_timestamp": existing_dt.isoformat(),
            })
            return {
                "applied": False,
                "reason": "stale",
                "detail": "A newer customization already exists for this prospect; this write was discarded, not applied.",
                "current_customized_at": existing_dt.isoformat(),
            }

    supabase.table("prospects").update({
        "note": body.note,
        "selected_gap_indices": body.selected_gap_indices,
        "customized_at": incoming.isoformat(),
    }).eq("id", str(prospect_id)).execute()

    _log_prospect_access("prospect.customized", str(agent_id), {"prospect_id": str(prospect_id)})
    return {"applied": True, "reason": None, "detail": None, "current_customized_at": incoming.isoformat()}
