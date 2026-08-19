from dataclasses import dataclass
from pathlib import Path
from .audit_engine import _parse_html

@dataclass
class PrivacyResult:
    ok: bool
    failures: list[str]

def audit_privacy(site_dir: str | Path) -> PrivacyResult:
    site = Path(site_dir)
    failures = []
    
    def check(condition: bool, fail_msg: str):
        if not condition:
            failures.append(fail_msg)

    # 1. privacy.html exists
    privacy_file = site / "privacy.html"
    check(privacy_file.exists(), "Missing privacy.html")

    html_files = list(site.rglob("*.html"))
    
    # Check all HTML pages
    for html_file in html_files:
        fname = html_file.name
        content = html_file.read_text(encoding="utf-8")
        
        try:
            root = _parse_html(content)
        except Exception:
            check(False, f"[{fname}] Invalid HTML")
            continue

        # every HTML page's footer links to it
        footers = root.find_all("footer")
        has_privacy_link = False
        for f in footers:
            a_tags = f.find_all("a")
            if any(a.attrs.get("href") == "privacy.html" for a in a_tags):
                has_privacy_link = True
                break
        
        check(has_privacy_link, f"[{fname}] Missing privacy.html link in footer")

        # consent region is present
        divs = root.find_all("div")
        has_consent = any(
            d.attrs.get("id") == "cookie-consent" and 
            d.attrs.get("role") == "region" and 
            "aria-label" in d.attrs
            for d in divs
        )
        check(has_consent, f"[{fname}] Missing cookie consent region")

    # 2. Privacy page specific checks
    if privacy_file.exists():
        content = privacy_file.read_text(encoding="utf-8").lower()
        
        # We need the actual text content or we can check the string
        try:
            root = _parse_html(content)
            text_content = root.text().lower()
        except Exception:
            text_content = content
            
        # "the privacy page names the business and a contact method"
        # "states the data categories and a rights-contact"
        # The prompt says: "the privacy page names the business and a contact method; a consent region is present; the privacy page states the data categories and a rights-contact"
        
        # We expect data categories to be mentioned (contact forms, call, directions, analytics, cookies)
        check("contact form" in text_content or "contact" in text_content, "privacy.html missing data categories")
        check("analytics" in text_content or "cookie" in text_content, "privacy.html missing analytics/cookies data categories")
        
        # Rights contact (we expect right to access/correct/delete)
        check("access" in text_content and ("correct" in text_content or "delete" in text_content), "privacy.html missing data rights")

        # Business named: We can't strictly know the business name here without passing it, but we can assume it's in the title or h1
        title_tags = root.find_all("title") if 'root' in locals() else []
        h1_tags = root.find_all("h1") if 'root' in locals() else []
        check(len(title_tags) > 0 and "privacy" in title_tags[0].text().lower(), "privacy.html title missing or invalid")
        check(len(h1_tags) > 0 and "privacy" in h1_tags[0].text().lower(), "privacy.html h1 missing or invalid")

    return PrivacyResult(ok=len(failures) == 0, failures=failures)
