from . import Template, _inject_css, _wrap_h2, _footer_class, _wrap_faq, _esc
import re

# Site Generator design library, Slice 4 template batch (2026-08-22):
# second of two new templates. Genuinely different information
# architecture from all 9 existing templates AND from Grid Modern
# (this same batch): the Services and Service Areas sections are
# numbered via a real CSS counter (counter-reset on <main>,
# counter-increment on .section-head, rendered into the kicker text via
# ::before) -- an "annual report / structured document" register none
# of the other ten attempt. Timeline Flow (Slice C.4) numbers SERVICES
# WITHIN one section via a CSS counter; this numbers whole PAGE
# SECTIONS the same mechanical way, a materially different scope.
# About and FAQ deliberately render without a numbered kicker -- same
# as every other template in this codebase, none of which give About/
# FAQ the _wrap_h2() section-head treatment either (only services_block/
# areas_block ever get it); the numbers shown are always sequential
# starting at 01, matching however many of the (up to 2) numberable
# sections a given business's facts actually include. Left-aligned
# display type (var(--disp), so this genuinely varies across the real
# 11 type pairings, not hardcoded to one serif choice -- fixed from an
# Opus 5 review finding: the first draft used var(--serif), a fixed
# Georgia constant unrelated to theme.typography, so every Ledger page
# downloaded its assigned pairing's webfont via the real @import but
# then never rendered it, discarding the whole typography dimension for
# headings on this one template), thin top/bottom rules instead of
# cards or shadows, restrained neutral color use -- suits Legal/Finance
# and Dental/Medical (info-dense, trust/process-led decisions)
# especially well.
#
# 2026-08-22, Opus 5 review: counter-increment originally lived on
# section.ledger-section itself, which every section triggers regardless
# of whether it renders a number -- the common real case (no service
# areas) showed a lone "02" with no "01" anywhere. See the
# counter-increment declaration below for the fix.
#
# Both established lessons applied from the start: uses the shared
# _wrap_h2()/_wrap_faq()/_footer_class() helpers; the one accent-filled
# element (.band) is never paired with default-size white text -- .band
# uses ink-on-accent-soft (a light tint), never white-on-accent,
# structurally safe regardless of which of the 25 palettes is active.
CSS_BASE = """
  /* 2026-08-22, Opus 5 review: both new templates in this batch shipped
     without .price/.menu-disclaimer -- present in all 9 existing
     templates, backing site_engine.py's _build_menu_page() output
     (<span class="price">, <p class="menu-disclaimer">). A verbatim
     regression of the exact "markup class matches no real CSS" defect
     compact_utility.py's own header comment already documents as fixed
     once this session -- reachable via the general fallback for any
     unclassified food-adjacent subtype with menu_items. */
  .price{font-weight:600;color:var(--accent)}
  .menu-disclaimer{color:var(--muted);font-size:14px;margin-top:28px}
  *{box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);line-height:1.65;-webkit-font-smoothing:antialiased}
  a{color:var(--accent);text-decoration:none}
  a:hover{text-decoration:underline}
  .wrap{max-width:760px;margin:0 auto;padding:0 24px}
  h1,h2,h3{line-height:1.2;margin:0;font-family:var(--disp)}

  header.ledger-hdr{border-bottom:2px solid var(--ink);padding:18px 0}
  .bar{display:flex;align-items:center;justify-content:space-between}
  .brand{font-family:var(--disp);font-size:18px;font-weight:700;color:var(--ink)}
  nav.primary{display:flex;gap:18px;align-items:center}
  nav.primary a{color:var(--muted);font-size:13px;font-weight:600}
  nav.primary a:hover{color:var(--ink);text-decoration:none}
  .ledger-call{color:var(--accent) !important;font-weight:700}

  main{counter-reset:ledger-num}

  /* Deliberately NOT wired to Site Generator Slice 3's hero-background
     SVG (site_engine.py's _hero_bg_svg), matching Compact Utility's own
     established precedent: this template's whole design intent is a
     restrained, decoration-free "document" register -- a decorative
     background pattern would contradict that, the same reasoning
     Compact Utility's own header comment already documents for its own
     borderless-panel choice. */
  .hero{padding:48px 0 32px;border-bottom:1px solid var(--line)}
  .hero h1{font-size:clamp(28px,4vw,40px);max-width:22ch}
  .hero .lede{color:var(--muted);font-size:16px;max-width:62ch;margin-top:14px;font-family:var(--font)}

  .rating{display:inline-flex;align-items:center;gap:7px;color:var(--muted);font-size:14px;margin-top:16px}
  .stars{color:var(--gold);letter-spacing:1px;font-size:15px}
  .highlights{display:flex;flex-wrap:wrap;gap:6px 22px;padding:0;margin:14px 0 0;list-style:none}
  .highlights span{font-size:14px;color:var(--muted);font-family:var(--font)}

  section.ledger-section{padding:36px 0;border-bottom:1px solid var(--line)}
  section.ledger-section:last-of-type{border-bottom:none}
  /* 2026-08-22, Opus 5 review: counter-increment used to live on
     section.ledger-section itself, but not every .ledger-section gets a
     .section-head (only sections built via _wrap_h2() -- Services and
     Areas -- do; p2/stats-band/location/about/FAQ render bare, with no
     kicker to display a number in at all). Every section was still
     incrementing the shared counter regardless, so real pages skipped
     numbers and, with no service areas (the common case), showed a
     single lone "02" with no "01" anywhere -- directly contradicting
     this file's own claim that services/areas/about/FAQ are all
     numbered. Moved counter-increment onto .section-head itself, so
     only a section that actually renders a number consumes one -- the
     numbers shown are always sequential starting at 01, regardless of
     which optional sections a given business's facts happen to include.
  */
  .section-head{counter-increment:ledger-num;margin-bottom:18px}
  .section-head .k{color:var(--accent);font-weight:700;font-size:12px;letter-spacing:.05em;text-transform:uppercase;font-family:var(--font)}
  .section-head .k::before{content:counter(ledger-num,decimal-leading-zero) " \\2014 "}
  .section-head h2{font-size:22px;margin-top:6px}

  ul.plain{list-style:none;padding:0;margin:0}
  ul.plain li{padding:12px 0;border-top:1px dotted var(--line);color:var(--ink)}
  ul.plain li:first-child{border-top:none}

  .chips{display:flex;flex-wrap:wrap;gap:8px}
  .chip{border:1px solid var(--line);padding:5px 12px;font-size:13px;color:var(--ink)}

  .band{background:var(--accent-soft);border-radius:var(--radius);padding:22px}
  .band h2{color:var(--ink);font-size:16px;font-family:var(--disp)}
  .band .sub{color:var(--ink);margin-top:6px;font-size:14px;font-family:var(--font)}

  address{font-style:normal;color:var(--ink)}
  .directions-link{display:inline-block;margin-top:8px;color:var(--accent);font-weight:700}
  .hours-list{list-style:none;padding:0;margin:10px 0 0}
  .hours-list li{padding:3px 0;color:var(--muted);font-size:14px}

  .faq{display:grid;gap:0}
  details{border-bottom:1px dotted var(--line);padding:6px 0}
  details:last-child{border-bottom:none}
  summary{cursor:pointer;font-weight:700;padding:14px 0;list-style:none;display:flex;justify-content:space-between;align-items:center;font-family:var(--font)}
  summary::-webkit-details-marker{display:none}
  summary::after{content:"+";color:var(--accent);font-size:18px;font-weight:400}
  details[open] summary::after{content:"\\2212"}
  details p{color:var(--muted);margin:0 0 14px;font-family:var(--font)}

  footer.ledger{padding:28px 0 36px;font-size:13px;color:var(--muted)}
  footer.ledger a{color:var(--ink)}
  footer.ledger p,footer.ledger a{display:block;margin:0 0 6px}
"""


def _apply_css(head_html: str, theme) -> str:
    h = _inject_css(head_html, theme.palette, theme.typography)
    return h.replace("</style>", f"{CSS_BASE}\n</style>")


def _format_nav(nav_html: str, phone: str) -> str:
    links_match = re.search(r'<nav[^>]*>(.*?)</nav>', nav_html, re.S)
    links = links_match.group(1).strip() if links_match else nav_html
    tel_digits = "".join(c for c in phone if c.isdigit() or c == "+")
    if not tel_digits.startswith("+"):
        tel_digits = "+" + tel_digits
    return f"""
<header class="ledger-hdr">
  <div class="wrap bar">
    <div class="brand">Your Business</div>
    <nav class="primary" aria-label="Primary">
      {links}
      <a class="ledger-call" href="tel:{tel_digits}">Call {_esc(phone)}</a>
    </nav>
  </div>
</header>
"""


def _to_plain_list(block_html: str) -> str:
    return block_html.replace('<ul>', '<ul class="plain">')


def _to_chips(block_html: str) -> str:
    return (block_html
            .replace('<ul>', '<div class="chips">')
            .replace('</ul>', '</div>')
            .replace('<li>', '<span class="chip">')
            .replace('</li>', '</span>'))


def render_index(facts, base_url, theme, blocks) -> str:
    head = _apply_css(blocks["head"], theme)
    nav = _format_nav(blocks["nav"], facts.telephone).replace("Your Business", _esc(facts.business_name))
    footer = _footer_class(blocks["footer"], "ledger")

    html = [head, "<body>", '  <a href="#main" class="skip">Skip to content</a>', nav, '  <main id="main">', '    <article>']

    html.append('<div class="wrap"><div class="hero">')
    html.append(f'<h1>{_esc(facts.business_name)} in {_esc(facts.locality)}</h1>')
    html.append(blocks["p1_html"])
    if blocks.get("rating_html"):
        html.append(blocks["rating_html"])
    if blocks.get("highlights_html"):
        html.append(blocks["highlights_html"])
    html.append('</div></div>')

    if blocks.get("p2_html"):
        html.append('<section class="ledger-section"><div class="wrap">')
        html.append(blocks["p2_html"])
        html.append('</div></section>')

    html.append('<section class="ledger-section"><div class="wrap">')
    html.append(_to_plain_list(_wrap_h2(blocks["services_block"], "Services")))
    html.append('</div></section>')

    if blocks.get("stats_band"):
        html.append('<section class="ledger-section"><div class="wrap">')
        html.append(blocks["stats_band"])
        html.append('</div></section>')

    if blocks["areas_block"]:
        html.append('<section class="ledger-section"><div class="wrap">')
        html.append(_to_chips(_wrap_h2(blocks["areas_block"], "Service areas")))
        html.append('</div></section>')

    if blocks.get("location_html"):
        html.append('<section class="ledger-section"><div class="wrap">')
        html.append(blocks["location_html"])
        html.append('</div></section>')

    html.append('<section class="ledger-section"><div class="wrap">')
    html.append(blocks["about_block"])
    html.append('</div></section>')

    if blocks["faq_block"]:
        html.append('<section class="ledger-section"><div class="wrap">')
        html.append(_wrap_faq(blocks["faq_block"]))
        html.append('</div></section>')

    html.append('    </article>')
    html.append('  </main>')
    html.append(footer)
    html.append(blocks["cookie"])
    html.append('</body></html>')
    return "\n".join(html)


def render_service(facts, base_url, theme, blocks) -> str:
    head = _apply_css(blocks["head"], theme)
    nav = _format_nav(blocks["nav"], facts.telephone).replace("Your Business", _esc(facts.business_name))
    html = [head, "<body>", '  <a href="#main" class="skip">Skip to content</a>', nav,
            '  <main id="main">', '    <section class="wrap"><article>']
    html.append(blocks["content"])
    html.append('    </article></section>')
    html.append('  </main>')
    html.append(_footer_class(blocks["footer"], "ledger"))
    html.append(blocks["cookie"])
    html.append('</body></html>')
    return "\n".join(html)


def render_about(facts, base_url, theme, blocks) -> str:
    return render_service(facts, base_url, theme, blocks)


def render_privacy(facts, base_url, theme, blocks) -> str:
    return render_service(facts, base_url, theme, blocks)


TemplateLedger = Template("Ledger", render_index, render_service, render_about, render_privacy)
