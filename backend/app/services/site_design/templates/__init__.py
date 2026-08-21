import collections
import html as _html
import re

Template = collections.namedtuple("Template", [
    "name",
    "render_index",
    "render_service",
    "render_about",
    "render_privacy"
])


def _esc(text) -> str:
    """Escape a facts field before it's interpolated into raw HTML.

    2026-08-21, Opus review of the Slice 1 prose commit flagged one
    unescaped business_name interpolation inside site_prose.py's <a> anchor
    text (fixed in site_engine.py's _esc_inline). Verifying that fix
    directly against a real XSS-payload business name surfaced a much
    larger, real, pre-existing, fleet-wide instance of the identical
    defect: every one of these 9 templates' own render_index()/render_about()
    /render_service()/render_privacy() interpolates facts.business_name (and
    most also facts.locality) DIRECTLY into <h1> and the nav-brand
    replacement with zero escaping -- a genuine stored-XSS vector via the
    business_name field on every generated homepage, present since these
    templates were first written, not something this session's prose work
    introduced. This shared helper (mirroring site_engine.py's own _esc())
    is used at every one of those interpolation points instead.
    """
    return _html.escape(str(text or ""), quote=True)

def _inject_css(head_html: str, palette, typography) -> str:
    # Build token CSS
    vars_css = f"""
  :root {{
    --bg: {palette.bg};
    --surface: {palette.surface};
    --ink: {palette.ink};
    --muted: {palette.muted};
    --line: {palette.line};
    --border: {palette.line};
    --accent: {palette.accent};
    --accent-2: {palette.accent_dark};
    --accent-dark: {palette.accent_dark};
    --accent-soft: {palette.accent_soft};
    --grad: linear-gradient(135deg, {palette.grad_start} 0%, {palette.grad_end} 100%);
    --dark: #0C1211;
    --gold: {palette.gold};
    --glass: rgba(255,255,255,.72);
    --shadow-sm: 0 1px 2px rgba(12,15,14,.05);
    --shadow: 0 10px 30px rgba(12,15,14,.08);
    --shadow-lg: 0 30px 60px -20px rgba(12,15,14,.22);
    --r: 18px;
    --radius: 14px;
    --maxw: 1120px;
    --font: {typography.body_family};
    --disp: {typography.display_family};
    --serif: Georgia, serif;
  }}
"""
    custom_style = f"<style>\n{typography.css}\n{vars_css}\n"
    return head_html.replace("</head>", f"{custom_style}</style>\n</head>")


def _wrap_h2(block_html: str, kicker: str, k_class: str = "k") -> str:
    """Wrap a blocks-dict fragment's own <h2> in a section-head + kicker
    label, preserving whatever attributes that <h2> already carries.

    2026-08-21, Opus 5 review of Slice C.2: a literal .replace('<h2>',
    ...) -- the pattern this replaces, previously duplicated per-template
    -- only matches a completely bare <h2> tag. It silently missed
    site_engine.py's services_block, which emits <h2 id="services"> (that
    id is the real anchor target for _nav()'s "#services" link, so it
    must survive). The opening substitution would never fire for
    services_block, but a paired </h2> -> </h2></div> substitution still
    would, leaving one extra, unbalanced closing </div> that closes up
    through the real section/wrap divs and pushes everything after it
    outside the page's layout -- found live in two templates' generated
    output before this helper existed. Centralized here (not duplicated
    per template) so a new template can't reintroduce the same bug by
    copy-pasting the broken pattern. \\g<0> reinserts the h2 tag exactly
    as matched, id and all."""
    block_html = re.sub(
        r"<h2[^>]*>",
        f'<div class="section-head"><div class="{k_class}">{kicker}</div>\\g<0>',
        block_html, count=1,
    )
    return block_html.replace("</h2>", "</h2></div>", 1)


def _wrap_faq(faq_html: str) -> str:
    """Converts site_engine.py's flat <h3>/<p> FAQ pairs into real
    <details>/<summary> accordion items, wrapped in a <div class="faq">
    -- matching the .faq{...}/details{...}/summary{...}/summary::after{...}
    accordion CSS every template already declares.

    2026-08-21, Opus 5 review of the footer/contrast fix commit: found
    this dead across all 9 templates, the same "CSS rule matches nothing
    real" defect class as the footer bug. site_engine.py's faq_block only
    ever emits plain <h3>/<p> pairs, never <details>/<summary>, and every
    template applied class="faq-sec" to the outer <section> -- a class no
    template's CSS actually defines -- instead of the real, styled .faq
    class on an inner wrapper. Centralized here so a new template can't
    reintroduce the same gap by copying the old, broken
    .replace('<section ', 'class="faq-sec"') pattern.

    2026-08-21, Opus 5 review: the div-open and div-close steps used to
    run unconditionally -- safe only because site_engine.py's real
    faq_block always contains both an <h2> and a </section>, which
    nothing here actually asserted. Now only opens the div if the <h2>
    substitution really matched (an unmatched <h2> means no div was
    opened, so nothing gets closed either), and closes it before
    </section> when one exists, or at the very end otherwise -- so this
    can never emit an unbalanced </div> or leave one un-closed."""
    def _pair(m):
        return f'<details><summary>{m.group(1)}</summary><p>{m.group(2)}</p></details>'
    wrapped = re.sub(r"<h3>(.*?)</h3>\s*<p>(.*?)</p>", _pair, faq_html, flags=re.S)
    wrapped, n = re.subn(r"(<h2[^>]*>.*?</h2>)", r'\1\n<div class="faq">', wrapped, count=1, flags=re.S)
    if n == 0:
        return wrapped
    if "</section>" in wrapped:
        return wrapped.replace("</section>", "</div>\n    </section>", 1)
    return wrapped + "</div>"


def _footer_class(footer_html: str, class_name: str) -> str:
    """Add this template's own class to site_engine.py's shared _footer()
    output.

    2026-08-21, Opus 5 review of Slice C.3: _footer() (site_engine.py)
    returns a bare, classless <footer> tag -- it has no way to know which
    template will render it, so it can't emit footer.site/footer.clinic/
    etc. itself. Every template's own footer.<name>{...} CSS rule was
    therefore silently matching nothing: footers rendered with zero
    visual treatment (plain default browser stacking) on every generated
    site, across every template, since the very first one. This wasn't
    caught earlier because nothing ever asserted the class was actually
    present -- only that the CSS rule existed."""
    return footer_html.replace("<footer>", f'<footer class="{class_name}">', 1)
