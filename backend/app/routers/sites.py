import logging
import os
import pathlib
import tempfile

from fastapi import APIRouter, Depends, HTTPException, Path
from uuid import UUID
from pydantic import BaseModel
from typing import Dict, Any, Optional
from ..core.permissions import require_sales_agent
from ..core.rubric import PUBLISH_THRESHOLD
from ..services import audit_engine, site_pipeline
from ..services.site_engine import generate_site
from ..services.compliance.compliance_checker import audit_site as compliance_audit
from ..services.a11y_audit import audit_accessibility
from ..services.privacy_audit import audit_privacy
from ..schemas.site_schemas import BusinessFacts
from ..repositories.audit_results_repository import (
    InMemoryAuditResultsRepository,
    SupabaseAuditResultsRepository,
)
from ..repositories.content_pages_repository import (
    InMemoryContentPagesRepository,
    SupabaseContentPagesRepository,
)
from ..repositories.optimization_files_repository import (
    InMemoryOptimizationFilesRepository,
    SupabaseOptimizationFilesRepository,
)
from ..repositories.schema_records_repository import (
    InMemorySchemaRecordsRepository,
    SupabaseSchemaRecordsRepository,
)

router = APIRouter(prefix="/sites", tags=["sites"])
logger = logging.getLogger(__name__)

# 2026-08-08, GEO Brain Trust review, open item 5 (Jasiah's finding): a
# passing audit used to generate into a temp directory and discard it, so
# nothing about a "publishable" site ever reached a real store. These
# module-level singletons persist across requests within one running
# process when Supabase isn't configured, matching the same
# GEO_USE_SUPABASE_CLIENT_STORE-gated pattern client_store.py already uses,
# so a test run or verify.py --geo never invents a live Supabase round-trip
# just because credentials happen to be present in the environment.
_CONTENT_REPO = InMemoryContentPagesRepository()
_SCHEMA_REPO = InMemorySchemaRecordsRepository()
_OPT_REPO = InMemoryOptimizationFilesRepository()
_AUDIT_REPO = InMemoryAuditResultsRepository()


def _use_supabase_site_repos() -> bool:
    if os.environ.get("GEO_USE_SUPABASE_SITE_REPOS", "").strip() != "1":
        return False
    try:
        from ..core.supabase_client import get_supabase_admin

        get_supabase_admin()
        return True
    except Exception:
        return False


def get_site_repos():
    """Return (content_repo, schema_repo, opt_repo, audit_repo)."""
    if _use_supabase_site_repos():
        return (
            SupabaseContentPagesRepository(),
            SupabaseSchemaRecordsRepository(),
            SupabaseOptimizationFilesRepository(),
            SupabaseAuditResultsRepository(),
        )
    return (_CONTENT_REPO, _SCHEMA_REPO, _OPT_REPO, _AUDIT_REPO)


class PipelineSite(BaseModel):
    site_id: str
    business_name: Optional[str] = None
    city: Optional[str] = None
    score: Optional[int] = None
    passed: Optional[bool] = None
    run_at: Optional[str] = None


class PipelineListResponse(BaseModel):
    sites: list[PipelineSite]


class AuditRequest(BaseModel):
    facts: BusinessFacts
    # Optional Core Web Vitals field data (LCP seconds, INP ms, CLS). When
    # absent, the performance category is excluded from the denominator rather
    # than assumed to pass.
    cwv: Optional[Dict[str, float]] = None


class AuditResponse(BaseModel):
    score: int
    passed: bool
    breakdown: Dict[str, Any]


def _supplemental_findings(rule_prefix: str, failures: list) -> list:
    # 2026-08-08, GEO Brain Trust review, open item (rank 6): a11y_audit.py
    # (SPEC_A11Y1) and privacy_audit.py (SPEC_PRIV1) were built, real, and
    # verified by direct execution to already pass on a freshly generated
    # site, but neither was ever called from the publish path. Their plain
    # string failures are wrapped in the same {rule, severity, element,
    # message} shape compliance_checker.py's blocking findings use, so the
    # API response stays one consistent list regardless of which validator
    # caught the issue.
    return [
        {"rule": f"{rule_prefix}-{idx}", "severity": "error", "element": rule_prefix, "message": msg}
        for idx, msg in enumerate(failures, start=1)
    ]


@router.post("/{site_id}/audit", response_model=AuditResponse)
def trigger_audit(
    req: AuditRequest,
    site_id: str = Path(...),
    payload: dict = Depends(require_sales_agent),
):
    """Generate the site from confirmed facts, run the AI-Search Readiness audit,
    and refuse to publish below the threshold.

    2026-08-20, Pipeline slice 1: widened from require_owner to
    require_sales_agent, matching every other sales-floor route
    (sales_preview.py's own require_sales_agent docstring). This route is
    Nova's real "Save to Pipeline" persist path -- gating it to owner-only
    meant no actual field rep could ever use it, only an owner account.
    owner/admin keep full access, same as before.

    The site and audit engines are real (Sprint days 3-8). This route returns a
    genuine score derived from the generated artifacts. It still refuses to
    publish below PUBLISH_THRESHOLD, so a failing site returns 400 with its
    score and fixes.

    2026-08-08: a passing site that also clears the compliance gate is now
    actually persisted via site_pipeline.generate_and_store, instead of
    being generated into a temp directory and discarded. Persistence
    failures are logged and reported as 500s rather than silently returning
    a 200 that claims the site is live when it never left local disk.

    2026-08-08: the compliance gate now composes three validators rather
    than one. compliance_checker.py (SPEC_GATE_COMPLIANCE) covers WCAG,
    marketing-claim, and PHI-testimonial findings on index.html; a11y_audit.py
    (SPEC_A11Y1) and privacy_audit.py (SPEC_PRIV1) were already built and
    tested but never wired in, and each covers real gaps the other lacks
    (a11y_audit checks every generated page, not just index.html, and adds
    skip-link/landmark/title checks; privacy_audit is the only validator that
    checks privacy.html, its footer link, and the consent region at all).
    Their findings are added to the same blocking list with a11y-/privacy-
    rule prefixes so a client always sees one composed list, not three
    separate gates to debug.
    """
    UUID(str(site_id))  # validate the id at the boundary

    # 2026-08-20: this used to generate_site()+run_audit() here to decide
    # pass/fail, then call site_pipeline.generate_and_store() below -- which
    # unconditionally called generate_site()+run_audit() again on a *second*
    # fresh temp dir. Every single successful publish paid for both twice.
    # The temp dir now stays alive through the persist call so
    # generate_and_store can reuse this same generation and audit result
    # instead of silently redoing both.
    with tempfile.TemporaryDirectory(prefix="geo_audit_") as tmp:
        out = pathlib.Path(tmp)
        generate_site(req.facts, out)
        result = audit_engine.run_audit(out, cwv=req.cwv)
        breakdown = audit_engine.result_to_breakdown(result)

        if not result.passed:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": f"Audit scored {result.normalized_score}; publish threshold is {PUBLISH_THRESHOLD}.",
                    "score": result.normalized_score,
                    "fix_list": result.fix_list,
                },
            )

        index_html = (out / "index.html").read_text(encoding="utf-8")
        compliance = compliance_audit(index_html, mode="publish")
        a11y = audit_accessibility(out)
        privacy = audit_privacy(out)

        blocking = list(compliance["blocking"])
        blocking += _supplemental_findings("a11y", a11y.failures)
        blocking += _supplemental_findings("privacy", privacy.failures)

        if blocking:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Compliance gate failed; site cannot publish.",
                    "score": result.normalized_score,
                    "blocking": blocking,
                },
            )

        content_repo, schema_repo, opt_repo, audit_repo = get_site_repos()
        try:
            site_pipeline.generate_and_store(
                site_id,
                req.facts,
                content_repo=content_repo,
                schema_repo=schema_repo,
                opt_repo=opt_repo,
                audit_repo=audit_repo,
                cwv=req.cwv,
                trigger="owner_publish",
                site_dir=out,
                audit_result=result,
            )
        except Exception as exc:
            logger.exception("Site %s passed both gates but failed to persist", site_id)
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Site passed the audit and compliance gates but could not be "
                    "saved. Nothing was published. Try again or contact support.",
                    "score": result.normalized_score,
                },
            ) from exc

    return AuditResponse(score=result.normalized_score, passed=result.passed, breakdown=breakdown)


def _prospects_by_id(site_ids: list[str]) -> dict[str, dict]:
    """business_name/city for a Pipeline list come from prospects, not the
    pipeline tables -- audit_results/content_pages/etc deliberately carry no
    business-identifying columns of their own (they're audit/content
    records, not a sites table). Works because Pipeline slice 1 reuses the
    prospect's own id as site_id, so this is a real join, not a guess.
    Degrades to an empty map (business_name/city show as None, never
    fabricated) on any failure -- unconfigured client, network error, or
    otherwise -- rather than raising: the site_id/score/passed/run_at a
    caller actually needs are already known from audit_results by this
    point, so a prospects lookup failure shouldn't 500 the whole list over
    what's genuinely an enrichment, not the core data."""
    if not site_ids:
        return {}
    from ..core.supabase_client import get_supabase_admin

    try:
        db = get_supabase_admin()
        res = db.table("prospects").select("id,business_name,city").in_("id", site_ids).execute()
        data = getattr(res, "data", None) or []
        return {row["id"]: row for row in data}
    except Exception:
        logger.exception("Pipeline list: prospects lookup failed, showing site_id-only rows")
        return {}


@router.get("/pipeline", response_model=PipelineListResponse)
def list_pipeline(payload: dict = Depends(require_sales_agent)):
    """The real Pipeline list: every site actually persisted through
    /{site_id}/audit (Pipeline slice 1's "Save to Pipeline" button), not
    the ephemeral demo state Nova otherwise shows. Newest save first."""
    _, _, _, audit_repo = get_site_repos()
    latest = audit_repo.list_latest_per_site()
    if not latest:
        return PipelineListResponse(sites=[])

    prospects = _prospects_by_id([row.get("site_id", "") for row in latest])

    sites = []
    for row in latest:
        sid = row.get("site_id", "")
        prospect = prospects.get(sid)
        sites.append(PipelineSite(
            site_id=sid,
            business_name=prospect.get("business_name") if prospect else None,
            city=prospect.get("city") if prospect else None,
            score=row.get("score"),
            passed=row.get("passed"),
            run_at=row.get("run_at"),
        ))
    return PipelineListResponse(sites=sites)
