import os
from dataclasses import dataclass
from pathlib import Path
from .audit_engine import _parse_html, _El

@dataclass
class A11yResult:
    ok: bool
    score: int
    failures: list[str]

def audit_accessibility(site_dir: str | Path) -> A11yResult:
    site = Path(site_dir)
    failures = []
    total_checks = 0
    passed_checks = 0

    def check(condition: bool, fail_msg: str):
        nonlocal total_checks, passed_checks
        total_checks += 1
        if condition:
            passed_checks += 1
        else:
            failures.append(fail_msg)

    # find all html files
    html_files = list(site.rglob("*.html"))
    if not html_files:
        return A11yResult(ok=True, score=100, failures=[])

    for html_file in html_files:
        fname = html_file.name
        content = html_file.read_text(encoding="utf-8")
        
        try:
            root = _parse_html(content)
        except Exception:
            check(False, f"[{fname}] Invalid HTML")
            continue

        html_tags = root.find_all("html")
        if root.tag == "html":
            html_tag = root
        else:
            html_tag = html_tags[0] if html_tags else None

        if html_tag:
            check("lang" in html_tag.attrs, f"[{fname}] <html> missing lang attribute")
        else:
            check(False, f"[{fname}] Missing <html> tag")

        title_tags = root.find_all("title")
        if title_tags:
            check(bool(title_tags[0].text().strip()), f"[{fname}] <title> is empty")
        else:
            check(False, f"[{fname}] Missing <title> tag")

        h1_tags = root.find_all("h1")
        check(len(h1_tags) == 1, f"[{fname}] Expected exactly one <h1>, found {len(h1_tags)}")

        # No skipped heading levels
        headings = root.find_all("h1", "h2", "h3", "h4", "h5", "h6")
        prev_level = 0
        for h in headings:
            level = int(h.tag[1])
            if prev_level > 0 and level > prev_level + 1:
                check(False, f"[{fname}] Skipped heading level from h{prev_level} to h{level}")
            prev_level = level

        # every <img> has an alt attribute
        for img in root.find_all("img"):
            check("alt" in img.attrs, f"[{fname}] <img> missing alt attribute")

        # every <a> has discernible text
        for a in root.find_all("a"):
            has_text = bool(a.text().strip())
            has_aria_label = bool(a.attrs.get("aria-label", "").strip())
            # For this test, discernible text is defined as non-empty text content or an aria-label.
            # "bare-URL-only link text" also needs to be caught if it's strictly required, but the prompt says:
            # "no empty anchors, no bare-URL-only link text"
            # Actually, `site_engine.py` generates `<a href="tel:...">...</a>` or `<a href="...">google</a>`
            # Let's check for bare URLs as link text.
            text_content = a.text().strip()
            is_bare_url = text_content.startswith("http://") or text_content.startswith("https://")
            is_discernible = (has_text and not is_bare_url) or has_aria_label
            check(is_discernible, f"[{fname}] <a> lacks discernible text or uses bare URL")

        # every form control has a label or aria-label
        for ctrl in root.find_all("input", "select", "textarea"):
            has_aria = bool(ctrl.attrs.get("aria-label", "").strip())
            if not has_aria:
                if ctrl.tag == "input" and ctrl.attrs.get("type") in ("submit", "hidden", "button"):
                    continue
                # If not aria-label, check if it has an id and there's a label with `for` == `id`
                c_id = ctrl.attrs.get("id")
                has_label = False
                if c_id:
                    labels = root.find_all("label")
                    for lbl in labels:
                        if lbl.attrs.get("for") == c_id:
                            has_label = True
                            break
                # Alternatively, is it wrapped in a <label>?
                curr = ctrl.parent
                while curr:
                    if curr.tag == "label":
                        has_label = True
                        break
                    curr = curr.parent
                
                check(has_label, f"[{fname}] <{ctrl.tag}> missing associated label or aria-label")

        # skip link present
        # `<a href="#main" class="skip">`
        a_tags = root.find_all("a")
        has_skip = any(a.attrs.get("href") == "#main" and "skip" in a.attrs.get("class", "").split() for a in a_tags)
        check(has_skip, f"[{fname}] Missing skip-to-content link")

        # main and nav landmarks
        main_tags = root.find_all("main")
        check(len(main_tags) > 0, f"[{fname}] Missing <main> landmark")
        
        nav_tags = root.find_all("nav")
        check(len(nav_tags) > 0, f"[{fname}] Missing <nav> landmark")

    score = int((passed_checks / total_checks) * 100) if total_checks > 0 else 100
    return A11yResult(ok=len(failures) == 0, score=score, failures=failures)
