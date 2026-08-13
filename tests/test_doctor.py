"""Doctor tests: the scorecard leads with security, FAILs on a missing or
uninstalled secret guard, and degrades to WARN (never FAIL) for the
availability-dependent checks."""

import json
import subprocess

import pytest
from conftest import init_repo, run_script


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


def test_user_edit_reported_as_fine(tmp_path):
    repo = healthy_repo(tmp_path)
    claude = repo / "CLAUDE.md"
    claude.write_text(claude.read_text() + "\nextra personal rule\n")
    code, payload = run_script("doctor.py", repo)
    assert code == 0
    check = checks_by_name(payload, "setup")["managed files"]
    assert check["status"] == "PASS"
    assert "fine" in check["detail"]
