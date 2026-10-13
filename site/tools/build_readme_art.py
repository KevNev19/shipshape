#!/usr/bin/env python3
"""Build the README art in site/assets/readme/ from the site's own fonts and colours.

GitHub strips CSS from READMEs, so the README borrows the marketing site's
look through SVG images. Each image embeds a subset of the site's fonts and
comes in a light and a dark variant, which the README picks with
<picture> and prefers-color-scheme.

Dev-only tool that never runs on consumer machines: it needs fontTools and
brotli (pip install fonttools brotli). ADR 0002's stdlib-only rule covers the
kit scripts in scripts/, which do run there; nothing in the kit invokes this.
Output is byte-for-byte reproducible for a given fontTools and brotli version.

    python3 site/tools/build_readme_art.py

Keep THEMES in step with the :root tokens in site/styles.css.
"""

from __future__ import annotations

import base64
import io
from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

SITE = Path(__file__).resolve().parents[1]
FONTS = SITE / "assets" / "fonts"
OUT = SITE / "assets" / "readme"

THEMES = {
    "light": {
        "paper": "#f3f6f6",
        "paper2": "#e6eef0",
        "ink": "#0e2033",
        "ink2": "#4b5d6f",
        "rule": "#c4d0d7",
        "grid": "#dbe5e9",
        "accent": "#1c3f94",
        "accent_ink": "#ffffff",
        "red": "#d4202c",
        "yellow": "#f5c400",
        "blue": "#1c3f94",
        "white": "#ffffff",
        "black": "#101418",
        "edge": "#0e2033",
        "term_bg": "#0c1826",
        "term_edge": "#0c1826",
    },
    "dark": {
        "paper": "#08131f",
        "paper2": "#0e1d2e",
        "ink": "#e4ecf1",
        "ink2": "#97a9b9",
        "rule": "#233649",
        "grid": "#13243a",
        "accent": "#8db0ff",
        "accent_ink": "#08131f",
        "red": "#d4202c",
        "yellow": "#f5c400",
        "blue": "#2753c2",
        "white": "#f4f3ec",
        "black": "#101418",
        "edge": "#4a6178",
        "term_bg": "#040b14",
        "term_edge": "#233649",
    },
}
# The terminal is dark in both themes, as on the site.
TERM = {
    "fg": "#dce6ee",
    "dim": "#8a9db0",
    "you": "#f5c400",
    "path": "#9dbbff",
    "done": "#7fe0a8",
    "bar": "#1e3247",
    "dot": "#2a3e54",
}

FACE_FILES = {
    "display": "big-shoulders-stencil-800.woff2",
    "body": "atkinson-hyperlegible-next.woff2",
    "mono": "atkinson-hyperlegible-mono.woff2",
}
FAMILIES = {"display": "ShipStencil", "body": "ShipBody", "mono": "ShipMono"}
FALLBACKS = {
    "display": "'Arial Narrow', Impact, sans-serif",
    "body": "'Segoe UI', Helvetica, Arial, sans-serif",
    "mono": "ui-monospace, Menlo, Consolas, monospace",
}


class Face:
    """One face at one weight: measures text and emits subset woff2 data."""

    def __init__(self, face: str, weight: int):
        font = TTFont(FONTS / FACE_FILES[face], recalcTimestamp=False)
        if "fvar" in font:
            font = instancer.instantiateVariableFont(font, {"wght": weight})
        buffer = io.BytesIO()
        font.save(buffer)
        self.data = buffer.getvalue()
        self.cmap = font.getBestCmap()
        self.hmtx = font["hmtx"]
        self.upm = font["head"].unitsPerEm

    def width(self, text: str, size: float, spacing: float = 0.0) -> float:
        units = sum(self.hmtx[self.cmap.get(ord(c), ".notdef")][0] for c in text)
        return units * size / self.upm + spacing * len(text)

    def woff2(self, chars: set[str]) -> str:
        font = TTFont(io.BytesIO(self.data), recalcTimestamp=False)
        options = subset.Options()
        options.flavor = "woff2"
        options.layout_features = ["kern", "liga"]
        subsetter = subset.Subsetter(options)
        subsetter.populate(unicodes={ord(c) for c in chars} | {0x20})
        subsetter.subset(font)
        out = io.BytesIO()
        font.flavor = "woff2"
        font.save(out)
        return base64.b64encode(out.getvalue()).decode("ascii")


_FACES: dict[tuple[str, int], Face] = {}


def face(name: str, weight: int) -> Face:
    key = (name, 800 if name == "display" else weight)
    if key not in _FACES:
        _FACES[key] = Face(*key)
    return _FACES[key]


def wrap(text: str, name: str, weight: int, size: float, max_width: float) -> list[str]:
    lines: list[str] = []
    line = ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and face(name, weight).width(trial, size) > max_width:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    return lines


class Svg:
    """A minimal SVG builder that tracks which glyphs each face needs."""

    def __init__(self, width: int, height: int, theme: str, label: str):
        self.width, self.height = width, height
        self.t = THEMES[theme]
        self.label = label
        self.parts: list[str] = []
        self.used: dict[tuple[str, int], set[str]] = defaultdict(set)
        self.css: list[str] = []

    def color(self, token: str) -> str:
        return token if token.startswith("#") else self.t[token]

    def add(self, markup: str) -> None:
        self.parts.append(markup)

    def text(
        self,
        x: float,
        y: float,
        s: str,
        name: str = "body",
        weight: int = 400,
        size: float = 16,
        fill: str = "ink",
        anchor: str = "start",
        spacing: float = 0.0,
    ) -> float:
        weight = 800 if name == "display" else weight
        missing = sorted({c for c in s if ord(c) not in face(name, weight).cmap})
        if missing:
            raise ValueError(f"{name} {weight} has no glyph for {missing}; re-subset the fonts")
        self.used[(name, weight)].update(s)
        attrs = [
            f'x="{x:g}"',
            f'y="{y:g}"',
            f'font-family="{FAMILIES[name]}, {FALLBACKS[name]}"',
            f'font-size="{size:g}"',
            f'font-weight="{weight}"',
            f'fill="{self.color(fill)}"',
        ]
        if anchor != "start":
            attrs.append(f'text-anchor="{anchor}"')
        if spacing:
            attrs.append(f'letter-spacing="{spacing:g}"')
        self.add(f"<text {' '.join(attrs)}>{escape(s)}</text>")
        return face(name, weight).width(s, size, spacing)

    def render(self) -> str:
        label = escape(self.label, {'"': "&quot;"})
        fonts = []
        for (name, weight), chars in sorted(self.used.items()):
            data = face(name, weight).woff2(chars)
            fonts.append(
                f"@font-face{{font-family:{FAMILIES[name]};font-weight:{weight};"
                f"src:url(data:font/woff2;base64,{data}) format('woff2')}}"
            )
        style = "\n".join(fonts + self.css)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" '
            f'height="{self.height}" viewBox="0 0 {self.width} {self.height}" '
            f'role="img" aria-label="{label}">\n'
            f"<title>{escape(self.label)}</title>\n"
            f"<style>\n{style}\n</style>\n"
            f"{flag_defs(self.t)}\n" + "\n".join(self.parts) + "\n</svg>\n"
        )


# ---------- Signal flags (International Code of Signals, 3:2) ----------

FLAG_SHAPES = {
    "S": [("white", "M0 0H60V40H0Z"), ("blue", "M20 13.333H40V26.667H20Z")],
    "H": [("white", "M0 0H30V40H0Z"), ("red", "M30 0H60V40H30Z")],
    "I": [("yellow", "M0 0H60V40H0Z"), ("black", "M20 20A10 10 0 1 0 40 20A10 10 0 1 0 20 20Z")],
    "P": [("blue", "M0 0H60V40H0Z"), ("white", "M20 13.333H40V26.667H20Z")],
    "A": [("white", "M0 0H30V40H0Z"), ("blue", "M30 0H60L45 20L60 40H30Z")],
    "E": [("blue", "M0 0H60V20H0Z"), ("red", "M0 20H60V40H0Z")],
}
FLAG_EDGES = {"A": "M0.5 0.5H59L44.4 20L59 39.5H0.5Z"}
WORD = "SHIPSHAPE"


def flag_defs(t: dict[str, str]) -> str:
    symbols = []
    for letter, shapes in FLAG_SHAPES.items():
        paths = "".join(f'<path fill="{t[c]}" d="{d}"/>' for c, d in shapes)
        edge = FLAG_EDGES.get(letter, "M0.5 0.5H59.5V39.5H0.5Z")
        paths += (
            f'<path fill="none" stroke="{t["edge"]}" stroke-width="1" '
            f'vector-effect="non-scaling-stroke" d="{edge}"/>'
        )
        symbols.append(f'<symbol id="flag-{letter}" viewBox="0 0 60 40">{paths}</symbol>')
    return "<defs>" + "".join(symbols) + "</defs>"


def flag(svg: Svg, letter: str, x: float, y: float, w: float) -> None:
    svg.add(
        f'<use href="#flag-{letter}" x="{x:g}" y="{y:g}" width="{w:g}" height="{w * 2 / 3:g}"/>'
    )


def panel(svg: Svg) -> None:
    svg.add(
        f'<rect x="0.5" y="0.5" width="{svg.width - 1}" height="{svg.height - 1}" rx="6" '
        f'fill="{svg.t["paper"]}" stroke="{svg.t["rule"]}"/>'
    )


# ---------- Artworks ----------


def hero(theme: str) -> Svg:
    svg = Svg(
        880,
        470,
        theme,
        "Signal flags spelling SHIPSHAPE beside the headline: Get your repository "
        "shipshape. A proper software delivery process for any repository, set up "
        "in one conversation, in plain English. Scan, a few questions, preview, set up.",
    )
    panel(svg)
    left = 48
    svg.text(
        left, 72, "FOR CODEX AND CLAUDE CODE · MIT LICENSED", "mono", 700, 12.5, "ink2", spacing=2
    )
    for i, (line, fill) in enumerate(
        [("GET YOUR", "ink"), ("REPOSITORY", "ink"), ("SHIPSHAPE.", "accent")]
    ):
        svg.text(left - 2, 160 + i * 80, line, "display", size=94, fill=fill, spacing=0.5)
    svg.text(left, 362, "A proper software delivery process for any repository,", size=19.5)
    svg.text(left, 389, "set up in one conversation, in plain English.", size=19.5)

    x = left
    for i, stop in enumerate(["SCAN", "A FEW QUESTIONS", "PREVIEW", "SET UP"]):
        if i:
            svg.add(
                f'<line x1="{x + 10:g}" y1="425" x2="{x + 38:g}" y2="425" '
                f'stroke="{svg.t["ink2"]}" stroke-width="2" stroke-dasharray="4 3"/>'
            )
            x += 48
        x += svg.text(x, 430, stop, "mono", 700, 13, "ink", spacing=0.6)

    # The hoist: nine flags on one halyard, read top to bottom.
    halyard, fx, fw, step, top = 744, 760, 60, 42, 46
    svg.add(
        f'<line x1="{halyard}" y1="{top - 10}" x2="{halyard}" y2="{top + 9 * step + 6}" '
        f'stroke="{svg.t["ink"]}" stroke-width="2"/>'
        f'<circle cx="{halyard}" cy="{top - 14}" r="5" fill="{svg.t["paper"]}" '
        f'stroke="{svg.t["ink"]}" stroke-width="2"/>'
    )
    for i, letter in enumerate(WORD):
        y = top + i * step
        svg.add(
            f'<line x1="{halyard}" y1="{y + 20}" x2="{fx}" y2="{y + 20}" '
            f'stroke="{svg.t["ink"]}" stroke-width="2"/>'
        )
        flag(svg, letter, fx, y, fw)
        svg.text(fx + fw + 14, y + 25, letter, "mono", 700, 13, "ink2")
    svg.text(fx + fw + 22, 448, "The word itself, in the", "mono", 400, 10.5, "ink2", anchor="end")
    svg.text(
        fx + fw + 22, 462, "International Code of Signals", "mono", 400, 10.5, "ink2", anchor="end"
    )
    return svg


def course(theme: str) -> Svg:
    stops = [
        ("Scan", "Reads your languages, package setup and how tests run. It only looks."),
        ("A few questions", "Five at most, about outcomes. What the scan knows is only confirmed."),
        ("Preview", "Every file it will add, and why. Files you already have are left alone."),
        ("Set up", "Writes exactly what you saw and switches on the commit guard."),
    ]
    svg = Svg(
        880,
        340,
        theme,
        "The course $shipshape-init follows, drawn as a chart: 1 Scan, 2 A few questions, "
        "3 Preview, 4 Set up. Nothing changes before the preview. "
        + " ".join(f"{name}: {body}" for name, body in stops),
    )
    t = svg.t
    w, h = svg.width, svg.height
    svg.add(f'<rect x="0" y="0" width="{w}" height="{h}" fill="{t["paper"]}"/>')
    for gx in range(8 + 96, w - 8, 96):
        svg.add(f'<line x1="{gx}" y1="8" x2="{gx}" y2="{h - 8}" stroke="{t["grid"]}"/>')
    for gy in range(8 + 96, h - 8, 96):
        svg.add(f'<line x1="8" y1="{gy}" x2="{w - 8}" y2="{gy}" stroke="{t["grid"]}"/>')
    # Chart neatline: outer rule, alternating ladder band, inner rule.
    ladder = f'stroke="{t["ink"]}" stroke-width="6" stroke-dasharray="24 24"'
    svg.add(
        f'<line x1="1" y1="4" x2="{w - 1}" y2="4" {ladder}/>'
        f'<line x1="1" y1="{h - 4}" x2="{w - 1}" y2="{h - 4}" {ladder}/>'
        f'<line x1="4" y1="1" x2="4" y2="{h - 1}" {ladder}/>'
        f'<line x1="{w - 4}" y1="1" x2="{w - 4}" y2="{h - 1}" {ladder}/>'
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" fill="none" stroke="{t["ink"]}"/>'
        f'<rect x="7.5" y="7.5" width="{w - 15}" height="{h - 15}" fill="none" '
        f'stroke="{t["ink"]}"/>'
    )

    left, gap = 44, 28
    col = (w - 2 * left - 3 * gap) / 4
    cy, r = 76, 25
    svg.add(
        f'<line x1="{left + r}" y1="{cy}" x2="{left + 3 * (col + gap) + r:g}" y2="{cy}" '
        f'stroke="{t["accent"]}" stroke-width="2" stroke-dasharray="6 5"/>'
    )
    for i, (name, body) in enumerate(stops):
        x = left + i * (col + gap)
        last = i == len(stops) - 1
        ring, fill, num = ("accent", "accent", "accent_ink") if last else ("ink", "paper", "ink")
        svg.add(
            f'<circle cx="{x + r}" cy="{cy}" r="{r}" fill="{t[fill]}" '
            f'stroke="{t[ring]}" stroke-width="2"/>'
            f'<circle cx="{x + r}" cy="{cy}" r="{r - 5}" fill="none" '
            f'stroke="{t["accent_ink"] if last else t["rule"]}" '
            f'stroke-opacity="{0.4 if last else 1}"/>'
        )
        svg.text(x + r, cy + 10, str(i + 1), "display", size=28, fill=num, anchor="middle")
        svg.text(x, 140, name.upper(), "display", size=26, spacing=0.3)
        lines = wrap(body, "body", 400, 15, col)
        if len(lines) > 4:
            raise ValueError(f"course stop {name!r} wraps to {len(lines)} lines; keep it to 4")
        for j, line in enumerate(lines):
            svg.text(x, 170 + j * 22, line, size=15)

    box_w, box_h = 272, 46
    bx, by = w - left - box_w, h - 36 - box_h
    svg.add(
        f'<rect x="{bx}" y="{by}" width="{box_w}" height="{box_h}" fill="{t["paper"]}" '
        f'stroke="{t["ink"]}"/>'
    )
    svg.text(
        bx + box_w - 12,
        by + 19,
        "Course for $shipshape-init",
        "mono",
        400,
        11.5,
        "ink2",
        anchor="end",
    )
    svg.text(
        bx + box_w - 12,
        by + 35,
        "Nothing changes before the preview",
        "mono",
        400,
        11.5,
        "ink2",
        anchor="end",
    )
    return svg


def conversation(theme: str) -> Svg:
    you, say, plan, gap = "you", "say", "plan", "gap"
    script = [
        (you, "$shipshape-init"),
        (gap, ""),
        (say, "This looks like a Python project that uses pytest for its tests. Is that right?"),
        (gap, ""),
        (you, "yep. it's just me working on it"),
        (gap, ""),
        (say, "Got it: solo, changes go straight to main, and checks run after each push."),
        (say, "Here's the plan, and nothing you already have gets touched:"),
        (gap, ""),
        (plan, ".github/workflows/ci.yml|runs your tests on GitHub after each push to main"),
        (plan, ".sdlc/hooks/secret-guard.sh|stops a commit that adds a key or credential file"),
        (plan, "docs/sdlc/harness.md|your working agreement, in plain English"),
        (plan, "…|"),
        (gap, ""),
        (say, "Shall I go ahead?"),
        (gap, ""),
        (you, "go ahead"),
        (gap, ""),
        ("done", "Done. Everything is written, and the secret guard is on for this copy."),
        ("next", "Next step: commit these new files and push them to GitHub."),
    ]
    size, lead, gap_h = 14, 22, 10
    body_h = sum(gap_h if kind == gap else lead for kind, _ in script)
    height = 44 + 26 + body_h + 24
    svg = Svg(
        880,
        int(height),
        theme,
        "An example $shipshape-init conversation. Shipshape confirms the project uses "
        "pytest, asks who works on it, shows a plan that leaves existing files alone, "
        "and writes it on the go-ahead.",
    )
    t = svg.t
    svg.add(
        f'<rect x="0.5" y="0.5" width="879" height="{height - 1}" rx="8" fill="{t["term_bg"]}" '
        f'stroke="{t["term_edge"]}"/>'
        f'<line x1="1" y1="44" x2="879" y2="44" stroke="{TERM["bar"]}"/>'
    )
    for i in range(3):
        svg.add(f'<circle cx="{24 + i * 16}" cy="22" r="5" fill="{TERM["dot"]}"/>')
    svg.text(84, 26, "my-project", "mono", 400, 12, TERM["dim"], spacing=0.8)

    mono = face("mono", 400)
    ch = mono.width("m", size)
    x0, indent = 32, 32 + 6 * ch
    y = 44 + 26 + 14
    for kind, line in script:
        if kind == gap:
            y += gap_h
            continue
        if kind == you:
            svg.text(x0, y, "you>", "mono", 700, size, TERM["you"])
            svg.text(indent, y, line, "mono", 400, size, TERM["fg"])
        elif kind == plan:
            path, note = line.split("|")
            svg.text(indent + 2 * ch, y, path, "mono", 400, size, TERM["path"])
            if note:
                svg.text(indent + 32 * ch, y, note, "mono", 400, size, TERM["dim"])
        else:
            fill = TERM["done"] if kind == "done" else TERM["fg"]
            end = svg.text(indent, y, line, "mono", 400, size, fill)
            if kind == "next":
                svg.add(
                    f'<rect class="cursor" x="{indent + end + ch:g}" y="{y - 13}" '
                    f'width="{ch:g}" height="17" fill="{TERM["you"]}"/>'
                )
        y += lead
    svg.css.append(
        "@keyframes blink{50%{opacity:0}}.cursor{animation:blink 1.1s steps(1) infinite}"
        "@media (prefers-reduced-motion:reduce){.cursor{animation:none}}"
    )
    return svg


def watch_bill(theme: str) -> Svg:
    rows = [
        (
            "Every commit, on your computer",
            "Secret guard",
            "Stops a commit that adds a key file (like .env or a private key) or a known AWS, "
            "GitHub, Slack, Stripe or Google token. Flags changes to files that steer AI tools.",
        ),
        (
            "Pushes and pull requests to main",
            "CI",
            "Runs your tests on GitHub. In straight-to-main mode it reports after the change "
            "lands.",
        ),
        (
            "Pushes and pull requests to main",
            "Secret scan",
            "Checks every new commit again on GitHub, so a key added in one commit and deleted "
            "in the next is still caught.",
        ),
        (
            "Pushes, pull requests and weekly",
            "CodeQL",
            "For Python, JavaScript/TypeScript, Go, Java, Ruby or C# code: finds known security "
            "mistakes and lists them in the Security tab. Free on public repositories.",
        ),
        (
            "Weekly",
            "Dependabot",
            "Suggests newer versions of your libraries and GitHub Actions as pull requests.",
        ),
        (
            "Every Wednesday",
            "Health check",
            "Re-checks every protection and, when anything is rated WARN or FAIL, opens or "
            "updates one issue with the counts and the next thing to fix.",
        ),
        (
            "You push a version tag",
            "Release",
            "Publishes a GitHub release for that exact commit, only if its checks passed on "
            "GitHub.",
        ),
        (
            "Once you say yes",
            "Branch rule",
            "Stops anyone deleting main or overwriting its history with a force-push.",
        ),
    ]
    cols = (40, 262, 398)
    desc_w = 880 - 40 - cols[2]
    when_w = cols[1] - cols[0] - 18
    size, lead, when_size, when_lead = 15, 22, 13.5, 19
    cells = [
        (wrap(when, "mono", 400, when_size, when_w), wrap(desc, "body", 400, size, desc_w))
        for when, _, desc in rows
    ]
    heights = [max(when_lead * len(w), lead * len(d)) for w, d in cells]
    height = 40 + 30 + 34 + sum(28 + h for h in heights) + 24
    svg = Svg(
        880,
        int(height),
        theme,
        "Watch bill. "
        + " ".join(f"{when}: {who}. {desc}" for when, who, desc in rows)
        + " Everything that fits your project is on by default for a solo, straight-to-main "
        "setup, except the branch rule, which waits for your yes.",
    )
    t = svg.t
    panel(svg)
    svg.text(cols[0], 56, "WATCH BILL", "mono", 700, 12.5, "ink2", spacing=2)
    for x, head in zip(cols, ("WHEN", "ON WATCH", "WHAT IT DOES"), strict=True):
        svg.text(x, 96, head, "mono", 700, 11.5, "ink2", spacing=1.4)
    svg.add(
        f'<line x1="{cols[0]}" y1="108" x2="{880 - 40}" y2="108" stroke="{t["ink"]}" '
        f'stroke-width="2"/>'
    )
    y = 108
    for i, ((_, who, _), (when_lines, lines), row_h) in enumerate(
        zip(rows, cells, heights, strict=True)
    ):
        base = y + 14 + 17
        for j, line in enumerate(when_lines):
            svg.text(cols[0], base + j * when_lead, line, "mono", 400, when_size, "ink2")
        svg.text(cols[1], base, who, "body", 700, size)
        for j, line in enumerate(lines):
            svg.text(cols[2], base + j * lead, line, size=size)
        y += 28 + row_h
        if i < len(rows) - 1:
            svg.add(
                f'<line x1="{cols[0]}" y1="{y}" x2="{880 - 40}" y2="{y}" stroke="{t["rule"]}"/>'
            )
    return svg


def install(theme: str) -> Svg:
    caption = "Flown in harbour, it means: all aboard, this vessel is about to sail."
    svg = Svg(600, 104, theme, f"Flag P, the Blue Peter. {caption}")
    flag(svg, "P", 0.5, 2, 150)
    x = 178
    svg.text(x, 30, "FLAG P, THE BLUE PETER", "mono", 700, 12.5, "ink2", spacing=2)
    for i, line in enumerate(wrap(caption, "body", 400, 17, 600 - x)):
        svg.text(x, 60 + i * 25, line, size=17)
    return svg


def footer(theme: str) -> Svg:
    svg = Svg(880, 110, theme, "Signal flags spelling SHIPSHAPE. Get your repository shipshape.")
    for i, letter in enumerate(WORD):
        flag(svg, letter, 0.5 + i * 40, 4, 36)
    svg.text(-1, 92, "GET YOUR REPOSITORY SHIPSHAPE.", "display", size=46, spacing=0.4)
    return svg


ARTWORKS = {
    "hero": hero,
    "course": course,
    "conversation": conversation,
    "watch-bill": watch_bill,
    "install": install,
    "footer": footer,
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, build in ARTWORKS.items():
        for theme in THEMES:
            path = OUT / f"{name}-{theme}.svg"
            path.write_text(build(theme).render(), encoding="utf-8")
            print(f"{path.relative_to(SITE.parent)}  {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
