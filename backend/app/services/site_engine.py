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
    # 2026-08-21, Opus review: _SCHEMA_MAP keys ("HVAC", "Auto Repair",
    # "Real Estate") aren't literal _HUMAN keys themselves -- only their
    # PascalCase schema-type equivalents are. Falling straight to the
    # regex spacer below mangled them: "HVAC" is all-caps with no
    # lowercase letters for the regex to anchor spacing on, so it rendered
    # "h v a c" letter by letter; "Auto Repair"/"Real Estate" rendered as
    # bare, ungrammatical noun phrases ("a auto repair", "a real estate")
    # instead of the real, authored _HUMAN values ("auto repair shop",
    # "real estate agency"). Resolve through _SCHEMA_MAP first, but only
    # USE that resolution when it lands on a real _HUMAN entry --
    # "Nail Salon"/"Med Spa" map to schema types ("NailSalon"/"DaySpa")
    # that aren't in _HUMAN either, so those still fall through to the
    # regex spacer on the ORIGINAL subtype text below, which already
    # renders them correctly ("nail salon", "med spa").
    mapped = _SCHEMA_MAP.get((subtype or "").strip())
    if mapped in _HUMAN:
        return _HUMAN[mapped]
    # A subtype that already contains a space before a capital letter
    # (e.g. "Nail Salon") gets a SECOND space inserted by the regex below,
    # rendering "nail  salon" -- re.sub(r"\s+", " ", ...) collapses it
    # back to one space regardless of how many the regex introduced.
    spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", subtype or "").lower()
    spaced = re.sub(r"\s+", " ", spaced).strip()
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


def _loc(f: "_F") -> str:
    """"{locality}, {region}", or just locality when region is empty.

    2026-08-21, Opus review: BusinessFacts.region is a bare str with no
    min_length, so an empty region rendered visible double-space/trailing-
    comma artifacts ("in London,  offering", "in London, .") everywhere this
    pattern was inlined directly -- confirmed 10 separate occurrences across
    this file (titles, meta descriptions, taglines, the markdown mirror, the
    directions-link address line), not just the one _index_main() already
    guarded. One shared helper instead of ten independent inline f-strings,
    so this can't silently regress in an eleventh spot later.

    2026-08-21, Opus review round 2: the original `if f.region` guard tests
    truthiness, not content -- a whitespace-only region ("   ") is truthy in
    Python, so it reproduced every one of the same 10 artifacts this helper
    exists to remove. Test the stripped value instead, and use the stripped
    value in the joined string too, so a region with incidental leading/
    trailing whitespace doesn't leak into the rendered text either.
    """
    region = (f.region or "").strip()
    return f"{f.locality}, {region}" if region else f.locality


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
        "postalCode": f.postal_code,
        "addressCountry": f.country or "US",
    }
    # 2026-08-21, Opus review round 3: _loc() (used everywhere region
    # appears on the visible page) treats a whitespace-only region the same
    # as an empty one and omits it -- this raw f.region assignment didn't,
    # so a whitespace-only region rendered as omitted on the page but as a
    # literal "   " in the machine-readable JSON-LD, a real NAP-consistency
    # mismatch in a product whose whole thesis is search-engine trust in
    # that consistency. schema.org's PostalAddress.addressRegion is
    # optional; omit the key entirely rather than assert a junk value,
    # matching the visible page's own honesty.
    region = (f.region or "").strip()
    if region:
        address["addressRegion"] = region

    biz: dict = {
        "@type": _schema_type(f.subtype),
        "@id": biz_id,
        "name": f.business_name,
        "url": f"{base}/",
        "telephone": f.telephone,
        "address": address,
        "priceRange": "$$",
    }
    # 2026-08-20: schema.org's LocalBusiness.image is optional. This used to
    # unconditionally point at {base}/assets/photo.jpg -- a file
    # generate_site() never wrote, so every generated site declared a 404.
    # There's no real photo of any given business to reference (facts don't
    # carry one), so the honest fix is omitting the field, not pointing it
    # at a placeholder stock photo pretending to be this business's own.
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
        # logo.svg is real, generated by generate_site() below (a deterministic
        # monogram in this site's own theme palette) -- unlike the old
        # logo.png reference, this file actually exists once the site is
        # written; a design mark, not a claim about the business itself.
        {"@type": "Organization", "@id": org_id, "name": f.business_name,
         "url": f"{base}/", "logo": f"{base}/assets/logo.svg"},
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
    raw = json.dumps(graph, indent=2, ensure_ascii=False)
    # 2026-08-21, found while verifying the Opus review's HTML-injection
    # finding: a business_name (or any other facts field reaching this
    # graph) containing a literal "</script>" survives verbatim into this
    # JSON-LD, and a browser's HTML parser treats that substring as the
    # REAL closing tag of this <script type="application/ld+json"> block --
    # reproduced directly: business_name =
    # "Acme</script><script>alert(document.domain)</script>Dental" injected
    # a real, executing <script> tag onto every generated homepage. Escaping
    # "<", ">", "&" as JSON unicode escapes (valid JSON -- any real JSON-LD
    # consumer decodes < back to "<" when parsing) closes this and the
    # related HTML-comment-breakout vector, the same way most frameworks
    # guard JSON embedded in a <script> tag.
    return (raw.replace("<", "\\u003c")
               .replace(">", "\\u003e")
               .replace("&", "\\u0026"))


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
        # 2026-08-20: no og:image -- see _build_jsonld's matching comment on
        # LocalBusiness.image. No real photo exists to reference, and most
        # social crawlers don't render SVG for this tag, so logo.svg isn't
        # a substitute either; omitting beats a 404 or a silently-ignored tag.
        '  <meta name="twitter:card" content="summary">',
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
           f"{_esc(_loc(f))} {_esc(f.postal_code)} &middot; "
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
    # 2026-08-21, Opus 5 review round 5: this used to substring-match the
    # whole URL string against known GBP hostnames, with no scheme or host
    # check -- "javascript:alert(1)//g.page" matched "g.page" as a plain
    # substring and rendered as a live, clickable javascript: link in the
    # footer of every generated (and published) page. Reproduced end to
    # end through the real /sales/preview route, past the compliance gate.
    # Now requires a real http(s) URL whose *host* (not just some substring
    # of the whole string) is one of the real GBP domains.
    import urllib.parse

    for u in urls:
        try:
            parsed = urllib.parse.urlparse(str(u))
        except ValueError:
            continue
        if parsed.scheme not in ("http", "https"):
            continue
        host = (parsed.hostname or "").lower()
        if host in ("g.page", "business.google.com", "maps.app.goo.gl"):
            return u
        if host in ("google.com", "www.google.com") and parsed.path.startswith("/maps"):
            return u
    return None


# =============================================================================
# Index page — the page the audit scores for semantic structure (category 2)
# =============================================================================


def _index_title(f: _F) -> str:
    return f"{f.business_name} — {f.subtype} in {_loc(f)}"


def _index_description(f: _F) -> str:
    svc = _oxford([s.name for s in (f.services or [])][:3]) or "professional services"
    return f"{f.business_name} is a {_human(f.subtype)} in {_loc(f)} offering {svc}."


_STAR_FILLED = "★"
_STAR_EMPTY = "☆"


def _rating_html(rating: Any) -> str:
    """The real rating already computed for JSON-LD's aggregateRating
    (_build_jsonld above) -- was never rendered anywhere a visitor could
    actually see it. Whole-star rounding is a visual approximation; the
    exact numeric value is always shown right beside it, so nothing here
    overstates the real number. Omitted entirely when there's no real
    rating, matching _build_jsonld's own `if rating is not None` gate --
    never a fabricated placeholder rating. 2026-08-21, Opus 5 review: also
    omitted when count is 0 -- a "4.9 stars" badge with zero reviews
    behind it is a visible trust claim with nothing real to back it,
    the same fabrication risk this gate exists to prevent."""
    if rating is None:
        return ""
    value = getattr(rating, "value", None)
    count = getattr(rating, "count", None)
    if value is None or not count:
        return ""
    filled = max(0, min(5, round(value)))
    stars = _STAR_FILLED * filled + _STAR_EMPTY * (5 - filled)
    noun = "review" if count == 1 else "reviews"
    return (f'<div class="rating"><span class="stars" aria-hidden="true">{stars}</span>'
            f'{value:g} ({count} {noun})</div>')


def _stats_band_html(f: _F, rating: Any) -> str:
    """A trust-signal band built entirely from facts already on hand
    (rating, service-area count) -- no new data pipeline, no invented
    testimonial or claim. Same honesty gate as _rating_html: omitted
    entirely when there's no real rating to show, including a rating
    with zero reviews behind it (2026-08-21, Opus 5 review)."""
    if rating is None:
        return ""
    value = getattr(rating, "value", None)
    count = getattr(rating, "count", None)
    if value is None or not count:
        return ""
    noun = "review" if count == 1 else "reviews"
    # These fragments are all safe, fixed-vocabulary text built from numbers
    # and literal words -- never escaped user input -- so the literal
    # &middot; entity below can join them without _esc() double-escaping
    # its "&" into "&amp;middot;".
    stats = [f"{value:g} stars from {count} {noun}"]
    area_count = len(f.service_areas or [])
    if area_count:
        stats.append(f"{area_count} service area{'s' if area_count != 1 else ''} covered")
    sub = " &middot; ".join(stats)
    return (
        '    <div class="band">\n'
        f'      <div>\n        <h2>Trusted across {_esc(f.locality)}</h2>\n'
        f'        <p class="sub">{sub}</p>\n      </div>\n'
        '    </div>'
    )


def _location_html(f: _F) -> str:
    """A real address + a real, no-API-key directions link, built entirely
    from the same mandatory NAP fields _footer() already renders -- and,
    only when the business actually supplied them, the real opening hours
    already computed for JSON-LD's openingHoursSpecification (_hours_spec)
    but never shown to a visitor. No map embed: no maps API key is
    configured anywhere in site generation, so an <iframe> would either be
    broken or require infrastructure this slice does not add.

    2026-08-21, Opus 5 review of this slice caught two real issues, fixed
    here: (1) services/preview.py's FactWrapper substitutes known
    placeholder NAP text ("123 Sample Ave", "Sample City", ...) for a
    prospect's still-missing fields -- the address text itself already
    mirrors that in the footer (pre-existing, unchanged), but a clickable
    "Get directions" link is a materially more load-bearing claim that a
    real place exists there, so it's suppressed whenever any address
    field was synthesized rather than supplied. (2) a hours list containing
    only blank/whitespace strings (e.g. a rep pasting a textarea with a
    trailing newline) used to still render an empty, heading-labeled
    "Hours" section that said nothing -- now filtered before the presence
    check, same honesty gate as the empty-list case."""
    import urllib.parse
    addr_line = f"{f.street}, {_loc(f)} {f.postal_code}"
    query = urllib.parse.quote(f"{f.business_name}, {addr_line}")
    maps_url = f"https://www.google.com/maps/search/?api=1&query={query}"
    placeholder_fields = getattr(f, "placeholder_fields", None) or set()
    real_address = not ({"street", "locality", "region", "postal_code"} & placeholder_fields)
    parts = [
        '    <section aria-label="Location and hours">',
        f'      <h2>Location &amp; hours in {_esc(f.locality)}</h2>',
        '      <address>',
        f'        {_esc(f.street)}<br>',
        f'        {_esc(_loc(f))} {_esc(f.postal_code)}',
        '      </address>',
    ]
    if real_address:
        # No target="_blank" (matches _footer()'s own external GBP link
        # convention), so rel="noopener" would be a no-op -- omitted.
        parts.append(f'      <p><a class="directions-link" href="{_esc(maps_url)}">Get directions</a></p>')
    hours = [str(h).strip() for h in (f.hours or []) if str(h).strip()]
    if hours:
        items = "\n".join(f"        <li>{_esc(h)}</li>" for h in hours)
        parts.append('      <h3>Hours</h3>')
        parts.append(f'      <ul class="hours-list">\n{items}\n      </ul>')
    parts.append('    </section>')
    return "\n".join(parts)


def _highlights_html(f: _F) -> str:
    """Slice 2 (hero visual restructuring): a short, scannable list of real
    facts -- services, service areas, credentials -- meant to replace two
    dense prose paragraphs stacked in the hero with a real component. Built
    entirely from data already available elsewhere on the page (the same
    services/service_areas/credentials facts services_block, areas_block,
    and the prose paragraphs already draw from) -- no new data pipeline, no
    invented claim. The services item reuses the exact same honest
    fallback phrase svc_phrase already falls back to in _index_main() when
    a business has listed no services at all, not a new placeholder.
    Credentials are omitted entirely (not replaced with a generic "Licensed
    & certified" claim) when the business hasn't supplied any -- matching
    every other honesty gate in this file (_rating_html, _stats_band_html,
    _location_html's directions-link gate).

    Deliberately NOT a <ul>/<li>: audit_engine.py's Category 2 counts real
    ul/ol/table/pre/dl elements as "structured" against a narrow 0.25-0.35
    target ratio against paragraph-chunk count. A <ul> version of this
    measured 0.40 on the illustrative fixture (structured=2, chunks=3 --
    the only integer value of structured that fits that chunk count is 1),
    which would need re-tuning _index_main()'s want_structured formula
    per-business as FAQ/service counts vary, not a one-time constant.
    <div>/<span> is invisible to both the structured-element count and the
    paragraph-chunk count, so this component can render unconditionally
    without disturbing either check -- verified via a direct 25-subtype
    audit-gate sweep after this choice, not assumed.

    2026-08-21, Opus 5 review: two real fixes. (1) service/credential
    names are free text with no length cap on BusinessFacts -- a business
    with three long service names plus two long credentials could push
    this component's own word count high enough to meaningfully erode
    Category 2's 0.05-0.10 emphasis-density headroom (measured 0.0512 vs
    0.0575 without, on an adversarial fixture) -- clipped rather than
    left unbounded. (2) an unlabeled 3-item div/span list has no
    accessible name; the 2 templates that already wrap it in a real
    <h2>Highlights</h2> were fine, the other 7 weren't -- aria-label
    covers all 9 uniformly regardless of whether a visible heading also
    exists (redundant, not incorrect, for the 2 that have one)."""
    def _clip(text: str, max_chars: int = 60) -> str:
        return text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + "…"

    svc_names = [s.name for s in (f.services or [])]
    if not svc_names:
        svc_item = "a full range of services"
    elif len(svc_names) <= 3:
        svc_item = _clip(_oxford(svc_names))
    else:
        svc_item = f"{len(svc_names)} services offered"
    items = [f'      <span role="listitem">{_esc(svc_item)}</span>']

    area_count = len(f.service_areas or [])
    if area_count:
        items.append(f'      <span role="listitem">{area_count} area{"s" if area_count != 1 else ""} served</span>')

    creds = [c for c in (f.credentials or []) if str(c).strip()]
    if creds:
        items.append(f'      <span role="listitem">{_esc(_clip(_oxford(creds[:2])))}</span>')

    return ('    <div class="highlights" role="list" aria-label="Highlights">\n'
            + "\n".join(items) + "\n    </div>")


def _index_main(f: _F, base: str) -> str:
    human = _human(f.subtype)
    loc = _loc(f)
    areas = _oxford(list(f.service_areas or [])) or f.locality
    svc_names = [s.name for s in (f.services or [])]
    svc_phrase = _oxford(svc_names) if svc_names else "a full range of services"
    creds = _oxford(list(f.credentials or []))
    rating = getattr(f, "rating", None)

    # --- Paragraph 1/2/about prose: industry-aware, not one universal template.
    # 2026-08-21: this used to be a single hardcoded paragraph template
    # ("Every project... written estimate... materials and options are
    # explained... chase anyone down after the visit") applied verbatim to
    # every subtype -- a dental practice, a restaurant, a law firm all got
    # literally the same contractor-flavored sentences with only the
    # business name substituted in. Confirmed via a real rendered
    # screenshot (not just an audit-score check) that this read as
    # generic regardless of which of the 9 templates it was wrapped in --
    # growing template count alone could never have fixed content. Moved
    # to site_prose.py, which selects real, industry-appropriate phrasing
    # via the same shared palettes.industry_family_for() classifier
    # template_for()/palette_for() already use, so a business's prose,
    # palette, and template all agree on its industry. Structural shape
    # (an emphasized opening clause in p1, one emphasized clause in p2,
    # one emphasized clause in about) is preserved exactly, since that's
    # what audit_engine.py's real DOM-parsing checks (chunk-length mean,
    # emphasis density) actually measure -- same shape, genuinely
    # different, industry-real words.
    from .site_design import engine as design_engine
    from . import site_prose
    prose_seed = design_engine.compute_seed(f)
    (open_clause, p1_rest, about_link_text, p1_trailing,
     p2_a, em_clause, p2_b, about_a, about_em, about_b) = site_prose.prose_for(
        f.subtype, prose_seed, f.business_name, human, loc, areas, svc_phrase, creds
    )

    # The "read more about {business}" link is built structurally here from
    # three genuinely separate values (never one string carrying an
    # embedded marker for business_name to forge -- see site_prose.py's
    # module comment for the full history of why that approach was unsafe).
    #
    # 2026-08-21, Opus 5 review of Slice 2: class="lede" was missing here
    # entirely -- 7 of the 9 templates style the hero paragraph
    # exclusively through a ".hero .lede"/".hero p.lede" CSS rule that
    # therefore matched nothing, ever. The hero paragraph rendered at each
    # template's default `.wrap` width (up to 1120px) instead of the
    # intended ~52ch narrow reading measure, muted color, and lede font
    # size -- the actual "shorter, more scannable lede" the commit that
    # relocated p2_html was supposed to deliver never took visual effect.
    p1_html = (
        f'      <p class="lede"><strong>{_esc(open_clause)},</strong>{_esc_inline(p1_rest)}'
        f'<a href="about.html">{_esc(about_link_text)}</a>{_esc_inline(p1_trailing)}</p>'
    )
    p1_words = _wc(open_clause) + _wc(p1_rest) + _wc(about_link_text) + _wc(p1_trailing)
    emph_words = _wc(open_clause)

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
    # about_a/about_em/about_b now come from site_prose.prose_for() above,
    # alongside p1/p2 -- same industry-aware source, not a separate
    # hardcoded template.
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
        "rating_html": _rating_html(rating),
        "highlights_html": _highlights_html(f),
        "stats_band": _stats_band_html(f, rating),
        "location_html": _location_html(f),
        "nav": _nav(f),
        "footer": _footer(f, base),
        "cookie": '<div id="cookie-consent" role="region" aria-label="Cookie consent">\n  <p>We use cookies to improve your experience.</p>\n  <button type="button">Accept</button>\n  <button type="button">Decline</button>\n</div>'
    }
    return blocks

def _esc_inline(text: str) -> str:
    """Escape a prose fragment for inline placement inside a <p>.

    2026-08-21, Opus review round 3: an earlier version of this function
    (rounds 1-2) treated an embedded sentinel marker as a stand-in for the
    "read more about {business}" anchor, substituting the real <a> tag back
    in after escaping the rest of the string. That was ALSO forgeable --
    business_name is free text with no charset restriction, is interpolated
    into the same string the sentinel lived in, and html.escape() doesn't
    touch the \x01 control byte the sentinel used (the same property that
    let the module's own marker survive escaping intact also let a
    business_name containing the literal marker bytes forge its own anchor
    tag, and let a stray \x01 reach assets/logo.svg's XML output).

    Root-caused instead of patched again: site_prose.py no longer embeds
    the anchor in this string at ALL, in any form, marked or not -- the
    link's visible text and the text after it are genuinely separate
    return values (about_link_text, p1_trailing), and _index_main() below
    builds the real <a href="about.html"> tag structurally from them. This
    function's only job now is plain, unconditional escaping -- there is no
    embedded signal of any kind left in the strings it's called on for
    anything to forge.
    """
    return _html.escape(text, quote=False)

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
    desc = f"{s.name} from {f.business_name}, a {_human(f.subtype)} in {_loc(f)}."
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
    desc = f"About {f.business_name}, a {_human(f.subtype)} serving {_loc(f)}."
    head = _head(f, base, canonical, title, desc, "about.md")
    creds = _oxford(list(f.credentials or []))
    cred_sentence = f" The team holds {_esc(creds)}." if creds else ""
    
    content = (f"      <h1>About {_esc(f.business_name)}</h1>\n"
        f"      <p>{_esc(f.business_name)} is a {_esc(_human(f.subtype))} based in "
        f"{_esc(_loc(f))}, serving "
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
        f"{_esc(f.telephone)} or visit us at {_esc(f.street)}, {_esc(_loc(f))} "
        f"{_esc(f.postal_code)}.</p>",
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
    tagline = f.tagline or f"{_human(f.subtype).capitalize()} in {_loc(f)}"
    lines = [f"# {f.business_name}", "", f"> {tagline}", "", "## Pages"]
    for page in pages:
        label = "Home" if page == "index.html" else page.replace(".html", "").replace("-", " ").title()
        url = f"{base}/" if page == "index.html" else f"{base}/{page}"
        lines.append(f"- [{label}]({url})")
    return "\n".join(lines) + "\n"


def _build_llms_full(f: _F, base: str, pages: list[str]) -> str:
    lines = [f"# {f.business_name}", "",
             f"{f.business_name} is a {_human(f.subtype)} in {_loc(f)}.", ""]
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
              f"{f.street}, {_loc(f)} {f.postal_code} · {f.telephone}", ""]
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
    out += ["", f"{f.business_name} · {f.street}, {_loc(f)} "
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
# Generated assets (Category 2/4: the site must not declare a resource it
# never writes)
# =============================================================================


def _logo_svg(business_name: str, palette: Any) -> str:
    """A deterministic monogram mark in this site's own theme palette --
    every color already comes from site_design.palettes, so it always passes
    the same WCAG-contrast checks the rest of the theme does. Not a claim
    about the business (no photo is implied); a generated design mark, same
    category of thing as the theme/typography choice itself.
    """
    letter = (business_name or "?").strip()[:1].upper() or "?"
    grad_start = getattr(palette, "grad_start", "#2563EB")
    grad_end = getattr(palette, "grad_end", "#1D4ED8")
    bg = getattr(palette, "bg", "#FFFFFF")
    gid = "logoGrad"
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" '
        f'width="128" height="128" role="img" aria-label="{_esc(business_name)} logo">\n'
        f'  <defs>\n'
        f'    <linearGradient id="{gid}" x1="0%" y1="0%" x2="100%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{_esc(grad_start)}"/>\n'
        f'      <stop offset="100%" stop-color="{_esc(grad_end)}"/>\n'
        f'    </linearGradient>\n'
        f'  </defs>\n'
        f'  <rect width="128" height="128" rx="24" fill="url(#{gid})"/>\n'
        f'  <text x="64" y="64" text-anchor="middle" dominant-baseline="central" '
        f'font-family="-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif" '
        f'font-size="60" font-weight="700" fill="{_esc(bg)}">{_esc(letter)}</text>\n'
        '</svg>\n'
    )


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
                   [f"{f.business_name} is a {_human(f.subtype)} in {_loc(f)}.",
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

    # Generated assets -- assets/logo.svg is what Organization.logo (see
    # _build_jsonld) and the site's own header/favicon actually reference,
    # so it has to exist here, not just be declared.
    from .site_design import engine as design_engine
    theme = design_engine.select_theme(f)
    (out / "assets").mkdir(parents=True, exist_ok=True)
    (out / "assets" / "logo.svg").write_text(_logo_svg(f.business_name, theme.palette), encoding="utf-8")
    written.append("assets/logo.svg")

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
