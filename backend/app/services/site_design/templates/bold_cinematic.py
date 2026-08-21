from . import Template, _inject_css
import re

CSS_BASE = """
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

  .hero{position:relative;background:var(--dark);color:#fff;padding:150px 0 110px;text-align:center;}
  .hero h1{font-family:var(--disp);font-weight:600;font-size:clamp(44px,7vw,84px);letter-spacing:-.02em;line-height:1.02}
  .hero .rating{display:inline-flex;align-items:center;gap:9px;color:rgba(255,255,255,.82);font-size:15px;margin-top:28px}
  .hero .stars{color:var(--gold);letter-spacing:3px;font-size:18px}

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
    html.append(f'<h1>{facts.business_name}</h1>')
    html.append(blocks["p1_html"])
    if blocks.get("rating_html"):
        html.append(blocks["rating_html"])
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
        html.append(blocks["faq_block"])
        html.append('</section>')
        
    html.append('    </article>')
    html.append('  </main>')
    html.append(blocks["footer"])
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
    html.append(blocks["footer"])
    html.append(blocks["cookie"])
    html.append('</body></html>')
    return "\n".join(html)

def render_about(facts, base_url, theme, blocks) -> str:
    return render_service(facts, base_url, theme, blocks)

def render_privacy(facts, base_url, theme, blocks) -> str:
    return render_service(facts, base_url, theme, blocks)

TemplateBoldCinematic = Template("Bold Cinematic", render_index, render_service, render_about, render_privacy)

