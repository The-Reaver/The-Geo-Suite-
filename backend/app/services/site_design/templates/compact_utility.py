from . import Template, _inject_css, _wrap_h2, _footer_class, _wrap_faq, _esc
import re

# Site Generator robustness push, Slice C.4 (2026-08-21): second of two
# new templates added this round, per the operator's explicit correction
# that the design library needs to be "vast." A genuinely different
# density/restraint from all seven existing templates, which are all
# spacious and decorative -- this one is a tight, utilitarian "spec
# sheet" feel: a smaller base type scale, hairline/dashed rules instead
# of cards or shadows, monospace-styled section labels, minimal color use
# outside the accent itself.
#
# Both lessons from the Opus 5 review of Slice C.2 applied from the
# start: uses the shared _wrap_h2() helper; .band uses no background
# fill at all (border rules only, ink-on-bg text), so it's safe by
# construction for every one of the 20 palettes regardless of accent
# value -- the same category of fix already proven for the accent-fill
# bands in Trust Panel/Framed Gallery/Directory Listing/Timeline Flow,
# just via a different, borderless-panel route.
CSS_BASE = """
  *{box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);line-height:1.5;font-size:15px;-webkit-font-smoothing:antialiased}
  a{color:var(--accent);text-decoration:none}
  a:hover{text-decoration:underline}
  .wrap{max-width:880px;margin:0 auto;padding:0 20px}
  h1,h2,h3{line-height:1.2;letter-spacing:-.005em;margin:0}

  header.utility{border-bottom:2px solid var(--ink);padding:14px 0}
  .bar{display:flex;align-items:center;justify-content:space-between}
  .brand{font-family:var(--disp);font-size:16px;font-weight:700;color:var(--ink);text-transform:uppercase;letter-spacing:.03em}
  nav.primary{display:flex;gap:16px;align-items:center}
  nav.primary a{color:var(--muted);font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.04em}
  nav.primary a:hover{color:var(--ink);text-decoration:none}
  .util-call{color:var(--accent) !important;font-weight:700}
  @media(max-width:640px){nav.primary a:not(.util-call){display:none}}

  .hero{padding:36px 0 24px;border-bottom:1px solid var(--line)}
  .hero h1{font-size:clamp(24px,3.6vw,34px);font-family:var(--disp);max-width:24ch}
  .hero .lede{color:var(--muted);font-size:15px;max-width:60ch;margin-top:10px}

  .rating{display:inline-flex;align-items:center;gap:7px;color:var(--muted);font-size:13px;margin-top:14px}
  .stars{color:var(--gold);letter-spacing:1px;font-size:14px}
  /* 2026-08-21, Opus 5 review of Slice 2: the original version separated
     items with a CSS-generated em-dash colored var(--line) -- the
     hairline token, ~1.08-1.21:1 contrast on every one of the 20
     palettes, effectively invisible. It was also exposed to screen
     readers in Chrome/Firefox (generated content isn't reliably stripped
     from the accessibility tree), so every item was announced with a
     leading dash nobody could see. Removed rather than re-colored --
     the flex gap alone already separates items visually, matching how
     every other template's chips separate without a text character. */
  .highlights{display:flex;flex-wrap:wrap;gap:6px 20px;padding:0;margin:12px 0 0}
  .highlights span{font-size:13px;color:var(--muted)}

  section.block{padding:22px 0;border-bottom:1px solid var(--line)}
  section.block:last-child{border-bottom:none}
  .section-head{margin-bottom:14px}
  .section-head .k{color:var(--accent);font-weight:700;font-size:11px;letter-spacing:.06em;text-transform:uppercase;font-family:monospace}
  .section-head h2{font-size:17px;margin-top:4px}

  .spec-rows{border-top:1px dashed var(--line)}
  .spec-row{padding:10px 0;border-bottom:1px dashed var(--line);color:var(--ink);font-size:14px}

  .chips{display:flex;flex-wrap:wrap;gap:6px}
  .chip{border:1px solid var(--line);padding:4px 10px;font-size:12px;color:var(--ink)}

  .band{border-top:2px solid var(--ink);border-bottom:2px solid var(--ink);padding:16px 0}
  .band h2{color:var(--ink);font-size:13px;text-transform:uppercase;letter-spacing:.04em;font-family:monospace}
  .band .sub{color:var(--muted);margin-top:4px;font-size:13px}

  address{font-style:normal;color:var(--ink);font-size:14px}
  .directions-link{display:inline-block;margin-top:6px;color:var(--accent);font-weight:600;font-size:13px}
  .hours-list{list-style:none;padding:0;margin:8px 0 0}
  .hours-list li{padding:2px 0;color:var(--muted);font-size:13px}

  .faq{display:grid;gap:0}
  details{border-bottom:1px dashed var(--line);padding:4px 0}
  details:last-child{border-bottom:none}
  summary{cursor:pointer;font-weight:600;padding:12px 0;list-style:none;display:flex;justify-content:space-between;align-items:center;font-size:14px}
  summary::-webkit-details-marker{display:none}
  summary::after{content:"+";color:var(--accent);font-size:16px;font-weight:400}
  details[open] summary::after{content:"–"}
  details p{color:var(--muted);margin:0 0 12px;font-size:13px}

  footer.utility{padding:24px 0 32px;font-size:12px;color:var(--muted)}
  footer.utility a{color:var(--ink)}
  footer.utility p,footer.utility a{display:block;margin:0 0 5px}
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
<header class="utility">
  <div class="wrap bar">
    <div class="brand">Your Business</div>
    <nav class="primary" aria-label="Primary">
      {links}
      <a class="util-call" href="tel:{tel_digits}">Call {_esc(phone)}</a>
    </nav>
  </div>
</header>
"""


def render_index(facts, base_url, theme, blocks) -> str:
    head = _apply_css(blocks["head"], theme)
    nav = _format_nav(blocks["nav"], facts.telephone).replace("Your Business", _esc(facts.business_name))
    # 2026-08-21, Opus 5 review of Slice C.3: site_engine.py's _footer()
    # emits a classless <footer> -- footer.utility{...} below never
    # matched anything without this.
    footer = _footer_class(blocks["footer"], "utility")

    html = [head, "<body>", '  <a href="#main" class="skip">Skip to content</a>', nav, '  <main id="main">', '    <article>']

    # 2026-08-21, Slice 2: p1_html stays in the hero; p2_html moves to its
    # own section right after (was two dense paragraphs stacked in the
    # tightest type scale of the 9 templates, reading especially dense).
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
        .replace('<ul>', '<div class="spec-rows">')
        .replace('</ul>', '</div>')
        .replace('<li>', '<div class="spec-row">')
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
    html.append(_footer_class(blocks["footer"], "utility"))
    html.append(blocks["cookie"])
    html.append('</body></html>')
    return "\n".join(html)


def render_about(facts, base_url, theme, blocks) -> str:
    return render_service(facts, base_url, theme, blocks)


def render_privacy(facts, base_url, theme, blocks) -> str:
    return render_service(facts, base_url, theme, blocks)


TemplateCompactUtility = Template("Compact Utility", render_index, render_service, render_about, render_privacy)
