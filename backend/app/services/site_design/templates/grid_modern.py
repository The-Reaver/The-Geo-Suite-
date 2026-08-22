from . import Template, _inject_css, _wrap_h2, _footer_class, _wrap_faq, _esc
import re

# Site Generator design library, Slice 4 template batch (2026-08-22):
# first of two new templates, growing the library from 9 toward the next
# checkpoint. Services render as a real CSS GRID of bordered cards
# (auto-fit minmax) -- not a single-column list, chip row, spec-sheet
# row, or connected timeline, which is what the other 8 non-grid
# templates use.
#
# 2026-08-22, Opus 5 review: an earlier version of this comment claimed
# this grid mechanism was distinct from "all 9 existing templates,"
# which was false -- Editorial Minimal's own .cards grid
# (repeat(auto-fit,minmax(260px,1fr))) is nearly the same mechanism as
# this file's .grid (minmax(240px,1fr)), just with a hover-lift
# transition and an icon-dot badge Grid Modern doesn't have. The real,
# accurate distinction is the overall page register, not the grid
# primitive itself: centered hero/section-heads (Editorial Minimal's are
# left-aligned), alternating section backgrounds striping the whole page
# (section.gm-section:nth-child(even)), and a pill-shaped CTA button in
# the header -- together read as a more overtly "modern SaaS marketing
# page" feel than Editorial Minimal's own softer editorial register.
# Genuine, known overlap: a Beauty/Salon business landing on both Grid
# Modern and Editorial Minimal (both are in that family) will see a
# near-identical services grid layout, even though the surrounding page
# differs -- not fully resolved by this slice, flagged honestly rather
# than papered over.
#
# Both established lessons applied from the start: uses the shared
# _wrap_h2()/_wrap_faq()/_footer_class() helpers (never a local
# .replace('<h2>', ...) or hand-rolled FAQ/footer class); no white text
# rendered directly on var(--accent) anywhere -- the CTA button and the
# trust band both use var(--accent-dark) (>=5.18:1 white-on-accent-dark
# on every one of the 25 real palettes, the same structural safety
# margin already proven for the other nine templates' accent-dark CTAs).
CSS_BASE = """
  /* 2026-08-22, Opus 5 review: both new templates in this batch shipped
     without .price/.menu-disclaimer -- present in all 9 existing
     templates, backing site_engine.py's _build_menu_page() output
     (<span class="price">, <p class="menu-disclaimer">). A verbatim
     regression of the exact "markup class matches no real CSS" defect
     compact_utility.py's own header comment already documents as fixed
     once this session -- reachable directly, since Grid Modern is in
     FOOD_RESTAURANT_TEMPLATES and a Restaurant with menu_items lands
     here. */
  .price{font-weight:600;color:var(--accent)}
  .menu-disclaimer{color:var(--muted);font-size:14px;margin-top:28px}
  *{box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);line-height:1.6;-webkit-font-smoothing:antialiased}
  a{color:var(--accent);text-decoration:none}
  a:hover{text-decoration:underline}
  .wrap{max-width:1080px;margin:0 auto;padding:0 24px}
  h1,h2,h3{line-height:1.15;letter-spacing:-.01em;margin:0;font-family:var(--disp)}

  header.grid-hdr{padding:20px 0;border-bottom:1px solid var(--line)}
  .bar{display:flex;align-items:center;justify-content:space-between;gap:20px}
  .brand{font-family:var(--disp);font-size:19px;font-weight:700;color:var(--ink)}
  nav.primary{display:flex;gap:22px;align-items:center}
  nav.primary a{color:var(--muted);font-size:14px;font-weight:600}
  nav.primary a:hover{color:var(--ink);text-decoration:none}
  .pill-cta{background:var(--accent-dark);color:#fff !important;padding:9px 18px;border-radius:999px;font-weight:700;font-size:13px;text-decoration:none !important}
  .pill-cta:hover{opacity:.9}

  /* Wires Site Generator Slice 3's deterministic hero-background SVG
     (site_engine.py's _hero_bg_svg) -- composited at a single group
     opacity of 0.015-0.020 (see that function's own docstring for why),
     comfortably clear of the 4.5:1 AA floor on every one of the 25 real
     palettes. */
  .hero{padding:64px 0 48px;text-align:center;background-image:url('assets/hero-bg.svg');background-size:cover;background-position:center;background-repeat:no-repeat}
  .hero h1{font-size:clamp(30px,4.6vw,46px);max-width:20ch;margin:0 auto}
  .hero .lede{color:var(--muted);font-size:17px;max-width:56ch;margin:16px auto 0}

  .rating{display:inline-flex;align-items:center;gap:7px;color:var(--muted);font-size:14px;margin-top:16px}
  .stars{color:var(--gold);letter-spacing:1px;font-size:15px}
  .highlights{display:flex;flex-wrap:wrap;gap:8px;list-style:none;padding:0;margin:16px 0 0;justify-content:center}
  .highlights span{background:var(--surface);border:1px solid var(--line);border-radius:999px;padding:5px 14px;font-size:13px;color:var(--ink)}

  section.gm-section{padding:40px 0}
  section.gm-section:nth-child(even){background:var(--surface)}
  .section-head{text-align:center;margin-bottom:28px}
  .section-head .k{color:var(--accent);font-weight:700;font-size:12px;letter-spacing:.06em;text-transform:uppercase}
  .section-head h2{font-size:26px;margin-top:6px}

  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px;list-style:none;padding:0;margin:0}
  .card{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:22px;box-shadow:var(--shadow-sm)}
  .card:hover{box-shadow:var(--shadow)}

  .chips{display:flex;flex-wrap:wrap;gap:8px;justify-content:center}
  .chip{background:var(--surface);border:1px solid var(--line);border-radius:999px;padding:6px 14px;font-size:13px;color:var(--ink)}

  .band{background:var(--accent-dark);color:#fff;border-radius:var(--r);padding:28px;text-align:center}
  .band h2{color:#fff;font-size:18px}
  /* 2026-08-22, Opus 5 review: this was rgba(255,255,255,.85) -- the
     header comment's own ">=5.18:1 white-on-accent-dark" claim is only
     true for OPAQUE white; at 85% alpha it composites to a different,
     lighter-against-itself color. Measured on Orange (the tightest real
     palette): 4.148:1 at 14px/400, below the 4.5:1 normal-text floor
     this text size actually requires (not the 3:1 large-text floor).
     Opaque #fff avoids the compositing math entirely and matches .band
     h2's own already-safe value. */
  .band .sub{color:#fff;margin-top:6px;font-size:14px}

  address{font-style:normal;color:var(--ink)}
  .directions-link{display:inline-block;margin-top:8px;color:var(--accent);font-weight:700}
  .hours-list{list-style:none;padding:0;margin:10px 0 0}
  .hours-list li{padding:3px 0;color:var(--muted);font-size:14px}

  .faq{display:grid;gap:0;max-width:760px;margin:0 auto}
  details{border-bottom:1px solid var(--line);padding:6px 0}
  details:last-child{border-bottom:none}
  summary{cursor:pointer;font-weight:700;padding:14px 0;list-style:none;display:flex;justify-content:space-between;align-items:center}
  summary::-webkit-details-marker{display:none}
  summary::after{content:"+";color:var(--accent);font-size:20px;font-weight:400}
  details[open] summary::after{content:"\\2212"}
  details p{color:var(--muted);margin:0 0 14px}

  footer.grid-modern{padding:32px 0 40px;font-size:13px;color:var(--muted);text-align:center}
  footer.grid-modern a{color:var(--ink)}
  footer.grid-modern p,footer.grid-modern a{display:block;margin:0 0 6px}
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
<header class="grid-hdr">
  <div class="wrap bar">
    <div class="brand">Your Business</div>
    <nav class="primary" aria-label="Primary">
      {links}
      <a class="pill-cta" href="tel:{tel_digits}">Call {_esc(phone)}</a>
    </nav>
  </div>
</header>
"""


def _to_grid(block_html: str) -> str:
    return (block_html
            .replace('<ul>', '<div class="grid">')
            .replace('</ul>', '</div>')
            .replace('<li>', '<div class="card">')
            .replace('</li>', '</div>'))


def _to_chips(block_html: str) -> str:
    return (block_html
            .replace('<ul>', '<div class="chips">')
            .replace('</ul>', '</div>')
            .replace('<li>', '<span class="chip">')
            .replace('</li>', '</span>'))


def render_index(facts, base_url, theme, blocks) -> str:
    head = _apply_css(blocks["head"], theme)
    nav = _format_nav(blocks["nav"], facts.telephone).replace("Your Business", _esc(facts.business_name))
    footer = _footer_class(blocks["footer"], "grid-modern")

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
        html.append('<section class="gm-section"><div class="wrap">')
        html.append(blocks["p2_html"])
        html.append('</div></section>')

    html.append('<section class="gm-section"><div class="wrap">')
    html.append(_to_grid(_wrap_h2(blocks["services_block"], "What we offer")))
    html.append('</div></section>')

    if blocks.get("stats_band"):
        html.append('<section class="gm-section"><div class="wrap">')
        html.append(blocks["stats_band"])
        html.append('</div></section>')

    if blocks["areas_block"]:
        html.append('<section class="gm-section"><div class="wrap">')
        html.append(_to_chips(_wrap_h2(blocks["areas_block"], "Where we serve")))
        html.append('</div></section>')

    if blocks.get("location_html"):
        html.append('<section class="gm-section"><div class="wrap">')
        html.append(blocks["location_html"])
        html.append('</div></section>')

    html.append('<section class="gm-section"><div class="wrap">')
    html.append(blocks["about_block"])
    html.append('</div></section>')

    if blocks["faq_block"]:
        html.append('<section class="gm-section"><div class="wrap">')
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
    html.append(_footer_class(blocks["footer"], "grid-modern"))
    html.append(blocks["cookie"])
    html.append('</body></html>')
    return "\n".join(html)


def render_about(facts, base_url, theme, blocks) -> str:
    return render_service(facts, base_url, theme, blocks)


def render_privacy(facts, base_url, theme, blocks) -> str:
    return render_service(facts, base_url, theme, blocks)


TemplateGridModern = Template("Grid Modern", render_index, render_service, render_about, render_privacy)
