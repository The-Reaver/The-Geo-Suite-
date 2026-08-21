from . import Template, _inject_css
import re

CSS_BASE = """
  *{box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);line-height:1.6;font-size:17px;-webkit-font-smoothing:antialiased}
  a{color:var(--accent);text-decoration:none}
  a:hover{text-decoration:underline}
  .wrap{max-width:var(--maxw);margin:0 auto;padding:0 24px}
  h1,h2,h3{line-height:1.2;letter-spacing:-.01em;margin:0}
  
  header.site{position:sticky;top:0;z-index:20;background:rgba(255,255,255,.85);backdrop-filter:saturate(180%) blur(10px);border-bottom:1px solid var(--border)}
  .bar{display:flex;align-items:center;justify-content:space-between;height:68px}
  .brand{font-family:var(--disp);font-size:20px;font-weight:700;letter-spacing:-.02em;color:var(--ink)}
  .brand span{color:var(--accent)}
  nav.primary{display:flex;gap:26px;align-items:center}
  nav.primary a{color:var(--muted);font-size:15px;font-weight:500}
  nav.primary a:hover{color:var(--ink);text-decoration:none}
  .call-btn{display:inline-flex;align-items:center;gap:8px;background:var(--accent);color:#fff !important;padding:11px 18px;border-radius:999px;font-weight:600;font-size:15px;min-height:44px}
  .call-btn:hover{background:var(--accent-dark);text-decoration:none}
  @media(max-width:720px){nav.primary a:not(.call-btn){display:none}}
  
  .hero{padding:76px 0 56px}
  .eyebrow{display:inline-block;background:var(--accent-soft);color:var(--accent-dark);font-size:13px;font-weight:600;letter-spacing:.02em;padding:6px 13px;border-radius:999px;margin-bottom:22px}
  .hero h1{font-size:clamp(34px,5vw,52px);max-width:16ch;font-family:var(--disp);}
  .hero p.lede{font-size:20px;color:var(--muted);max-width:52ch;margin:20px 0 0}
  .hero-cta{display:flex;flex-wrap:wrap;gap:14px;margin-top:34px;align-items:center}
  .btn-primary{background:var(--accent);color:#fff !important;padding:14px 26px;border-radius:999px;font-weight:600;min-height:48px;display:inline-flex;align-items:center}
  .btn-primary:hover{background:var(--accent-dark);text-decoration:none}
  .btn-ghost{padding:14px 22px;border-radius:999px;border:1px solid var(--border);color:var(--ink) !important;font-weight:600;background:var(--surface)}
  .btn-ghost:hover{border-color:var(--accent);text-decoration:none}
  .rating{display:inline-flex;align-items:center;gap:9px;color:var(--muted);font-size:15px;margin-top:26px}
  .stars{color:var(--gold);letter-spacing:2px;font-size:16px}
  
  section{padding:56px 0}
  .section-head{max-width:60ch;margin-bottom:36px}
  .section-head .k{color:var(--accent);font-weight:700;font-size:14px;letter-spacing:.04em;text-transform:uppercase}
  .section-head h2{font-size:clamp(26px,3.4vw,34px);margin-top:10px;font-family:var(--disp);}
  .section-head p{color:var(--muted);margin:12px 0 0;font-size:18px}
  
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:20px}
  .card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:28px;box-shadow:var(--shadow);transition:transform .15s ease,box-shadow .15s ease}
  .card:hover{transform:translateY(-3px);box-shadow:0 2px 4px rgba(31,36,33,.05),0 16px 40px rgba(31,36,33,.09)}
  .card .dot{width:40px;height:40px;border-radius:11px;background:var(--accent-soft);display:flex;align-items:center;justify-content:center;color:var(--accent-dark);font-weight:700;margin-bottom:16px}
  .card h3{font-size:20px}
  .card p{color:var(--muted);margin:9px 0 0;font-size:16px}
  
  .chips{display:flex;flex-wrap:wrap;gap:10px}
  .chip{background:var(--surface);border:1px solid var(--border);border-radius:999px;padding:9px 16px;color:var(--ink);font-size:15px;font-weight:500}
  
  .band{background:var(--accent);color:#fff;border-radius:20px;padding:44px;display:flex;flex-wrap:wrap;gap:28px;align-items:center;justify-content:space-between}
  .band h2{color:#fff;font-size:28px;max-width:20ch}
  .band .btn-primary{background:#fff;color:var(--accent-dark) !important}
  .band .sub{color:rgba(255,255,255,.86);margin-top:8px}

  address{font-style:normal;color:var(--ink);line-height:1.5}
  .directions-link{display:inline-block;margin-top:10px;color:var(--accent);font-weight:600}
  .hours-list{list-style:none;padding:0;margin:12px 0 0}
  .hours-list li{padding:4px 0;color:var(--muted);font-size:15px}

  .faq{display:grid;gap:14px;max-width:760px}
  details{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:4px 22px}
  summary{cursor:pointer;font-weight:600;padding:18px 0;list-style:none;display:flex;justify-content:space-between;align-items:center;font-size:17px}
  summary::-webkit-details-marker{display:none}
  summary::after{content:"+";color:var(--accent);font-size:22px;font-weight:400}
  details[open] summary::after{content:"–"}
  details p{color:var(--muted);margin:0 0 18px}
  
  footer.site{background:#fff;border-top:1px solid var(--border);padding:52px 0 40px;margin-top:24px}
  .foot-grid{display:grid;grid-template-columns:1.4fr 1fr 1fr;gap:32px}
  .foot-grid h4{font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin:0 0 14px}
  .foot-grid p,.foot-grid a{color:var(--ink);font-size:15px;margin:0 0 8px;display:block}
  .foot-brand{font-family:var(--disp);font-size:19px;font-weight:700}
  .foot-brand span{color:var(--accent)}
  .legal{border-top:1px solid var(--border);margin-top:36px;padding-top:22px;color:var(--muted);font-size:14px;display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px}
  @media(max-width:720px){.foot-grid{grid-template-columns:1fr 1fr}.band{padding:32px}}
"""

def _apply_css(head_html: str, theme) -> str:
    h = _inject_css(head_html, theme.palette, theme.typography)
    return h.replace("</style>", f"{CSS_BASE}\n</style>")

def _format_nav(nav_html: str, phone: str) -> str:
    # `site_engine` produces: '  <nav aria-label="Primary">\n    <a href="index.html">Home</a>...'
    # We replace the outer structure to include the brand and phone CTA
    # The actual semantic links are kept
    links_match = re.search(r'<nav[^>]*>(.*?)</nav>', nav_html, re.S)
    if links_match:
        links = links_match.group(1).strip()
    else:
        links = nav_html
    
    # Extract just digits for tel
    tel_digits = "".join(c for c in phone if c.isdigit() or c == "+")
    if not tel_digits.startswith("+"):
        tel_digits = "+" + tel_digits
        
    return f"""
<header class="site">
  <div class="wrap bar">
    <div class="brand">Your <span>Business</span></div>
    <nav class="primary" aria-label="Primary">
      {links}
      <a class="call-btn" href="tel:{tel_digits}">Call {phone}</a>
    </nav>
  </div>
</header>
"""

def _format_footer(footer_html: str, blocks: dict) -> str:
    return footer_html

def render_index(facts, base_url, theme, blocks) -> str:
    head = _apply_css(blocks["head"], theme)
    nav = _format_nav(blocks["nav"], facts.telephone)
    footer = _format_footer(blocks["footer"], blocks)
    
    # We use facts directly for layout content to match the mockup structure while
    # passing the audit's structure requirements.
    # The audit wants: 1) article with h1, 2) p1_html, 3) p2_html, 4) services, 5) FAQ
    # We wrap them in divs.
    
    # Fix brand in nav:
    nav = nav.replace("Your <span>Business</span>", f"{facts.business_name}")
    
    html = [head, "<body>", '  <a href="#main" class="skip">Skip to content</a>', nav, '  <main id="main">', '    <article>']
    
    # Hero (wraps h1 and p1)
    html.append('<div class="wrap"><section class="hero">')
    # The H1 must be exactly what is in blocks["title"] or close, but let's just emit the original h1 block
    html.append(f'<h1>{facts.business_name} in {facts.locality}</h1>')
    html.append(blocks["p1_html"])
    html.append(blocks["p2_html"])
    if blocks.get("rating_html"):
        html.append(blocks["rating_html"])
    html.append('</section></div>')

    # Services
    html.append('<div class="wrap">')
    html.append(blocks["services_block"].replace('<h2>', '<div class="section-head"><div class="k">What we do</div><h2>').replace('</h2>', '</h2></div>').replace('<ul>', '<div class="cards">').replace('</ul>', '</div>').replace('<li>', '<article class="card">').replace('</li>', '</article>'))
    html.append('</div>')

    # Trust band (real rating + service-area count, already computed for
    # JSON-LD -- 2026-08-20, never rendered anywhere visible until now)
    if blocks.get("stats_band"):
        html.append('<div class="wrap">')
        html.append(blocks["stats_band"])
        html.append('</div>')

    # Areas
    if blocks["areas_block"]:
        html.append('<div class="wrap">')
        html.append(blocks["areas_block"].replace('<h2>', '<div class="section-head"><div class="k">Where we serve</div><h2>').replace('</h2>', '</h2></div>').replace('<ul>', '<div class="chips">').replace('</ul>', '</div>').replace('<li>', '<span class="chip">').replace('</li>', '</span>'))
        html.append('</div>')

    # Location + hours (real NAP + a real directions link, no map embed --
    # no maps API key exists anywhere in site generation)
    if blocks.get("location_html"):
        html.append('<div class="wrap">')
        html.append(blocks["location_html"])
        html.append('</div>')

    html.append(blocks["about_block"])
    
    if blocks["faq_block"]:
        html.append('<div class="wrap">')
        html.append(blocks["faq_block"].replace('<section ', '<section class="faq-sec" '))
        html.append('</div>')
        
    html.append('    </article>')
    html.append('  </main>')
    html.append(footer)
    html.append(blocks["cookie"])
    html.append('</body></html>')
    
    return "\n".join(html)

def render_service(facts, base_url, theme, blocks) -> str:
    head = _apply_css(blocks["head"], theme)
    nav = _format_nav(blocks["nav"], facts.telephone)
    footer = _format_footer(blocks["footer"], blocks)
    nav = nav.replace("Your <span>Business</span>", f"{facts.business_name}")
    
    html = [head, "<body>", '  <a href="#main" class="skip">Skip to content</a>', nav, '  <main id="main">', '    <article class="wrap" style="padding:60px 24px">']
    html.append(blocks["content"])
    html.append('    </article>')
    html.append('  </main>')
    html.append(footer)
    html.append(blocks["cookie"])
    html.append('</body></html>')
    return "\n".join(html)

def render_about(facts, base_url, theme, blocks) -> str:
    return render_service(facts, base_url, theme, blocks)

def render_privacy(facts, base_url, theme, blocks) -> str:
    return render_service(facts, base_url, theme, blocks)

TemplateEditorialMinimal = Template(
    "Editorial Minimal",
    render_index, render_service, render_about, render_privacy
)
