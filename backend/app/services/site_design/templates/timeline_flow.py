from . import Template, _inject_css, _wrap_h2, _footer_class, _wrap_faq, _esc
import re

# Site Generator robustness push, Slice C.4 (2026-08-21): first of two new
# templates added this round, per the operator's explicit correction that
# the design library needs to be "vast." A genuinely different visual
# treatment for services from all seven existing templates (cards, grid
# cells, dotted menu rows, list-dot rows, bordered cells): a connected
# vertical timeline with numbered circles, using a real CSS counter
# (counter-reset/counter-increment) for the numbers -- not attempted via
# Python string substitution, which can't produce a real per-item
# incrementing value from the uniform blocks-dict content every template
# receives.
#
# Both lessons from the Opus 5 review of Slice C.2 applied from the
# start: uses the shared _wrap_h2() helper (never a hand-rolled literal
# .replace('<h2>', ...)); the numbered-circle badges use the same
# provably-safe accent-soft/accent-dark pairing already established in
# Trust Panel/Framed Gallery/Directory Listing, not white text on
# var(--accent) at a size too small to qualify as WCAG large text.
CSS_BASE = """
  *{box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);line-height:1.6;font-size:17px;-webkit-font-smoothing:antialiased}
  a{color:var(--accent);text-decoration:none}
  a:hover{text-decoration:underline}
  .wrap{max-width:var(--maxw);margin:0 auto;padding:0 24px}
  h1,h2,h3{line-height:1.2;letter-spacing:-.01em;margin:0}

  header.timeline-top{position:sticky;top:0;z-index:20;background:var(--glass);backdrop-filter:saturate(180%) blur(10px);border-bottom:1px solid var(--line)}
  .bar{display:flex;align-items:center;justify-content:space-between;height:68px}
  .brand{font-family:var(--disp);font-size:19px;font-weight:700;color:var(--ink)}
  nav.primary{display:flex;gap:24px;align-items:center}
  nav.primary a{color:var(--muted);font-size:15px;font-weight:500}
  nav.primary a:hover{color:var(--ink);text-decoration:none}
  /* 2026-08-21, Opus 5 review of Slice C.3: white text on var(--accent)
     at 14px only clears WCAG's 3:1 floor -- 2 of 20 palettes genuinely
     failed the real 4.5:1 bar this size needed. Switched to the
     accent-soft/accent-dark pairing already proven safe at any size. */
  .tl-call{display:inline-flex;align-items:center;gap:8px;background:var(--accent-soft);color:var(--accent-dark) !important;padding:10px 18px;border-radius:8px;font-weight:600;font-size:14px;min-height:40px}
  /* 2026-08-21, Opus 5 review: white on var(--accent) at .tl-call's own
     inherited 14px/600 fails 4.5:1 for 2 of 20 palettes. accent-dark is
     safe by construction at any size (>=5.18:1 on every palette). */
  .tl-call:hover{background:var(--accent-dark);color:#fff !important;text-decoration:none}
  @media(max-width:720px){nav.primary a:not(.tl-call){display:none}}

  .hero{padding:64px 0 48px;text-align:center}
  .hero h1{font-size:clamp(30px,4.8vw,48px);font-family:var(--disp);max-width:18ch;margin:0 auto}
  .hero .lede{color:var(--muted);font-size:19px;max-width:52ch;margin:16px auto 0}

  .rating{display:inline-flex;align-items:center;gap:9px;color:var(--muted);font-size:15px;margin-top:22px;justify-content:center}
  .stars{color:var(--gold);letter-spacing:2px;font-size:16px}
  .highlights{display:flex;flex-wrap:wrap;justify-content:center;gap:10px;padding:0;margin:22px 0 0}
  .highlights span{background:var(--accent-soft);color:var(--accent-dark);font-size:14px;font-weight:600;padding:8px 14px;border-radius:999px}

  section.block{padding:44px 0}
  .section-head{margin-bottom:32px}
  .section-head .k{color:var(--accent);font-weight:700;font-size:13px;letter-spacing:.04em;text-transform:uppercase}
  .section-head h2{font-size:clamp(24px,3.2vw,32px);margin-top:8px;font-family:var(--disp)}

  .timeline{border-left:2px solid var(--line);margin-left:14px}
  .timeline-item{position:relative;padding:0 0 32px 30px;color:var(--ink);font-size:16px}
  .timeline-item:last-child{padding-bottom:0}

  .chips{display:flex;flex-wrap:wrap;gap:9px}
  .chip{background:var(--surface);border:1px solid var(--line);border-radius:999px;padding:8px 15px;color:var(--ink);font-size:14px;font-weight:500}

  .band{background:var(--accent-soft);border-radius:16px;padding:32px}
  .band h2{color:var(--accent-dark);font-size:20px;font-family:var(--disp)}
  .band .sub{color:var(--ink);margin-top:8px;font-size:15px}

  address{font-style:normal;color:var(--ink);line-height:1.6}
  .directions-link{display:inline-block;margin-top:10px;color:var(--accent);font-weight:600}
  .hours-list{list-style:none;padding:0;margin:12px 0 0}
  .hours-list li{padding:4px 0;color:var(--muted);font-size:15px}

  .faq{display:grid;gap:12px;max-width:760px}
  details{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:4px 22px}
  summary{cursor:pointer;font-weight:600;padding:17px 0;list-style:none;display:flex;justify-content:space-between;align-items:center;font-size:16px}
  summary::-webkit-details-marker{display:none}
  summary::after{content:"+";color:var(--accent);font-size:20px;font-weight:400}
  details[open] summary::after{content:"–"}
  details p{color:var(--muted);margin:0 0 16px}

  footer.timeline-bottom{background:var(--surface);border-top:1px solid var(--line);padding:44px 0 32px;margin-top:20px;font-size:14px;color:var(--muted)}
  footer.timeline-bottom a{color:var(--ink)}
  footer.timeline-bottom p,footer.timeline-bottom a{display:block;margin:0 0 8px}
"""

# 2026-08-21: a real CSS counter, not a Python-side attempt to split
# "Name: Description" text runs (which have no tag boundary between
# them) into numbered pieces -- the same constraint every prior template
# respects by wrapping each <li> uniformly rather than trying to inject
# per-item content. counter-reset/counter-increment scope entirely to
# the .timeline element these two rules are injected next to.
_COUNTER_CSS = (
    '<style>.timeline{counter-reset:tl-step}'
    '.timeline-item{counter-increment:tl-step}'
    '.timeline-item::before{content:counter(tl-step);position:absolute;left:-17px;top:-2px;'
    'width:30px;height:30px;border-radius:50%;background:var(--accent-soft);color:var(--accent-dark);'
    'display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;'
    'border:3px solid var(--bg)}</style>'
)


def _apply_css(head_html: str, theme) -> str:
    h = _inject_css(head_html, theme.palette, theme.typography)
    h = h.replace("</style>", f"{CSS_BASE}\n</style>")
    return h.replace("</head>", f"{_COUNTER_CSS}\n</head>")


def _format_nav(nav_html: str, phone: str) -> str:
    links_match = re.search(r'<nav[^>]*>(.*?)</nav>', nav_html, re.S)
    links = links_match.group(1).strip() if links_match else nav_html
    tel_digits = "".join(c for c in phone if c.isdigit() or c == "+")
    if not tel_digits.startswith("+"):
        tel_digits = "+" + tel_digits
    return f"""
<header class="timeline-top">
  <div class="wrap bar">
    <div class="brand">Your Business</div>
    <nav class="primary" aria-label="Primary">
      {links}
      <a class="tl-call" href="tel:{tel_digits}">Call {_esc(phone)}</a>
    </nav>
  </div>
</header>
"""


def render_index(facts, base_url, theme, blocks) -> str:
    head = _apply_css(blocks["head"], theme)
    nav = _format_nav(blocks["nav"], facts.telephone).replace("Your Business", _esc(facts.business_name))
    # 2026-08-21, Opus 5 review of Slice C.3: site_engine.py's _footer()
    # emits a classless <footer> -- footer.timeline-bottom{...} below
    # never matched anything without this.
    footer = _footer_class(blocks["footer"], "timeline-bottom")

    html = [head, "<body>", '  <a href="#main" class="skip">Skip to content</a>', nav, '  <main id="main">', '    <article>']

    # 2026-08-21, Slice 2: p1_html stays in the hero; p2_html moves to its
    # own section right after (was two dense paragraphs stacked centered
    # above the timeline).
    html.append('<div class="wrap"><div class="hero">')
    html.append(f'<h1>{_esc(facts.business_name)} in {_esc(facts.locality)}</h1>')
    html.append(blocks["p1_html"])
    if blocks.get("rating_html"):
        html.append(blocks["rating_html"])
    if blocks.get("highlights_html"):
        html.append(blocks["highlights_html"])
    html.append('</div></div>')

    if blocks.get("p2_html"):
        html.append('<div class="wrap"><section aria-label="Our approach">')
        html.append(blocks["p2_html"])
        html.append('</section></div>')

    html.append('<div class="wrap"><section class="block">')
    html.append(_wrap_h2(blocks["services_block"], "What we do")
        .replace('<ul>', '<div class="timeline">')
        .replace('</ul>', '</div>')
        .replace('<li>', '<div class="timeline-item">')
        .replace('</li>', '</div>')
    )
    html.append('</section></div>')

    if blocks.get("stats_band"):
        html.append('<div class="wrap"><section class="block">')
        html.append(blocks["stats_band"])
        html.append('</section></div>')

    if blocks["areas_block"]:
        html.append('<div class="wrap"><section class="block">')
        html.append(_wrap_h2(blocks["areas_block"], "Where we serve")
            .replace('<ul>', '<div class="chips">')
            .replace('</ul>', '</div>')
            .replace('<li>', '<span class="chip">')
            .replace('</li>', '</span>')
        )
        html.append('</section></div>')

    if blocks.get("location_html"):
        html.append('<div class="wrap"><section class="block">')
        html.append(blocks["location_html"])
        html.append('</section></div>')

    html.append('<div class="wrap"><section class="block">')
    html.append(blocks["about_block"])
    html.append('</section></div>')

    if blocks["faq_block"]:
        html.append('<div class="wrap"><section class="block">')
        html.append(_wrap_faq(blocks["faq_block"]))
        html.append('</section></div>')

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
    html.append(_footer_class(blocks["footer"], "timeline-bottom"))
    html.append(blocks["cookie"])
    html.append('</body></html>')
    return "\n".join(html)


def render_about(facts, base_url, theme, blocks) -> str:
    return render_service(facts, base_url, theme, blocks)


def render_privacy(facts, base_url, theme, blocks) -> str:
    return render_service(facts, base_url, theme, blocks)


TemplateTimelineFlow = Template("Timeline Flow", render_index, render_service, render_about, render_privacy)
