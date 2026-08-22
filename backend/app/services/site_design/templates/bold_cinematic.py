from . import Template, _inject_css, _footer_class, _wrap_faq, _esc
import re

CSS_BASE = """
  /* 2026-08-21, Opus 5 review of the menu-page slice: .price and
     .menu-disclaimer (site_engine.py's _build_menu_page) had zero CSS
     backing in any of the 9 templates -- the exact "markup class
     matches no real CSS" defect already fixed once this session for
     the shared footer/FAQ/lede. */
  .price{font-weight:600;color:var(--accent)}
  .menu-disclaimer{color:var(--muted);font-size:14px;margin-top:28px}
  *{box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);font-size:17px;line-height:1.6;-webkit-font-smoothing:antialiased;letter-spacing:-.006em;overflow-x:hidden}
  a{text-decoration:none;color:var(--accent)}
  .wrap{max-width:var(--maxw);margin:0 auto;padding:0 26px}
  h1,h2,h3{margin:0;line-height:1.05;letter-spacing:-.03em}

  header.nav{position:fixed;top:0;left:0;right:0;z-index:40;background:var(--glass);backdrop-filter:saturate(180%) blur(16px);border-bottom:1px solid var(--line)}
  header.nav .bar{display:flex;align-items:center;justify-content:space-between;height:74px}
  .brand{font-weight:800;font-size:19px;color:var(--ink);}
  header.nav nav{display:flex;gap:30px;align-items:center}
  header.nav nav a{color:var(--muted);font-size:15px;font-weight:500;}

  /* 2026-08-21, Site Generator Slice 3: real, licensing-free hero
     background pattern layered on top of the existing solid --dark fill
     (site_engine.py's _hero_bg_svg) -- split from the old `background`
     shorthand into background-color/background-image so both coexist.
     Composited at a single group-level opacity (0.015-0.020, see
     _hero_bg_svg's own docstring for why group opacity is what makes
     this a real, verified guarantee rather than a per-shape one) --
     Opus 5 review measured this template's real worst-case contrast with
     the pattern applied at >=9.97:1 for the white h1 and >=7.87:1 for
     .hero .rating, both comfortably clear of the white-on-dark floor this
     template already relied on. */
  .hero{position:relative;background-color:var(--dark);background-image:url('assets/hero-bg.svg');background-size:cover;background-position:center;background-repeat:no-repeat;color:#fff;padding:150px 0 110px;text-align:center;}
  .hero h1{font-family:var(--disp);font-weight:600;font-size:clamp(44px,7vw,84px);letter-spacing:-.02em;line-height:1.02}
  .hero .rating{display:inline-flex;align-items:center;gap:9px;color:rgba(255,255,255,.82);font-size:15px;margin-top:28px}
  .hero .stars{color:var(--gold);letter-spacing:3px;font-size:18px}
  /* White text on a transparent, bordered pill (not a solid fill) --
     safe by construction on the dark hero background at any palette,
     the same "safe by construction, not by clearing a threshold"
     approach already used for the nav call button elsewhere in this
     session (see other templates' own CTA classes). */
  .hero .highlights{display:flex;flex-wrap:wrap;justify-content:center;gap:10px;padding:0;margin:26px 0 0}
  .hero .highlights span{border:1px solid rgba(255,255,255,.35);color:#fff;font-size:14px;font-weight:600;padding:8px 16px;border-radius:999px}

  section{padding:96px 0}
  .grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:22px}
  .svc{position:relative;background:#fff;border-radius:var(--r);padding:34px;box-shadow:var(--shadow);border:1px solid var(--line)}

  .band{background:var(--dark);border-radius:30px;padding:70px;text-align:center;color:#fff}
  .band h2{font-family:var(--disp);color:#fff;}

  address{font-style:normal;color:var(--ink);line-height:1.5}
  .directions-link{display:inline-block;margin-top:10px;color:var(--accent);font-weight:600}
  .hours-list{list-style:none;padding:0;margin:12px 0 0}
  .hours-list li{padding:4px 0;color:var(--muted);font-size:15px}

  .faq{display:grid;gap:14px;max-width:800px;margin:0 auto}
  /* 2026-08-21, Opus 5 review: the shared _wrap_faq() helper
     (templates/__init__.py) now turns the real FAQ content into a real
     accordion (details/summary elements) for every template -- but this
     file had no details/summary CSS at all before, the mirror-image of
     the dead-CSS bug _wrap_faq() itself fixed: real markup with nothing
     to style it, rendering as an unstyled native disclosure triangle
     with the answer collapsed by default. */
  details{background:#fff;border:1px solid var(--line);border-radius:var(--r);padding:4px 22px}
  summary{cursor:pointer;font-weight:600;padding:18px 0;list-style:none;display:flex;justify-content:space-between;align-items:center;font-size:17px}
  summary::-webkit-details-marker{display:none}
  summary::after{content:"+";color:var(--accent);font-size:22px;font-weight:400}
  details[open] summary::after{content:"–"}
  details p{color:var(--muted);margin:0 0 18px}

  /* 2026-08-21, Opus 5 review of Slice C.3: site_engine.py's _footer()
     emits a classless <footer> -- this never matched anything until
     _footer_class() was wired in at both call sites. */
  footer.site{background:var(--dark);color:#fff;padding:72px 0 40px;margin-top:24px}
  footer.site a{color:rgba(255,255,255,.82)}
"""

def _apply_css(head_html: str, theme) -> str:
    h = _inject_css(head_html, theme.palette, theme.typography)
    return h.replace("</style>", f"{CSS_BASE}\n</style>")

def render_index(facts, base_url, theme, blocks) -> str:
    head = _apply_css(blocks["head"], theme)
    html = [head, "<body>", '  <a href="#main" class="skip">Skip to content</a>', blocks["nav"], '  <main id="main">', '    <article>']
    
    html.append('<section class="hero"><div class="wrap">')
    html.append(f'<h1>{_esc(facts.business_name)}</h1>')
    html.append(blocks["p1_html"])
    if blocks.get("rating_html"):
        html.append(blocks["rating_html"])
    if blocks.get("highlights_html"):
        html.append(blocks["highlights_html"])
    html.append('</div></section>')

    html.append('<section class="wrap">')
    html.append(blocks["p2_html"])
    html.append('</section>')

    html.append('<section class="wrap"><div class="grid3">')
    html.append(blocks["services_block"].replace('<ul>', '').replace('</ul>', '').replace('<li>', '<div class="svc">').replace('</li>', '</div>'))
    html.append('</div></section>')

    # Trust band (real rating + service-area count, already computed for
    # JSON-LD -- 2026-08-20, never rendered anywhere visible until now)
    if blocks.get("stats_band"):
        html.append('<section class="wrap">')
        html.append(blocks["stats_band"])
        html.append('</section>')

    if blocks["areas_block"]:
        html.append('<section class="wrap">')
        html.append(blocks["areas_block"])
        html.append('</section>')

    # Location + hours (real NAP + a real directions link, no map embed --
    # no maps API key exists anywhere in site generation)
    if blocks.get("location_html"):
        html.append('<section class="wrap">')
        html.append(blocks["location_html"])
        html.append('</section>')

    html.append('<section class="wrap">')
    html.append(blocks["about_block"])
    html.append('</section>')
    
    if blocks["faq_block"]:
        html.append('<section class="wrap">')
        html.append(_wrap_faq(blocks["faq_block"]))
        html.append('</section>')
        
    html.append('    </article>')
    html.append('  </main>')
    html.append(_footer_class(blocks["footer"], "site"))
    html.append(blocks["cookie"])
    html.append('</body></html>')
    return "\n".join(html)

# 2026-08-20: interior pages used to delegate to editorial_minimal's own
# render_service/about/privacy -- which calls *editorial_minimal's own*
# _apply_css/CSS_BASE internally, not this module's. A "Bold Cinematic"
# home page linked to About/Privacy/every service page rendered in
# Editorial Minimal's CSS entirely, not just a similar layout -- a real,
# visible theme break on every click past the homepage. Now built from
# this template's own _apply_css and its own wrap/section conventions
# (the same ones render_index already uses for about_block/faq_block), so
# the whole site stays inside one theme.
def render_service(facts, base_url, theme, blocks) -> str:
    head = _apply_css(blocks["head"], theme)
    html = [head, "<body>", '  <a href="#main" class="skip">Skip to content</a>', blocks["nav"],
            '  <main id="main">', '    <section class="wrap"><article>']
    html.append(blocks["content"])
    html.append('    </article></section>')
    html.append('  </main>')
    html.append(_footer_class(blocks["footer"], "site"))
    html.append(blocks["cookie"])
    html.append('</body></html>')
    return "\n".join(html)

def render_about(facts, base_url, theme, blocks) -> str:
    return render_service(facts, base_url, theme, blocks)

def render_privacy(facts, base_url, theme, blocks) -> str:
    return render_service(facts, base_url, theme, blocks)

TemplateBoldCinematic = Template("Bold Cinematic", render_index, render_service, render_about, render_privacy)

