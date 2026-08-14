"""Render tests: every fixture gets a full plan + apply into a temp copy.

Asserts the manifest's destinations are honored, no {{TOKEN}} survives into
written output, every managed file self-identifies, and the right CI variant
is chosen per detected stack.
"""

import json
import os
import re
import subprocess
import sys
import textwrap
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
    "AGENTS.md",
    ".github/workflows/secret-scan.yml",
    ".github/workflows/copilot-setup-steps.yml",
    ".github/agents/reviewer.md",
    ".github/copilot-instructions.md",
    ".sdlc/scripts/doctor.py",
    ".github/workflows/shipshape-doctor.yml",
}
CODEQL = ".github/workflows/codeql.yml"
LOW_RISK_AUTOMERGE = ".github/workflows/low-risk-automerge.yml"

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


def test_rendered_doctor_is_executable(tmp_path):
    repo = init_repo("repo-python", tmp_path)
    run_script("render.py", "apply", repo)
    doctor = repo / ".sdlc" / "scripts" / "doctor.py"
    assert os.access(doctor, os.X_OK), f"{doctor} is not executable"


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
    assert ".github/workflows/secret-scan.yml" not in written
    assert ".github/dependabot.yml" not in written
    assert "SECURITY.md" in written  # policy doc is not feature-gated


def test_github_agents_flag_gates_agent_surface(tmp_path):
    repo = init_repo("repo-python", tmp_path, overrides=["features.github_agents=false"])
    code, result = run_script("render.py", "apply", repo)
    assert code == 0
    written = set(result["written"])
    assert ".github/workflows/copilot-setup-steps.yml" not in written
    assert ".github/agents/reviewer.md" not in written
    assert ".github/copilot-instructions.md" not in written
    assert "AGENTS.md" in written  # the adapter is always written


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        (["workflow_style=pr", "features.tiered_review=true"], True),
        (["workflow_style=pr", "features.tiered_review=false"], False),
        (
            [
                "workflow_style=trunk",
                "profile=solo",
                "features.tiered_review=true",
            ],
            False,
        ),
    ],
)
def test_tiered_review_requires_pr_style_and_feature_flag(tmp_path, overrides, expected):
    repo = init_repo("repo-python", tmp_path, overrides=overrides)
    code, result = run_script("render.py", "apply", repo)

    assert code == 0, result
    assert (LOW_RISK_AUTOMERGE in result["written"]) is expected
    assert (repo / LOW_RISK_AUTOMERGE).is_file() is expected


def test_disabling_tiered_review_removes_the_managed_workflow(tmp_path):
    repo = init_repo(
        "repo-python",
        tmp_path,
        overrides=["workflow_style=pr", "features.tiered_review=true"],
    )
    code, enabled = run_script("render.py", "apply", repo)
    assert code == 0, enabled
    assert (repo / LOW_RISK_AUTOMERGE).is_file()

    code, _ = run_script("render.py", "set-config", repo, "--set", "features.tiered_review=false")
    assert code == 0
    code, plan = run_script("render.py", "plan", repo)
    assert code == 0, plan
    assert [item["path"] for item in plan["removals"]] == [LOW_RISK_AUTOMERGE]

    code, disabled = run_script("render.py", "apply", repo)
    assert code == 0, disabled
    assert disabled["removed"] == [LOW_RISK_AUTOMERGE]
    assert not (repo / LOW_RISK_AUTOMERGE).exists()


def test_disabling_tiered_review_never_deletes_a_drifted_workflow(tmp_path):
    repo = init_repo(
        "repo-python",
        tmp_path,
        overrides=["workflow_style=pr", "features.tiered_review=true"],
    )
    code, enabled = run_script("render.py", "apply", repo)
    assert code == 0, enabled
    workflow = repo / LOW_RISK_AUTOMERGE
    workflow.write_text(workflow.read_text() + "\n# owner edit\n")
    code, _ = run_script("render.py", "set-config", repo, "--set", "features.tiered_review=false")
    assert code == 0

    code, disabled = run_script("render.py", "apply", repo)

    assert code == 0, disabled
    assert disabled["removed"] == []
    assert workflow.is_file()
    assert [item["path"] for item in disabled["conflicts_untouched"]] == [LOW_RISK_AUTOMERGE]

    code, confirmed = run_script("render.py", "apply", repo, "--force", LOW_RISK_AUTOMERGE)
    assert code == 0, confirmed
    assert confirmed["removed"] == [LOW_RISK_AUTOMERGE]
    assert confirmed["forced"] == [LOW_RISK_AUTOMERGE]
    assert not workflow.exists()


def test_tiered_review_workflow_never_executes_proposed_content(tmp_path):
    repo = init_repo(
        "repo-python",
        tmp_path,
        overrides=["workflow_style=pr", "features.tiered_review=true"],
    )
    code, result = run_script("render.py", "apply", repo)
    assert code == 0, result

    workflow = (repo / LOW_RISK_AUTOMERGE).read_text()
    trigger = workflow.split("\non:\n", 1)[1].split("\npermissions:\n", 1)[0]
    permissions = workflow.split("\npermissions:\n", 1)[1].split("\nconcurrency:\n", 1)[0]

    assert "# managed-by: shipshape" in "\n".join(workflow.splitlines()[:5])
    assert trigger == (
        "  pull_request_target:\n    types: [opened, synchronize, reopened, labeled]\n"
    )
    assert permissions == "  contents: read\n  pull-requests: write\n"
    assert not re.search(r"(?m)^\s*uses\s*:", workflow)
    for forbidden in (
        "actions/checkout",
        "github.event.pull_request.head",
        "github.head_ref",
        "head_ref",
        "gh pr checkout",
        "gh pr diff",
        "git fetch",
        "git clone",
        "git show",
        "curl ",
        "wget ",
        "eval ",
        "source ",
        "/archive/",
        "/blobs/",
        "/contents/",
        "actions/upload-artifact",
        "actions/cache",
    ):
        assert forbidden not in workflow
    for untrusted_context in (
        "github.event.pull_request.title",
        "github.event.pull_request.body",
        "github.event.pull_request.head.ref",
        "github.event.pull_request.labels",
    ):
        assert untrusted_context not in workflow


def test_tiered_review_workflow_fails_closed_on_incomplete_metadata(tmp_path):
    repo = init_repo(
        "repo-python",
        tmp_path,
        overrides=["workflow_style=pr", "features.tiered_review=true"],
    )
    code, result = run_script("render.py", "apply", repo)
    assert code == 0, result

    workflow = (repo / LOW_RISK_AUTOMERGE).read_text()
    assert "gh pr view" in workflow
    assert "author,body,commits,headRefOid,changedFiles,labels" in workflow
    assert 'API_PAGE_SIZE: "100"' in workflow
    assert "/pulls/" in workflow and "/files?per_page=$API_PAGE_SIZE" in workflow
    assert "--paginate" in workflow and "--slurp" in workflow
    assert "MAX_INSPECTABLE_FILES = 3000" in workflow
    assert "changedFiles" in workflow
    assert "len(files) != changed_files" in workflow
    assert "json.loads" in workflow
    assert "filename" in workflow and "status" in workflow
    assert "metadata:" in workflow
    assert "file count:" in workflow
    assert "file records:" in workflow
    assert 'if ! python3 - \\\n            "$pr_json"' in workflow


def test_tiered_review_workflow_pins_the_two_low_risk_classes(tmp_path):
    repo = init_repo(
        "repo-python",
        tmp_path,
        overrides=["workflow_style=pr", "features.tiered_review=true"],
    )
    code, result = run_script("render.py", "apply", repo)
    assert code == 0, result

    workflow = (repo / LOW_RISK_AUTOMERGE).read_text()
    for protected in (
        '".github/"',
        '".sdlc/"',
        '".claude/"',
        '".vscode/"',
        '"AGENTS.md"',
        '"CLAUDE.md"',
        '"SECURITY.md"',
        '"docs/sdlc/"',
        '"docs/adr/"',
    ):
        assert protected in workflow
    for dependency_file in (
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "pyproject.toml",
        "poetry.lock",
        "uv.lock",
        "requirements*.txt",
        "go.mod",
        "go.sum",
        "Cargo.toml",
        "Cargo.lock",
        "Gemfile",
        "Gemfile.lock",
        "*.gradle",
        "gradle.lockfile",
    ):
        assert dependency_file in workflow
    assert 'author_login == "dependabot[bot]"' in workflow
    assert 'status == "modified"' in workflow
    assert "version-update:semver-patch" in workflow
    assert "version-update:semver-minor" in workflow
    assert "version-update:semver-major" in workflow


def test_tiered_review_workflow_authenticates_and_audits_break_glass(tmp_path):
    repo = init_repo(
        "repo-python",
        tmp_path,
        overrides=["workflow_style=pr", "features.tiered_review=true"],
    )
    code, result = run_script("render.py", "apply", repo)
    assert code == 0, result

    workflow = (repo / LOW_RISK_AUTOMERGE).read_text()
    assert "break-glass-automerge" in workflow
    assert "/issues/" in workflow and "/events?per_page=$API_PAGE_SIZE" in workflow
    assert "/collaborators/" in workflow and "/permission" in workflow
    assert '"admin"' in workflow and '"write"' in workflow
    assert "/comments?per_page=$API_PAGE_SIZE" in workflow
    assert "gh pr comment" in workflow
    assert "shipshape-break-glass" in workflow
    assert "label_event_id" in workflow
    assert "classified_head" in workflow
    assert "label_actor" in workflow
    assert "label_timestamp" in workflow
    assert "class rules were bypassed" in workflow
    assert "marker_count != 1" in workflow
    assert "break-glass must be reapplied to the classified head" in workflow
    assert '[ "$EVENT_ACTION" != "labeled" ]' in workflow
    assert workflow.count('[ "$marker_count" != "1" ]') == 1


def test_tiered_review_workflow_revokes_its_auto_merge_for_an_ineligible_head(tmp_path):
    repo = init_repo(
        "repo-python",
        tmp_path,
        overrides=["workflow_style=pr", "features.tiered_review=true"],
    )
    code, result = run_script("render.py", "apply", repo)
    assert code == 0, result

    workflow = (repo / LOW_RISK_AUTOMERGE).read_text()
    assert "autoMergeRequest,headRefOid" in workflow
    assert 'enabled_by == "github-actions[bot]"' in workflow
    assert "--disable-auto" in workflow
    assert "Removed workflow-owned auto-merge" in workflow


def test_tiered_review_workflow_binds_merge_to_the_classified_head(tmp_path):
    repo = init_repo(
        "repo-python",
        tmp_path,
        overrides=["workflow_style=pr", "features.tiered_review=true"],
    )
    code, result = run_script("render.py", "apply", repo)
    assert code == 0, result

    workflow = (repo / LOW_RISK_AUTOMERGE).read_text()
    assert workflow.count("headRefOid") >= 2
    assert "recheck_head" in workflow
    assert "head changed after classification" in workflow
    assert "gh pr merge" in workflow
    assert '--match-head-commit "$CLASSIFIED_HEAD"' in workflow
    assert "--auto --squash" in workflow


def run_tiered_review_classifier(tmp_path, *, author, body, files, commits):
    repo = init_repo(
        "repo-python",
        tmp_path,
        overrides=["workflow_style=pr", "features.tiered_review=true"],
    )
    code, result = run_script("render.py", "apply", repo)
    assert code == 0, result
    workflow = (repo / LOW_RISK_AUTOMERGE).read_text()
    match = re.search(r"<<'PY'\n(?P<script>.*?)\n          PY", workflow, re.DOTALL)
    assert match, "classifier script not found in rendered workflow"

    pr = {
        "author": {"login": author},
        "body": body,
        "changedFiles": len(files),
        "commits": commits,
        "headRefOid": "a" * 40,
        "labels": [],
    }
    pr_path = tmp_path / "pr.json"
    files_path = tmp_path / "files.json"
    commits_path = tmp_path / "commits.json"
    output_path = tmp_path / "github-output"
    pr_path.write_text(json.dumps(pr))
    files_path.write_text(json.dumps([files]))
    commits_path.write_text(json.dumps([commits]))
    proc = subprocess.run(
        [
            sys.executable,
            "-",
            str(pr_path),
            str(files_path),
            str(commits_path),
            str(output_path),
        ],
        input=textwrap.dedent(match.group("script")),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return dict(line.split("=", 1) for line in output_path.read_text().splitlines())


@pytest.mark.parametrize(
    ("path", "expected"),
    [("docs/guide.rst", "docs-only"), ("docs/build.sh", "none")],
)
def test_tiered_review_docs_class_rejects_executable_paths(tmp_path, path, expected):
    result = run_tiered_review_classifier(
        tmp_path,
        author="contributor",
        body="",
        files=[{"filename": path, "status": "modified"}],
        commits=[],
    )

    assert result["class_name"] == expected


def test_tiered_review_dependency_class_rejects_human_appended_commit(tmp_path):
    result = run_tiered_review_classifier(
        tmp_path,
        author="dependabot[bot]",
        body="version-update:semver-patch",
        files=[{"filename": "package.json", "status": "modified"}],
        commits=[
            {
                "authors": [{"login": "dependabot[bot]"}],
                "messageBody": "",
                "messageHeadline": "Bump example from 1.0.0 to 1.0.1",
            },
            {
                "authors": [{"login": "maintainer"}],
                "messageBody": "",
                "messageHeadline": "Add install script",
            },
        ],
    )

    assert result["class_name"] == "none"


@pytest.mark.parametrize(
    "path",
    [
        ".sdlc/package.json",
        ".claude/package.json",
        ".vscode/package-lock.json",
        "docs/sdlc/requirements.txt",
        "docs/adr/build.gradle",
        "AGENTS.md",
        "CLAUDE.md",
        "SECURITY.md",
    ],
)
def test_tiered_review_dependency_class_rejects_protected_paths(tmp_path, path):
    result = run_tiered_review_classifier(
        tmp_path,
        author="dependabot[bot]",
        body="version-update:semver-patch",
        files=[{"filename": path, "status": "modified"}],
        commits=[
            {
                "authors": [{"login": "dependabot[bot]"}],
                "messageBody": "version-update:semver-patch",
                "messageHeadline": "Bump dependency",
            }
        ],
    )

    assert result["class_name"] == "none"


def test_copilot_setup_matches_language_and_reviewer_has_frontmatter(tmp_path):
    repo = init_repo("repo-go", tmp_path)
    run_script("render.py", "apply", repo)
    setup = (repo / ".github/workflows/copilot-setup-steps.yml").read_text()
    assert "actions/setup-go" in setup
    assert "copilot-setup-steps:" in setup, "job name is contractual"
    reviewer = (repo / ".github/agents/reviewer.md").read_text()
    assert reviewer.startswith("---\nname: reviewer\n")
    assert "description:" in reviewer


def test_init_config_captures_detection(tmp_path):
    repo = init_repo("repo-python", tmp_path)
    config = json.loads((repo / ".sdlc/config.json").read_text())
    assert "python" in config["languages"]
    assert "pytest" in config["commands"]["test"]
    assert config["features"]["tiered_review"] is False


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
