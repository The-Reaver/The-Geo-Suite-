from . import Template, _inject_css, _wrap_h2, _footer_class, _wrap_faq, _esc
import re

# Site Generator robustness push, Slice C.2 (2026-08-21): the first of two
# new templates added this round, per the operator's explicit correction
# that the design library needs to be "vast." Editorial Minimal, Split
# Modern, and Bold Cinematic all put every trust signal (rating, hours,
# location) inline in the page flow. Trust Panel is a genuinely different
# information architecture, not just a palette/font swap: a persistent
# sidebar groups every real, already-computed trust fact (rating, review
# count, service-area count, address, hours) into one place a visitor can
# scan without reading the whole page -- a real structural difference,
# same "why does this template exist" bar Bold Cinematic's full-bleed
# dark hero and Split Modern's side-by-side hero already set.
CSS_BASE = """
  *{box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);line-height:1.65;font-size:17px;-webkit-font-smoothing:antialiased}
  a{color:var(--accent);text-decoration:none}
  a:hover{text-decoration:underline}
  .wrap{max-width:var(--maxw);margin:0 auto;padding:0 28px}
  h1,h2,h3{line-height:1.25;letter-spacing:-.01em;margin:0}

  header.clinic{position:sticky;top:0;z-index:20;background:var(--glass);backdrop-filter:saturate(180%) blur(12px);border-bottom:1px solid var(--line)}
  .bar{display:flex;align-items:center;justify-content:space-between;height:72px}
  .brand{font-family:var(--disp);font-size:20px;font-weight:600;color:var(--ink);display:flex;align-items:center;gap:10px}
  .brand .mark{width:32px;height:32px;border-radius:9px;background:var(--grad)}
  nav.primary{display:flex;gap:24px;align-items:center}
  nav.primary a{color:var(--muted);font-size:15px;font-weight:500}
  nav.primary a:hover{color:var(--ink);text-decoration:none}
  /* 2026-08-21, Opus 5 review: the call-pill link is rendered inside
     nav.primary (it's one of the nav CTA links), so the plain
     nav.primary anchor rule and its own hover rule (same specificity as
     the two below, but declared LATER in the cascade) were silently
     winning the `color` property on every state -- this template was
     the only one of the 9 whose nav CTA didn't mark color !important,
     so its "fix" below never actually rendered. Resting state really
     showed var(--muted) at the plain nav link's own 15px/500, not
     accent-dark/14px/600; hovering showed var(--ink) on
     var(--accent-dark), which is <=1.22:1 on 19 of 20 palettes and
     exactly 1.00:1 (ink and accent_dark are the same hex) on Navy --
     invisible text, strictly worse than the pre-fix var(--ink)-on-
     var(--accent) it replaced. !important on both matches every other
     template's own nav CTA pattern -- each already marks its CTA's
     color !important for exactly this reason. */
  .call-pill{display:inline-flex;align-items:center;gap:8px;background:var(--accent-soft);color:var(--accent-dark) !important;padding:10px 18px;border-radius:999px;font-weight:600;font-size:14px;min-height:40px}
  .call-pill:hover{background:var(--accent-dark);color:#fff !important;text-decoration:none}
  @media(max-width:860px){nav.primary a:not(.call-pill){display:none}}

  .layout{display:grid;grid-template-columns:1fr 320px;gap:52px;padding:56px 0}
  @media(max-width:900px){.layout{grid-template-columns:1fr}}

  .hero h1{font-size:clamp(32px,4.6vw,46px);font-family:var(--disp);max-width:18ch}
  .hero .lede{color:var(--muted);font-size:19px;max-width:52ch;margin-top:16px}

  .sidebar{display:flex;flex-direction:column;gap:18px}
  @media(min-width:901px){.sidebar{position:sticky;top:96px;align-self:start}}
  .fact-card{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:24px;box-shadow:var(--shadow-sm)}
  .fact-card h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-bottom:14px}

  .rating{display:inline-flex;align-items:center;gap:9px;color:var(--muted);font-size:15px}
  .stars{color:var(--gold);letter-spacing:2px;font-size:16px}
  .band{background:var(--accent-soft);border-radius:12px;padding:16px 18px;margin-top:14px}
  .band h2{color:var(--accent-dark);font-size:13px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px}
  .band .sub{color:var(--ink);font-size:14px}
  address{font-style:normal;color:var(--ink);line-height:1.6;font-size:15px}
  .directions-link{display:inline-block;margin-top:8px;color:var(--accent);font-weight:600;font-size:15px}
  .hours-list{list-style:none;padding:0;margin:10px 0 0}
  .hours-list li{padding:3px 0;color:var(--muted);font-size:14px}

  section.block{padding:8px 0 40px}
  .section-head{margin-bottom:26px}
  .section-head .k{color:var(--accent);font-weight:700;font-size:13px;letter-spacing:.04em;text-transform:uppercase}
  .section-head h2{font-size:clamp(24px,3vw,30px);margin-top:8px;font-family:var(--disp)}

  .svc-list{border-top:1px solid var(--line)}
  .svc-row{padding:20px 0;border-bottom:1px solid var(--line);color:var(--ink);font-size:16px}

  .chips{display:flex;flex-wrap:wrap;gap:9px}
  .chip{background:var(--accent-soft);color:var(--accent-dark);border-radius:999px;padding:8px 15px;font-size:14px;font-weight:500}

  .faq{display:grid;gap:12px;max-width:760px}
  details{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:4px 22px}
  summary{cursor:pointer;font-weight:600;padding:17px 0;list-style:none;display:flex;justify-content:space-between;align-items:center;font-size:16px}
  summary::-webkit-details-marker{display:none}
  summary::after{content:"+";color:var(--accent);font-size:20px;font-weight:400}
  details[open] summary::after{content:"–"}
  details p{color:var(--muted);margin:0 0 16px}

  footer.clinic{background:var(--surface);border-top:1px solid var(--line);padding:44px 0 32px;margin-top:20px;font-size:14px;color:var(--muted)}
  footer.clinic a{color:var(--ink)}
  footer.clinic p,footer.clinic a{display:block;margin:0 0 8px}
  @media(max-width:900px){.sidebar{position:static}}
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
<header class="clinic">
  <div class="wrap bar">
    <div class="brand"><span class="mark" aria-hidden="true"></span>Your Business</div>
    <nav class="primary" aria-label="Primary">
      {links}
      <a class="call-pill" href="tel:{tel_digits}">Call {_esc(phone)}</a>
    </nav>
  </div>
</header>
"""


# 2026-08-21: _wrap_h2() moved to templates/__init__.py (shared) so a
# future new template can't reintroduce the id-attribute bug this fixed
# by copy-pasting the broken pattern instead of the fixed helper.

def _sidebar(blocks: dict) -> str:
    # Groups every real, already-computed trust fact (rating/stats/
    # location+hours) into one scannable panel instead of scattering them
    # through the page flow -- the whole point of this template. Each
    # piece is still independently gated exactly as it is everywhere else
    # (site_engine.py's own honesty gates, unchanged); this only changes
    # WHERE the same real-or-nothing content renders.
    cards = []
    if blocks.get("rating_html") or blocks.get("stats_band"):
        inner = (blocks.get("rating_html") or "") + (blocks.get("stats_band") or "")
        cards.append(f'<div class="fact-card"><h2>Reputation</h2>{inner}</div>')
    if blocks.get("location_html"):
        cards.append(f'<div class="fact-card">{blocks["location_html"]}</div>')
    if not cards:
        return ""
    return '<aside class="sidebar" aria-label="Business facts">' + "".join(cards) + "</aside>"


def render_index(facts, base_url, theme, blocks) -> str:
    head = _apply_css(blocks["head"], theme)
    nav = _format_nav(blocks["nav"], facts.telephone).replace("Your Business", _esc(facts.business_name))
    # 2026-08-21, Opus 5 review of Slice C.3: site_engine.py's _footer()
    # emits a classless <footer> -- footer.clinic{...} below never
    # matched anything without this.
    footer = _footer_class(blocks["footer"], "clinic")

    html = [head, "<body>", '  <a href="#main" class="skip">Skip to content</a>', nav, '  <main id="main">', '    <article>']

    html.append('<div class="wrap layout">')
    html.append('<div class="hero">')
    html.append(f'<h1>{_esc(facts.business_name)} in {_esc(facts.locality)}</h1>')
    html.append(blocks["p1_html"])
    html.append(blocks["p2_html"])
    html.append('</div>')
    sidebar = _sidebar(blocks)
    html.append(sidebar if sidebar else '<div></div>')
    html.append('</div>')

    html.append('<div class="wrap"><section class="block">')
    html.append(_wrap_h2(blocks["services_block"], "What we do")
        .replace('<ul>', '<div class="svc-list">')
        .replace('</ul>', '</div>')
        .replace('<li>', '<div class="svc-row">')
        .replace('</li>', '</div>')
    )
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
    html.append(_footer_class(blocks["footer"], "clinic"))
    html.append(blocks["cookie"])
    html.append('</body></html>')
    return "\n".join(html)


def render_about(facts, base_url, theme, blocks) -> str:
    return render_service(facts, base_url, theme, blocks)


def render_privacy(facts, base_url, theme, blocks) -> str:
    return render_service(facts, base_url, theme, blocks)


TemplateTrustPanel = Template("Trust Panel", render_index, render_service, render_about, render_privacy)
