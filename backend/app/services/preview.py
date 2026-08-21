import os
import tempfile
from dataclasses import dataclass, field
from typing import Any
from pathlib import Path
from . import site_engine, audit_engine
from .audit_engine import _parse_html
from ..core import rubric

@dataclass
class PreviewResult:
    is_preview: bool
    publishable: bool
    score: int
    passed_threshold: bool
    fix_list: list[str]
    out_dir: str

def generate_preview(prospect_facts: Any, *, cwv: dict = None, out_dir: str = None) -> PreviewResult:
    fix_list = []
    
    # We need to wrap or modify prospect_facts to fill in placeholders
    # Because we don't import Pydantic here per constraints (we could, but wrapping is safer)
    class FactWrapper:
        # 2026-08-21, Opus 5 review of the Site Generator location/hours
        # slice: site_engine.py's new "Get directions" link is a much more
        # load-bearing claim than plain placeholder text ("this is a real,
        # visitable place") -- so it needs to know which NAP fields below
        # are real vs. synthesized, not just receive whatever string comes
        # back from __getattr__. placeholder_fields is a real instance
        # attribute (not routed through __getattr__ itself), so
        # site_engine.py can check it directly via getattr(f,
        # "placeholder_fields", None) without recursing.
        def __init__(self, obj):
            self._obj = obj
            self.placeholder_fields = set()

        def __getattr__(self, name):
            val = getattr(self._obj, name, None)
            if not val:
                # Provide defaults for missing fields
                if name == "business_name":
                    fix_list.append("Confirm business name")
                    self.placeholder_fields.add(name)
                    return "Demo Business"
                if name == "subtype":
                    fix_list.append("Confirm business subtype")
                    self.placeholder_fields.add(name)
                    return "Local Business"
                if name == "locality":
                    fix_list.append("Confirm locality")
                    self.placeholder_fields.add(name)
                    return "Sample City"
                if name == "region":
                    fix_list.append("Confirm region")
                    self.placeholder_fields.add(name)
                    return "ST"
                if name == "street":
                    fix_list.append("Confirm street address")
                    self.placeholder_fields.add(name)
                    return "123 Sample Ave"
                if name == "telephone":
                    fix_list.append("Confirm telephone")
                    self.placeholder_fields.add(name)
                    return "555-0000"
                if name == "postal_code":
                    fix_list.append("Confirm postal code")
                    self.placeholder_fields.add(name)
                    return "00000"
                if name == "domain":
                    return "demo.example"
                if name == "services" or name == "service_areas" or name == "faqs" or name == "same_as" or name == "hours" or name == "credentials":
                    return []
            return val

    facts_wrapper = FactWrapper(prospect_facts)
    
    if not out_dir:
        out_dir = tempfile.mkdtemp(prefix="preview_")
        
    out_path = Path(out_dir)
    
    # Generate the site
    site_engine.generate_site(facts_wrapper, out_path)
    
    # Watermark every HTML page
    for html_file in out_path.rglob("*.html"):
        content = html_file.read_text(encoding="utf-8")
        
        # Add noindex meta tag to <head>
        if "<head>" in content:
            content = content.replace("<head>", '<head>\n  <meta name="robots" content="noindex">', 1)
            
        # Add demo banner to <body>
        banner = '<div class="demo-banner" style="background: red; color: white; text-align: center; padding: 10px;">DEMO PREVIEW - NOT FOR PUBLICATION</div>'
        if "<body>" in content:
            content = content.replace("<body>", f"<body>\n  {banner}", 1)
            
        html_file.write_text(content, encoding="utf-8")
        
    # Run audit
    audit_res = audit_engine.run_audit(str(out_path), cwv=cwv)
    
    # Audit's gaps are in audit_res.fix_list
    if hasattr(audit_res, "fix_list"):
        fix_list.extend(audit_res.fix_list)
        
    return PreviewResult(
        is_preview=True,
        publishable=False,
        score=audit_res.normalized_score,
        # 2026-08-16: was hardcoded 90, independently of rubric.PUBLISH_THRESHOLD
        # (raised to 93 on 2026-08-08) — same staleness class caught across
        # render_html.py and the Nova UI this same session.
        passed_threshold=audit_res.normalized_score >= rubric.PUBLISH_THRESHOLD,
        fix_list=fix_list,
        out_dir=str(out_path)
    )
