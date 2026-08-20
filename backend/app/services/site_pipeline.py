import tempfile
from pathlib import Path
from typing import Any
import json
from uuid import uuid4

from .site_engine import generate_site, _build_jsonld
from .audit_engine import run_audit

# Real page types generate_site() actually writes today (see site_engine.py's
# "Public entry point" section). Kept as a real lookup, not a chain of elifs
# with a "faq.html" branch that no code has ever produced (there is no FAQ
# page -- FAQs render as a section of index.html) -- that branch was dead,
# and everything that *did* exist past "about.html" (privacy.html,
# accessibility.html) silently fell through the old "default fallback" and
# got mislabeled page_type "about" in the content repo.
_STATIC_PAGE_TYPES = {
    "index.html": "home",
    "about.html": "about",
    "privacy.html": "privacy",
    "accessibility.html": "accessibility",
}


def _page_type_for(filename: str) -> str:
    if filename in _STATIC_PAGE_TYPES:
        return _STATIC_PAGE_TYPES[filename]
    if filename.startswith("service-"):
        return "service"
    return "other"


def _persist(
    site_id: Any, facts: Any, tmp_dir: Path, audit_res: Any, *,
    content_repo: Any, schema_repo: Any, opt_repo: Any, audit_repo: Any,
    trigger: str,
) -> dict:
    # 1. save content pages
    for html_file in tmp_dir.glob("*.html"):
        filename = html_file.name
        slug = "/" if filename == "index.html" else f"/{filename[:-5]}"
        title = filename[:-5].replace("-", " ").title() if filename != "index.html" else facts.business_name

        content_repo.save_page(
            site_id, slug=slug, title=title,
            page_type=_page_type_for(filename), body_json={"html": html_file.read_text(encoding="utf-8")},
            status="draft"
        )

    # 2. schema_repo.save
    graph = _build_jsonld(facts, f"https://{facts.domain}")
    schema_repo.save(site_id, page_id="/", schema_type="LocalBusiness", json_ld=graph)

    # 3. opt_repo.save_site_dir
    opt_repo.save_site_dir(site_id, tmp_dir)

    # 4. audit_repo.save
    audit_repo.save(site_id, audit_res, trigger=trigger)

    # Build summary read back from repos
    pages = content_repo.list_pages(site_id)

    opt_count = 0
    for ftype in ["robots", "sitemap", "llms", "llms_full"]:
        if opt_repo.latest(site_id, ftype):
            opt_count += 1

    schema_rec = schema_repo.get(site_id, "/")
    schema_status = schema_rec["validation_status"] if schema_rec else "error"

    audit_rec = audit_repo.latest(site_id)

    return {
        "pages": len(pages),
        "opt_files": opt_count,
        "schema_status": schema_status,
        "score": audit_rec["score"] if audit_rec else 0,
        "passed": audit_rec["passed"] if audit_rec else False
    }


def generate_and_store(
    site_id: Any, facts: Any, *,
    content_repo: Any, schema_repo: Any, opt_repo: Any, audit_repo: Any,
    cwv: dict | None = None, trigger: str = "manual",
    site_dir: Path | None = None, audit_result: Any = None,
) -> dict:
    """Persist a generated site into the given repos.

    By default this generates the site and runs the audit itself. Callers
    that already generated the site and ran the audit to gate on it before
    deciding whether to persist at all (site_dir + audit_result) -- e.g.
    routers/sites.py's /{site_id}/audit route, which must check pass/fail
    *before* persisting -- can pass that work through instead of silently
    paying for a second full generate_site()+run_audit() on every single
    publish, which is what happened here before: this function always
    regenerated and re-audited from scratch even when the caller had just
    done exactly that a few lines earlier.
    """
    if site_dir is not None:
        if audit_result is None:
            audit_result = run_audit(site_dir, cwv=cwv)
        return _persist(
            site_id, facts, site_dir, audit_result,
            content_repo=content_repo, schema_repo=schema_repo,
            opt_repo=opt_repo, audit_repo=audit_repo, trigger=trigger,
        )

    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)
        generate_site(facts, tmp_dir)
        audit_res = run_audit(tmp_dir, cwv=cwv)
        return _persist(
            site_id, facts, tmp_dir, audit_res,
            content_repo=content_repo, schema_repo=schema_repo,
            opt_repo=opt_repo, audit_repo=audit_repo, trigger=trigger,
        )
