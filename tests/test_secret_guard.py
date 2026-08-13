"""Secret-guard tests: the rendered hook must block planted credentials and
credential files, and pass clean changes. The guard is invoked directly (as
the git hook would) against a real staged index."""

import subprocess
from pathlib import Path

import pytest
from conftest import init_repo, run_script

# Amazon's canonical documentation example key — not a real credential.
# Built by concatenation so this test file itself never contains a string
# the guard (or GitHub push protection) would match.
FAKE_AWS_KEY = "AKIA" + "IOSFODNN7EXAMPLE"


def guarded_repo(tmp_path):
    repo = init_repo("repo-python", tmp_path)
    code, _ = run_script("render.py", "apply", repo)
    assert code == 0
    subprocess.run(["git", "init", "-qb", "main"], cwd=repo, check=True)
    return repo


def run_guard(repo):
    return subprocess.run(
        ["bash", ".sdlc/hooks/secret-guard.sh"],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def stage(repo, relpath, content):
    path = repo / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    subprocess.run(["git", "add", "-f", str(relpath)], cwd=repo, check=True)


def unstage_all(repo):
    subprocess.run(["git", "reset", "-q"], cwd=repo, check=True)


def test_clean_change_passes(tmp_path):
    repo = guarded_repo(tmp_path)
    stage(repo, "src/feature.py", "def feature() -> str:\n    return 'ok'\n")
    result = run_guard(repo)
    assert result.returncode == 0, result.stderr
    assert "WARN" not in result.stderr


def test_control_file_change_warns_without_blocking(tmp_path):
    repo = guarded_repo(tmp_path)
    stage(repo, ".claude/preferences.json", '{"theme": "dark"}\n')
    result = run_guard(repo)
    assert result.returncode == 0, result.stderr
    assert "WARN" in result.stderr
    assert ".claude/preferences.json" in result.stderr
    assert "automated tools behave" in result.stderr


@pytest.mark.parametrize(
    "control_path",
    [".github/copilot-instructions.md", "AGENTS.md", ".sdlc/hooks/custom.sh"],
)
def test_each_remaining_control_path_warns(tmp_path, control_path):
    repo = guarded_repo(tmp_path)
    stage(repo, control_path, "Review this control change.\n")
    result = run_guard(repo)
    assert result.returncode == 0, result.stderr
    assert "WARN" in result.stderr
    assert control_path in result.stderr


def test_vscode_task_command_is_blocked(tmp_path):
    repo = guarded_repo(tmp_path)
    stage(
        repo,
        ".vscode/tasks.json",
        '{"version": "2.0.0", "tasks": [{"command": "make release"}]}\n',
    )
    result = run_guard(repo)
    assert result.returncode == 1
    assert "BLOCKED" in result.stderr
    assert ".vscode/tasks.json" in result.stderr
    assert "git commit --no-verify" in result.stderr


def test_benign_terminal_preference_warns_without_blocking(tmp_path):
    repo = guarded_repo(tmp_path)
    stage(repo, ".vscode/settings.json", '{"terminal.integrated.fontSize": 14}\n')
    result = run_guard(repo)
    assert result.returncode == 0, result.stderr
    assert "WARN" in result.stderr
    assert "BLOCKED" not in result.stderr


def test_terminal_shell_setting_is_blocked(tmp_path):
    repo = guarded_repo(tmp_path)
    stage(
        repo,
        ".vscode/settings.json",
        '{"terminal.integrated.shell.osx": "/tmp/run-on-open"}\n',
    )
    result = run_guard(repo)
    assert result.returncode == 1
    assert "BLOCKED" in result.stderr


def test_terminal_profile_with_executable_path_is_blocked(tmp_path):
    repo = guarded_repo(tmp_path)
    stage(
        repo,
        ".vscode/settings.json",
        "{\n"
        '  "terminal.integrated.profiles.osx": {\n'
        '    "release": {"path": "/tmp/run-on-open"}\n'
        "  }\n"
        "}\n",
    )
    result = run_guard(repo)
    assert result.returncode == 1
    assert "BLOCKED" in result.stderr


def test_claude_settings_base64_blob_is_blocked(tmp_path):
    repo = guarded_repo(tmp_path)
    encoded = "A" * 44
    stage(repo, ".claude/settings.json", f'{{"payload": "{encoded}"}}\n')
    result = run_guard(repo)
    assert result.returncode == 1
    assert "BLOCKED" in result.stderr
    assert "base64" in result.stderr


def test_markdown_control_file_command_warns_without_blocking(tmp_path):
    repo = guarded_repo(tmp_path)
    stage(repo, "CLAUDE.md", "Run `make test` before finishing.\n")
    result = run_guard(repo)
    assert result.returncode == 0, result.stderr
    assert "WARN" in result.stderr
    assert "CLAUDE.md" in result.stderr


def test_planted_api_key_is_blocked(tmp_path):
    repo = guarded_repo(tmp_path)
    stage(repo, "src/config.py", f'ACCESS_KEY = "{FAKE_AWS_KEY}"\n')
    result = run_guard(repo)
    assert result.returncode == 1
    assert "BLOCKED" in result.stderr
    assert "API key" in result.stderr


def test_env_file_is_blocked_by_name(tmp_path):
    repo = guarded_repo(tmp_path)
    stage(repo, ".env", "DB_PASSWORD=hunter2\n")
    result = run_guard(repo)
    assert result.returncode == 1
    assert "credential or key file" in result.stderr


def test_private_key_header_is_blocked(tmp_path):
    repo = guarded_repo(tmp_path)
    # Concatenated so this file never contains a line the guard would match.
    header = "-----BEGIN RSA PRIVATE " + "KEY-----"
    stage(repo, "deploy/server.txt", header + "\nabc\n")
    result = run_guard(repo)
    assert result.returncode == 1


def test_denylist_blocks_custom_strings(tmp_path):
    repo = guarded_repo(tmp_path)
    (repo / ".sdlc/hooks/denylist.txt").write_text("Sensitive Family Name\n")
    stage(repo, "notes.md", "payment from Sensitive Family Name arrived\n")
    result = run_guard(repo)
    assert result.returncode == 1
    assert "denylist" in result.stderr


def test_nothing_staged_passes(tmp_path):
    repo = guarded_repo(tmp_path)
    result = run_guard(repo)
    assert result.returncode == 0


def _commit(repo, message):
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            message,
        ],
        cwd=repo,
        check=True,
    )


def test_range_mode_catches_committed_secret(tmp_path):
    """CI mode: a secret already committed (e.g. by a cloud agent that never
    ran the local hook) is caught by --range base..HEAD."""
    repo = guarded_repo(tmp_path)
    stage(repo, "README2.md", "clean base\n")
    _commit(repo, "base")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    stage(repo, "src/config.py", f'ACCESS_KEY = "{FAKE_AWS_KEY}"\n')
    _commit(repo, "leaky")

    result = subprocess.run(
        ["bash", ".sdlc/hooks/secret-guard.sh", "--range", f"{base}..HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "rotate" in result.stderr, "CI mode must give rotation advice"


def test_range_mode_passes_clean_range(tmp_path):
    repo = guarded_repo(tmp_path)
    stage(repo, "a.md", "one\n")
    _commit(repo, "one")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    stage(repo, "b.md", "two\n")
    _commit(repo, "two")
    result = subprocess.run(
        ["bash", ".sdlc/hooks/secret-guard.sh", "--range", f"{base}..HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_range_mode_warns_for_control_file_change(tmp_path):
    repo = guarded_repo(tmp_path)
    stage(repo, "a.md", "one\n")
    _commit(repo, "one")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    stage(repo, ".github/agents/helper.md", "Review the whole diff.\n")
    _commit(repo, "control")

    result = subprocess.run(
        ["bash", ".sdlc/hooks/secret-guard.sh", "--range", f"{base}..HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "WARN" in result.stderr
    assert ".github/agents/helper.md" in result.stderr


def test_range_mode_control_failure_does_not_give_secret_rotation_advice(tmp_path):
    repo = guarded_repo(tmp_path)
    stage(repo, "a.md", "one\n")
    _commit(repo, "one")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    stage(repo, ".claude/settings.json", '{"hooks": {"command": "curl example.test"}}\n')
    _commit(repo, "control")

    result = subprocess.run(
        ["bash", ".sdlc/hooks/secret-guard.sh", "--range", f"{base}..HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "automated tools" in result.stderr
    assert "rotate" not in result.stderr
    assert "looks like a secret" not in result.stderr


def test_type_changed_control_file_warns(tmp_path):
    repo = guarded_repo(tmp_path)
    stage(repo, ".claude/settings.json", '{"theme": "dark"}\n')
    _commit(repo, "settings")
    settings = repo / ".claude" / "settings.json"
    settings.unlink()
    settings.symlink_to(Path("..") / "shared-settings.json")
    subprocess.run(["git", "add", ".claude/settings.json"], cwd=repo, check=True)

    result = run_guard(repo)
    assert result.returncode == 0, result.stderr
    assert "WARN" in result.stderr
    assert ".claude/settings.json" in result.stderr


def test_control_file_renamed_out_of_control_path_warns(tmp_path):
    repo = guarded_repo(tmp_path)
    stage(repo, ".claude/preferences.json", '{"theme": "dark"}\n')
    _commit(repo, "preferences")
    (repo / "config").mkdir()
    subprocess.run(
        ["git", "mv", ".claude/preferences.json", "config/preferences.json"],
        cwd=repo,
        check=True,
    )

    result = run_guard(repo)
    assert result.returncode == 0, result.stderr
    assert "WARN" in result.stderr
    assert ".claude/preferences.json" in result.stderr


@pytest.mark.parametrize("case", ["clean_after_block"])
def test_block_then_fix_passes(tmp_path, case):
    repo = guarded_repo(tmp_path)
    stage(repo, "src/config.py", f'ACCESS_KEY = "{FAKE_AWS_KEY}"\n')
    assert run_guard(repo).returncode == 1
    unstage_all(repo)
    stage(repo, "src/config.py", 'ACCESS_KEY = os.environ["ACCESS_KEY"]\n')
    assert run_guard(repo).returncode == 0
