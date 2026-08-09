#!/usr/bin/env python3
"""Regression guard: one dated test per historically fixed bug, so none can
silently return. Every test's docstring opens with the date and symptom of
the bug it guards. Run directly: python3 tests/regressions.py

Currently empty by design — the first entry arrives with the first fixed bug.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


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


def main() -> int:
    checks = [
        (
            "nested foreign files cannot claim test command",
            test_nested_foreign_files_cannot_claim_test_command,
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
