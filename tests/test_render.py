"""Render tests: every fixture gets a full plan + apply into a temp copy.

Asserts the manifest's destinations are honored, no {{TOKEN}} survives into
written output, every managed file self-identifies, and the right CI variant
is chosen per detected stack.
"""

from pathlib import Path

import pytest
from conftest import init_repo, run_script

M1_FILES = [
    "docs/sdlc/harness.md",
    "CLAUDE.md",
    "docs/sdlc/design.md",
    ".github/workflows/ci.yml",
]

# fixture name -> marker expected inside the rendered CI workflow
CI_MARKERS = {
    "repo-python": "actions/setup-python",
    "repo-node": "actions/setup-node",
    "repo-go": "actions/setup-go",
    "repo-mixed": "actions/setup-node",  # node sorts first among detected languages
    "repo-empty": "No tests configured yet",
}


@pytest.mark.parametrize("fixture", sorted(CI_MARKERS))
def test_full_apply(fixture, tmp_path):
    repo = init_repo(fixture, tmp_path)

    code, plan = run_script("render.py", "plan", repo)
    assert code == 0
    assert plan["ok"], plan.get("errors")
    assert not plan["conflicts"]
    assert {w["path"] for w in plan["writes"]} == set(M1_FILES)

    code, result = run_script("render.py", "apply", repo)
    assert code == 0 and result["ok"]
    assert set(result["written"]) == set(M1_FILES)

    for rel in M1_FILES:
        content = (repo / rel).read_text()
        assert "{{" not in content, f"unsubstituted token left in {rel}"
        assert "managed-by: shipshape" in content, f"missing managed header in {rel}"

    ci = (repo / ".github/workflows/ci.yml").read_text()
    assert CI_MARKERS[fixture] in ci

    state = (repo / ".sdlc/state.json").read_text()
    for rel in M1_FILES:
        assert rel in state


def test_init_config_captures_detection(tmp_path):
    repo = init_repo("repo-python", tmp_path)
    config = (repo / ".sdlc/config.json").read_text()
    assert '"python"' in config
    assert '"pytest"' in config


def test_init_config_set_overrides(tmp_path):
    repo = init_repo(
        "repo-python",
        tmp_path,
        overrides=["workflow_style=pr", "features.codeql=false", "commands.test=pytest -q"],
    )
    import json

    config = json.loads((repo / ".sdlc/config.json").read_text())
    assert config["workflow_style"] == "pr"
    assert config["features"]["codeql"] is False
    assert config["commands"]["test"] == "pytest -q"


def test_empty_repo_gets_fallback_test_command(tmp_path):
    repo = init_repo("repo-empty", tmp_path)
    run_script("render.py", "apply", repo)
    ci = (repo / ".github/workflows/ci.yml").read_text()
    assert "No tests configured yet" in ci


def test_plan_without_config_is_friendly_error(tmp_path):
    bare = tmp_path / "bare"
    bare.mkdir()
    code, payload = run_script("render.py", "plan", bare)
    assert code == 1
    assert "shipshape-init" in payload["error"]


def test_kit_templates_only_use_known_tokens():
    """Every {{TOKEN}} in every template must be one build_tokens can supply."""
    import re
    import sys

    kit_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(kit_root / "scripts"))
    from render import build_tokens  # noqa: E402

    known = set(build_tokens({"languages": ["python"]}))
    token_re = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
    for tmpl in (kit_root / "templates").rglob("*.tmpl"):
        used = set(token_re.findall(tmpl.read_text()))
        unknown = used - known
        assert not unknown, f"{tmpl.name} uses unknown tokens: {unknown}"
