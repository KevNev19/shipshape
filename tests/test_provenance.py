"""Optional Agent-Assisted-By commit labels stay off until requested."""

import os
import stat
import subprocess

from conftest import init_repo, run_script

HOOK = ".sdlc/hooks/commit-msg-provenance.sh"
INSTALLER = ".sdlc/hooks/install-provenance.sh"
PR_TEMPLATE = ".github/PULL_REQUEST_TEMPLATE.md"


def apply(tmp_path, overrides=None):
    repo = init_repo("repo-python", tmp_path, overrides=overrides)
    code, payload = run_script("render.py", "apply", repo)
    assert code == 0, payload
    return repo, set(payload["written"])


def git_init(repo):
    subprocess.run(["git", "init", "-qb", "main"], cwd=repo, check=True)


def run_hook(repo, message):
    path = repo / "commit-message.txt"
    path.write_text(message)
    return subprocess.run(
        ["bash", HOOK, str(path)],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def test_provenance_files_stay_off_by_default(tmp_path):
    repo, written = apply(tmp_path)
    assert HOOK not in written
    assert INSTALLER not in written
    assert not (repo / HOOK).exists()
    assert not (repo / INSTALLER).exists()


def test_provenance_files_render_executable_when_enabled(tmp_path):
    repo, written = apply(tmp_path, ["features.provenance_labels=true"])
    assert HOOK in written
    assert INSTALLER in written
    for rel in (HOOK, INSTALLER):
        mode = (repo / rel).stat().st_mode
        assert mode & stat.S_IXUSR, rel
    assert "not a safety" in (repo / HOOK).read_text()


def test_pr_template_asks_how_the_change_was_made(tmp_path):
    repo, written = apply(tmp_path, ["workflow_style=pr"])
    assert PR_TEMPLATE in written
    text = (repo / PR_TEMPLATE).read_text()
    assert "## How was this made?" in text
    assert "not a safety check" in text
    assert "Agent-Assisted-By" not in text


def test_unlabeled_commit_message_passes(tmp_path):
    repo, _written = apply(tmp_path, ["features.provenance_labels=true"])
    result = run_hook(repo, "Fix the typo in the readme.\n")
    assert result.returncode == 0, result.stderr


def test_valid_agent_trailer_passes(tmp_path):
    repo, _written = apply(tmp_path, ["features.provenance_labels=true"])
    message = "Add the label check.\n\nAgent-Assisted-By: GitHub Copilot\n"
    result = run_hook(repo, message)
    assert result.returncode == 0, result.stderr


def test_crlf_trailer_passes(tmp_path):
    repo, _written = apply(tmp_path, ["features.provenance_labels=true"])
    result = run_hook(repo, "Add the label check.\r\n\r\nAgent-Assisted-By: Claude\r\n")
    assert result.returncode == 0, result.stderr


def test_malformed_trailer_fails_without_calling_itself_a_safety_check(tmp_path):
    repo, _written = apply(tmp_path, ["features.provenance_labels=true"])
    result = run_hook(repo, "Add the label check.\n\nAgent-Assisted-By:\n")
    assert result.returncode == 1
    assert "not a safety check" in result.stderr
    assert "Remove the line" in result.stderr


def test_trailing_space_and_empty_tool_fail(tmp_path):
    repo, _written = apply(tmp_path, ["features.provenance_labels=true"])
    for message in (
        "Note\n\nAgent-Assisted-By: \n",
        "Note\n\nAgent-Assisted-By: Tool \n",
        "Note\n\nAgent-Assisted-By: bad/tool\n",
    ):
        result = run_hook(repo, message)
        assert result.returncode == 1, message


def test_installer_wires_commit_msg_and_is_idempotent(tmp_path):
    repo, _written = apply(tmp_path, ["features.provenance_labels=true"])
    git_init(repo)
    first = subprocess.run(["bash", INSTALLER], cwd=repo, capture_output=True, text=True)
    hook = repo / ".git" / "hooks" / "commit-msg"
    assert first.returncode == 0, first.stderr
    assert hook.is_symlink()
    assert hook.resolve() == (repo / HOOK).resolve()
    second = subprocess.run(["bash", INSTALLER], cwd=repo, capture_output=True, text=True)
    assert second.returncode == 0, second.stderr
    assert "already installed" in second.stdout


def test_installer_preserves_unrelated_commit_msg_hook(tmp_path):
    repo, _written = apply(tmp_path, ["features.provenance_labels=true"])
    git_init(repo)
    hook = repo / ".git" / "hooks" / "commit-msg"
    original = b"#!/bin/sh\nprintf unrelated\n"
    hook.write_bytes(original)
    hook.chmod(0o755)
    result = subprocess.run(["bash", INSTALLER], cwd=repo, capture_output=True, text=True)
    assert result.returncode != 0
    assert hook.read_bytes() == original
    assert "not changed" in result.stderr


def test_secret_guard_installer_also_wires_the_label_when_present(tmp_path):
    repo, _written = apply(tmp_path, ["features.provenance_labels=true"])
    git_init(repo)
    env = os.environ.copy()
    env["PATH"] = os.defpath
    result = subprocess.run(
        ["bash", ".sdlc/hooks/install.sh"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )
    hook = repo / ".git" / "hooks" / "commit-msg"
    assert result.returncode == 0, result.stderr
    assert hook.is_symlink()
    assert hook.resolve() == (repo / HOOK).resolve()
    assert (repo / ".git" / "hooks" / "pre-commit").is_symlink()


def test_installer_follows_configured_hooks_path(tmp_path):
    repo, _written = apply(tmp_path, ["features.provenance_labels=true"])
    git_init(repo)
    subprocess.run(["git", "config", "core.hooksPath", ".custom hooks"], cwd=repo, check=True)
    result = subprocess.run(["bash", INSTALLER], cwd=repo, capture_output=True, text=True)
    hook = repo / ".custom hooks" / "commit-msg"
    assert result.returncode == 0, result.stderr
    assert hook.is_symlink()
    assert not (repo / ".git" / "hooks" / "commit-msg").exists()
