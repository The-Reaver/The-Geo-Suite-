from . import Template, _inject_css, _footer_class, _wrap_faq
import re

# Site Generator robustness push, Slice C.2 (2026-08-21): the second of
# two new templates added this round, per the operator's explicit
# correction that the design library needs to be "vast." A genuinely
# different structural idea from all four existing templates: a narrow,
# single-column reading measure (like a magazine page, not a marketing
# landing page), an accent-bordered offset hero instead of a centered or
# split one, and a dotted-rule menu-style service list instead of cards
# or a grid. Style name, not an industry claim about THIS FILE's own
# copy -- section copy stays generic ("What we offer"/"Where we serve"),
# never authored as if it assumes a specific vertical, even though
# select_theme() (2026-08-21, industry-aware template selection) now
# does place this template in the Beauty/Salon and Food/Restaurant
# families specifically (plus the general fallback for anything else) --
# the two facts don't contradict: which businesses CAN land here is now
# industry-aware, but the words on the page still don't presume one.
CSS_BASE = """
  *{box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);line-height:1.65;font-size:17px;-webkit-font-smoothing:antialiased}
  a{color:var(--accent);text-decoration:none}
  a:hover{text-decoration:underline}
  .wrap{max-width:720px;margin:0 auto;padding:0 28px}
  h1,h2,h3{line-height:1.15;letter-spacing:-.01em;margin:0}

  header.boutique{padding:26px 0;border-bottom:1px solid var(--line)}
  .bar{display:flex;align-items:center;justify-content:space-between}
  .brand{font-family:var(--disp);font-size:21px;font-weight:600;color:var(--ink)}
  nav.primary{display:flex;gap:22px;align-items:center}
  nav.primary a{color:var(--muted);font-size:14px;font-weight:500;text-transform:uppercase;letter-spacing:.04em}
  nav.primary a:hover{color:var(--ink);text-decoration:none}
  .call-link{color:var(--accent) !important;font-weight:600}
  @media(max-width:640px){nav.primary a:not(.call-link){display:none}}

  .hero{border-left:4px solid var(--accent);padding:8px 0 8px 28px;margin:56px 0 48px}
  .hero h1{font-size:clamp(34px,6vw,54px);font-family:var(--disp);max-width:16ch}
  .hero .lede{font-size:19px;color:var(--muted);margin-top:16px}

  .rating{display:inline-flex;align-items:center;gap:9px;color:var(--muted);font-size:15px;margin-top:20px}
  .stars{color:var(--gold);letter-spacing:2px;font-size:16px}

  section.block{padding:40px 0}
  .kicker{color:var(--accent);font-weight:700;font-size:13px;letter-spacing:.06em;text-transform:uppercase;margin-bottom:14px}
  .block h2{font-size:clamp(24px,3.4vw,32px);font-family:var(--disp)}

  .menu-list{border-top:1px solid var(--line)}
  .menu-row{padding:20px 0;border-bottom:1px dotted var(--line);color:var(--ink);font-size:16px}

  .chips{display:flex;flex-wrap:wrap;gap:8px}
  .chip{border:1px solid var(--line);border-radius:4px;padding:7px 14px;font-size:14px;color:var(--ink)}

  .band{background:var(--accent);color:#fff;border-radius:8px;padding:32px 30px}
  /* 2026-08-21, Opus 5 review: white text on var(--accent) only clears
     WCAG's 3:1 floor (assert_wcag() in palettes.py), a valid bar only
     for large-scale text -- 22px here is under the 24px-regular
     threshold, so it needs an explicit bold weight to actually qualify
     as large text and legitimately rely on that 3:1 floor (2 of the 20
     palettes, Teal/Orange, are only 3.56-3.74:1, below the 4.5:1
     normal-text bar this size would otherwise need). */
  .band h2{color:#fff;font-family:var(--disp);font-size:22px;font-weight:700}
  /* Same reasoning: 16px was well under either large-text threshold.
     Solid white (not translucent, which only weakens contrast further)
     at 20px/700 genuinely clears it. */
  .band .sub{color:#fff;margin-top:8px;font-size:20px;font-weight:700}

  address{font-style:normal;color:var(--ink);line-height:1.6}
  .directions-link{display:inline-block;margin-top:10px;color:var(--accent);font-weight:600}
  .hours-list{list-style:none;padding:0;margin:12px 0 0}
  .hours-list li{padding:4px 0;color:var(--muted);font-size:15px}

  .faq{display:grid;gap:2px;border-top:1px solid var(--line)}
  details{border-bottom:1px solid var(--line);padding:4px 0}
  summary{cursor:pointer;font-weight:600;padding:18px 0;list-style:none;display:flex;justify-content:space-between;align-items:center;font-size:17px}
  summary::-webkit-details-marker{display:none}
  summary::after{content:"+";color:var(--accent);font-size:22px;font-weight:400}
  details[open] summary::after{content:"–"}
  details p{color:var(--muted);margin:0 0 18px}

  footer.boutique{border-top:1px solid var(--line);padding:44px 0;margin-top:20px;font-size:14px;color:var(--muted)}
  footer.boutique a{color:var(--ink)}
  footer.boutique p,footer.boutique a{display:block;margin:0 0 8px}
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
<header class="boutique">
  <div class="wrap bar">
    <div class="brand">Your Business</div>
    <nav class="primary" aria-label="Primary">
      {links}
      <a class="call-link" href="tel:{tel_digits}">Call {phone}</a>
    </nav>
  </div>
</header>
"""


def render_index(facts, base_url, theme, blocks) -> str:
    head = _apply_css(blocks["head"], theme)
    nav = _format_nav(blocks["nav"], facts.telephone).replace("Your Business", facts.business_name)
    # 2026-08-21, Opus 5 review of Slice C.3: site_engine.py's _footer()
    # emits a classless <footer> -- footer.boutique{...} below never
    # matched anything without this.
    footer = _footer_class(blocks["footer"], "boutique")

    html = [head, "<body>", '  <a href="#main" class="skip">Skip to content</a>', nav, '  <main id="main">', '    <article>']

    html.append('<div class="wrap"><div class="hero">')
    html.append(f'<h1>{facts.business_name} in {facts.locality}</h1>')
    html.append(blocks["p1_html"])
    html.append(blocks["p2_html"])
    if blocks.get("rating_html"):
        html.append(blocks["rating_html"])
    html.append('</div></div>')

    html.append('<div class="wrap"><section class="block">')
    html.append('<div class="kicker">What we offer</div>')
    html.append(blocks["services_block"]
        .replace('<ul>', '<div class="menu-list">')
        .replace('</ul>', '</div>')
        .replace('<li>', '<div class="menu-row">')
        .replace('</li>', '</div>')
    )
    html.append('</section></div>')

    if blocks.get("stats_band"):
        html.append('<div class="wrap"><section class="block">')
        html.append(blocks["stats_band"])
        html.append('</section></div>')

    if blocks["areas_block"]:
        html.append('<div class="wrap"><section class="block">')
        html.append('<div class="kicker">Where we serve</div>')
        html.append(blocks["areas_block"]
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
    nav = _format_nav(blocks["nav"], facts.telephone).replace("Your Business", facts.business_name)
    html = [head, "<body>", '  <a href="#main" class="skip">Skip to content</a>', nav,
            '  <main id="main">', '    <section class="wrap"><article>']
    html.append(blocks["content"])
    html.append('    </article></section>')
    html.append('  </main>')
    html.append(_footer_class(blocks["footer"], "boutique"))
    html.append(blocks["cookie"])
    html.append('</body></html>')
    return "\n".join(html)


def render_about(facts, base_url, theme, blocks) -> str:
    return render_service(facts, base_url, theme, blocks)


def render_privacy(facts, base_url, theme, blocks) -> str:
    return render_service(facts, base_url, theme, blocks)


TemplateBoutiqueEditorial = Template("Boutique Editorial", render_index, render_service, render_about, render_privacy)
