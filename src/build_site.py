"""
Step 5 — assemble the static GitHub Pages site (docs/index.html) from
site_src/shell.html (page frame + tiny data runtime) and site_src/dashboard.html (charts & tables).

    python src/build_site.py <github-user> <repo-name>
"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
user = sys.argv[1] if len(sys.argv) > 1 else "YOUR-USERNAME"
repo = sys.argv[2] if len(sys.argv) > 2 else "sector-performance-lab"

shell = (ROOT / "site_src/shell.html").read_text()
dash = (ROOT / "site_src/dashboard.html").read_text()
dash = dash.replace('<meta name="dash-one-writer">\n', "")
m = re.search(r"<script>[\s\S]*</script>\s*$", dash)
body, script = dash[: m.start()], m.group(0)
html = (shell.replace("<!--DASHBOARD-->", body).replace("<!--DASHSCRIPT-->", script)
             .replace("{{GH_USER}}", user).replace("{{REPO}}", repo))
(ROOT / "docs/index.html").write_text(html)
(ROOT / "docs/.nojekyll").write_text("")
print(f"docs/index.html written ({len(html)/1024:.0f} KB) for github.com/{user}/{repo}")
