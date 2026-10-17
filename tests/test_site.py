"""The marketing site and the README art it feeds stay wired together."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"


def test_readme_art_exists_in_both_themes():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    refs = re.findall(r'(?:src|srcset)="(site/[^"]+)"', readme)
    assert refs, "the README should show the site's art"
    for ref in refs:
        assert (ROOT / ref).is_file(), f"README points at a missing file: {ref}"
    light = {ref for ref in refs if ref.endswith("-light.svg")}
    dark = {ref for ref in refs if ref.endswith("-dark.svg")}
    assert {ref.replace("-light.svg", "-dark.svg") for ref in light} == dark


def test_site_local_references_exist():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    css = (SITE / "styles.css").read_text(encoding="utf-8")
    refs = re.findall(r'(?:href|src)="([^"#:]+)"', html) + re.findall(r'url\("([^"]+)"\)', css)
    assert refs, "the site should reference its own assets"
    for ref in refs:
        assert (SITE / ref).is_file(), f"site points at a missing file: {ref}"
    assert (SITE / "assets" / "og.png").is_file(), "og:image needs assets/og.png"


def test_site_scripts_stay_out_of_global_scope():
    # A top-level `var status` silently becomes the string window.status.
    html = (SITE / "index.html").read_text(encoding="utf-8")
    for script in re.findall(r"<script>(.*?)</script>", html, re.S):
        code = "\n".join(line for line in script.splitlines() if not line.strip().startswith("//"))
        assert code.strip().startswith("(function"), "wrap inline scripts in a function"


def test_readme_and_site_say_review_runs_the_projects_checks():
    """Review runs the repository's own checks, so neither page may call it read-only."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    html = (SITE / "index.html").read_text(encoding="utf-8")
    [row] = [line for line in readme.splitlines() if line.startswith("| `$shipshape-review`")]
    [card] = re.findall(r"<code>\$shipshape-review</code>(.*?)</li>", html, re.S)
    for text in (row.lower(), card.lower()):
        assert "read-only" not in text
        assert "runs your project's own checks on local work" in text
        assert "asking first on a branch someone else wrote" in text
    assert "Doctor and review only look and report" not in html
