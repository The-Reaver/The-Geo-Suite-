import collections
import re

Template = collections.namedtuple("Template", [
    "name",
    "render_index",
    "render_service",
    "render_about",
    "render_privacy"
])

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
