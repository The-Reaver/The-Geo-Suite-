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
  body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);line-height:1.6;font-size:17px;-webkit-font-smoothing:antialiased}
  a{color:var(--accent-2);text-decoration:none}
  .wrap{max-width:var(--maxw);margin:0 auto;padding:0 26px}
  h1,h2,h3{margin:0;line-height:1.08;letter-spacing:-.03em;font-weight:800}

  header.site{position:sticky;top:0;z-index:30;background:var(--glass);backdrop-filter:saturate(180%) blur(14px);border-bottom:1px solid var(--border)}
  .bar{display:flex;align-items:center;justify-content:space-between;height:70px}
  .brand{font-size:19px;font-weight:800;letter-spacing:-.03em;display:flex;align-items:center;gap:10px}
  nav.primary{display:flex;gap:28px;align-items:center}
  nav.primary a{color:var(--muted);font-size:15px;font-weight:500}
  nav.primary a:hover{color:var(--ink)}
  .cta{display:inline-flex;align-items:center;gap:8px;background:var(--ink);color:#fff !important;padding:11px 20px;border-radius:12px;font-weight:600;font-size:15px;min-height:44px;box-shadow:var(--shadow-sm)}
  @media(max-width:820px){nav.primary a:not(.cta){display:none}}

  .hero-in{position:relative;overflow:hidden;z-index:1;display:grid;grid-template-columns:1.05fr .95fr;gap:56px;align-items:center;padding:80px 0 70px}
  h1{font-size:clamp(40px,5.6vw,62px);margin:24px 0 0;max-width:15ch;font-family:var(--disp);}

  .visual{position:relative;height:420px;border-radius:26px;background:var(--grad);box-shadow:var(--shadow-lg);overflow:hidden}
  @media(max-width:860px){.hero-in{grid-template-columns:1fr;gap:40px}.visual{height:300px}}
  .rating{display:inline-flex;align-items:center;gap:9px;color:var(--muted);font-size:15px;margin-top:24px}
  .stars{color:var(--gold);letter-spacing:2px;font-size:16px}
  .highlights{display:flex;flex-wrap:wrap;gap:10px;padding:0;margin:22px 0 0}
  .highlights span{background:var(--surface);border:1px solid var(--border);font-size:14px;font-weight:600;padding:8px 14px;border-radius:999px}

  section{padding:78px 0}
  .head{max-width:58ch;margin:0 auto 46px;text-align:center}
  
  .grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:22px}
  .svc{position:relative;background:#fff;border:1px solid var(--border);border-radius:var(--r);padding:32px;box-shadow:var(--shadow-sm);transition:.18s ease;overflow:hidden}
  
  .band{background:var(--dark);border-radius:28px;padding:60px;text-align:center;position:relative;overflow:hidden;color:#fff}
  .band h2{color:#fff;}

  address{font-style:normal;color:var(--ink);line-height:1.5}
  .directions-link{display:inline-block;margin-top:10px;color:var(--accent-2);font-weight:700}
  .hours-list{list-style:none;padding:0;margin:12px 0 0}
  .hours-list li{padding:4px 0;color:var(--muted);font-size:15px}

  .faq{display:grid;gap:14px;max-width:780px;margin:0 auto}
  /* 2026-08-21, Opus 5 review: the shared _wrap_faq() helper
     (templates/__init__.py) now turns the real FAQ content into a real
     accordion (details/summary elements) for every template -- but this
     file had no details/summary CSS at all before, the mirror-image of
     the dead-CSS bug _wrap_faq() itself fixed: real markup with nothing
     to style it, rendering as an unstyled native disclosure triangle
     with the answer collapsed by default. */
  details{background:#fff;border:1px solid var(--border);border-radius:var(--r);padding:4px 22px}
  summary{cursor:pointer;font-weight:600;padding:18px 0;list-style:none;display:flex;justify-content:space-between;align-items:center;font-size:17px}
  summary::-webkit-details-marker{display:none}
  summary::after{content:"+";color:var(--accent);font-size:22px;font-weight:400}
  details[open] summary::after{content:"–"}
  details p{color:var(--muted);margin:0 0 18px}

  /* 2026-08-21, Opus 5 review of Slice C.3: site_engine.py's _footer()
     emits a classless <footer> -- this never matched anything until
     _footer_class() was wired in at both call sites. */
  footer.site{background:var(--dark);color:#fff;padding:64px 0 40px;margin-top:20px}
  footer.site a{color:rgba(255,255,255,.82)}
"""

def _apply_css(head_html: str, theme) -> str:
    h = _inject_css(head_html, theme.palette, theme.typography)
    return h.replace("</style>", f"{CSS_BASE}\n</style>")

def render_index(facts, base_url, theme, blocks) -> str:
    head = _apply_css(blocks["head"], theme)
    # Minimal transform to use CSS_BASE
    # Split Modern has a side-by-side hero.
    
    html = [head, "<body>", '  <a href="#main" class="skip">Skip to content</a>', blocks["nav"], '  <main id="main">', '    <article>']
    
    # Split hero
    # 2026-08-21, Slice 2: p1_html stays in the hero; p2_html moves to its
    # own section right after (was two dense paragraphs stacked next to
    # the visual box). highlights_html adds a real, scannable component.
    html.append('<div class="wrap hero-in">')
    html.append('<div>')
    html.append(f'<h1>{_esc(facts.business_name)}</h1>')
    html.append(blocks["p1_html"])
    if blocks.get("rating_html"):
        html.append(blocks["rating_html"])
    if blocks.get("highlights_html"):
        html.append(blocks["highlights_html"])
    html.append('</div>')
    html.append('<div class="visual" aria-hidden="true"></div>') # The visual
    html.append('</div>')

    if blocks.get("p2_html"):
        html.append('<div class="wrap"><section aria-label="Our approach">')
        html.append(blocks["p2_html"])
        html.append('</section></div>')

    html.append('<div class="wrap"><div class="grid3">')
    html.append(blocks["services_block"].replace('<ul>', '').replace('</ul>', '').replace('<li>', '<div class="svc">').replace('</li>', '</div>'))
    html.append('</div></div>')

    # Trust band (real rating + service-area count, already computed for
    # JSON-LD -- 2026-08-20, never rendered anywhere visible until now)
    if blocks.get("stats_band"):
        html.append('<div class="wrap">')
        html.append(blocks["stats_band"])
        html.append('</div>')

    if blocks["areas_block"]:
        html.append('<div class="wrap">')
        html.append(blocks["areas_block"])
        html.append('</div>')

    # Location + hours (real NAP + a real directions link, no map embed --
    # no maps API key exists anywhere in site generation)
    if blocks.get("location_html"):
        html.append('<div class="wrap">')
        html.append(blocks["location_html"])
        html.append('</div>')

    html.append(blocks["about_block"])
    html.append(_wrap_faq(blocks["faq_block"]))
        
    html.append('    </article>')
    html.append('  </main>')
    html.append(_footer_class(blocks["footer"], "site"))
    html.append(blocks["cookie"])
    html.append('</body></html>')
    
    return "\n".join(html)

# 2026-08-20: interior pages used to delegate to editorial_minimal's own
# render_service/about/privacy -- which calls *editorial_minimal's own*
# _apply_css/CSS_BASE internally, not this module's. A "Split Modern" home
# page linked to About/Privacy/every service page rendered in Editorial
# Minimal's CSS entirely, not just a similar layout -- a real, visible
# theme break on every click past the homepage. Now built from this
# template's own _apply_css and its own wrap/section conventions (the same
# ones render_index already uses for about_block/faq_block), so the whole
# site stays inside one theme.
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

TemplateSplitModern = Template("Split Modern", render_index, render_service, render_about, render_privacy)

