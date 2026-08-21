from . import Template, _inject_css, _wrap_h2, _footer_class, _wrap_faq, _esc
import re

# Site Generator robustness push, Slice C.3 (2026-08-21): first of two new
# templates added this round, per the operator's explicit correction that
# the design library needs to be "vast." A genuinely different visual
# language from all five existing templates: every one of them uses
# shadow/color-fill for depth (cards, gradients, dark bands); this one
# uses a thick bordered "frame" around the whole page's content instead,
# with border-rule dividers between sections rather than spacing/shadow.
# 2026-08-21, Opus 5 review of Slice C.2 caught two real defect classes
# in the previous two templates -- both deliberately avoided here from
# the start: (1) uses the shared _wrap_h2() helper (not a hand-rolled
# literal .replace('<h2>', ...)) so it can't silently drop the
# id="services" anchor target; (2) .band never puts white text on
# var(--accent) -- it's an outlined box with dark text instead, safe by
# construction regardless of which of the 20 palettes is selected.
CSS_BASE = """
  *{box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{margin:0;background:var(--surface);color:var(--ink);font-family:var(--font);line-height:1.6;font-size:17px;-webkit-font-smoothing:antialiased}
  a{color:var(--accent);text-decoration:none}
  a:hover{text-decoration:underline}
  .wrap{max-width:var(--maxw);margin:0 auto;padding:0 24px}
  h1,h2,h3{line-height:1.2;letter-spacing:-.01em;margin:0}

  header.frame-top{padding:22px 0}
  .bar{display:flex;align-items:center;justify-content:space-between}
  .brand{font-family:var(--disp);font-size:19px;font-weight:700;color:var(--ink)}
  nav.primary{display:flex;gap:24px;align-items:center}
  nav.primary a{color:var(--muted);font-size:14px;font-weight:600;text-transform:uppercase;letter-spacing:.03em}
  nav.primary a:hover{color:var(--ink);text-decoration:none}
  .frame-call{border:2px solid var(--ink);color:var(--ink) !important;padding:9px 16px;font-weight:700;font-size:13px;text-transform:uppercase;letter-spacing:.03em}
  .frame-call:hover{background:var(--ink);color:var(--surface) !important;text-decoration:none}
  @media(max-width:720px){nav.primary a:not(.frame-call){display:none}}

  .frame{border:3px solid var(--ink);margin:0 24px 40px}
  @media(max-width:760px){.frame{margin:0 12px 32px}}

  .hero{padding:64px 40px;text-align:center;border-bottom:3px solid var(--ink)}
  .hero h1{font-size:clamp(30px,4.6vw,46px);font-family:var(--disp);max-width:20ch;margin:0 auto}
  .hero .lede{color:var(--muted);font-size:18px;max-width:52ch;margin:18px auto 0}
  @media(max-width:640px){.hero{padding:44px 22px}}

  .rating{display:inline-flex;align-items:center;gap:9px;color:var(--muted);font-size:15px;margin-top:22px;justify-content:center}
  .stars{color:var(--gold);letter-spacing:2px;font-size:16px}

  section.block{padding:36px 40px;border-bottom:3px solid var(--ink)}
  section.block:last-child{border-bottom:none}
  @media(max-width:640px){section.block{padding:28px 22px}}
  .section-head{margin-bottom:24px}
  .section-head .k{color:var(--accent);font-weight:700;font-size:13px;letter-spacing:.05em;text-transform:uppercase}
  .section-head h2{font-size:clamp(22px,3vw,28px);margin-top:8px;font-family:var(--disp)}

  .grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));border-top:1px solid var(--line);border-left:1px solid var(--line)}
  .cell{border-right:1px solid var(--line);border-bottom:1px solid var(--line);padding:22px}
  .cell:hover{background:var(--accent-soft)}

  .chips{display:flex;flex-wrap:wrap;gap:8px}
  .chip{border:1px solid var(--ink);padding:7px 14px;font-size:14px;color:var(--ink)}

  .band{border:3px solid var(--accent);padding:32px}
  .band h2{color:var(--accent-dark);font-size:22px;font-family:var(--disp)}
  .band .sub{color:var(--ink);margin-top:8px;font-size:16px}

  address{font-style:normal;color:var(--ink);line-height:1.6}
  .directions-link{display:inline-block;margin-top:10px;color:var(--accent);font-weight:700}
  .hours-list{list-style:none;padding:0;margin:12px 0 0}
  .hours-list li{padding:4px 0;color:var(--muted);font-size:15px}

  .faq{display:grid;gap:0}
  details{border-bottom:1px solid var(--line);padding:4px 0}
  details:last-child{border-bottom:none}
  summary{cursor:pointer;font-weight:700;padding:18px 0;list-style:none;display:flex;justify-content:space-between;align-items:center;font-size:16px}
  summary::-webkit-details-marker{display:none}
  summary::after{content:"+";color:var(--accent);font-size:20px;font-weight:400}
  details[open] summary::after{content:"–"}
  details p{color:var(--muted);margin:0 0 16px}

  footer.frame-bottom{padding:32px 0;font-size:14px;color:var(--muted)}
  footer.frame-bottom a{color:var(--ink)}
  footer.frame-bottom p,footer.frame-bottom a{display:block;margin:0 0 8px}
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
<header class="frame-top">
  <div class="wrap bar">
    <div class="brand">Your Business</div>
    <nav class="primary" aria-label="Primary">
      {links}
      <a class="frame-call" href="tel:{tel_digits}">Call {_esc(phone)}</a>
    </nav>
  </div>
</header>
"""


def render_index(facts, base_url, theme, blocks) -> str:
    head = _apply_css(blocks["head"], theme)
    nav = _format_nav(blocks["nav"], facts.telephone).replace("Your Business", _esc(facts.business_name))
    # 2026-08-21, Opus 5 review of Slice C.3: site_engine.py's _footer()
    # emits a classless <footer> -- footer.frame-bottom{...} below never
    # matched anything without this.
    footer = _footer_class(blocks["footer"], "frame-bottom")

    html = [head, "<body>", '  <a href="#main" class="skip">Skip to content</a>', nav, '  <main id="main">', '    <article>']

    html.append('<div class="wrap"><div class="frame">')

    html.append('<div class="hero">')
    html.append(f'<h1>{_esc(facts.business_name)} in {_esc(facts.locality)}</h1>')
    html.append(blocks["p1_html"])
    html.append(blocks["p2_html"])
    if blocks.get("rating_html"):
        html.append(blocks["rating_html"])
    html.append('</div>')

    html.append('<section class="block">')
    html.append(_wrap_h2(blocks["services_block"], "What we do")
        .replace('<ul>', '<div class="grid2">')
        .replace('</ul>', '</div>')
        .replace('<li>', '<div class="cell">')
        .replace('</li>', '</div>')
    )
    html.append('</section>')

    if blocks.get("stats_band"):
        html.append('<section class="block">')
        html.append(blocks["stats_band"])
        html.append('</section>')

    if blocks["areas_block"]:
        html.append('<section class="block">')
        html.append(_wrap_h2(blocks["areas_block"], "Where we serve")
            .replace('<ul>', '<div class="chips">')
            .replace('</ul>', '</div>')
            .replace('<li>', '<span class="chip">')
            .replace('</li>', '</span>')
        )
        html.append('</section>')

    if blocks.get("location_html"):
        html.append('<section class="block">')
        html.append(blocks["location_html"])
        html.append('</section>')

    html.append('<section class="block">')
    html.append(blocks["about_block"])
    html.append('</section>')

    if blocks["faq_block"]:
        html.append('<section class="block">')
        html.append(_wrap_faq(blocks["faq_block"]))
        html.append('</section>')

    html.append('</div></div>')

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
            '  <main id="main">', '    <div class="wrap"><div class="frame"><section class="block"><article>']
    html.append(blocks["content"])
    html.append('    </article></section></div></div>')
    html.append('  </main>')
    html.append(_footer_class(blocks["footer"], "frame-bottom"))
    html.append(blocks["cookie"])
    html.append('</body></html>')
    return "\n".join(html)


def render_about(facts, base_url, theme, blocks) -> str:
    return render_service(facts, base_url, theme, blocks)


def render_privacy(facts, base_url, theme, blocks) -> str:
    return render_service(facts, base_url, theme, blocks)


TemplateFramedGallery = Template("Framed Gallery", render_index, render_service, render_about, render_privacy)
