"""Release tests: the kit states one version and runs on it.

render.kit_version() is the kit's version. Every manifest that names a
version carries the same one, the site's specimen of a generated header
shows it, and the kit's own setup was applied with it: .sdlc/config.json
records it, the last apply ran it, and no managed file is left to write
or regenerate. The files the kit keeps hand-written or edited on purpose
stay conflicts, so render.py records the setup as partial and keeps the
completed version at the last complete apply.
"""

import json
import re
import sys

from conftest import KIT_ROOT, SCRIPTS, run_script

# Bumped in the release commit with the manifests, so a half-bumped release fails.
RELEASE = "0.4.0"
PYPROJECT_VERSION = re.compile(r'^version = "([^"]+)"$', re.MULTILINE)
SITE_HEADER = "<mark>managed-by:</mark> shipshape v{}</pre>"
# Hand-written or locally edited on purpose; apply never touches them unforced.
INTENDED_CONFLICTS = [
    ".github/workflows/ci.yml",
    ".pre-commit-config.yaml",
    "AGENTS.md",
    "CLAUDE.md",
    "docs/sdlc/harness.md",
]


def load(rel: str) -> dict:
    return json.loads((KIT_ROOT / rel).read_text(encoding="utf-8"))


def render_kit_version() -> str:
    sys.path.insert(0, str(SCRIPTS))
    from render import kit_version

    return kit_version()


def manifest_versions() -> dict[str, str]:
    marketplace = load(".claude-plugin/marketplace.json")
    (listing,) = [p for p in marketplace["plugins"] if p["name"] == "shipshape"]
    pyproject = (KIT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    return {
        ".claude-plugin/plugin.json": load(".claude-plugin/plugin.json")["version"],
        ".claude-plugin/marketplace.json": listing["version"],
        ".codex-plugin/plugin.json": load(".codex-plugin/plugin.json")["version"],
        "pyproject.toml": PYPROJECT_VERSION.search(pyproject).group(1),
    }


def test_kit_version_is_the_release_version():
    assert render_kit_version() == RELEASE


def test_every_manifest_carries_the_kit_version():
    versions = manifest_versions()
    assert versions == dict.fromkeys(versions, render_kit_version())


def test_site_shows_the_header_the_kit_writes():
    site = (KIT_ROOT / "site" / "index.html").read_text(encoding="utf-8")
    assert SITE_HEADER.format(render_kit_version()) in site


def test_kit_setup_was_applied_at_the_kit_version():
    assert load(".sdlc/config.json")["kit_version"] == render_kit_version()
    assert load(".sdlc/state.json")["last_run_kit_version"] == render_kit_version()


def test_kit_managed_files_are_all_applied():
    code, plan = run_script("render.py", "plan", KIT_ROOT)
    assert code == 0 and plan["ok"], plan.get("errors")
    assert plan["writes"] == []
    assert plan["regenerates"] == []
    assert sorted(conflict["path"] for conflict in plan["conflicts"]) == INTENDED_CONFLICTS
