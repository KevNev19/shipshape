"""The consumer doctor is executable, JSON-only, and kept in sync."""

import json
import os
import subprocess
import sys

import pytest
from conftest import init_repo, prepend_to_path, run_script


@pytest.fixture(autouse=True)
def pin_doctor_subprocess_path(hermetic_doctor_path):
    return hermetic_doctor_path


def install_routed_fake_gh(tmp_path):
    bin_dir = tmp_path / "rendered-bin"
    bin_dir.mkdir(exist_ok=True)
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        '  *"/protection/required_status_checks"*)\n'
        "    printf '%s\\n' \"${FAKE_GH_PROTECTION_BODY:-}\"\n"
        "    printf '%s\\n' \"${FAKE_GH_PROTECTION_ERROR:-}\" >&2\n"
        '    exit "${FAKE_GH_PROTECTION_CODE:-1}" ;;\n'
        '  *"/rules/branches/"*)\n'
        "    printf '%s\\n' \"${FAKE_GH_RULES_BODY:-}\"\n"
        '    exit "${FAKE_GH_RULES_CODE:-1}" ;;\n'
        '  *"/branches/"*)\n'
        "    printf '%s\\n' \"${FAKE_GH_BRANCH_BODY:-}\"\n"
        '    exit "${FAKE_GH_BRANCH_CODE:-1}" ;;\n'
        "esac\n"
        "exit 1\n"
    )
    gh.chmod(0o755)
    return bin_dir


def set_fake_gh_response(monkeypatch, name, payload, exit_code=0):
    body = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setenv(f"FAKE_GH_{name}_BODY", body)
    monkeypatch.setenv(f"FAKE_GH_{name}_CODE", str(exit_code))


def set_fake_gh_error(monkeypatch, name, message):
    monkeypatch.setenv(f"FAKE_GH_{name}_ERROR", message)


def rendered_repo(tmp_path):
    repo = init_repo("repo-python", tmp_path)
    code, payload = run_script("render.py", "apply", repo)
    assert code == 0, payload
    subprocess.run(["git", "init", "-qb", "main"], cwd=repo, check=True)
    hooks_dir = repo / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    (hooks_dir / "pre-commit").symlink_to("../../.sdlc/hooks/secret-guard.sh")
    return repo


def run_rendered_doctor(repo, *, github_actions=False):
    env = os.environ.copy()
    if github_actions:
        env["GITHUB_ACTIONS"] = "true"
    else:
        env.pop("GITHUB_ACTIONS", None)
    proc = subprocess.run(
        [sys.executable, str(repo / ".sdlc" / "scripts" / "doctor.py"), str(repo)],
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode, json.loads(proc.stdout)


def check_map(payload):
    return {item["name"]: item for section in payload["sections"] for item in section["checks"]}


def test_rendered_doctor_reports_a_healthy_repo(tmp_path):
    repo = rendered_repo(tmp_path)
    code, payload = run_rendered_doctor(repo)

    assert code == 0, payload
    assert payload["ok"] is True
    assert payload["counts"]["FAIL"] == 0
    assert set(payload) == {"ok", "set_up", "counts", "sections", "next_action"}
    assert check_map(payload)["tiered review gates"] == {
        "name": "tiered review gates",
        "status": "PASS",
        "detail": "tiered review is off; every change needs a person",
        "next_action": "",
    }


def test_rendered_doctor_warns_when_tiered_review_cannot_verify_checks(tmp_path):
    repo = rendered_repo(tmp_path)
    config_path = repo / ".sdlc" / "config.json"
    config = json.loads(config_path.read_text())
    config["features"]["tiered_review"] = True
    config_path.write_text(json.dumps(config))
    workflow = repo / ".github" / "workflows" / "low-risk-automerge.yml"
    workflow.write_text("permissions:\n  contents: read\n  pull-requests: write\n")
    code, payload = run_rendered_doctor(repo)

    tiered_review = check_map(payload)["tiered review gates"]
    assert code == 0, payload
    assert tiered_review["status"] == "WARN"
    assert tiered_review["detail"] == ("could not verify that required checks guard auto-merge")


def test_rendered_doctor_fails_when_tiered_review_workflow_is_missing(tmp_path):
    repo = rendered_repo(tmp_path)
    config_path = repo / ".sdlc" / "config.json"
    config = json.loads(config_path.read_text())
    config["features"]["tiered_review"] = True
    config_path.write_text(json.dumps(config))

    code, payload = run_rendered_doctor(repo)

    tiered_review = check_map(payload)["tiered review gates"]
    assert code == 1
    assert tiered_review["status"] == "FAIL"
    assert tiered_review["next_action"] == (
        "Turn off tiered review until every required check is enforced."
    )


def test_rendered_doctor_fails_when_required_checks_are_empty(tmp_path, monkeypatch):
    repo = rendered_repo(tmp_path)
    config_path = repo / ".sdlc" / "config.json"
    config = json.loads(config_path.read_text())
    config["features"]["tiered_review"] = True
    config["repo"]["owner_repo"] = "example/project"
    config_path.write_text(json.dumps(config))
    workflow = repo / ".github" / "workflows" / "low-risk-automerge.yml"
    workflow.write_text("permissions:\n  contents: read\n  pull-requests: write\n")
    prepend_to_path(monkeypatch, install_routed_fake_gh(tmp_path))
    set_fake_gh_response(monkeypatch, "BRANCH", {"protected": True})
    set_fake_gh_response(monkeypatch, "PROTECTION", {"contexts": [], "checks": []})
    set_fake_gh_response(monkeypatch, "RULES", [])

    code, payload = run_rendered_doctor(repo)

    tiered_review = check_map(payload)["tiered review gates"]
    assert code == 1
    assert tiered_review["status"] == "FAIL"


def test_rendered_doctor_fails_when_classic_protection_is_not_configured(tmp_path, monkeypatch):
    repo = rendered_repo(tmp_path)
    config_path = repo / ".sdlc" / "config.json"
    config = json.loads(config_path.read_text())
    config["features"]["tiered_review"] = True
    config["repo"]["owner_repo"] = "example/project"
    config_path.write_text(json.dumps(config))
    workflow = repo / ".github" / "workflows" / "low-risk-automerge.yml"
    workflow.write_text("permissions:\n  contents: read\n  pull-requests: write\n")
    prepend_to_path(monkeypatch, install_routed_fake_gh(tmp_path))
    set_fake_gh_response(monkeypatch, "BRANCH", {"protected": True})
    set_fake_gh_response(monkeypatch, "PROTECTION", None, exit_code=1)
    set_fake_gh_error(monkeypatch, "PROTECTION", "gh: Branch not protected (HTTP 404)")
    set_fake_gh_response(monkeypatch, "RULES", [])

    code, payload = run_rendered_doctor(repo)

    tiered_review = check_map(payload)["tiered review gates"]
    assert code == 1
    assert tiered_review["status"] == "FAIL"


def test_rendered_doctor_warns_when_api_shape_is_malformed(tmp_path, monkeypatch):
    repo = rendered_repo(tmp_path)
    config_path = repo / ".sdlc" / "config.json"
    config = json.loads(config_path.read_text())
    config["features"]["tiered_review"] = True
    config["repo"]["owner_repo"] = "example/project"
    config_path.write_text(json.dumps(config))
    workflow = repo / ".github" / "workflows" / "low-risk-automerge.yml"
    workflow.write_text("permissions:\n  contents: read\n  pull-requests: write\n")
    prepend_to_path(monkeypatch, install_routed_fake_gh(tmp_path))
    set_fake_gh_response(monkeypatch, "BRANCH", {"protected": True})
    set_fake_gh_response(monkeypatch, "PROTECTION", {"contexts": None, "checks": []})
    set_fake_gh_response(monkeypatch, "RULES", [])

    code, payload = run_rendered_doctor(repo)

    tiered_review = check_map(payload)["tiered review gates"]
    assert code == 0, payload
    assert tiered_review["status"] == "WARN"


def test_rendered_doctor_accepts_required_test_from_active_rules(tmp_path, monkeypatch):
    repo = rendered_repo(tmp_path)
    config_path = repo / ".sdlc" / "config.json"
    config = json.loads(config_path.read_text())
    config["features"]["tiered_review"] = True
    config["repo"]["owner_repo"] = "example/project"
    config_path.write_text(json.dumps(config))
    workflow = repo / ".github" / "workflows" / "low-risk-automerge.yml"
    workflow.write_text("permissions:\n  contents: read\n  pull-requests: write\n")
    prepend_to_path(monkeypatch, install_routed_fake_gh(tmp_path))
    set_fake_gh_response(monkeypatch, "BRANCH", {"protected": True})
    set_fake_gh_response(monkeypatch, "PROTECTION", {"contexts": [], "checks": []})
    set_fake_gh_response(
        monkeypatch,
        "RULES",
        [
            {
                "type": "required_status_checks",
                "parameters": {"required_status_checks": [{"context": "test"}]},
            }
        ],
    )

    code, payload = run_rendered_doctor(repo)

    tiered_review = check_map(payload)["tiered review gates"]
    assert code == 0, payload
    assert tiered_review["status"] == "PASS"


def test_rendered_doctor_warns_when_required_check_payload_is_malformed(tmp_path, monkeypatch):
    repo = rendered_repo(tmp_path)
    config_path = repo / ".sdlc" / "config.json"
    config = json.loads(config_path.read_text())
    config["features"]["tiered_review"] = True
    config["repo"]["owner_repo"] = "example/project"
    config_path.write_text(json.dumps(config))
    workflow = repo / ".github" / "workflows" / "low-risk-automerge.yml"
    workflow.write_text("permissions:\n  contents: read\n  pull-requests: write\n")
    prepend_to_path(monkeypatch, install_routed_fake_gh(tmp_path))
    set_fake_gh_response(monkeypatch, "BRANCH", {"protected": True})
    set_fake_gh_response(monkeypatch, "PROTECTION", {"contexts": None, "checks": []})
    set_fake_gh_response(monkeypatch, "RULES", [])

    code, payload = run_rendered_doctor(repo)

    tiered_review = check_map(payload)["tiered review gates"]
    assert code == 0, payload
    assert tiered_review["status"] == "WARN"


def test_rendered_doctor_fails_when_the_secret_guard_is_missing(tmp_path):
    repo = rendered_repo(tmp_path)
    (repo / ".sdlc" / "hooks" / "secret-guard.sh").unlink()

    code, payload = run_rendered_doctor(repo)

    assert code == 1
    assert payload["ok"] is False
    assert check_map(payload)["secret guard"]["status"] == "FAIL"


def test_rendered_doctor_accepts_secret_scan_in_ci_without_local_hook(tmp_path):
    repo = rendered_repo(tmp_path)
    (repo / ".git" / "hooks" / "pre-commit").unlink()

    code, payload = run_rendered_doctor(repo, github_actions=True)

    installed = check_map(payload)["secret guard installed"]
    assert code == 0, payload
    assert installed["status"] == "PASS"
    assert installed["detail"] == (
        "per-clone hook not checkable in CI; pushes are covered by the secret-scan workflow"
    )


def test_rendered_doctor_fails_when_secret_scan_is_missing_in_ci(tmp_path):
    repo = rendered_repo(tmp_path)
    (repo / ".github" / "workflows" / "secret-scan.yml").unlink()

    code, payload = run_rendered_doctor(repo, github_actions=True)

    installed = check_map(payload)["secret guard installed"]
    assert code == 1
    assert payload["ok"] is False
    assert installed["status"] == "FAIL"
    assert installed["next_action"] == (
        "Re-run /shipshape-init to restore the secret-scan workflow."
    )


def test_rendered_doctor_still_requires_local_hook_outside_ci(tmp_path):
    repo = rendered_repo(tmp_path)
    (repo / ".git" / "hooks" / "pre-commit").unlink()

    code, payload = run_rendered_doctor(repo)

    installed = check_map(payload)["secret guard installed"]
    assert code == 1
    assert payload["ok"] is False
    assert installed == {
        "name": "secret guard installed",
        "status": "FAIL",
        "detail": "the scanner exists but is not active for this clone",
        "next_action": "run: bash .sdlc/hooks/install.sh",
    }


def test_rendered_and_plugin_doctors_report_the_same_checks(tmp_path):
    repo = rendered_repo(tmp_path)

    plugin_code, plugin_payload = run_script("doctor.py", repo)
    rendered_code, rendered_payload = run_rendered_doctor(repo)
    plugin_checks = check_map(plugin_payload)
    rendered_checks = check_map(rendered_payload)

    assert plugin_code == rendered_code == 0
    assert set(rendered_checks) == set(plugin_checks)
    assert {name: item["status"] for name, item in rendered_checks.items()} == {
        name: item["status"] for name, item in plugin_checks.items()
    }
