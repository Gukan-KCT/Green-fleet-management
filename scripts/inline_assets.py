import re
from pathlib import Path

public_dir = Path("public")
css = (public_dir / "style.css").read_text(encoding="utf-8")
js = (public_dir / "app.js").read_text(encoding="utf-8")
html = (public_dir / "index.html").read_text(encoding="utf-8")

# Strip all old stylesheet link tags
html = re.sub(r'<link rel="stylesheet"[^>]+>\s*', '', html)

# Inject CSS directly into <head>
style_block = f"<style>\n{css}\n</style>\n"
html = html.replace('<!-- Plotly CDN for interactive charts -->', f'{style_block}<!-- Plotly CDN for interactive charts -->')

# Replace <script src="/static/app.js"></script> with full inline script
html = html.replace('<script src="/static/app.js"></script>', f'<script>\n{js}\n</script>')

(public_dir / "index.html").write_text(html, encoding="utf-8")
print("Successfully inlined CSS and JS into public/index.html")
