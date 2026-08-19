import logging
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Path
from uuid import UUID
from pydantic import BaseModel
from typing import Dict, Any, Optional
from ..core.permissions import require_owner
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
    payload: dict = Depends(require_owner),
):
    """Generate the site from confirmed facts, run the AI-Search Readiness audit,
    and refuse to publish below the threshold.

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

    with tempfile.TemporaryDirectory(prefix="geo_audit_") as tmp:
        out = Path(tmp)
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
