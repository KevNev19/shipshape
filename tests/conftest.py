import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

KIT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = KIT_ROOT / "scripts"
FIXTURES = KIT_ROOT / "tests" / "fixtures"


@pytest.fixture
def hermetic_doctor_path(tmp_path: Path, monkeypatch) -> Path:
    """Keep doctor subprocesses away from host tools and ambient CI mode."""
    bin_dir = tmp_path / "doctor-bin"
    bin_dir.mkdir(exist_ok=True)
    for command in ("git", "python3"):
        executable = shutil.which(command)
        assert executable is not None
        (bin_dir / command).symlink_to(executable)
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert shutil.which("gh") is None
    return bin_dir


def prepend_to_path(monkeypatch, directory: Path) -> None:
    """Put a test shim ahead of the curated subprocess PATH."""
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")


def run_script(script: str, *args) -> tuple[int, dict]:
    """Run a shipshape script and parse its JSON stdout."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *[str(a) for a in args]],
        capture_output=True,
        text=True,
    )
    payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    return proc.returncode, payload


def init_repo(fixture: str, tmp_path: Path, overrides: list[str] | None = None) -> Path:
    """Copy a fixture to a temp dir and run detect + init-config on it."""
    repo = tmp_path / fixture
    shutil.copytree(FIXTURES / fixture, repo)
    detect_proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "detect.py"), str(repo), "--no-network"],
        capture_output=True,
        text=True,
        check=True,
    )
    detect_file = tmp_path / f"{fixture}-detect.json"
    detect_file.write_text(detect_proc.stdout)
    args = ["init-config", repo, "--detect", detect_file]
    for override in overrides or []:
        args += ["--set", override]
    code, payload = run_script("render.py", *args)
    assert code == 0, payload
    return repo


# A parent that adopts orphans and never reaps them, like the PID 1 of a
# container without an init: a Linux child subreaper that runs the command in
# argv[2:], then prints its exit status and whether the process whose pid is in
# the file argv[1] is still in the process table.
PARENT_THAT_NEVER_REAPS = """
import ctypes, json, subprocess, sys
from pathlib import Path

ctypes.CDLL(None).prctl(36, ctypes.c_ulong(1), *[ctypes.c_ulong(0)] * 3)
code = subprocess.run(sys.argv[2:], stdout=subprocess.DEVNULL).returncode
pid = int(Path(sys.argv[1]).read_text())
print(json.dumps({"code": code, "left": Path(f"/proc/{pid}").exists()}))
"""

linux_only = pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="child subreapers exist on Linux only"
)


def left_unreaped(pid_file: Path, *command: str) -> bool:
    """Run `command` under PARENT_THAT_NEVER_REAPS and say whether the process
    whose pid `pid_file` holds outlived it, alive or as a zombie nobody reaped."""
    proc = subprocess.run(
        [sys.executable, "-c", PARENT_THAT_NEVER_REAPS, str(pid_file), *command],
        capture_output=True,
        text=True,
        check=True,
    )
    answer = json.loads(proc.stdout)
    assert answer["code"] == 0, answer
    return answer["left"]
