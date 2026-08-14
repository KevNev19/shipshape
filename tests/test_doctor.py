"""Doctor tests: the scorecard leads with security, FAILs on a missing or
uninstalled secret guard, and degrades to WARN (never FAIL) for the
availability-dependent checks."""

import json
import subprocess

import pytest
from conftest import init_repo, prepend_to_path, run_script


@pytest.fixture(autouse=True)
def pin_doctor_subprocess_path(hermetic_doctor_path):
    return hermetic_doctor_path


def healthy_repo(tmp_path):
    repo = init_repo("repo-python", tmp_path)
    code, _ = run_script("render.py", "apply", repo)
    assert code == 0
    subprocess.run(["git", "init", "-qb", "main"], cwd=repo, check=True)
    # Activate the guard the way init's step 7 does.
    hooks_dir = repo / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    (hooks_dir / "pre-commit").symlink_to("../../.sdlc/hooks/secret-guard.sh")
    return repo


def checks_by_name(payload, section):
    (match,) = [s for s in payload["sections"] if s["name"] == section]
    return {c["name"]: c for c in match["checks"]}


def install_fake_gh(tmp_path, response: dict | None, exit_code: int = 0):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    gh = bin_dir / "gh"
    output = json.dumps(response) if response is not None else ""
    gh.write_text(f"#!/bin/sh\nprintf '%s\\n' '{output}'\nexit {exit_code}\n")
    gh.chmod(0o755)
    return bin_dir


def install_routed_fake_gh(tmp_path):
    bin_dir = tmp_path / "routed-bin"
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


def enable_tiered_review(repo, *, workflow=True):
    config_path = repo / ".sdlc" / "config.json"
    config = json.loads(config_path.read_text())
    config["features"]["tiered_review"] = True
    config["repo"]["owner_repo"] = "example/project"
    config_path.write_text(json.dumps(config))
    if workflow:
        path = repo / ".github" / "workflows" / "low-risk-automerge.yml"
        path.write_text("permissions:\n  contents: read\n  pull-requests: write\n")


def test_unset_repo_points_to_init(tmp_path):
    bare = tmp_path / "bare"
    bare.mkdir()
    code, payload = run_script("doctor.py", bare)
    assert code == 1
    assert payload["set_up"] is False
    assert "shipshape-init" in payload["next_action"]


def test_healthy_repo_all_green(tmp_path):
    repo = healthy_repo(tmp_path)
    code, payload = run_script("doctor.py", repo)
    assert code == 0, payload
    assert payload["ok"] is True
    assert payload["counts"]["FAIL"] == 0
    assert payload["sections"][0]["name"] == "security", "security must lead"
    assert "shipshape" in payload["next_action"]


def test_tiered_review_gates_pass_when_feature_is_off(tmp_path):
    repo = healthy_repo(tmp_path)

    code, payload = run_script("doctor.py", repo)

    tiered_review = checks_by_name(payload, "security")["tiered review gates"]
    assert code == 0, payload
    assert tiered_review == {
        "name": "tiered review gates",
        "status": "PASS",
        "detail": "tiered review is off; every change needs a person",
        "next_action": "",
    }


def test_tiered_review_gates_fail_when_feature_is_off_but_workflow_remains(tmp_path):
    repo = healthy_repo(tmp_path)
    workflow = repo / ".github" / "workflows" / "low-risk-automerge.yml"
    workflow.write_text("name: unexpectedly active\n")

    code, payload = run_script("doctor.py", repo)

    tiered_review = checks_by_name(payload, "security")["tiered review gates"]
    assert code == 1
    assert tiered_review["status"] == "FAIL"
    assert tiered_review["next_action"] == (
        "Remove .github/workflows/low-risk-automerge.yml before relying on tiered review being off."
    )


def test_tiered_review_gates_warn_when_required_checks_cannot_be_verified(tmp_path):
    repo = healthy_repo(tmp_path)
    config_path = repo / ".sdlc" / "config.json"
    config = json.loads(config_path.read_text())
    config["features"]["tiered_review"] = True
    config_path.write_text(json.dumps(config))
    workflow = repo / ".github" / "workflows" / "low-risk-automerge.yml"
    workflow.write_text("permissions:\n  contents: read\n  pull-requests: write\n")
    code, payload = run_script("doctor.py", repo)

    tiered_review = checks_by_name(payload, "security")["tiered review gates"]
    assert code == 0, payload
    assert tiered_review["status"] == "WARN"
    assert tiered_review["detail"] == ("could not verify that required checks guard auto-merge")


def test_tiered_review_gates_warn_when_protection_api_is_inaccessible(tmp_path, monkeypatch):
    repo = healthy_repo(tmp_path)
    enable_tiered_review(repo)
    prepend_to_path(monkeypatch, install_routed_fake_gh(tmp_path))
    set_fake_gh_response(monkeypatch, "BRANCH", {"protected": True})

    code, payload = run_script("doctor.py", repo)

    tiered_review = checks_by_name(payload, "security")["tiered review gates"]
    assert code == 0, payload
    assert tiered_review["status"] == "WARN"
    assert tiered_review["detail"] == ("could not verify that required checks guard auto-merge")


@pytest.mark.parametrize(
    ("protection", "rules"),
    [
        ({"contexts": ["test"], "checks": []}, []),
        ({"contexts": [], "checks": [{"context": "test"}]}, []),
        (
            {"contexts": [], "checks": []},
            [
                {
                    "type": "required_status_checks",
                    "parameters": {"required_status_checks": [{"context": "test"}]},
                }
            ],
        ),
    ],
)
def test_tiered_review_gates_pass_when_test_is_required(tmp_path, monkeypatch, protection, rules):
    repo = healthy_repo(tmp_path)
    enable_tiered_review(repo)
    prepend_to_path(monkeypatch, install_routed_fake_gh(tmp_path))
    set_fake_gh_response(monkeypatch, "BRANCH", {"protected": True})
    set_fake_gh_response(monkeypatch, "PROTECTION", protection)
    set_fake_gh_response(monkeypatch, "RULES", rules)

    code, payload = run_script("doctor.py", repo)

    tiered_review = checks_by_name(payload, "security")["tiered review gates"]
    assert code == 0, payload
    assert tiered_review["status"] == "PASS"
    assert "`test` is required" in tiered_review["detail"]


def test_tiered_review_gates_fail_when_api_shows_no_required_checks(tmp_path, monkeypatch):
    repo = healthy_repo(tmp_path)
    enable_tiered_review(repo)
    prepend_to_path(monkeypatch, install_routed_fake_gh(tmp_path))
    set_fake_gh_response(monkeypatch, "BRANCH", {"protected": True})
    set_fake_gh_response(monkeypatch, "PROTECTION", {"contexts": [], "checks": []})
    set_fake_gh_response(monkeypatch, "RULES", [])

    code, payload = run_script("doctor.py", repo)

    tiered_review = checks_by_name(payload, "security")["tiered review gates"]
    assert code == 1
    assert tiered_review["status"] == "FAIL"
    assert tiered_review["next_action"] == (
        "Turn off tiered review until every required check is enforced."
    )


def test_tiered_review_gates_fail_when_classic_protection_is_not_configured(tmp_path, monkeypatch):
    repo = healthy_repo(tmp_path)
    enable_tiered_review(repo)
    prepend_to_path(monkeypatch, install_routed_fake_gh(tmp_path))
    set_fake_gh_response(monkeypatch, "BRANCH", {"protected": True})
    set_fake_gh_response(monkeypatch, "PROTECTION", None, exit_code=1)
    set_fake_gh_error(monkeypatch, "PROTECTION", "gh: Branch not protected (HTTP 404)")
    set_fake_gh_response(monkeypatch, "RULES", [])

    code, payload = run_script("doctor.py", repo)

    tiered_review = checks_by_name(payload, "security")["tiered review gates"]
    assert code == 1
    assert tiered_review["status"] == "FAIL"
    assert tiered_review["next_action"] == (
        "Turn off tiered review until every required check is enforced."
    )


def test_tiered_review_gates_fail_when_workflow_is_missing(tmp_path):
    repo = healthy_repo(tmp_path)
    enable_tiered_review(repo, workflow=False)
    code, payload = run_script("doctor.py", repo)

    tiered_review = checks_by_name(payload, "security")["tiered review gates"]
    assert code == 1
    assert tiered_review["status"] == "FAIL"
    assert tiered_review["next_action"] == (
        "Turn off tiered review until every required check is enforced."
    )


def test_tiered_review_gates_fail_when_branch_is_unprotected(tmp_path, monkeypatch):
    repo = healthy_repo(tmp_path)
    enable_tiered_review(repo)
    prepend_to_path(monkeypatch, install_routed_fake_gh(tmp_path))
    set_fake_gh_response(monkeypatch, "BRANCH", {"protected": False})

    code, payload = run_script("doctor.py", repo)

    tiered_review = checks_by_name(payload, "security")["tiered review gates"]
    assert code == 1
    assert tiered_review["status"] == "FAIL"
    assert tiered_review["next_action"] == (
        "Turn off tiered review until every required check is enforced."
    )


def test_tiered_review_gates_warn_when_api_output_is_malformed(tmp_path, monkeypatch):
    repo = healthy_repo(tmp_path)
    enable_tiered_review(repo)
    prepend_to_path(monkeypatch, install_routed_fake_gh(tmp_path))
    set_fake_gh_response(monkeypatch, "BRANCH", "not-json")

    code, payload = run_script("doctor.py", repo)

    tiered_review = checks_by_name(payload, "security")["tiered review gates"]
    assert code == 0, payload
    assert tiered_review["status"] == "WARN"
    assert tiered_review["detail"] == ("could not verify that required checks guard auto-merge")


def test_tiered_review_gates_warn_when_api_shape_is_malformed(tmp_path, monkeypatch):
    repo = healthy_repo(tmp_path)
    enable_tiered_review(repo)
    prepend_to_path(monkeypatch, install_routed_fake_gh(tmp_path))
    set_fake_gh_response(monkeypatch, "BRANCH", {"protected": True})
    set_fake_gh_response(monkeypatch, "PROTECTION", {"contexts": None, "checks": []})
    set_fake_gh_response(monkeypatch, "RULES", [])

    code, payload = run_script("doctor.py", repo)

    tiered_review = checks_by_name(payload, "security")["tiered review gates"]
    assert code == 0, payload
    assert tiered_review["status"] == "WARN"


def test_tiered_review_gates_warn_when_required_check_payload_is_malformed(tmp_path, monkeypatch):
    repo = healthy_repo(tmp_path)
    enable_tiered_review(repo)
    prepend_to_path(monkeypatch, install_routed_fake_gh(tmp_path))
    set_fake_gh_response(monkeypatch, "BRANCH", {"protected": True})
    set_fake_gh_response(monkeypatch, "PROTECTION", {"contexts": None, "checks": []})
    set_fake_gh_response(monkeypatch, "RULES", [])

    code, payload = run_script("doctor.py", repo)

    tiered_review = checks_by_name(payload, "security")["tiered review gates"]
    assert code == 0, payload
    assert tiered_review["status"] == "WARN"
    assert tiered_review["detail"] == ("could not verify that required checks guard auto-merge")


def test_agent_control_file_coverage_passes_with_guard_and_reviewer(tmp_path):
    repo = healthy_repo(tmp_path)
    code, payload = run_script("doctor.py", repo)
    coverage = checks_by_name(payload, "security")["agent control-file coverage"]
    assert code == 0, payload
    assert coverage["status"] == "PASS"


def test_agent_control_file_coverage_warns_without_github_agents(tmp_path):
    repo = healthy_repo(tmp_path)
    config_path = repo / ".sdlc" / "config.json"
    config = json.loads(config_path.read_text())
    config["features"]["github_agents"] = False
    config_path.write_text(json.dumps(config))

    code, payload = run_script("doctor.py", repo)
    coverage = checks_by_name(payload, "security")["agent control-file coverage"]
    assert code == 0, payload
    assert coverage["status"] == "WARN"
    assert "deterministic" in coverage["detail"]


def test_agent_control_file_coverage_fails_for_stale_guard(tmp_path):
    repo = healthy_repo(tmp_path)
    guard = repo / ".sdlc" / "hooks" / "secret-guard.sh"
    guard.write_text(guard.read_text().replace("# layer 3: agent control files", ""))

    code, payload = run_script("doctor.py", repo)
    coverage = checks_by_name(payload, "security")["agent control-file coverage"]
    assert code == 1
    assert coverage["status"] == "FAIL"
    assert coverage["next_action"] == (
        "Re-run /shipshape-init to restore checks for agent and editor control files."
    )


@pytest.mark.parametrize(
    "removed_rule",
    [
        "are security findings: report purpose and consequence.",
        'Unexplained control-file changes require at least "Needs attention first".',
    ],
)
def test_agent_control_file_coverage_fails_for_stale_reviewer(tmp_path, removed_rule):
    repo = healthy_repo(tmp_path)
    reviewer = repo / ".github" / "agents" / "reviewer.md"
    reviewer.write_text(reviewer.read_text().replace(removed_rule, ""))

    code, payload = run_script("doctor.py", repo)
    coverage = checks_by_name(payload, "security")["agent control-file coverage"]
    assert code == 1
    assert coverage["status"] == "FAIL"
    assert "reviewer" in coverage["detail"]


def test_uninstalled_guard_is_fail_with_fix(tmp_path):
    repo = healthy_repo(tmp_path)
    (repo / ".git" / "hooks" / "pre-commit").unlink()
    code, payload = run_script("doctor.py", repo)
    assert code == 1
    assert payload["ok"] is False
    check = checks_by_name(payload, "security")["secret guard installed"]
    assert check["status"] == "FAIL"
    assert "install.sh" in payload["next_action"]


def test_missing_dependabot_is_warn_not_fail(tmp_path):
    repo = healthy_repo(tmp_path)
    (repo / ".github" / "dependabot.yml").unlink()
    code, payload = run_script("doctor.py", repo)
    assert code == 0, "availability gaps must not hard-fail"
    check = checks_by_name(payload, "security")["dependency watch (Dependabot)"]
    assert check["status"] == "WARN"


def test_workflow_without_permissions_is_flagged(tmp_path):
    repo = healthy_repo(tmp_path)
    (repo / ".github" / "workflows" / "deploy.yml").write_text(
        "name: Deploy\non: push\njobs:\n  d:\n    runs-on: ubuntu-latest\n    steps: []\n"
    )
    code, payload = run_script("doctor.py", repo)
    check = checks_by_name(payload, "security")["workflow permissions"]
    assert check["status"] == "WARN"
    assert "deploy.yml" in check["detail"]


def test_unused_project_board_setting_is_warn_not_fail(tmp_path):
    repo = healthy_repo(tmp_path)
    config_path = repo / ".sdlc" / "config.json"
    config = json.loads(config_path.read_text())
    config["features"]["project_board"] = False
    config_path.write_text(json.dumps(config))

    code, payload = run_script("doctor.py", repo)
    check = checks_by_name(payload, "setup")["unused settings"]
    message = (
        "Remove features.project_board; this setting has never changed what shipshape installs."
    )
    assert code == 0
    assert check == {
        "name": "unused settings",
        "status": "WARN",
        "detail": message,
        "next_action": message,
    }


def test_no_unused_settings_is_pass(tmp_path):
    repo = healthy_repo(tmp_path)
    code, payload = run_script("doctor.py", repo)
    check = checks_by_name(payload, "setup")["unused settings"]
    assert code == 0
    assert check["status"] == "PASS"
    assert check["detail"] == "no unused settings"


@pytest.mark.parametrize(
    "retry_step",
    [
        "uses: nick-fields/retry@v3",
        "uses: nick-invision/retry@v1",
        "uses: Wandalen/wretry.action@v3",
        "run: pytest --retries 2",
        "run: |\n          until pytest; do sleep 1; done",
        "run: |\n          for attempt in 1 2 3; do\n            pytest && break\n          done",
    ],
)
def test_known_test_retry_is_warn_not_fail(tmp_path, retry_step):
    repo = healthy_repo(tmp_path)
    (repo / ".github" / "workflows" / "retry.yml").write_text(
        "name: Tests\n"
        "on: push\n"
        "permissions:\n"
        "  contents: read\n"
        "jobs:\n"
        "  test:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        f"      - {retry_step}\n"
    )

    code, payload = run_script("doctor.py", repo)
    check = checks_by_name(payload, "setup")["test retries"]
    assert code == 0
    assert check["status"] == "WARN"
    assert "retry.yml" in check["detail"]
    assert check["next_action"] == (
        "Remove the retry and fix or quarantine the flaky test so one green run means the "
        "test passed."
    )


def test_no_test_retries_is_pass(tmp_path):
    repo = healthy_repo(tmp_path)
    code, payload = run_script("doctor.py", repo)
    check = checks_by_name(payload, "setup")["test retries"]
    assert code == 0
    assert check["status"] == "PASS"
    assert check["detail"] == "no test retries found"


def test_scheduled_health_check_passes_when_managed_files_are_present(tmp_path):
    repo = healthy_repo(tmp_path)
    doctor = repo / ".sdlc" / "scripts" / "doctor.py"
    doctor.parent.mkdir(parents=True, exist_ok=True)
    doctor.write_text("# managed doctor\n")
    workflow = repo / ".github" / "workflows" / "shipshape-doctor.yml"
    workflow.write_text("on:\n  schedule:\n    - cron: '41 4 * * 3'\n")

    code, payload = run_script("doctor.py", repo)
    scheduled = checks_by_name(payload, "setup")["scheduled health check"]
    assert code == 0, payload
    assert scheduled["status"] == "PASS"


def test_scheduled_health_check_warns_when_feature_is_off(tmp_path):
    repo = healthy_repo(tmp_path)
    config_path = repo / ".sdlc" / "config.json"
    config = json.loads(config_path.read_text())
    config["features"]["scheduled_health"] = False
    config_path.write_text(json.dumps(config))

    code, payload = run_script("doctor.py", repo)
    scheduled = checks_by_name(payload, "setup")["scheduled health check"]
    assert code == 0, payload
    assert scheduled["status"] == "WARN"
    assert scheduled["detail"] == "scheduled health check is turned off"


@pytest.mark.parametrize("missing", ["doctor", "workflow", "schedule"])
def test_scheduled_health_check_fails_when_setup_is_incomplete(tmp_path, missing):
    repo = healthy_repo(tmp_path)
    doctor = repo / ".sdlc" / "scripts" / "doctor.py"
    doctor.parent.mkdir(parents=True, exist_ok=True)
    doctor.write_text("# managed doctor\n")
    workflow = repo / ".github" / "workflows" / "shipshape-doctor.yml"
    workflow.write_text("on:\n  schedule:\n    - cron: '41 4 * * 3'\n")
    if missing == "doctor":
        doctor.unlink()
    elif missing == "workflow":
        workflow.unlink()
    else:
        workflow.write_text("on: workflow_dispatch\n")

    code, payload = run_script("doctor.py", repo)
    scheduled = checks_by_name(payload, "setup")["scheduled health check"]
    assert code == 1
    assert scheduled["status"] == "FAIL"
    assert scheduled["next_action"] == (
        "Re-run /shipshape-init to restore the scheduled health check."
    )


def test_user_edit_reported_as_fine(tmp_path):
    repo = healthy_repo(tmp_path)
    claude = repo / "CLAUDE.md"
    claude.write_text(claude.read_text() + "\nextra personal rule\n")
    code, payload = run_script("doctor.py", repo)
    assert code == 0
    check = checks_by_name(payload, "setup")["managed files"]
    assert check["status"] == "PASS"
    assert "fine" in check["detail"]
