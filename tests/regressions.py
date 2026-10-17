#!/usr/bin/env python3
"""Regression guard: one dated test per historically fixed bug, so none can
silently return. Every test's docstring opens with the date and symptom of
the bug it guards. Run directly: python3 tests/regressions.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
TEMPLATES = ROOT / "templates"
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT))


def render_fixture(fixture: str, root: Path, overrides: list[str] | None = None) -> Path:
    """Render a detected fixture through the consumer installation path."""
    repo = root / fixture
    shutil.copytree(FIXTURES / fixture, repo)
    detect = subprocess.run(
        [sys.executable, str(SCRIPTS / "detect.py"), str(repo), "--no-network"],
        capture_output=True,
        text=True,
        check=True,
    )
    detect_file = root / f"{fixture}-detect.json"
    detect_file.write_text(detect.stdout)
    init_args = [
        sys.executable,
        str(SCRIPTS / "render.py"),
        "init-config",
        str(repo),
        "--detect",
        str(detect_file),
    ]
    for override in overrides or []:
        init_args.extend(["--set", override])
    subprocess.run(init_args, capture_output=True, text=True, check=True)
    subprocess.run(
        [sys.executable, str(SCRIPTS / "render.py"), "apply", str(repo)],
        capture_output=True,
        text=True,
        check=True,
    )
    return repo


def run_focused_pytest(*nodeids: str, environment: dict[str, str] | None = None) -> None:
    """Run existing behavioral tests as dated regression evidence."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *nodeids],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_nested_foreign_files_cannot_claim_test_command() -> None:
    """2026-08-10: dogfooding on shipshape itself guessed 'go test ./...' as
    the test command for a pure-Python project. A single main.go deep in
    tests/fixtures/ produced a low-confidence 'go' language, the implicit
    'go test' runner was added regardless of confidence, and the guess picked
    runners alphabetically ('go test' < 'pytest'). Guard: implicit runners
    require high confidence and the guess follows language-confidence order."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\ntestpaths=['tests']\n")
        (root / "tests").mkdir()
        nested = root / "examples" / "toy-go"
        nested.mkdir(parents=True)
        (nested / "main.go").write_text("package main\n")
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "detect.py"), str(root), "--no-network"],
            capture_output=True,
            text=True,
            check=True,
        )
        result = json.loads(proc.stdout)
        assert result["test_command_guess"] == "pytest", result["test_command_guess"]


def test_lookalike_remote_host_is_not_github() -> None:
    """2026-08-10: CodeQL flagged detect_git's `"github.com" in url` substring
    check (high severity, incomplete URL sanitization) — a remote like
    https://evilgithub.com.attacker.example/o/r would have been classified as
    GitHub and its path offered as owner_repo. Guard: remotes are parsed into
    an exact host, and only github.com (or *.github.com) counts."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        subprocess.run(["git", "init", "-qb", "main", str(root)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "remote",
                "add",
                "origin",
                "https://evilgithub.com.attacker.example/owner/repo.git",
            ],
            check=True,
        )
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "detect.py"), str(root), "--no-network"],
            capture_output=True,
            text=True,
            check=True,
        )
        git_info = json.loads(proc.stdout)["git"]
        assert git_info["remote"] == "other", git_info
        assert git_info["owner_repo"] == "", git_info


def test_ci_doctor_uses_secret_scan_workflow() -> None:
    """2026-08-14: the weekly rendered doctor checked a per-clone pre-commit
    hook that cannot exist in GitHub Actions, so healthy repositories received
    false-positive health issues. Guard: CI checks the secret-scan workflow
    that protects pushed changes instead of the runner clone's local hook."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        doctor = root / ".sdlc" / "scripts" / "doctor.py"
        doctor.parent.mkdir(parents=True)
        template = TEMPLATES / "scripts" / "doctor.py.tmpl"
        doctor.write_text(template.read_text().replace("{{KIT_VERSION}}", "test"))
        review_gates = doctor.with_name("review-gates.py")
        review_gates.write_text(
            (TEMPLATES / "scripts" / "review-gates.py.tmpl")
            .read_text()
            .replace("{{KIT_VERSION}}", "test")
        )
        config = {
            "workflow_style": "trunk",
            "default_branch": "main",
            "languages": ["python"],
            "repo": {"owner_repo": ""},
            "features": {
                "branch_protection": False,
                "codeql": False,
                "github_agents": False,
                "scheduled_health": False,
                "secret_guard": True,
                "tiered_review": False,
            },
            "commands": {"test": ""},
        }
        (root / ".sdlc" / "config.json").write_text(json.dumps(config))
        guard = root / ".sdlc" / "hooks" / "secret-guard.sh"
        guard.parent.mkdir()
        guard.write_text("# layer 3: agent control files\n")
        workflow = root / ".github" / "workflows" / "secret-scan.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text("permissions:\n  contents: read\n")
        env = os.environ.copy()
        env["GITHUB_ACTIONS"] = "true"

        proc = subprocess.run(
            [sys.executable, str(doctor), str(root)],
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
        checks = {
            item["name"]: item
            for section in json.loads(proc.stdout)["sections"]
            for item in section["checks"]
        }
        installed = checks["secret guard installed"]
        assert installed["status"] == "WARN", installed
        assert installed["detail"] == (
            "secret-scan workflow is configured; local hook was not verified in GitHub Actions"
        ), installed


def test_python_ci_installs_pytest_when_project_does_not() -> None:
    """2026-08-24: a fresh Python repo's first CI run failed because the
    rendered workflow invoked pytest without ensuring the runner was installed."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = render_fixture("repo-python", Path(tmp))
        workflow = (repo / ".github" / "workflows" / "ci.yml").read_text()
        assert 'python -c "import pytest" >/dev/null 2>&1 || pip install pytest' in workflow


def test_low_risk_automerge_has_merge_permission() -> None:
    """2026-08-24: eligible pull requests could not enable auto-merge because
    the rendered PR-style workflow had read-only contents permission."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = render_fixture(
            "repo-python",
            Path(tmp),
            overrides=["workflow_style=pr", "features.tiered_review=true"],
        )
        workflow = (repo / ".github" / "workflows" / "low-risk-automerge.yml").read_text()
        assert "  contents: write\n" in workflow
        assert "  pull-requests: write\n" in workflow
        review_helper = repo / ".sdlc" / "scripts" / "review-gates.py"
        assert review_helper.is_file()
        assert review_helper.stat().st_mode & 0o111 == 0
        release_helper = repo / ".sdlc" / "scripts" / "release-preflight.py"
        assert release_helper.is_file()
        assert release_helper.stat().st_mode & 0o111


def test_verification_window_uses_the_exact_clock_boundary() -> None:
    """2026-09-10: verification-cost aggregation mixed a date boundary with
    an exact timestamp boundary, so a run just outside the window could count."""
    from scripts import verification_cost

    original_fetch = verification_cost.fetch_json
    original_token = os.environ.get("GITHUB_TOKEN")
    now = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
    search_queries = []

    def fake_fetch(path: str):
        if path.startswith("repos/"):
            return {
                "workflow_runs": [
                    {
                        "run_attempt": 1,
                        "run_started_at": "2026-08-10T12:00:00Z",
                        "updated_at": "2026-08-10T12:01:00Z",
                    },
                    {
                        "run_attempt": 1,
                        "run_started_at": "2026-08-10T11:59:59.999999Z",
                        "updated_at": "2026-08-10T12:01:00Z",
                    },
                ]
            }
        search_queries.append(urllib.parse.unquote(path.split("q=", 1)[1].split("&", 1)[0]))
        return {"total_count": 1}

    try:
        os.environ["GITHUB_TOKEN"] = "regression-token"
        verification_cost.fetch_json = fake_fetch
        result = verification_cost.summarize("example/project", 30, now=now)
    finally:
        verification_cost.fetch_json = original_fetch
        if original_token is None:
            os.environ.pop("GITHUB_TOKEN", None)
        else:
            os.environ["GITHUB_TOKEN"] = original_token

    assert result["runs"] == 1, result
    assert result["minutes"] == 1, result
    assert search_queries == [
        "repo:example/project is:pr is:merged merged:>=2026-08-10T12:00:00+00:00"
    ], search_queries


def test_automatic_merge_rejects_nested_and_renamed_controls() -> None:
    """2026-09-09: nested controls and a rename away from a control path were
    classified from only the destination basename and became auto-mergeable;
    plural ADR and decision directories were also treated as ordinary docs."""
    from scripts import review_gates

    def blob(path: str) -> dict:
        return {"path": path, "mode": "100644", "type": "blob", "sha": "f" * 40}

    nested = "docs/guides/AGENTS.md"
    classification, _ = review_gates.classify_documentation(
        [{"filename": nested, "status": "modified"}],
        {nested: blob(nested)},
        {nested: blob(nested)},
    )
    assert classification == "none"

    old = ".github/agents/reviewer.md"
    new = "docs/guides/reviewer.md"
    classification, _ = review_gates.classify_documentation(
        [{"filename": new, "previous_filename": old, "status": "renamed"}],
        {old: blob(old)},
        {new: blob(new)},
    )
    assert classification == "none"

    for path in (
        "docs/adrs/0010-architecture.md",
        "docs/decisions/0010-platform.md",
        "docs/architecture-decisions/0010-platform.md",
    ):
        classification, _ = review_gates.classify_documentation(
            [{"filename": path, "status": "modified"}],
            {path: blob(path)},
            {path: blob(path)},
        )
        assert classification == "none", path

    guide = "docs/guides/usage.md"
    classification, _ = review_gates.classify_documentation(
        [{"filename": guide, "status": "modified"}],
        {guide: blob(guide)},
        {guide: blob(guide)},
    )
    assert classification == "docs-only"


def test_weekly_report_projects_alerts_and_paginates_pulls() -> None:
    """2026-09-09: weekly collection retained unbounded API alert fields and
    treated a full first page of open pull requests as a complete result."""
    from scripts import security_report

    class API:
        def __init__(self):
            self.calls = []
            self.unretained_fixture_value = "fixture-" + "private-material"
            self.responses = {
                "repos/example/project": {
                    "full_name": "example/project",
                    "default_branch": "main",
                },
                "repos/example/project/code-scanning/alerts?state=open&per_page=100&page=1": [],
                "repos/example/project/dependabot/alerts?state=open&per_page=100&page=1": [],
                "repos/example/project/secret-scanning/alerts?state=open&per_page=100&page=1": [
                    {
                        "secret_type_display_name": "Synthetic token",
                        "html_url": "https://example.invalid/secret/1",
                        "secret": self.unretained_fixture_value,
                        "future_api_field": "unretained",
                    }
                ],
                "repos/example/project/actions/runs?branch=main&per_page=20": {
                    "workflow_runs": [],
                    "total_count": 0,
                },
                "repos/example/project/pulls?state=open&per_page=50&page=1": [
                    {
                        "number": number,
                        "title": f"Pull {number}",
                        "created_at": "2026-09-09T08:00:00Z",
                        "draft": False,
                    }
                    for number in range(1, 51)
                ],
                "repos/example/project/pulls?state=open&per_page=50&page=2": [],
            }

        def get(self, path: str):
            self.calls.append(path)
            return self.responses[path]

    with tempfile.TemporaryDirectory() as tmp:
        api = API()
        report = security_report.collect_report(
            api,
            "example/project",
            Path(tmp),
        )

    sections = report["raw_collection"]["sections"]
    assert set(sections["secret_scanning"]["items"][0]) == {
        "secret_type_display_name",
        "html_url",
    }
    assert sections["pull_requests"]["count"] == 50
    assert "repos/example/project/pulls?state=open&per_page=50&page=2" in api.calls
    assert api.unretained_fixture_value not in json.dumps(report)


def test_automatic_authority_uses_exact_gates_and_refuses_persistent_state() -> None:
    """2026-09-09: check names without exact sources and prior persistent
    auto-merge state could be treated as current automatic authority."""
    from scripts import review_gates

    gates = review_gates.required_gates(True)
    assert [(gate.context, gate.app_id) for gate in gates] == [
        ("test", review_gates.GITHUB_ACTIONS_APP_ID),
        ("secret-scan", review_gates.GITHUB_ACTIONS_APP_ID),
        ("CodeQL", review_gates.CODEQL_APP_ID),
    ]

    class PersistentAPI:
        def get(self, path: str):
            if path == "repos/example/project":
                return {
                    "id": 1,
                    "name": "project",
                    "full_name": "example/project",
                    "url": "https://api.github.com/repos/example/project",
                    "default_branch": "main",
                }
            return {
                "id": 2,
                "number": 7,
                "url": "https://api.github.com/repos/example/project/pulls/7",
                "state": "open",
                "draft": False,
                "changed_files": 1,
                "merge_commit_sha": "c" * 40,
                "mergeable": True,
                "mergeable_state": "clean",
                "head": {
                    "sha": "a" * 40,
                    "ref": "docs",
                    "repo": {
                        "id": 3,
                        "name": "project",
                        "full_name": "contributor/project",
                        "url": "https://api.github.com/repos/contributor/project",
                    },
                },
                "base": {
                    "sha": "b" * 40,
                    "ref": "main",
                    "repo": {
                        "id": 1,
                        "name": "project",
                        "full_name": "example/project",
                        "url": "https://api.github.com/repos/example/project",
                    },
                },
            }

        def graphql(self, _query, _variables):
            return {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "id": "PR_7",
                            "autoMergeRequest": {"enabledBy": {"login": "maintainer"}},
                        }
                    }
                }
            }

        def put(self, _path, _payload):
            raise AssertionError("persistent authorization must refuse before mutation")

    result = review_gates.evaluate(PersistentAPI(), "example/project", 7)
    assert result["merged"] is False, result
    assert result["persistent_auto_merge_present"] is True, result
    assert "cancel auto-merge manually" in result["reason"].lower(), result


def test_secret_guard_scans_history_and_propagates_git_errors() -> None:
    """2026-09-09: history scans could miss add-then-remove secrets, text-diff
    presentation could hide content, and Git inspection errors could pass."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = render_fixture("repo-python", Path(tmp))
        subprocess.run(["git", "init", "-qb", "main"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Regression"], cwd=repo, check=True)
        subprocess.run(
            ["git", "config", "user.email", "regression@example.invalid"], cwd=repo, check=True
        )
        (repo / "base.txt").write_text("clean\n")
        subprocess.run(["git", "add", "base.txt"], cwd=repo, check=True)
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "base"],
            cwd=repo,
            check=True,
        )
        base = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
        ).stdout.strip()
        synthetic_key = "AKIA" + "A" * 16
        (repo / "note.txt").write_text(f"++{synthetic_key}\n")
        subprocess.run(["git", "add", "note.txt"], cwd=repo, check=True)
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "add then remove"],
            cwd=repo,
            check=True,
        )
        (repo / "note.txt").unlink()
        subprocess.run(["git", "add", "-u"], cwd=repo, check=True)
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "remove"],
            cwd=repo,
            check=True,
        )
        guard = ["bash", ".sdlc/hooks/secret-guard.sh", "--range"]
        history = subprocess.run(
            [*guard, f"{base}..HEAD"], cwd=repo, capture_output=True, text=True
        )
        invalid = subprocess.run(
            [*guard, "missing-revision..HEAD"], cwd=repo, capture_output=True, text=True
        )
        assert history.returncode == 1, history.stderr
        assert "API key" in history.stderr and synthetic_key not in history.stderr
        assert invalid.returncode != 0 and "could not inspect" in invalid.stderr


def test_hook_installation_preserves_user_hook_and_pins_commit_stage() -> None:
    """2026-09-09: installation could overwrite custom hooks, while a global
    manual-only pre-commit default silently kept the guard out of commits."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = render_fixture("repo-python", Path(tmp))
        subprocess.run(["git", "init", "-qb", "main"], cwd=repo, check=True)
        hook = repo / ".git" / "hooks" / "pre-commit"
        original = b"#!/bin/sh\nprintf user-hook\n"
        hook.write_bytes(original)
        hook.chmod(0o755)
        result = subprocess.run(
            ["bash", ".sdlc/hooks/install.sh"], cwd=repo, capture_output=True, text=True
        )
        assert result.returncode != 0, result.stdout
        assert hook.read_bytes() == original
        pre_commit = (repo / ".pre-commit-config.yaml").read_text()
        assert "stages: [pre-commit]" in pre_commit


def test_node_package_manager_selection_is_explicit() -> None:
    """2026-09-09: Node setup defaulted to npm despite lockfiles or unsafe,
    conflicting package-manager declarations."""
    from scripts import detect

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        (repo / "package.json").write_text('{"packageManager":"pnpm@10.15.1"}\n')
        (repo / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
        selected = detect.detect_node_package_manager(repo)
        assert selected["name"] == "pnpm", selected
        assert selected["variant"] == "pnpm", selected
        (repo / "package-lock.json").write_text("{}\n")
        conflict = detect.detect_node_package_manager(repo)
        assert "conflicting Node package-manager signals" in conflict["error"], conflict


def test_setup_refuses_symlinks_and_records_partial_completion() -> None:
    """2026-09-09: setup could follow repository symlinks, overwrite config,
    or claim the newest kit version after a partial apply."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        escaped = root / "outside.json"
        escaped.write_text('{"outside":true}\n')
        unsafe = root / "unsafe"
        (unsafe / ".sdlc").mkdir(parents=True)
        (unsafe / ".sdlc" / "config.json").symlink_to(escaped)
        refused = subprocess.run(
            [sys.executable, str(SCRIPTS / "render.py"), "plan", str(unsafe)],
            capture_output=True,
            text=True,
        )
        assert refused.returncode == 1 and "symlink" in refused.stdout
        assert escaped.read_text() == '{"outside":true}\n'

        repo = render_fixture("repo-python", root)
        claude = repo / "CLAUDE.md"
        claude.write_text(claude.read_text() + "\nUser edit.\n")
        (repo / "AGENTS.md").unlink()
        state_path = repo / ".sdlc" / "state.json"
        state = json.loads(state_path.read_text())
        state["kit_version"] = state["completed_kit_version"] = "0.1.0"
        state_path.write_text(json.dumps(state))
        applied = subprocess.run(
            [sys.executable, str(SCRIPTS / "render.py"), "apply", str(repo)],
            capture_output=True,
            text=True,
            check=True,
        )
        result = json.loads(applied.stdout)
        final_state = json.loads(state_path.read_text())
        assert result["status"] == "partial", result
        assert final_state["completed_kit_version"] == "0.1.0", final_state
        assert final_state["pending_conflicts"] == ["CLAUDE.md"], final_state


def test_release_publisher_uses_exact_context_from_a_bare_directory() -> None:
    """2026-09-09: the release publisher relied on checkout Git context and
    could publish from an implicit repository or a non-exact candidate."""
    workflow = (TEMPLATES / "github" / "workflows" / "release.yml.tmpl").read_text()
    section = workflow.split("      - name: Verify the exact tag and publish\n", 1)[1]
    block = section.split("        run: |\n", 1)[1]
    script_lines = []
    for line in block.splitlines():
        if line and not line.startswith("          "):
            break
        script_lines.append(line[10:] if line.startswith("          ") else "")
    script = textwrap.dedent("\n".join(script_lines))

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        runner = root / "runner"
        runner.mkdir()
        helper = runner / "release-preflight.py"
        helper.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "expected=['publish','--repo',os.environ['GITHUB_REPOSITORY'],'--tag',"
            "os.environ['GITHUB_REF_NAME'],'--candidate',os.environ['GITHUB_SHA']]\n"
            "if sys.argv[1:] != expected:\n"
            "    raise SystemExit(2)\n"
            "print(json.dumps({'ok': True, 'candidate_sha': os.environ['GITHUB_SHA']}))\n"
        )
        bindir = root / "bin"
        bindir.mkdir()
        calls = root / "calls.json"
        fake_gh = bindir / "gh"
        fake_gh.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "args=sys.argv[1:]\n"
            "json.dump(args, open(os.environ['CALLS'], 'w'))\n"
            "raise SystemExit(0 if '--repo' in args and '--target' in args else 2)\n"
        )
        fake_gh.chmod(0o755)
        environment = os.environ.copy()
        environment.update(
            {
                "CALLS": str(calls),
                "GH_TOKEN": "regression-token",
                "GITHUB_REF_NAME": "v1.2.3",
                "GITHUB_REPOSITORY": "example/project",
                "GITHUB_SHA": "a" * 40,
                "PATH": f"{bindir}{os.pathsep}{environment['PATH']}",
                "RUNNER_TEMP": str(runner),
            }
        )
        result = subprocess.run(
            ["bash", "-c", script], cwd=root, capture_output=True, text=True, env=environment
        )
        assert result.returncode == 0, result.stderr
        call = json.loads(calls.read_text())
        assert call[call.index("--repo") + 1] == "example/project", call
        assert call[call.index("--target") + 1] == "a" * 40, call


def test_reviewed_plan_binds_candidate_and_rendered_outputs() -> None:
    """2026-09-10: apply could accept changed candidate bytes or changed
    rendered output after a human reviewed an earlier plan."""
    run_focused_pytest(
        "tests/test_setup_safety.py::test_reviewed_candidate_change_is_rejected_before_repository_mutation",
        "tests/test_setup_safety.py::test_reviewed_candidate_byte_change_is_rejected_even_when_json_is_equal",
        "tests/test_codex_plugin.py::test_reviewed_plan_rejects_a_changed_rendered_template_before_writes",
    )


def test_managed_drift_uses_raw_bytes_and_recorded_modes() -> None:
    """2026-09-10: CRLF-only and chmod-only edits could look unchanged, and
    legacy records could adopt a mode without evidence."""
    run_focused_pytest(
        "tests/test_setup_safety.py::test_crlf_only_drift_conflicts_before_regeneration",
        "tests/test_setup_safety.py::test_mode_only_drift_conflicts_before_removal",
        "tests/test_setup_safety.py::test_legacy_state_does_not_adopt_an_unknown_mode",
        "tests/test_setup_safety.py::test_legacy_state_migrates_known_generated_modes",
    )


def test_copied_bundle_upgrade_preserves_completion_truth() -> None:
    """2026-09-10: a newer copied bundle could leave config and generated
    files stale while recording the new version as completely installed."""
    run_focused_pytest(
        "tests/test_codex_plugin.py::test_copied_bundle_upgrade_updates_config_outputs_and_completed_state",
        "tests/test_codex_plugin.py::test_copied_bundle_upgrade_keeps_completion_at_old_version_on_conflict",
    )


def test_fresh_node_setup_requires_reproducible_inputs() -> None:
    """2026-09-10: fresh Node setup accepted missing lockfiles and missing or
    contradictory package-manager declarations."""
    run_focused_pytest(
        "tests/test_package_managers.py::test_package_json_without_a_lockfile_is_rejected_for_fresh_setup",
        "tests/test_package_managers.py::test_non_npm_lock_requires_an_exact_package_manager_declaration",
        "tests/test_package_managers.py::test_contradictory_manager_signals_fail_instead_of_defaulting_to_npm",
    )


def test_node_25_bootstrap_is_pinned_and_ordered() -> None:
    """2026-09-10: accepted Node 25 workflows invoked absent bundled
    Corepack instead of installing a pinned compatible manager first."""
    run_focused_pytest(
        "tests/test_package_managers.py::test_node_25_installs_pinned_corepack_before_enabling_manager",
        "tests/test_package_managers.py::test_node_25_declared_npm_installs_the_exact_manager_without_corepack",
    )


def test_managed_helpers_install_remove_and_preserve_drift() -> None:
    """2026-09-10: release-preflight and review-gates generated copies were
    absent from installation or removal expectations and drift guarantees."""
    run_focused_pytest(
        "tests/test_render.py::test_full_apply",
        "tests/test_render.py::test_tiered_review_requires_pr_style_and_feature_flag",
        "tests/test_render.py::test_disabling_tiered_review_removes_the_managed_workflow",
        "tests/test_render.py::test_disabling_tiered_review_never_deletes_a_drifted_workflow",
    )


def test_setup_callers_apply_only_the_saved_preview() -> None:
    """2026-09-10: init and customize could apply a regenerated proposal
    without binding it to the JSON preview the person approved."""
    run_focused_pytest(
        "tests/test_doctor.py::test_setup_skills_bind_apply_to_the_saved_preview",
        "tests/test_setup_safety.py::test_proposed_config_and_plan_do_not_modify_repository",
        "tests/test_setup_safety.py::test_candidate_apply_requires_the_reviewed_plan_digest",
    )


def test_doctor_health_uses_byte_mode_and_version_evidence() -> None:
    """2026-09-10: both doctors could call CRLF or mode drift unmodified and
    pass installed-version health while config still named another version."""
    run_focused_pytest(
        "tests/test_doctor.py::test_managed_file_inspection_detects_byte_and_mode_only_edits",
        "tests/test_doctor.py::test_managed_file_inspection_warns_when_legacy_modes_are_unknown",
        "tests/test_doctor.py::test_managed_file_inspection_does_not_follow_symlinks",
        "tests/test_doctor.py::test_kit_version_requires_config_and_completed_state_to_match",
        "tests/test_rendered_doctor.py::test_rendered_doctor_detects_byte_and_mode_only_edits",
        "tests/test_rendered_doctor.py::test_rendered_doctor_exposes_unknown_legacy_modes",
    )


def test_release_latest_current_attempt_uses_run_started_at() -> None:
    """2026-09-10: release evidence ordered by run number and ignored a
    chronologically later failed attempt of an older workflow run."""
    run_focused_pytest(
        "tests/test_release_preflight.py::test_chronologically_later_older_run_rerun_takes_precedence"
    )


def test_release_readiness_requires_registered_active_publisher() -> None:
    """2026-09-10: local release readiness could pass without the exact active
    release workflow and publication helper on the candidate commit."""
    run_focused_pytest(
        "tests/test_release_preflight.py::test_local_preflight_requires_exact_active_release_workflow",
        "tests/test_release_preflight.py::test_local_preflight_requires_exact_publication_helper",
    )


def test_release_uses_push_code_scanning_evidence() -> None:
    """2026-10-13: every CodeQL-enabled release failed because default-branch
    push commits lack the required check run; absent severity and later API
    pages could also let incomplete CodeQL evidence pass."""
    run_focused_pytest(
        "tests/test_release_preflight.py::test_push_commit_with_no_codeql_check_run_uses_clean_code_scanning_evidence",
        "tests/test_release_preflight.py::test_open_high_codeql_alert_on_candidate_refuses_without_echoing_source",
        "tests/test_release_preflight.py::test_missing_security_severity_member_fails_closed",
        "tests/test_release_preflight.py::test_codeql_analysis_on_second_page_satisfies_exact_candidate_evidence",
        "tests/test_release_preflight.py::test_blocking_codeql_alert_on_second_page_refuses_release",
        "tests/test_release_preflight.py::test_all_release_modes_refuse_blocking_codeql_alerts",
    )


def test_review03_automation_boundaries() -> None:
    """2026-09-10: broad documentation paths, partial GraphQL errors, and
    run-number ordering could incorrectly authorize automatic merging."""
    run_focused_pytest(
        "tests/test_render.py::test_tiered_review_docs_class_rejects_executable_paths",
        "tests/test_review_gates.py::test_rename_checks_both_sides_of_fixed_document_location_allowlist",
        "tests/test_review_gates.py::test_partial_graphql_errors_never_prove_persistent_auto_merge_absent",
        "tests/test_review_gates.py::test_malformed_graphql_errors_state_remains_unknown",
        "tests/test_review_gates.py::test_chronologically_later_lower_id_rerun_overrides_older_green",
        "tests/test_review_gates.py::test_malformed_workflow_run_chronology_never_merges",
    )


def test_review03_configured_protection_modes() -> None:
    """2026-09-10: health inspection could omit ordinary branch protection,
    infer CodeQL from presence, or accept malformed feature metadata."""
    run_focused_pytest(
        "tests/test_protection.py::test_config_derives_exact_ordinary_pr_protection_request",
        "tests/test_protection.py::test_config_derives_exact_trunk_safeguard_request_without_status_checks",
        "tests/test_protection.py::test_config_derives_exact_tiered_pr_request",
        "tests/test_protection.py::test_config_derivation_rejects_nonboolean_feature_flags",
        "tests/test_protection.py::test_configured_protection_reports_missing_codeql_as_unknown_without_api_reads",
        "tests/test_protection.py::test_non_tiered_requested_protection_is_inspected_and_missing_state_refuses",
        "tests/test_doctor.py::test_non_tiered_pr_protection_is_verified_read_only",
        "tests/test_doctor.py::test_trunk_protection_is_verified_without_inventing_status_checks",
        "tests/test_doctor.py::test_configured_applicable_codeql_missing_is_not_reported_as_protected",
        "tests/test_rendered_doctor.py::test_rendered_doctor_verifies_non_tiered_pr_protection_read_only",
        "tests/test_rendered_doctor.py::test_rendered_doctor_verifies_trunk_safeguards_without_status_checks",
        "tests/test_rendered_doctor.py::test_rendered_doctor_rejects_malformed_protection_metadata",
    )


def test_review03_guard_report_access_boundaries() -> None:
    """2026-09-10: structured control files could evade the guard, and
    truncated Actions history or obsolete access syntax could overclaim proof."""
    run_focused_pytest(
        "tests/test_secret_guard.py::test_complete_executable_json_structure_is_blocked",
        "tests/test_secret_guard.py::test_value_only_change_under_split_command_key_is_blocked",
        "tests/test_secret_guard.py::test_guard_reads_exact_staged_control_blob",
        "tests/test_secret_guard.py::test_malformed_supported_json_fails_closed_without_leaking_content",
        "tests/test_secret_guard.py::test_range_mode_scans_each_control_blob_before_later_removal",
        "tests/test_security_report.py::test_actions_window_reports_available_history_truncation",
        "tests/test_security_report.py::test_actions_window_rejects_invalid_total_count",
    )
    access_skill = ROOT / "skills" / "shipshape-access" / "SKILL.md"
    assert "protect <branch> <trunk|pr>" in access_skill.read_text()


def test_doctor_tests_isolate_ambient_github_actions_mode() -> None:
    """2026-09-10: hosted pytest inherited GITHUB_ACTIONS=true, so local-hook
    tests accidentally exercised the doctor's explicit CI evidence mode."""
    environment = os.environ.copy()
    environment["GITHUB_ACTIONS"] = "true"
    run_focused_pytest(
        "tests/test_doctor.py::test_uninstalled_guard_is_fail_with_fix",
        "tests/test_doctor.py::test_github_actions_reports_configuration_without_claiming_local_hook",
        "tests/test_rendered_doctor.py::test_rendered_doctor_still_requires_local_hook_outside_ci",
        "tests/test_rendered_doctor.py::test_rendered_doctor_accepts_secret_scan_in_ci_without_local_hook",
        environment=environment,
    )


def test_weekly_report_rejects_untrusted_repository_metadata() -> None:
    """2026-09-10: a path-insensitive synthetic API fixture made a raw alert
    field appear able to become repository metadata and reach JSON stdout."""
    run_focused_pytest(
        "tests/test_security_report.py::test_alert_records_are_projected_through_section_allowlists",
        "tests/test_security_report.py::test_malformed_repository_metadata_is_not_echoed",
    )


def test_prove_kills_what_a_finished_command_left_running() -> None:
    """2026-10-16: a proved command that exited and left a background child
    running let the child outlive the scan: the prove step killed a command's
    process group only when the budget ran out or the scan was stopped."""
    run_focused_pytest(
        "tests/test_detect_checks.py::test_prove_kills_what_a_finished_command_left_running",
    )


def test_prove_under_no_network_runs_commands_offline() -> None:
    """2026-10-16: --no-network skipped only the gh probe, so a scan run with
    --prove and --no-network still let cargo, go and npm fetch dependencies."""
    run_focused_pytest(
        "tests/test_detect_checks.py::test_prove_without_network_runs_commands_offline",
    )


def test_node_check_scripts_match_safe_configured_commands() -> None:
    """2026-10-17: Node check scripts could hide unsafe shell flags or lifecycle hooks,
    and pnpm, Yarn or Bun test checks could prove a different command than config."""
    run_focused_pytest(
        "tests/test_detect_checks.py::test_node_scripts_that_delegate_to_unsafe_scripts_are_never_proposed",
        "tests/test_detect_checks.py::test_node_check_screens_lifecycle_hooks_for_selected_and_delegated_scripts",
        "tests/test_detect_checks.py::test_node_script_flag_screening_respects_shell_tokens",
        "tests/test_detect_checks.py::test_safe_node_script_cycle_does_not_recurse_forever",
        "tests/test_detect_checks.py::test_an_unsafe_node_test_script_is_not_guessed_or_proposed",
        "tests/test_detect_checks.py::test_node_scripts_propose_checks_through_the_projects_runner",
    )


def test_unsafe_node_test_script_does_not_hide_go_test_check() -> None:
    """2026-10-17: an unsafe Node test script could suppress a selected Go test."""
    run_focused_pytest(
        "tests/test_detect_checks.py::test_an_unsafe_node_test_script_does_not_hide_a_go_test_check",
    )


def test_node_check_screen_reads_scripts_as_the_shell_does() -> None:
    """2026-10-17: shell punctuation (`--fix>lint.log`, `(eslint . --fix)`),
    a shell wrapper (`sh -c 'eslint . --fix'`), a command string passed to
    another program, or a script named by run-s or npm-run-all kept a rewrite
    flag from the Node check screen, so --prove could rewrite sources."""
    run_focused_pytest(
        "tests/test_detect_checks.py::test_shell_punctuation_cannot_hide_a_rejected_flag",
        "tests/test_detect_checks.py::test_a_script_running_shell_code_the_screen_cannot_read_is_never_proposed",
        "tests/test_detect_checks.py::test_a_script_named_through_any_runner_is_screened",
        "tests/test_detect_checks.py::test_a_safe_script_using_shell_syntax_is_still_proposed",
    )


def test_unsafe_node_test_script_lets_another_runner_be_guessed() -> None:
    """2026-10-17: dropping an unsafe Node test script cleared the test guess
    instead of passing to the next runner, so a Node and Python repo whose
    test script watched got the no-tests placeholder instead of pytest."""
    run_focused_pytest(
        "tests/test_detect_checks.py::test_an_unsafe_node_test_script_lets_another_languages_runner_be_guessed",
    )


def test_a_shell_expansion_cannot_hide_a_rejected_flag() -> None:
    """2026-10-17: the shell joins `--fi`, a backslash-newline and `x` into --fix,
    expands `--{fix,}` into --fix, puts `$(cat .lint-flags)` output in the command
    and turns `--fi?` into a file named --fix, but shlex does none of that, so the
    Node check screen passed scripts that rewrite files."""
    run_focused_pytest(
        "tests/test_detect_checks.py::test_a_shell_expansion_cannot_hide_a_rejected_flag",
        "tests/test_detect_checks.py::test_a_pattern_that_cannot_make_a_rejected_flag_is_still_proposed",
    )


def test_prove_reaps_what_it_kills() -> None:
    """2026-10-17: in a container whose PID 1 reaps nothing, the prove step
    killed a command's whole group at once, so the shell died before it could
    reap its child and every interrupted proof left a zombie; on Windows only
    the shell was killed."""
    run_focused_pytest(
        "tests/test_detect_checks.py::test_prove_reaps_what_it_kills_where_pid_1_reaps_nothing",
        "tests/test_detect_checks.py::test_prove_ends_the_process_tree_where_there_are_no_process_groups",
    )


def test_a_script_running_other_packages_scripts_is_never_proposed() -> None:
    """2026-10-17: the Node check screen reads only the root package.json, yet
    it proposed `npm run lint --workspaces`, `pnpm -r run lint` and the other
    forms that run each package's own lint, which may be `eslint . --fix`."""
    run_focused_pytest(
        "tests/test_detect_checks.py::test_a_script_running_other_packages_scripts_is_never_proposed",
        "tests/test_detect_checks.py::test_mochas_require_flag_is_not_read_as_a_recursive_run",
    )


def test_prove_answers_when_stopped_by_any_stop_signal() -> None:
    """2026-10-17: the prove step handled only SIGTERM, so a SIGHUP from a
    closed terminal killed the scan with no JSON and left the proved command's
    group running in its own session; a nohup'd scan must still ignore it."""
    run_focused_pytest(
        "tests/test_detect_checks.py::test_prove_answers_and_kills_the_running_command_when_it_is_stopped",
        "tests/test_detect_checks.py::test_prove_keeps_ignoring_a_signal_the_caller_ignored",
    )


def test_a_deep_script_chain_is_not_proposed_and_the_scan_answers() -> None:
    """2026-10-17: a chain of a few hundred scripts each running the next ran
    the Node check screen out of stack, so the scan printed a traceback and no
    JSON, even without --prove."""
    run_focused_pytest(
        "tests/test_detect_checks.py::test_a_script_chain_deeper_than_the_screen_follows_is_not_proposed",
    )


def test_jest_watch_all_is_not_a_check() -> None:
    """2026-10-17: `jest --watchAll` (and `--watch-all`, `vitest watch`) was
    proposed as the test check, so --prove ran it until the shared budget
    ended and every later check stayed unproven."""
    run_focused_pytest(
        "tests/test_detect_checks.py::test_an_unsafe_node_test_script_is_not_guessed_or_proposed",
    )


def test_a_script_named_by_any_glob_is_screened() -> None:
    """2026-10-17: a word naming scripts was read as a glob only when it held
    `*`, so `run-s 'lint:fi?'`, `run-s 'lint:fi[x]'` and concurrently's
    `npm:lint:fix` ran a rewriting script the screen never read."""
    run_focused_pytest(
        "tests/test_detect_checks.py::test_a_script_named_through_any_runner_is_screened",
        "tests/test_detect_checks.py::test_a_safe_script_using_shell_syntax_is_still_proposed",
    )


def test_check_output_cannot_hold_the_runner() -> None:
    """2026-10-16: checks.py read a check's output through a pipe, so a check
    that passed but left a child holding its output ran out the budget and was
    reported failed, a child that left the check's process group kept the
    runner from answering a stop, and the whole output was held in memory."""
    run_focused_pytest(
        "tests/test_checks.py::test_a_check_that_leaves_a_child_holding_its_output_passes_at_once",
        "tests/test_checks.py::test_a_stop_answers_while_a_child_outside_the_group_holds_the_output",
    )


def test_failure_counts_take_linear_time_on_blank_lines() -> None:
    """2026-10-16: the pytest and jest or vitest summary patterns matched blanks
    with \\s*, which ran across line ends, so a run of blank lines in a check's
    output took quadratic time to count failures in."""
    run_focused_pytest(
        "tests/test_checks.py::test_run_counts_failures_after_a_long_run_of_blank_lines_in_linear_time",
    )


def test_a_run_where_nothing_ran_is_not_ok() -> None:
    """2026-10-16: checks.py answered "ok": true when no check ran, so a caller
    gating on "ok" read a repo without checks as green."""
    run_focused_pytest(
        "tests/test_checks.py::test_run_without_config_or_commands_runs_nothing_and_exits_zero",
        "tests/test_checks.py::test_run_with_no_command_set_runs_nothing",
    )


def test_cargo_failures_add_up_across_test_binaries() -> None:
    """2026-10-16: cargo test --no-fail-fast prints a summary per test binary,
    and checks.py counted only the last one's failures."""
    run_focused_pytest(
        "tests/test_checks.py::test_run_counts_the_failures_a_tool_reports",
    )


def test_checks_run_reaps_what_it_kills() -> None:
    """2026-10-17: in a container whose PID 1 reaps nothing, checks.py killed a
    check's whole group at once, so the shell died before it could reap its
    child and every stopped or finished check left a zombie; on Windows only
    the shell was killed."""
    run_focused_pytest(
        "tests/test_checks.py::test_run_reaps_what_it_kills_where_pid_1_reaps_nothing",
        "tests/test_checks.py::test_run_ends_the_process_tree_where_there_are_no_process_groups",
    )


def test_review_asks_before_running_another_authors_checks() -> None:
    """2026-10-17: shipshape-review ran the checks on another author's
    checked-out branch without asking unless its config, package scripts or
    CI files changed, although the checks run that branch's tests and test
    configuration, which are its code too."""
    run_focused_pytest(
        "tests/test_review_contract.py::test_review_skill_asks_before_running_another_authors_checks_whatever_changed",
    )


def test_checks_run_answers_and_kills_the_check_on_any_stop() -> None:
    """2026-10-17: checks.py handled only SIGTERM, so Ctrl-C, a closed terminal
    or SIGQUIT ended the runner with no JSON while the check, leading a session
    of its own, kept running; the wait's cleanup also skipped an exception."""
    run_focused_pytest(
        "tests/test_checks.py::test_a_stop_kills_the_running_check_and_still_answers",
        "tests/test_checks.py::test_a_signal_the_caller_ignored_stays_ignored",
        "tests/test_checks.py::test_a_check_is_killed_however_its_wait_ends",
    )


def test_a_check_not_reached_is_never_all_passed() -> None:
    """2026-10-17: a stop or the budget that kept a check from running still
    gave "ok": true when the checks that ran passed, and a stop before the
    first check said "All checks passed."."""
    run_focused_pytest(
        "tests/test_checks.py::test_a_stop_before_the_first_check_is_not_all_passed",
        "tests/test_checks.py::test_a_stop_between_checks_is_not_ok",
        "tests/test_checks.py::test_a_budget_that_ends_between_checks_is_not_ok",
    )


def test_check_output_is_capped_on_disk_and_in_the_tail() -> None:
    """2026-10-17: a runaway check wrote gigabytes to the runner's output file,
    and one long output line made the JSON answer as long as the line."""
    run_focused_pytest(
        "tests/test_checks.py::test_run_ends_a_check_whose_output_passes_the_cap",
        "tests/test_checks.py::test_one_long_line_cannot_fill_the_answer",
        "tests/test_checks.py::test_the_tail_keeps_its_last_lines_within_its_size_cap",
    )


def test_a_command_that_cannot_start_is_not_a_config_error() -> None:
    """2026-10-17: a NUL byte in a configured command made Popen raise
    ValueError, which checks.py reported as an unreadable .sdlc/config.json
    with exit 2, dropping every other check."""
    run_focused_pytest(
        "tests/test_checks.py::test_a_command_holding_a_nul_byte_is_one_failed_check",
        "tests/test_checks.py::test_output_that_cannot_be_read_back_is_that_checks_failure",
    )


def test_review_is_not_called_read_only_and_says_how_it_runs_checks() -> None:
    """2026-10-17: the README and site called shipshape-review read-only after
    it began running the project's checks, and the skill left "a branch
    someone else wrote" undefined, ran past the shell tool's time limit and
    put branch names in commands unquoted."""
    run_focused_pytest(
        "tests/test_site.py::test_readme_and_site_say_review_runs_the_projects_checks",
        "tests/test_review_contract.py::test_review_skill_says_whose_branch_it_is_from_the_commit_authors",
        "tests/test_review_contract.py::test_review_skill_runs_the_checks_inside_the_shell_tools_time_limit",
        "tests/test_review_contract.py::test_review_skill_quotes_every_name_it_puts_in_a_command",
    )


def test_a_repository_git_refuses_is_an_error() -> None:
    """2026-10-16: test_integrity.py read any failure of git rev-parse as a
    folder outside a repository, so a repository git refused to open (unsafe
    ownership, a broken .git) answered "findings": [] instead of an error."""
    run_focused_pytest(
        "tests/test_test_integrity.py::test_a_repository_git_refuses_to_open_is_an_error_not_a_clean_scan",
    )


def test_a_skip_inside_a_new_test_is_not_a_weakening() -> None:
    """2026-10-16: test_integrity.py reported a skip inside a test the same
    diff added, such as a Go testing.Short() guard, as a skipped test, though
    it skips nothing that ran before."""
    run_focused_pytest(
        "tests/test_test_integrity.py::test_a_skip_inside_a_test_the_diff_adds_is_not_a_finding",
        "tests/test_test_integrity.py::test_a_skip_on_an_existing_test_is_a_finding_beside_new_tests",
    )


def test_a_skip_added_to_an_existing_test_is_still_reported() -> None:
    """2026-10-17: the exemption for a skip inside a new test also hid a skip
    added to an existing one when git put the two in one run: a renamed test,
    a Go skip after a new subtest, a Rust attribute on the test below, a
    module-level skip, or a class whose header changed."""
    run_focused_pytest(
        "tests/test_test_integrity.py::test_a_skip_is_a_finding_when_it_only_sits_beside_a_new_test",
    )


def test_a_test_file_moved_out_of_the_test_paths_is_a_deleted_test() -> None:
    """2026-10-17: `git mv tests/test_auth.py src/auth_checks.py` gave a rename with
    no hunks, which still counted as a test file by its old path, so the scan found
    nothing to report although the tests no longer ran."""
    run_focused_pytest(
        "tests/test_test_integrity.py::test_a_test_file_renamed_out_of_the_test_paths_is_a_deleted_test",
        "tests/test_test_integrity.py::test_range_scan_reports_a_test_file_moved_out_of_the_test_paths",
        "tests/test_test_integrity.py::test_a_test_file_renamed_out_of_the_test_paths_with_edits_is_one_deleted_test",
        "tests/test_test_integrity.py::test_range_scan_reports_a_test_file_moved_out_and_edited",
    )


def test_an_unrelated_addition_does_not_cancel_a_removal() -> None:
    """2026-10-17: a removed test or assertion counted as rewritten whenever the file
    added as many of its kind anywhere, so deleting an authorization assertion while
    adding an unrelated colour assertion elsewhere gave no finding."""
    run_focused_pytest(
        "tests/test_test_integrity.py::test_an_unrelated_assertion_added_elsewhere_keeps_a_removal",
        "tests/test_test_integrity.py::test_an_unrelated_test_added_elsewhere_keeps_a_deleted_test",
        "tests/test_test_integrity.py::test_a_rewrite_in_place_or_one_that_keeps_its_words_is_left_to_the_review",
    )


def test_a_failed_pr_diff_is_not_a_clean_scan() -> None:
    """2026-10-17: shipshape-review piped `gh pr diff` straight into the scan, so a
    failed fetch gave the scan empty input, which it answered as a clean diff with no
    warning, and the review read test integrity as checked."""
    run_focused_pytest(
        "tests/test_test_integrity.py::test_empty_input_on_stdin_is_a_warning",
        "tests/test_review_contract.py::test_review_skill_scans_a_pr_diff_only_once_gh_printed_it",
    )


def test_boilerplate_words_cannot_cancel_a_removal() -> None:
    """2026-10-17: the rewrite match counted words such as assert, response, status
    and code, so removing `assert response.status_code == 403` while adding `== 200`
    in another test, or deleting test_user_can_login beside a new
    test_user_can_logout, gave no finding."""
    run_focused_pytest(
        "tests/test_test_integrity.py::test_boilerplate_words_cannot_make_an_assertion_elsewhere_a_rewrite",
        "tests/test_test_integrity.py::test_an_unrelated_test_added_elsewhere_keeps_a_deleted_test",
        "tests/test_test_integrity.py::test_a_rewrite_in_place_or_one_that_keeps_its_words_is_left_to_the_review",
    )


def test_review_removes_the_pr_diff_file() -> None:
    """2026-10-17: shipshape-review saved each PR diff, possibly a private
    repository's, to a temporary file it never removed."""
    run_focused_pytest(
        "tests/test_review_contract.py::test_review_skill_removes_the_pr_diff_file_on_every_path",
        "tests/test_review_contract.py::test_review_skill_quotes_every_name_it_puts_in_a_command",
    )


def test_generated_briefings_carry_every_profile_lens() -> None:
    """2026-10-17: the generated GitHub briefings, which a consumer gets without
    profiles.json, left out the specification profile's ambiguity and completeness
    lenses, the plan profile's coverage and specificity lenses and the documentation
    profile's clarity and consistency lenses."""
    run_focused_pytest(
        "tests/test_review_profiles.py::test_generated_briefings_carry_every_lens_of_every_profile",
    )


def test_review_counts_a_partly_staged_file_once() -> None:
    """2026-10-17: shipshape-review listed uncommitted files as the unstaged names
    plus the staged ones, so a file with both counted twice and could tip the
    profile choice, such as a 2 to 2 tie that chose documentation over code."""
    run_focused_pytest(
        "tests/test_review_profiles.py::test_skill_counts_a_partly_staged_file_once",
    )


def main() -> int:
    checks = [
        (
            "nested foreign files cannot claim test command",
            test_nested_foreign_files_cannot_claim_test_command,
        ),
        (
            "lookalike remote host is not github",
            test_lookalike_remote_host_is_not_github,
        ),
        (
            "CI doctor uses secret-scan workflow",
            test_ci_doctor_uses_secret_scan_workflow,
        ),
        (
            "Python CI installs pytest when project does not",
            test_python_ci_installs_pytest_when_project_does_not,
        ),
        (
            "low-risk auto-merge has merge permission",
            test_low_risk_automerge_has_merge_permission,
        ),
        (
            "verification window uses exact clock boundary",
            test_verification_window_uses_the_exact_clock_boundary,
        ),
        (
            "automatic merge rejects nested and renamed controls",
            test_automatic_merge_rejects_nested_and_renamed_controls,
        ),
        (
            "weekly report projects alerts and paginates pulls",
            test_weekly_report_projects_alerts_and_paginates_pulls,
        ),
        (
            "automatic authority uses exact gates and refuses persistent state",
            test_automatic_authority_uses_exact_gates_and_refuses_persistent_state,
        ),
        (
            "secret guard scans history and propagates git errors",
            test_secret_guard_scans_history_and_propagates_git_errors,
        ),
        (
            "hook installation preserves user hook and pins commit stage",
            test_hook_installation_preserves_user_hook_and_pins_commit_stage,
        ),
        (
            "node package manager selection is explicit",
            test_node_package_manager_selection_is_explicit,
        ),
        (
            "setup refuses symlinks and records partial completion",
            test_setup_refuses_symlinks_and_records_partial_completion,
        ),
        (
            "release publisher uses exact bare context",
            test_release_publisher_uses_exact_context_from_a_bare_directory,
        ),
        (
            "reviewed plan binds candidate and rendered outputs",
            test_reviewed_plan_binds_candidate_and_rendered_outputs,
        ),
        (
            "managed drift uses raw bytes and recorded modes",
            test_managed_drift_uses_raw_bytes_and_recorded_modes,
        ),
        (
            "copied bundle upgrade preserves completion truth",
            test_copied_bundle_upgrade_preserves_completion_truth,
        ),
        (
            "fresh Node setup requires reproducible inputs",
            test_fresh_node_setup_requires_reproducible_inputs,
        ),
        (
            "Node 25 bootstrap is pinned and ordered",
            test_node_25_bootstrap_is_pinned_and_ordered,
        ),
        (
            "managed helpers install, remove, and preserve drift",
            test_managed_helpers_install_remove_and_preserve_drift,
        ),
        (
            "setup callers apply only the saved preview",
            test_setup_callers_apply_only_the_saved_preview,
        ),
        (
            "doctor health uses byte, mode, and version evidence",
            test_doctor_health_uses_byte_mode_and_version_evidence,
        ),
        (
            "release latest attempt uses run start time",
            test_release_latest_current_attempt_uses_run_started_at,
        ),
        (
            "release readiness requires active publisher",
            test_release_readiness_requires_registered_active_publisher,
        ),
        (
            "release uses push CodeQL evidence",
            test_release_uses_push_code_scanning_evidence,
        ),
        (
            "review03 automation boundaries",
            test_review03_automation_boundaries,
        ),
        (
            "review03 configured protection modes",
            test_review03_configured_protection_modes,
        ),
        (
            "review03 guard/report/access boundaries",
            test_review03_guard_report_access_boundaries,
        ),
        (
            "doctor tests isolate ambient GitHub Actions mode",
            test_doctor_tests_isolate_ambient_github_actions_mode,
        ),
        (
            "weekly report rejects untrusted repository metadata",
            test_weekly_report_rejects_untrusted_repository_metadata,
        ),
        (
            "prove kills what a finished command left running",
            test_prove_kills_what_a_finished_command_left_running,
        ),
        (
            "prove under --no-network runs commands offline",
            test_prove_under_no_network_runs_commands_offline,
        ),
        (
            "Node check scripts match safe configured commands",
            test_node_check_scripts_match_safe_configured_commands,
        ),
        (
            "unsafe Node test script does not hide Go test check",
            test_unsafe_node_test_script_does_not_hide_go_test_check,
        ),
        (
            "Node check screen reads scripts as the shell does",
            test_node_check_screen_reads_scripts_as_the_shell_does,
        ),
        (
            "unsafe Node test script lets another runner be guessed",
            test_unsafe_node_test_script_lets_another_runner_be_guessed,
        ),
        (
            "a shell expansion cannot hide a rejected flag",
            test_a_shell_expansion_cannot_hide_a_rejected_flag,
        ),
        (
            "prove reaps what it kills",
            test_prove_reaps_what_it_kills,
        ),
        (
            "a script running other packages' scripts is not proposed",
            test_a_script_running_other_packages_scripts_is_never_proposed,
        ),
        (
            "prove answers when stopped by any stop signal",
            test_prove_answers_when_stopped_by_any_stop_signal,
        ),
        (
            "a deep script chain is not proposed and the scan answers",
            test_a_deep_script_chain_is_not_proposed_and_the_scan_answers,
        ),
        (
            "jest --watchAll is not a check",
            test_jest_watch_all_is_not_a_check,
        ),
        (
            "a script named by any glob is screened",
            test_a_script_named_by_any_glob_is_screened,
        ),
        (
            "check output cannot hold the runner",
            test_check_output_cannot_hold_the_runner,
        ),
        (
            "failure counts take linear time on blank lines",
            test_failure_counts_take_linear_time_on_blank_lines,
        ),
        (
            "a run where nothing ran is not ok",
            test_a_run_where_nothing_ran_is_not_ok,
        ),
        (
            "cargo failures add up across test binaries",
            test_cargo_failures_add_up_across_test_binaries,
        ),
        (
            "checks run reaps what it kills",
            test_checks_run_reaps_what_it_kills,
        ),
        (
            "review asks before running another author's checks",
            test_review_asks_before_running_another_authors_checks,
        ),
        (
            "checks run answers and kills the check on any stop",
            test_checks_run_answers_and_kills_the_check_on_any_stop,
        ),
        (
            "a check not reached is never all passed",
            test_a_check_not_reached_is_never_all_passed,
        ),
        (
            "check output is capped on disk and in the tail",
            test_check_output_is_capped_on_disk_and_in_the_tail,
        ),
        (
            "a command that cannot start is not a config error",
            test_a_command_that_cannot_start_is_not_a_config_error,
        ),
        (
            "review is not called read-only and says how it runs checks",
            test_review_is_not_called_read_only_and_says_how_it_runs_checks,
        ),
        (
            "a repository git refuses is an error",
            test_a_repository_git_refuses_is_an_error,
        ),
        (
            "a skip inside a new test is not a weakening",
            test_a_skip_inside_a_new_test_is_not_a_weakening,
        ),
        (
            "a skip added to an existing test is still reported",
            test_a_skip_added_to_an_existing_test_is_still_reported,
        ),
        (
            "a test file moved out of the test paths is a deleted test",
            test_a_test_file_moved_out_of_the_test_paths_is_a_deleted_test,
        ),
        (
            "an unrelated addition does not cancel a removal",
            test_an_unrelated_addition_does_not_cancel_a_removal,
        ),
        (
            "a failed PR diff is not a clean scan",
            test_a_failed_pr_diff_is_not_a_clean_scan,
        ),
        (
            "boilerplate words cannot cancel a removal",
            test_boilerplate_words_cannot_cancel_a_removal,
        ),
        (
            "review removes the PR diff file",
            test_review_removes_the_pr_diff_file,
        ),
        (
            "generated briefings carry every profile lens",
            test_generated_briefings_carry_every_profile_lens,
        ),
        (
            "review counts a partly staged file once",
            test_review_counts_a_partly_staged_file_once,
        ),
    ]
    failures = 0
    for name, check in checks:
        try:
            check()
            print(f"[OK  ] {name}")
        except AssertionError as exc:
            print(f"[FAIL] {name}: {exc}")
            failures += 1
    print(f"{len(checks) - failures}/{len(checks)} regression checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
