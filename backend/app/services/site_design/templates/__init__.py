import collections

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
