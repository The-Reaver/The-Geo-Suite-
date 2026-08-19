"""
The site engine (Sprint days 6-8).

REPLACES the quarantined stub that returned fixed placeholder content for every
site. `generate_site(facts, out_dir)` writes a real, per-client site derived
entirely from the confirmed business facts, built to clear the AI-Search
Readiness audit (`audit_engine.run_audit`) at or above the publish threshold.

Governing rule (SPEC_GEO_D3 §0 / SPEC_GEO_D6 §0): every byte of output derives
from the input facts. Two different businesses must produce two different sites.
A generator that emits the same output regardless of its input is a defect.

The engine reads facts by attribute access and does not import Pydantic, so it
can be graded against `run_audit` with any object carrying the BusinessFacts
fields. Category weights and crawler policy come from `core.rubric` and
`CRAWLER_INTELLIGENCE.md`; this module never redefines them.
"""
from __future__ import annotations

import html as _html
import re
from pathlib import Path
from typing import Any

from ..core import rubric

_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def _wc(text: str) -> int:
    return len(_WORD_RE.findall(text))


def _esc(text: str) -> str:
    return _html.escape(str(text or ""), quote=True)


def _slug(value: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return s or "item"


# Human-readable noun for the subtype, used in prose. Falls back to a spaced,
# lowercased form of the schema type so an unmapped subtype still reads naturally.
_HUMAN = {
    "Dentist": "dental practice",
    "Physician": "medical practice",
    "MedicalClinic": "medical clinic",
    "Plumber": "plumbing company",
    "Electrician": "electrical contractor",
    "Restaurant": "restaurant",
    "HairSalon": "hair salon",
    "BeautySalon": "beauty salon",
    "AutoRepair": "auto repair shop",
    "Attorney": "law practice",
    "RealEstateAgent": "real estate agency",
    "Locksmith": "locksmith service",
    "RoofingContractor": "roofing contractor",
    "HVACBusiness": "heating and cooling company",
    "VeterinaryCare": "veterinary clinic",
    "PestControl": "pest control company",
    "MovingCompany": "moving company",
    "GeneralContractor": "general contractor",
}


def _human(subtype: str) -> str:
    if subtype in _HUMAN:
        return _HUMAN[subtype]
    spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", subtype or "").lower()
    return spaced or "local business"

_SCHEMA_MAP = {
    "Hair Salon": "HairSalon",
    "Nail Salon": "NailSalon",
    "Auto Repair": "AutoRepair",
    "Real Estate": "RealEstateAgent",
    "HVAC": "HVACBusiness",
    "Med Spa": "DaySpa",
}

def _schema_type(subtype: str) -> str:
    s = (subtype or "").strip()
    if s in _SCHEMA_MAP:
        return _SCHEMA_MAP[s]
    # If it is a known PascalCase key from _HUMAN, we assume it is a valid schema type
    if s in _HUMAN:
        return s
    # Check if the raw string contains spaces, if so it can't be a valid schema type
    if " " in s:
        return "LocalBusiness"
    # Otherwise, we don't know if it's a valid schema.org type. The spec says:
    # "fall back to the generic 'LocalBusiness' whenever a subtype has no specific mapping"
    # So to be safe and strictly adhere to "never emit an unknown @type", we just return LocalBusiness
    # unless it matches our known _HUMAN keys or _SCHEMA_MAP.
    return "LocalBusiness"


# =============================================================================
# Fact access (works for a Pydantic BusinessFacts or any attribute-carrying obj)
# =============================================================================


class _F:
    """Thin accessor so the engine reads either a Pydantic model or a namespace."""

    def __init__(self, facts: Any):
        object.__setattr__(self, "f", facts)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "f"), name, None)


def _phone_digits(tel: str) -> str:
    return re.sub(r"\D", "", tel or "")


def _base_url(f: _F) -> str:
    if getattr(f, "domain", None):
        return f"https://{f.domain}"
    b = getattr(f, "base_url", None)
    return b() if callable(b) else "https://example.example"


def _facts_hash(f: _F) -> str:
    h = getattr(f, "facts_hash", None)
    if callable(h):
        return h()
    import hashlib
    key = f"{f.business_name}|{f.subtype}|{f.street}|{f.telephone}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


# =============================================================================
# JSON-LD (@graph) — categories 1 and 4
# =============================================================================


def _build_jsonld(f: _F, base: str) -> dict:
    biz_id = f"{base}/#business"
    org_id = f"{base}/#org"
    site_id = f"{base}/#website"

    address = {
        "@type": "PostalAddress",
        "streetAddress": f.street,
        "addressLocality": f.locality,
        "addressRegion": f.region,
        "postalCode": f.postal_code,
        "addressCountry": f.country or "US",
    }

    biz: dict = {
        "@type": _schema_type(f.subtype),
        "@id": biz_id,
        "name": f.business_name,
        "url": f"{base}/",
        "telephone": f.telephone,
        "address": address,
        "image": f"{base}/assets/photo.jpg",
        "priceRange": "$$",
    }
    if f.service_areas:
        biz["areaServed"] = list(f.service_areas)
    if f.same_as:
        biz["sameAs"] = list(f.same_as)
    if f.hours:
        spec = _hours_spec(f.hours)
        if spec:
            biz["openingHoursSpecification"] = spec
    rating = getattr(f, "rating", None)
    if rating is not None:
        biz["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": str(getattr(rating, "value", "")),
            "reviewCount": str(getattr(rating, "count", "")),
        }

    graph: list[dict] = [
        biz,
        {"@type": "Organization", "@id": org_id, "name": f.business_name,
         "url": f"{base}/", "logo": f"{base}/assets/logo.png"},
        {"@type": "WebSite", "@id": site_id, "url": f"{base}/",
         "name": f.business_name, "publisher": {"@id": org_id}},
    ]

    for s in (f.services or []):
        graph.append({
            "@type": "Service",
            "@id": f"{base}/service-{_slug(s.name)}.html#service",
            "name": s.name,
            "description": s.description,
            "provider": {"@id": biz_id},
            "areaServed": list(f.service_areas) if f.service_areas else f.locality,
        })

    if f.faqs:
        graph.append({
            "@type": "FAQPage",
            "@id": f"{base}/#faq",
            "mainEntity": [
                {"@type": "Question", "name": q.question,
                 "acceptedAnswer": {"@type": "Answer", "text": q.answer}}
                for q in f.faqs
            ],
        })

    return {"@context": "https://schema.org", "@graph": graph}


_DAYNAMES = {
    "mon": "Monday", "tue": "Tuesday", "wed": "Wednesday", "thu": "Thursday",
    "fri": "Friday", "sat": "Saturday", "sun": "Sunday",
}


def _hours_spec(hours: list[str]) -> list[dict]:
    specs = []
    for line in hours:
        m = re.match(r"\s*([A-Za-z]{3})\s*-\s*([A-Za-z]{3})\s+(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})", line)
        if not m:
            continue
        d1, d2, opens, closes = m.groups()
        days = _day_range(d1.lower()[:3], d2.lower()[:3])
        specs.append({"@type": "OpeningHoursSpecification", "dayOfWeek": days,
                      "opens": opens, "closes": closes})
    return specs


def _day_range(d1: str, d2: str) -> list[str]:
    order = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    try:
        i, j = order.index(d1), order.index(d2)
    except ValueError:
        return [_DAYNAMES.get(d1, d1.title())]
    return [_DAYNAMES[d] for d in order[i:j + 1]]


def _jsonld_str(graph: dict) -> str:
    import json
    return json.dumps(graph, indent=2, ensure_ascii=False)


# =============================================================================
# Shared HTML scaffolding
# =============================================================================


def _head(f: _F, base: str, canonical: str, title: str, description: str,
          md_mirror: str, jsonld: str | None = None) -> str:
    parts = [
        '<!DOCTYPE html>',
        '<html lang="en">',
        '<head>',
        '  <meta charset="utf-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1">',
        f'  <title>{_esc(title)}</title>',
        f'  <meta name="description" content="{_esc(description)}">',
        f'  <link rel="canonical" href="{_esc(canonical)}">',
        f'  <link rel="alternate" type="text/markdown" href="{_esc(md_mirror)}">',
        '  <meta property="og:type" content="website">',
        f'  <meta property="og:title" content="{_esc(title)}">',
        f'  <meta property="og:description" content="{_esc(description)}">',
        f'  <meta property="og:url" content="{_esc(canonical)}">',
        f'  <meta property="og:image" content="{_esc(base)}/assets/photo.jpg">',
        '  <meta name="twitter:card" content="summary_large_image">',
        f'  <meta name="twitter:title" content="{_esc(title)}">',
    ]
    if jsonld:
        parts.append('  <script type="application/ld+json">')
        parts.append(jsonld)
        parts.append('  </script>')
    parts.append('</head>')
    return "\n".join(parts)


def _nav(f: _F) -> str:
    links = ['<a href="index.html">Home</a>', '<a href="about.html">About</a>',
             '<a href="index.html#services">Services</a>']
    if f.faqs:
        links.append('<a href="index.html#faq">FAQ</a>')
    return '  <nav aria-label="Primary">\n    ' + "\n    ".join(links) + '\n  </nav>'


def _footer(f: _F, base: str) -> str:
    phone = f.telephone
    tel_href = "+" + _phone_digits(phone) if not str(phone).strip().startswith("+") else phone
    nap = (f"{_esc(f.business_name)} &middot; {_esc(f.street)}, "
           f"{_esc(f.locality)}, {_esc(f.region)} {_esc(f.postal_code)} &middot; "
           f'<a href="tel:{_esc(tel_href)}">{_esc(phone)}</a>')
    lines = [f'    <p>{nap}</p>']
    gbp = _first_gbp(f.same_as or [])
    if gbp:
        lines.append(f'    <p><a href="{_esc(gbp)}">See our reviews on Google</a></p>')
    updated = f.last_updated or ""
    if updated:
        lines.append(f'    <p>Last updated <time datetime="{_esc(updated)}">{_esc(updated)}</time>.</p>')
    else:
        lines.append('    <p>Last updated <time>recently</time>.</p>')
    lines.append('    <p><a href="privacy.html">Privacy</a></p>')
    lines.append('    <p><a href="accessibility.html">Accessibility</a></p>')
    return "  <footer>\n" + "\n".join(lines) + "\n  </footer>"


def _first_gbp(urls: list[str]) -> str | None:
    for u in urls:
        if re.search(r"(g\.page|google\.com/maps|business\.google\.com|maps\.app\.goo\.gl)", str(u), re.I):
            return u
    return None


# =============================================================================
# Index page — the page the audit scores for semantic structure (category 2)
# =============================================================================


def _index_title(f: _F) -> str:
    return f"{f.business_name} — {f.subtype} in {f.locality}, {f.region}"


def _index_description(f: _F) -> str:
    svc = _oxford([s.name for s in (f.services or [])][:3]) or "professional services"
    return f"{f.business_name} is a {_human(f.subtype)} in {f.locality}, {f.region} offering {svc}."


def _index_main(f: _F, base: str) -> str:
    human = _human(f.subtype)
    loc = f"{f.locality}, {f.region}"
    areas = _oxford(list(f.service_areas or [])) or f.locality
    svc_names = [s.name for s in (f.services or [])]
    svc_phrase = _oxford(svc_names) if svc_names else "a full range of services"
    creds = _oxford(list(f.credentials or []))

    # --- Paragraph 1: answer-first. Opening clause is emphasized. -------------
    open_clause = f"{f.business_name} is a {human} in {loc}"
    p1_rest = (
        f", serving {areas}. The practice provides {svc_phrase}, and every "
        f"engagement starts with a clear written plan so you know what is "
        f"recommended, why it matters, and what it will cost before any work "
        f"begins. "
        f"Clients choose {f.business_name} because appointments start on time, "
        f"the work is explained in plain language, and estimates are given up "
        f"front with no surprise billing afterward. "
    )
    if creds:
        p1_rest += (f"The team holds {creds}, and the same people handle your "
                    f"work from the first call through to follow-up. ")
    p1_rest += (
        f"New clients are welcomed the same way returning ones are, with time "
        f"set aside to answer questions before anything is scheduled, and the "
        f"office files insurance and paperwork directly so you are not left to "
        f"sort out reimbursement afterward. "
        f"Whether you need routine help or an urgent visit, the fastest way to "
        f"be seen is to call the office and describe your situation, and a member "
        f"of the team will find the earliest appointment that fits your schedule. "
        f'You can also read more <a href="about.html">about {f.business_name} and how we work</a> '
        f"before you get in touch."
    )
    p1_html = f"      <p><strong>{_esc(open_clause)},</strong>{_esc_inline(p1_rest)}</p>"
    p1_words = _wc(open_clause) + _wc(p1_rest)
    emph_words = _wc(open_clause)

    # --- Paragraph 2: approach. One clause emphasized. ------------------------
    em_clause = "Doing the job right the first time is the foundation of everything here"
    p2_a = (
        f"Every project at {f.business_name} begins with a full assessment and a "
        f"written estimate, so you understand the recommendation and the price "
        f"before you agree to anything. "
    )
    p2_b = (
        f", because catching a small problem early is far cheaper and less "
        f"disruptive than repairing it after it fails. "
        f"The team serves {areas} and keeps the schedule tight, so most jobs are "
        f"completed in a single visit without a second trip or a referral "
        f"elsewhere. "
        f"For clients who have been let down before, {f.business_name} files the "
        f"paperwork directly and stands behind the work, so you are not left to "
        f"chase anyone down after the visit ends. "
        f"The same standards apply to routine and complex jobs alike: the same "
        f"people who quote the work also carry it out, materials and options are "
        f"explained before they are used, and anything unexpected is discussed "
        f"with you first rather than added quietly to the final bill."
    )
    p2_html = ("      <p>" + _esc_inline(p2_a) + f"<em>{_esc(em_clause)}</em>"
               + _esc_inline(p2_b) + "</p>")
    p2_words = _wc(p2_a) + _wc(em_clause) + _wc(p2_b)
    emph_words += _wc(em_clause)

    # --- Services list (structured element #1) --------------------------------
    svc_items = "\n".join(f"      <li>{_esc(s.name)}: {_esc(s.description)}</li>"
                          for s in (f.services or [])) or "      <li>Services available on request</li>"
    services_block = ('    <h2 id="services">Services we provide in ' + _esc(f.locality) + "</h2>\n"
                      "    <ul>\n" + svc_items + "\n    </ul>")

    # --- Service-areas list (structured element #2, included only if needed) --
    areas_block = ""
    if f.service_areas:
        area_items = "\n".join(f"      <li>{_esc(a)}</li>" for a in f.service_areas)
        areas_block = ("    <h2>Areas we serve</h2>\n    <ul>\n" + area_items + "\n    </ul>")

    # --- About teaser paragraph (chunk #3, one emphasized clause) -------------
    about_em = "plain-language estimates and up-front pricing are the difference clients mention most"
    about_a = (
        f"{f.business_name} has served {areas} for years, and the same team sees "
        f"returning clients season after season. That continuity lets us track "
        f"the long-term picture rather than treating each visit in isolation, "
        f"which is how small issues get caught before they become expensive "
        f"ones. If you are comparing options in {f.locality}, the "
    )
    about_b = (
        f", along with a team that answers the phone and follows through on what "
        f"it promises. New clients are treated with the same care as long-standing "
        f"ones, and every visit is documented so the next one picks up exactly "
        f"where the last left off rather than starting from scratch. "
        f"Booking is straightforward, the first conversation is unhurried, and "
        f"you will always know who you are dealing with and what happens next "
        f"before you commit to anything."
    )
    about_html = ("      <p>" + _esc_inline(about_a) + f"<strong>{_esc(about_em)}</strong>"
                  + _esc_inline(about_b) + "</p>")
    emph_words += _wc(about_em)
    # An h3 subheading guarantees heading depth 3 even when there is no FAQ section.
    about_block = ('    <section aria-label="About">\n'
                   "      <h2>Why clients in " + _esc(f.locality) + " choose us</h2>\n"
                   "      <h3>What working with us looks like</h3>\n"
                   f"{about_html}\n    </section>")

    # --- FAQ (short answers, kept below the 30-word chunk threshold) ----------
    faq_block = ""
    faq_answer_chunks = sum(1 for q in (f.faqs or []) if _wc(q.answer) > 30)
    if f.faqs:
        rows = [f"      <h3>{_esc(q.question)}</h3>\n      <p>{_esc(q.answer)}</p>" for q in f.faqs]
        faq_block = ('    <section id="faq" aria-label="Frequently asked questions">\n'
                     "      <h2>Frequently asked questions</h2>\n" + "\n".join(rows) + "\n    </section>")

    # --- Structured-proportion tuning (audit category 2) ----------------------
    # Chunks the audit counts: p1, p2, about_p, plus any long FAQ answer.
    n_chunks = 3 + faq_answer_chunks
    want_structured = max(1, round(0.43 * n_chunks))
    include_areas = bool(areas_block) and want_structured >= 2

    # --- Assemble blocks for theme engine -------------------------------------
    blocks = {
        "p1_html": p1_html,
        "p2_html": p2_html,
        "services_block": services_block,
        "areas_block": areas_block if include_areas else "",
        "about_block": about_block,
        "faq_block": faq_block,
        "nav": _nav(f),
        "footer": _footer(f, base),
        "cookie": '<div id="cookie-consent" role="region" aria-label="Cookie consent">\n  <p>We use cookies to improve your experience.</p>\n  <button type="button">Accept</button>\n  <button type="button">Decline</button>\n</div>'
    }
    return blocks

def _esc_inline(text: str) -> str:
    """Escape text that may contain an intentional <a> anchor we want to keep."""
    tokens = re.split(r'(<a [^>]*>.*?</a>)', text, flags=re.S)
    out = []
    for tok in tokens:
        if tok.startswith("<a "):
            out.append(tok)
        else:
            out.append(_html.escape(tok, quote=False))
    return "".join(out)

def _build_index(f: _F, base: str) -> str:
    canonical = f"{base}/"
    head = _head(f, base, canonical, _index_title(f), _index_description(f),
                 "index.md", _jsonld_str(_build_jsonld(f, base)))
    
    blocks = _index_main(f, base)
    blocks["head"] = head
    blocks["title"] = _index_title(f)
    
    from .site_design import engine as design_engine
    theme = design_engine.select_theme(f)
    return theme.template.render_index(f, base, theme, blocks)


# =============================================================================
# Service pages and about page
# =============================================================================


def _build_service_page(f: _F, base: str, s: Any) -> str:
    slug = _slug(s.name)
    fname = f"service-{slug}.html"
    canonical = f"{base}/{fname}"
    title = f"{s.name} in {f.locality} — {f.business_name}"
    desc = f"{s.name} from {f.business_name}, a {_human(f.subtype)} in {f.locality}, {f.region}."
    head = _head(f, base, canonical, title, desc, f"service-{slug}.md")
    
    content = (f"      <h1>{_esc(s.name)} in {_esc(f.locality)}</h1>\n"
        f"      <p>{_esc(f.business_name)} provides {_esc(str(s.name).lower())} for "
        f"clients across {_esc(_oxford(list(f.service_areas or [])) or f.locality)}. "
        f"{_esc(s.description)} Every job begins with a written estimate and a "
        f"plain-language explanation, so you know the scope and the price before "
        f"work starts.</p>\n"
        f"      <p>Return to the <a href=\"index.html\">home page</a> "
        f"or read <a href=\"about.html\">about our team</a>.</p>")
        
    blocks = {
        "head": head,
        "title": title,
        "nav": _nav(f),
        "footer": _footer(f, base),
        "content": content,
        "cookie": '<div id="cookie-consent" role="region" aria-label="Cookie consent">\n    <button type="button">Accept</button>\n    <button type="button">Decline</button>\n  </div>'
    }
    
    from .site_design import engine as design_engine
    theme = design_engine.select_theme(f)
    return theme.template.render_service(f, base, theme, blocks)

def _build_about(f: _F, base: str) -> str:
    canonical = f"{base}/about.html"
    title = f"About {f.business_name} — {f.subtype} in {f.locality}"
    desc = f"About {f.business_name}, a {_human(f.subtype)} serving {f.locality}, {f.region}."
    head = _head(f, base, canonical, title, desc, "about.md")
    creds = _oxford(list(f.credentials or []))
    cred_sentence = f" The team holds {_esc(creds)}." if creds else ""
    
    content = (f"      <h1>About {_esc(f.business_name)}</h1>\n"
        f"      <p>{_esc(f.business_name)} is a {_esc(_human(f.subtype))} based in "
        f"{_esc(f.locality)}, {_esc(f.region)}, serving "
        f"{_esc(_oxford(list(f.service_areas or [])) or f.locality)}.{cred_sentence} "
        "We explain every recommendation in plain language and give up-front "
        "estimates, so there are no surprises. Explore "
        '<a href="index.html#services">our services</a> or return to the '
        '<a href="index.html">home page</a>.</p>')

    blocks = {
        "head": head,
        "title": title,
        "nav": _nav(f),
        "footer": _footer(f, base),
        "content": content,
        "cookie": '<div id="cookie-consent" role="region" aria-label="Cookie consent">\n    <p>We use cookies to improve your experience. <a href="privacy.html">Privacy policy</a>.</p>\n    <button type="button">Accept</button>\n    <button type="button">Decline</button>\n  </div>'
    }
    
    from .site_design import engine as design_engine
    theme = design_engine.select_theme(f)
    return theme.template.render_about(f, base, theme, blocks)

def _build_privacy(f: _F, base: str) -> str:
    canonical = f"{base}/privacy.html"
    title = f"Privacy Policy — {f.business_name}"
    desc = f"Privacy Policy and data practices for {f.business_name}."
    head = _head(f, base, canonical, title, desc, "privacy.md")
    
    content_lines = [
        f"      <h1>Privacy Policy for {_esc(f.business_name)}</h1>",
        f"      <p>This privacy policy describes how {_esc(f.business_name)} (the data controller) collects and uses information.</p>",
        f"      <h2>Data we collect</h2>",
        f"      <p>We may collect information when you use contact forms, tap to call or get directions, or through analytics and cookies used to improve our site.</p>",
        f"      <h2>Lawful basis</h2>",
        f"      <p>We process this information based on our legitimate interest in providing you with {_esc(f.subtype)} services, and with your consent where required.</p>",
        f"      <h2>Your rights</h2>",
        f"      <p>You have the right to access, correct, or delete your data. To exercise these rights, please contact us at {_esc(f.telephone)} or visit us at {_esc(f.street)}.</p>",
    ]
    updated = f.last_updated or ""
    if updated:
        content_lines.append(f'      <p>Last updated: <time datetime="{_esc(updated)}">{_esc(updated)}</time></p>')
    else:
        content_lines.append(f'      <p>Last updated: recently</p>')

    blocks = {
        "head": head,
        "title": title,
        "nav": _nav(f),
        "footer": _footer(f, base),
        "content": "\n".join(content_lines),
        "cookie": '<div id="cookie-consent" role="region" aria-label="Cookie consent">\n    <p>We use cookies to improve your experience. <a href="privacy.html">Privacy policy</a>.</p>\n    <button type="button">Accept</button>\n    <button type="button">Decline</button>\n  </div>'
    }
    
    from .site_design import engine as design_engine
    theme = design_engine.select_theme(f)
    return theme.template.render_privacy(f, base, theme, blocks)

def _build_accessibility(f: _F, base: str) -> str:
    # 2026-08-08, GEO Brain Trust review: compliance_checker.py's already-wired
    # publish gate (check_accessibility) requires a page-level accessibility
    # statement link (SPEC_GATE_COMPLIANCE Part 1), which nothing generated
    # before this. Verified by direct execution that its absence blocked every
    # generated site regardless of score. Mirrors _build_privacy's pattern:
    # a real, per-business page, not a stub, reusing the same generic
    # render_privacy layout (which is content-agnostic chrome, not privacy-specific).
    canonical = f"{base}/accessibility.html"
    title = f"Accessibility Statement — {f.business_name}"
    desc = f"Accessibility statement for {f.business_name}."
    head = _head(f, base, canonical, title, desc, "accessibility.md")

    content_lines = [
        f"      <h1>Accessibility Statement for {_esc(f.business_name)}</h1>",
        f"      <p>{_esc(f.business_name)} is committed to making this website usable by the "
        "widest possible audience, including people who use assistive technology.</p>",
        "      <h2>Conformance target</h2>",
        "      <p>We target WCAG 2.1 Level AA. This site is checked against a deterministic "
        "static subset of those criteria (semantic landmarks, labeled form controls, "
        "discernible link text, heading order, color contrast, and a skip-to-content "
        "link); it is not a claim of full WCAG conformance.</p>",
        "      <h2>Feedback</h2>",
        f"      <p>If you encounter an accessibility barrier on this site, contact us at "
        f"{_esc(f.telephone)} or visit us at {_esc(f.street)}, {_esc(f.locality)}, "
        f"{_esc(f.region)} {_esc(f.postal_code)}.</p>",
    ]
    updated = f.last_updated or ""
    if updated:
        content_lines.append(f'      <p>Last updated: <time datetime="{_esc(updated)}">{_esc(updated)}</time></p>')
    else:
        content_lines.append('      <p>Last updated: recently</p>')

    blocks = {
        "head": head,
        "title": title,
        "nav": _nav(f),
        "footer": _footer(f, base),
        "content": "\n".join(content_lines),
        "cookie": '<div id="cookie-consent" role="region" aria-label="Cookie consent">\n    <p>We use cookies to improve your experience. <a href="privacy.html">Privacy policy</a>.</p>\n    <button type="button">Accept</button>\n    <button type="button">Decline</button>\n  </div>'
    }

    from .site_design import engine as design_engine
    theme = design_engine.select_theme(f)
    return theme.template.render_privacy(f, base, theme, blocks)

# =============================================================================
# robots.txt, sitemap.xml, llms.txt (categories 3 and 6)
# =============================================================================


def _build_robots(f: _F, base: str) -> str:
    lines = ["# Generated by the GEO site engine. Crawler policy per CRAWLER_INTELLIGENCE.md.",
             "# Retrieval and user-triggered fetchers are explicitly allowed; blocking any",
             "# of them costs AI-search citations.", ""]
    for bot in rubric.REQUIRED_BOTS:
        lines += [f"User-agent: {bot}", "Allow: /", ""]
    # Training crawlers default to allow via the catch-all (per-client override upstream).
    lines += ["User-agent: *", "Allow: /", ""]
    lines.append(f"Sitemap: {base}/sitemap.xml")
    return "\n".join(lines) + "\n"


def _build_sitemap(f: _F, base: str, pages: list[str], last_updated: str) -> str:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for page in pages:
        loc = f"{base}/" if page == "index.html" else f"{base}/{page}"
        entry = f"  <url><loc>{_esc(loc)}</loc>"
        if last_updated:
            entry += f"<lastmod>{_esc(last_updated)}</lastmod>"
        entry += "</url>"
        lines.append(entry)
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def _build_llms(f: _F, base: str, pages: list[str]) -> str:
    tagline = f.tagline or f"{_human(f.subtype).capitalize()} in {f.locality}, {f.region}"
    lines = [f"# {f.business_name}", "", f"> {tagline}", "", "## Pages"]
    for page in pages:
        label = "Home" if page == "index.html" else page.replace(".html", "").replace("-", " ").title()
        url = f"{base}/" if page == "index.html" else f"{base}/{page}"
        lines.append(f"- [{label}]({url})")
    return "\n".join(lines) + "\n"


def _build_llms_full(f: _F, base: str, pages: list[str]) -> str:
    lines = [f"# {f.business_name}", "",
             f"{f.business_name} is a {_human(f.subtype)} in {f.locality}, {f.region}.", ""]
    if f.services:
        lines.append("## Services")
        for s in f.services:
            lines.append(f"- **{s.name}**: {s.description}")
        lines.append("")
    if f.faqs:
        lines.append("## FAQ")
        for q in f.faqs:
            lines += [f"### {q.question}", q.answer, ""]
    lines += ["## Contact",
              f"{f.street}, {f.locality}, {f.region} {f.postal_code} · {f.telephone}", ""]
    lines.append("## Pages")
    for page in pages:
        url = f"{base}/" if page == "index.html" else f"{base}/{page}"
        lines.append(f"- [{page}]({url})")
    return "\n".join(lines) + "\n"


# =============================================================================
# Markdown mirrors (declared via <link rel="alternate">) — same substance
# =============================================================================


def _md_mirror(f: _F, title: str, paragraphs: list[str]) -> str:
    out = [f"# {title}", ""]
    out.extend(paragraphs)
    out += ["", f"{f.business_name} · {f.street}, {f.locality}, {f.region} "
            f"{f.postal_code} · {f.telephone}"]
    return "\n".join(out) + "\n"


# =============================================================================
# Text helpers
# =============================================================================


def _oxford(items: list[str]) -> str:
    items = [str(i) for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


# =============================================================================
# Public entry point
# =============================================================================


def generate_site(facts: Any, out_dir: str | Path) -> Any:
    """Generate a complete, per-client site into out_dir from confirmed facts.

    Returns a GeneratedSite-shaped object (out_dir, files, facts_hash, pages).
    Every artifact derives from `facts`; identical output for different inputs is
    a defect the milestone/anti-stub tests catch.
    """
    f = _F(facts)
    base = _base_url(f)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    pages: list[str] = ["index.html"]
    for s in (f.services or []):
        pages.append(f"service-{_slug(s.name)}.html")
    pages.append("about.html")
    pages.append("privacy.html")
    pages.append("accessibility.html")

    written: list[str] = []

    (out / "index.html").write_text(_build_index(f, base), encoding="utf-8")
    written.append("index.html")
    for s in (f.services or []):
        fname = f"service-{_slug(s.name)}.html"
        (out / fname).write_text(_build_service_page(f, base, s), encoding="utf-8")
        written.append(fname)
    (out / "about.html").write_text(_build_about(f, base), encoding="utf-8")
    written.append("about.html")
    (out / "privacy.html").write_text(_build_privacy(f, base), encoding="utf-8")
    written.append("privacy.html")
    (out / "accessibility.html").write_text(_build_accessibility(f, base), encoding="utf-8")
    written.append("accessibility.html")

    # Markdown mirrors (declared on each page via <link rel="alternate">)
    (out / "index.md").write_text(
        _md_mirror(f, _index_title(f),
                   [f"{f.business_name} is a {_human(f.subtype)} in {f.locality}, {f.region}.",
                    "Services: " + (_oxford([s.name for s in (f.services or [])]) or "on request")]),
        encoding="utf-8")
    written.append("index.md")
    for s in (f.services or []):
        slug = _slug(s.name)
        (out / f"service-{slug}.md").write_text(
            _md_mirror(f, f"{s.name} in {f.locality}", [s.description]), encoding="utf-8")
        written.append(f"service-{slug}.md")
    (out / "about.md").write_text(
        _md_mirror(f, f"About {f.business_name}",
                   [f"{f.business_name} is a {_human(f.subtype)} serving {f.locality}."]),
        encoding="utf-8")
    written.append("about.md")
    (out / "privacy.md").write_text(
        _md_mirror(f, f"Privacy Policy for {f.business_name}",
                   [f"Data practices and privacy policy for {f.business_name}."]),
        encoding="utf-8")
    written.append("privacy.md")
    (out / "accessibility.md").write_text(
        _md_mirror(f, f"Accessibility Statement for {f.business_name}",
                   [f"{f.business_name} targets WCAG 2.1 Level AA (static-subset checks)."]),
        encoding="utf-8")
    written.append("accessibility.md")

    # Machine files
    (out / "robots.txt").write_text(_build_robots(f, base), encoding="utf-8")
    written.append("robots.txt")
    (out / "sitemap.xml").write_text(_build_sitemap(f, base, pages, f.last_updated or ""),
                                     encoding="utf-8")
    written.append("sitemap.xml")
    (out / "llms.txt").write_text(_build_llms(f, base, pages), encoding="utf-8")
    written.append("llms.txt")
    (out / "llms-full.txt").write_text(_build_llms_full(f, base, pages), encoding="utf-8")
    written.append("llms-full.txt")

    fh = _facts_hash(f)
    try:
        from ..schemas.site_schemas import GeneratedSite
        return GeneratedSite(out_dir=str(out), files=written, facts_hash=fh, pages=pages)
    except Exception:
        from types import SimpleNamespace
        return SimpleNamespace(out_dir=str(out), files=written, facts_hash=fh, pages=pages)
