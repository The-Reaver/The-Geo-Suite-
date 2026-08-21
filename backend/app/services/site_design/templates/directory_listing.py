from . import Template, _inject_css, _wrap_h2
import re

# Site Generator robustness push, Slice C.3 (2026-08-21): second of two
# new templates added this round, per the operator's explicit correction
# that the design library needs to be "vast." Inspired by local-business
# directory listings: a compact "at a glance" strip surfaces the real
# rating and location/hours facts right under the hero instead of
# scattering them through the page (a different structural choice than
# Trust Panel's sidebar -- inline and near the top, not persistent), a
# compact dot-list for services instead of cards/grid, and a real,
# functional element none of the other five templates have -- a sticky
# mobile "Call now" bar fixed to the bottom of the viewport on small
# screens, where a header call button is easy to scroll past.
#
# Same two lessons from the Opus 5 review of Slice C.2, applied from the
# start: uses the shared _wrap_h2() helper (never a hand-rolled literal
# .replace('<h2>', ...)) so the id="services" anchor target can't be
# silently dropped, and .band never puts text directly on var(--accent)
# -- it's a light accent-soft tint with dark text, the same
# provably-safe pattern Trust Panel already uses.
CSS_BASE = """
  *{box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);line-height:1.6;font-size:16px;-webkit-font-smoothing:antialiased}
  a{color:var(--accent);text-decoration:none}
  a:hover{text-decoration:underline}
  .wrap{max-width:960px;margin:0 auto;padding:0 24px}
  h1,h2,h3{line-height:1.2;letter-spacing:-.01em;margin:0}

  header.directory{background:var(--surface);border-bottom:1px solid var(--line)}
  .bar{display:flex;align-items:center;justify-content:space-between;height:64px}
  .brand{font-family:var(--disp);font-size:18px;font-weight:700;color:var(--ink)}
  nav.primary{display:flex;gap:20px;align-items:center}
  nav.primary a{color:var(--muted);font-size:14px;font-weight:500}
  nav.primary a:hover{color:var(--ink);text-decoration:none}
  .dir-call{display:inline-flex;align-items:center;gap:6px;background:var(--accent);color:#fff !important;padding:9px 16px;border-radius:8px;font-weight:600;font-size:14px}
  .dir-call:hover{background:var(--accent-dark);text-decoration:none}
  @media(max-width:760px){nav.primary a:not(.dir-call){display:none}}

  .hero{padding:44px 0 0}
  .hero h1{font-size:clamp(28px,4.4vw,40px);font-family:var(--disp);max-width:20ch}
  .hero .lede{color:var(--muted);font-size:17px;max-width:56ch;margin-top:14px}

  .glance{display:flex;flex-wrap:wrap;gap:24px;padding:20px 22px;background:var(--surface);border:1px solid var(--line);border-radius:12px;margin-top:24px;margin-bottom:8px}
  .glance > *{flex:1 1 220px;min-width:220px}
  .glance h2{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin-bottom:8px}
  .glance .rating{margin-top:0}
  .glance address{font-size:14px}
  .glance .directions-link{font-size:14px}
  .glance .hours-list li{font-size:13px}

  .rating{display:inline-flex;align-items:center;gap:8px;color:var(--muted);font-size:14px}
  .stars{color:var(--gold);letter-spacing:1px;font-size:15px}

  section.block{padding:32px 0}
  .section-head{margin-bottom:20px}
  .section-head .k{color:var(--accent);font-weight:700;font-size:12px;letter-spacing:.04em;text-transform:uppercase}
  .section-head h2{font-size:clamp(20px,2.6vw,26px);margin-top:6px;font-family:var(--disp)}

  .list-rows{border-top:1px solid var(--line)}
  .list-row{display:flex;gap:14px;align-items:flex-start;padding:16px 0;border-bottom:1px solid var(--line)}
  .list-row .dot{width:8px;height:8px;border-radius:50%;background:var(--accent);margin-top:9px;flex-shrink:0}
  .list-row .txt{color:var(--ink);font-size:15px}

  .chips{display:flex;flex-wrap:wrap;gap:8px}
  .chip{background:var(--accent-soft);color:var(--accent-dark);border-radius:6px;padding:6px 12px;font-size:13px;font-weight:600}

  .band{background:var(--accent-soft);border-radius:12px;padding:24px 26px}
  .band h2{color:var(--accent-dark);font-size:15px;text-transform:uppercase;letter-spacing:.04em;margin-bottom:6px}
  .band .sub{color:var(--ink);font-size:15px}

  address{font-style:normal;color:var(--ink)}
  .directions-link{display:inline-block;margin-top:10px;color:var(--accent);font-weight:600}
  .hours-list{list-style:none;padding:0;margin:10px 0 0}
  .hours-list li{padding:3px 0;color:var(--muted)}

  .faq{display:grid;gap:10px;max-width:760px}
  details{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:4px 18px}
  summary{cursor:pointer;font-weight:600;padding:15px 0;list-style:none;display:flex;justify-content:space-between;align-items:center;font-size:15px}
  summary::-webkit-details-marker{display:none}
  summary::after{content:"+";color:var(--accent);font-size:19px;font-weight:400}
  details[open] summary::after{content:"–"}
  details p{color:var(--muted);margin:0 0 14px;font-size:14px}

  footer.directory{background:var(--surface);border-top:1px solid var(--line);padding:36px 0 40px;margin-top:16px;font-size:13px;color:var(--muted)}
  footer.directory a{color:var(--ink)}
  footer.directory p,footer.directory a{display:block;margin:0 0 6px}

  .mobile-call-bar{display:none}
  @media(max-width:640px){
    .mobile-call-bar{display:flex;position:fixed;left:0;right:0;bottom:0;z-index:40;background:var(--accent);padding:12px 20px;align-items:center;justify-content:center;box-shadow:0 -4px 12px rgba(0,0,0,.12)}
    .mobile-call-bar a{color:#fff !important;font-weight:700;font-size:16px;text-decoration:none}
    footer.directory{padding-bottom:88px}
  }
"""


def _apply_css(head_html: str, theme) -> str:
    h = _inject_css(head_html, theme.palette, theme.typography)
    return h.replace("</style>", f"{CSS_BASE}\n</style>")


def _tel_href(phone: str) -> str:
    tel_digits = "".join(c for c in phone if c.isdigit() or c == "+")
    if not tel_digits.startswith("+"):
        tel_digits = "+" + tel_digits
    return tel_digits


def _format_nav(nav_html: str, phone: str) -> str:
    links_match = re.search(r'<nav[^>]*>(.*?)</nav>', nav_html, re.S)
    links = links_match.group(1).strip() if links_match else nav_html
    tel_href = _tel_href(phone)
    return f"""
<header class="directory">
  <div class="wrap bar">
    <div class="brand">Your Business</div>
    <nav class="primary" aria-label="Primary">
      {links}
      <a class="dir-call" href="tel:{tel_href}">Call {phone}</a>
    </nav>
  </div>
</header>
"""


def _mobile_call_bar(phone: str) -> str:
    # A real, functional element the other five templates don't have --
    # not decorative. Hidden entirely above 640px (the header's own call
    # button already covers desktop) via the CSS media query, so it never
    # duplicates the header CTA on a screen large enough to see both.
    tel_href = _tel_href(phone)
    return f'<div class="mobile-call-bar"><a href="tel:{tel_href}">Call {phone}</a></div>'


def render_index(facts, base_url, theme, blocks) -> str:
    head = _apply_css(blocks["head"], theme)
    nav = _format_nav(blocks["nav"], facts.telephone).replace("Your Business", facts.business_name)
    footer = blocks["footer"]

    html = [head, "<body>", '  <a href="#main" class="skip">Skip to content</a>', nav, '  <main id="main">', '    <article>']

    html.append('<div class="wrap"><div class="hero">')
    html.append(f'<h1>{facts.business_name} in {facts.locality}</h1>')
    html.append(blocks["p1_html"])
    html.append(blocks["p2_html"])

    # "At a glance": the real rating and real location/hours facts,
    # placed near the top instead of scattered mid-page or tucked into a
    # sidebar -- both keep their own real headings, just styled compactly
    # (never hidden -- a hidden heading would drop real content from the
    # accessibility tree and page structure for no real gain).
    glance = (blocks.get("rating_html") or "") + (blocks.get("location_html") or "")
    if glance:
        html.append(f'<div class="glance">{glance}</div>')
    html.append('</div></div>')

    html.append('<div class="wrap"><section class="block">')
    html.append(_wrap_h2(blocks["services_block"], "What we do")
        .replace('<ul>', '<div class="list-rows">')
        .replace('</ul>', '</div>')
        .replace('<li>', '<div class="list-row"><span class="dot" aria-hidden="true"></span><span class="txt">')
        .replace('</li>', '</span></div>')
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

    html.append('<div class="wrap"><section class="block">')
    html.append(blocks["about_block"])
    html.append('</section></div>')

    if blocks["faq_block"]:
        html.append('<div class="wrap"><section class="block">')
        html.append(blocks["faq_block"].replace('<section ', '<section class="faq-sec" '))
        html.append('</section></div>')

    html.append('    </article>')
    html.append('  </main>')
    html.append(footer)
    html.append(_mobile_call_bar(facts.telephone))
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
    html.append(blocks["footer"])
    html.append(_mobile_call_bar(facts.telephone))
    html.append(blocks["cookie"])
    html.append('</body></html>')
    return "\n".join(html)


def render_about(facts, base_url, theme, blocks) -> str:
    return render_service(facts, base_url, theme, blocks)


def render_privacy(facts, base_url, theme, blocks) -> str:
    return render_service(facts, base_url, theme, blocks)


TemplateDirectoryListing = Template("Directory Listing", render_index, render_service, render_about, render_privacy)
