import tempfile
from pathlib import Path
from typing import Any
import json
from uuid import uuid4

from .site_engine import generate_site, _build_jsonld
from .audit_engine import run_audit

def generate_and_store(
    site_id: Any, facts: Any, *,
    content_repo: Any, schema_repo: Any, opt_repo: Any, audit_repo: Any,
    cwv: dict | None = None, trigger: str = "manual"
) -> dict:
    
    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)
        
        # 1. generate_site
        generate_site(facts, tmp_dir)
        
        # 2. save content pages
        for html_file in tmp_dir.glob("*.html"):
            filename = html_file.name
            slug = "/" if filename == "index.html" else f"/{filename[:-5]}"
            title = filename[:-5].replace("-", " ").title() if filename != "index.html" else facts.business_name
            
            if filename == "index.html":
                page_type = "home"
            elif filename == "about.html":
                page_type = "about"
            elif filename.startswith("service-"):
                page_type = "service"
            elif filename == "faq.html":
                page_type = "faq"
            else:
                page_type = "about" # default fallback
                
            content_repo.save_page(
                site_id, slug=slug, title=title, 
                page_type=page_type, body_json={"html": html_file.read_text(encoding="utf-8")},
                status="draft"
            )
            
        # 3. schema_repo.save 
        graph = _build_jsonld(facts, f"https://{facts.domain}")
        schema_repo.save(site_id, page_id="/", schema_type="LocalBusiness", json_ld=graph)
        
        # 4. opt_repo.save_site_dir
        opt_repo.save_site_dir(site_id, tmp_dir)
        
        # 5. audit_repo.save
        audit_res = run_audit(tmp_dir, cwv=cwv)
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
