"""The marketing site and the README art it feeds stay wired together."""

import re
from html.parser import HTMLParser
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
    # Read the site with the HTML parser. A tag-shaped regular expression is
    # the pattern CodeQL calls a bad HTML filter, and this test is not a filter.
    class InlineScripts(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.scripts = []
            self._chunks = None

        def handle_starttag(self, tag, attrs):
            if tag == "script" and "src" not in dict(attrs):
                self._chunks = []

        def handle_endtag(self, tag):
            if tag == "script" and self._chunks is not None:
                self.scripts.append("".join(self._chunks))
                self._chunks = None

        def handle_data(self, data):
            if self._chunks is not None:
                self._chunks.append(data)

    html = (SITE / "index.html").read_text(encoding="utf-8")
    parser = InlineScripts()
    parser.feed(html)
    parser.close()
    assert parser.scripts, "the site should include an inline script"
    for script in parser.scripts:
        code = "\n".join(line for line in script.splitlines() if not line.strip().startswith("//"))
        assert code.strip().startswith("(function"), "wrap inline scripts in a function"


def test_launch_film_sits_below_the_hero_and_is_credited():
    """The launch film is its own section, with a credit wherever it is published."""
    html = (SITE / "index.html").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    hero = html.index('class="hero"')
    launch = html.index('id="launch"')
    how = html.index('id="how"')
    watch = html.index('id="watch"')
    assert hero < launch < how < watch

    class LaunchMarkup(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.video = None
            self.sources = []
            self.tracks = []
            self.text = []
            self._depth = 0

        def handle_starttag(self, tag, attrs):
            attr = dict(attrs)
            if attr.get("id") == "launch":
                self._depth = 1
            elif self._depth and tag not in {"source", "track", "img", "br"}:
                self._depth += 1
            if self._depth and tag == "video":
                self.video = attr
            if self._depth and tag == "source":
                self.sources.append(attr)
            if self._depth and tag == "track":
                self.tracks.append(attr)

        def handle_endtag(self, tag):
            if self._depth:
                self._depth -= 1

        def handle_data(self, data):
            if self._depth:
                self.text.append(data)

    parser = LaunchMarkup()
    parser.feed(html)
    parser.close()
    video = parser.video
    assert video is not None, "the launch section needs a video"
    for present in ("controls", "playsinline", "loop", "muted"):
        assert present in video, present
    assert "autoplay" not in video, "autoplay is decided in script, not forced on"
    assert video.get("preload") == "metadata"
    assert video.get("poster") == "assets/video/launch-poster.jpg"
    assert video.get("width") == "1920"
    assert video.get("height") == "1080"
    assert [item.get("type") for item in parser.sources] == ["video/webm", "video/mp4"]
    assert [item.get("src") for item in parser.sources] == [
        "assets/video/launch.webm",
        "assets/video/launch.mp4",
    ]
    [track] = parser.tracks
    assert track.get("kind") == "captions"
    assert track.get("src") == "assets/video/launch.vtt"
    assert track.get("srclang") == "en"
    visible = " ".join(parser.text)
    for phrase in (
        "Happy Beats / Business Moves vol. 12",
        "Sascha Ende",
        "CC BY 4.0",
        "Kenney",
        "CC0",
    ):
        assert phrase in visible, phrase
        assert phrase in readme, phrase
    assert 'href="https://kevnev19.github.io/shipshape/#launch"' in readme
    assert 'src="site/assets/video/launch-poster.jpg"' in readme
    assert 'property="og:video"' in html
    script = html.split('id="launch-video"', 1)[1]
    assert "prefers-reduced-motion" in script
    assert "IntersectionObserver" in script
    # Play and pause the page starts are counted apart, so one cannot clear the other.
    assert "scriptPlays" in script
    assert "scriptPauses" in script
    assert "fromScript" not in script
    # Leaving the screen pauses the film even after the visitor pressed play.
    assert "if (userStarted) return" not in script
    captions = (SITE / "assets" / "video" / "launch.vtt").read_text(encoding="utf-8")
    assert captions.startswith("WEBVTT")
    assert "Sascha Ende" in captions

    video_dir = SITE / "assets" / "video"
    files = [path for path in video_dir.iterdir() if path.is_file()]
    total = sum(path.stat().st_size for path in files)
    assert total < 10 * 1024 * 1024, f"launch media is {total} bytes"
    mp4 = (video_dir / "launch.mp4").read_bytes()
    assert mp4.find(b"moov") < mp4.find(b"mdat"), "mp4 should be faststart"
    assert (video_dir / "launch.webm").read_bytes()[:4] == b"\x1a\x45\xdf\xa3"


def test_lighthouse_ci_guards_site_changes():
    workflow = (ROOT / ".github" / "workflows" / "lighthouse.yml").read_text(encoding="utf-8")
    config = (ROOT / "lighthouserc.json").read_text(encoding="utf-8")
    assert "pull_request:" in workflow
    assert "pull_request_target:" not in workflow
    assert "site/**" in workflow
    assert "contents: read" in workflow
    assert "contents: write" not in workflow
    assert "@lhci/cli@0.16.0" in workflow
    assert '"staticDistDir": "./site"' in config
    assert '"aggregationMethod": "pessimistic"' in config
    for audit in (
        "categories:performance",
        "categories:accessibility",
        "categories:best-practices",
        "cumulative-layout-shift",
        "total-byte-weight",
    ):
        assert audit in config


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
