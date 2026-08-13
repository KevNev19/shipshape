"""The consumer doctor is executable, JSON-only, and kept in sync."""

import json
import subprocess
import sys

from conftest import init_repo, run_script


def rendered_repo(tmp_path):
    repo = init_repo("repo-python", tmp_path)
    code, payload = run_script("render.py", "apply", repo)
    assert code == 0, payload
    subprocess.run(["git", "init", "-qb", "main"], cwd=repo, check=True)
    hooks_dir = repo / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    (hooks_dir / "pre-commit").symlink_to("../../.sdlc/hooks/secret-guard.sh")
    return repo


def run_rendered_doctor(repo):
    proc = subprocess.run(
        [sys.executable, str(repo / ".sdlc" / "scripts" / "doctor.py"), str(repo)],
        capture_output=True,
        text=True,
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


def test_rendered_doctor_fails_when_the_secret_guard_is_missing(tmp_path):
    repo = rendered_repo(tmp_path)
    (repo / ".sdlc" / "hooks" / "secret-guard.sh").unlink()

    code, payload = run_rendered_doctor(repo)

    assert code == 1
    assert payload["ok"] is False
    assert check_map(payload)["secret guard"]["status"] == "FAIL"


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
