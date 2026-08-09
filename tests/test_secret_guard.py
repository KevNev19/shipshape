"""Secret-guard tests: the rendered hook must block planted credentials and
credential files, and pass clean changes. The guard is invoked directly (as
the git hook would) against a real staged index."""

import subprocess

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
    subprocess.run(["git", "add", str(relpath)], cwd=repo, check=True)


def unstage_all(repo):
    subprocess.run(["git", "reset", "-q"], cwd=repo, check=True)


def test_clean_change_passes(tmp_path):
    repo = guarded_repo(tmp_path)
    stage(repo, "src/feature.py", "def feature() -> str:\n    return 'ok'\n")
    result = run_guard(repo)
    assert result.returncode == 0, result.stderr


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


@pytest.mark.parametrize("case", ["clean_after_block"])
def test_block_then_fix_passes(tmp_path, case):
    repo = guarded_repo(tmp_path)
    stage(repo, "src/config.py", f'ACCESS_KEY = "{FAKE_AWS_KEY}"\n')
    assert run_guard(repo).returncode == 1
    unstage_all(repo)
    stage(repo, "src/config.py", 'ACCESS_KEY = os.environ["ACCESS_KEY"]\n')
    assert run_guard(repo).returncode == 0
