"""
Site self-check (pre-publish invariant validator).
"""
from dataclasses import dataclass
from pathlib import Path

from .audit_engine import _parse_html, _is_internal, _resolves, _canonical_self, _sitemap_score
from .crawler_policy import validate_robots

@dataclass
class SiteCheckResult:
    ok: bool
    broken_links: list[str]
    pages_missing_canonical: list[str]
    pages_missing_mirror: list[str]
    robots_ok: bool
    sitemap_valid: bool
    findings: list[str]

def check_site(site_dir: str | Path) -> SiteCheckResult:
    site = Path(site_dir)
    if not site.is_dir():
        raise NotADirectoryError(f"site_dir is not a directory: {site}")
        
    broken_links = []
    pages_missing_canonical = []
    pages_missing_mirror = []
    findings = []
    
    # 1. HTML Pages check
    html_files = list(site.glob("*.html"))
    for hf in html_files:
        filename = hf.name
        dom = _parse_html(hf.read_text(encoding="utf-8"))
        
        # Check canonical
        canon = None
        for lnk in dom.find_all("link"):
            if lnk.attrs.get("rel", "").lower() == "canonical":
                canon = lnk.attrs.get("href", "")
                break
                
        if not canon or not _canonical_self(canon, filename):
            pages_missing_canonical.append(filename)
            
        # Check broken links
        links = [a.attrs.get("href", "") for a in dom.find_all("a")]
        for href in links:
            if _is_internal(href) and not _resolves(site, href):
                broken_links.append(f"{filename} -> {href}")
                
        # Check mirror
        # In this platform, every HTML page has a .md mirror for LLMs
        if not hf.with_suffix(".md").exists():
            pages_missing_mirror.append(filename)
                    
    # 2. Robots policy check
    robots_file = site / "robots.txt"
    robots_ok = False
    if robots_file.exists():
        r_result = validate_robots(robots_file.read_text(encoding="utf-8"))
        robots_ok = r_result.ok
        if not robots_ok:
            findings.extend(r_result.findings)
    else:
        findings.append("robots.txt missing")
        
    # 3. Sitemap valid
    sitemap_score = _sitemap_score(site)
    sitemap_valid = (sitemap_score == 1.0)
    if not sitemap_valid:
        findings.append("sitemap.xml is missing or invalid")
        
    ok = (
        len(broken_links) == 0 and 
        len(pages_missing_canonical) == 0 and 
        len(pages_missing_mirror) == 0 and 
        robots_ok and 
        sitemap_valid
    )
    
    return SiteCheckResult(
        ok=ok,
        broken_links=broken_links,
        pages_missing_canonical=pages_missing_canonical,
        pages_missing_mirror=pages_missing_mirror,
        robots_ok=robots_ok,
        sitemap_valid=sitemap_valid,
        findings=findings
    )
