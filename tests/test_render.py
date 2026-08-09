"""Render tests: every fixture gets a full plan + apply into a temp copy.

Asserts the manifest's destinations are honored, no {{TOKEN}} survives into
written output, every managed file self-identifies, and the right CI variant
is chosen per detected stack.
"""

import json
import os
import re
import sys
from pathlib import Path

import pytest
from conftest import init_repo, run_script

BASE_FILES = {
    "docs/sdlc/harness.md",
    "CLAUDE.md",
    "docs/sdlc/design.md",
    ".github/workflows/ci.yml",
    "SECURITY.md",
    "docs/sdlc/security.md",
    ".sdlc/hooks/secret-guard.sh",
    ".sdlc/hooks/install.sh",
    ".pre-commit-config.yaml",
    ".github/dependabot.yml",
    ".github/workflows/release.yml",
    "docs/sdlc/glossary.md",
}
CODEQL = ".github/workflows/codeql.yml"

# fixture name -> (has codeql, marker expected inside the rendered CI workflow)
FIXTURE_EXPECT = {
    "repo-python": (True, "actions/setup-python"),
    "repo-node": (True, "actions/setup-node"),
    "repo-go": (True, "actions/setup-go"),
    "repo-mixed": (True, "actions/setup-node"),  # node sorts first among detected languages
    "repo-empty": (False, "No tests configured yet"),
}


def expected_files(fixture: str) -> set[str]:
    has_codeql, _ = FIXTURE_EXPECT[fixture]
    return BASE_FILES | ({CODEQL} if has_codeql else set())


@pytest.mark.parametrize("fixture", sorted(FIXTURE_EXPECT))
def test_full_apply(fixture, tmp_path):
    repo = init_repo(fixture, tmp_path)

    code, plan = run_script("render.py", "plan", repo)
    assert code == 0
    assert plan["ok"], plan.get("errors")
    assert not plan["conflicts"]
    assert {w["path"] for w in plan["writes"]} == expected_files(fixture)

    code, result = run_script("render.py", "apply", repo)
    assert code == 0 and result["ok"]
    assert set(result["written"]) == expected_files(fixture)

    # GitHub Actions' own ${{ ... }} expressions are legitimate output; only
    # shipshape's uppercase {{TOKEN}} placeholders must not survive.
    token_re = re.compile(r"\{\{[A-Z0-9_]+\}\}")
    for rel in expected_files(fixture):
        content = (repo / rel).read_text()
        assert not token_re.search(content), f"unsubstituted token left in {rel}"
        assert "managed-by: shipshape" in content, f"missing managed header in {rel}"

    ci = (repo / ".github/workflows/ci.yml").read_text()
    assert FIXTURE_EXPECT[fixture][1] in ci

    state = (repo / ".sdlc/state.json").read_text()
    for rel in expected_files(fixture):
        assert rel in state


def test_hook_scripts_are_executable(tmp_path):
    repo = init_repo("repo-python", tmp_path)
    run_script("render.py", "apply", repo)
    for rel in (".sdlc/hooks/secret-guard.sh", ".sdlc/hooks/install.sh"):
        assert os.access(repo / rel, os.X_OK), f"{rel} is not executable"


def test_codeql_language_and_dependabot_ecosystems(tmp_path):
    repo = init_repo("repo-mixed", tmp_path)
    run_script("render.py", "apply", repo)
    codeql = (repo / CODEQL).read_text()
    assert 'languages: "javascript-typescript"' in codeql
    dependabot = (repo / ".github/dependabot.yml").read_text()
    for ecosystem in ("github-actions", "npm", "pip"):
        assert f'package-ecosystem: "{ecosystem}"' in dependabot


def test_feature_flags_gate_security_files(tmp_path):
    repo = init_repo(
        "repo-python",
        tmp_path,
        overrides=["features.secret_guard=false", "features.dependabot=false"],
    )
    code, result = run_script("render.py", "apply", repo)
    assert code == 0
    written = set(result["written"])
    assert ".sdlc/hooks/secret-guard.sh" not in written
    assert ".pre-commit-config.yaml" not in written
    assert ".github/dependabot.yml" not in written
    assert "SECURITY.md" in written  # policy doc is not feature-gated


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
    config = json.loads((repo / ".sdlc/config.json").read_text())
    assert config["workflow_style"] == "pr"
    assert config["features"]["codeql"] is False
    assert config["commands"]["test"] == "pytest -q"


def test_set_config_edits_in_place_and_replans(tmp_path):
    repo = init_repo("repo-python", tmp_path)
    run_script("render.py", "apply", repo)

    code, result = run_script(
        "render.py", "set-config", repo, "--set", "features.release_automation=false"
    )
    assert code == 0
    assert result["config"]["features"]["release_automation"] is False
    # Detection-derived values survive a set-config edit.
    assert result["config"]["languages"] == ["python"]

    code, plan = run_script("render.py", "plan", repo)
    assert code == 0
    planned = {p["path"] for group in ("writes", "regenerates", "skips") for p in plan[group]}
    assert ".github/workflows/release.yml" not in planned


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
    kit_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(kit_root / "scripts"))
    from render import build_tokens  # noqa: E402

    known = set(build_tokens({"languages": ["python"]}))
    token_re = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
    for tmpl in (kit_root / "templates").rglob("*.tmpl"):
        used = set(token_re.findall(tmpl.read_text()))
        unknown = used - known
        assert not unknown, f"{tmpl.name} uses unknown tokens: {unknown}"
