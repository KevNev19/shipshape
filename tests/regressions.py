#!/usr/bin/env python3
"""Regression guard: one dated test per historically fixed bug, so none can
silently return. Every test's docstring opens with the date and symptom of
the bug it guards. Run directly: python3 tests/regressions.py

Currently empty by design — the first entry arrives with the first fixed bug.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
TEMPLATES = ROOT / "templates"


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
        config = {
            "features": {
                "codeql": False,
                "github_agents": False,
                "scheduled_health": False,
                "secret_guard": True,
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
        assert installed["status"] == "PASS", installed
        assert installed["detail"] == (
            "per-clone hook not checkable in CI; pushes are covered by the secret-scan workflow"
        ), installed


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
