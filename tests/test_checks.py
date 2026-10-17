"""checks.py runs a repository's checks once each and prints one JSON answer.

Contract under test: one JSON object on stdout, never prose. run reads
commands.<kind> from .sdlc/config.json, each check named after its kind, or
runs --command=<command> flags instead, each check named after its command;
it reports per check whether it passed, the failure count the tool printed
and the last TAIL_LINES lines of output; "ok" is true only when checks ran
and all passed. It exits 0 whenever it printed an answer, failing checks and
"ran": false included; usage errors exit 2. One budget covers the whole run,
a check's leftover processes cannot hold the runner, and a stop (SIGTERM)
kills the running check's process group and still prints. Commands here are
shell one-liners standing in for real tools, so no test needs pytest, npm or
ruff installed.
"""

import contextlib
import json
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from conftest import SCRIPTS, init_repo, run_script

TAIL_LINES = 20
PYTHON = shlex.quote(sys.executable)
RUN_KEYS = {"ok", "mode", "ran", "reason", "results", "skipped", "next_action"}
RESULT_KEYS = {"name", "command", "passed", "exit_code", "failures", "tail", "duration_ms"}
NO_CONFIG = "no .sdlc/config.json and no --command given"
NOTHING_SET = "no command is set in .sdlc/config.json"
BUDGET_LINE = "stopped: the time budget for the checks ran out"
STOPPED_LINE = "stopped: the runner was asked to stop"
# A stand-in for a slow tool that starts a child, records its pid and waits for it.
SLOW = f"{PYTHON} -c 'import time; time.sleep(60)' & echo $! > child.pid; wait"
# A tool that passes at once but leaves a child holding its output open.
LEAVES_A_CHILD = f"{PYTHON} -c 'import time; time.sleep(60)' & echo $! > child.pid; echo done"
# A tool whose child leaves the check's process group (setsid), records its pid
# once it has, and holds the check's output open while the tool waits for it.
ESCAPES_THE_GROUP = (
    f"{PYTHON} -c 'import os, time; os.setsid(); "
    'open("child.pid", "w").write(str(os.getpid())); time.sleep(60)\' & wait'
)
BLANK_LINES = 100_000
# The runner reads a run of blank lines in linear time: the quadratic patterns
# this guards against took seconds per pattern on 40,000 lines, so 100,000 lines
# leave a wide margin under the budget.
BLANK_LINES_BUDGET_MS = 1000


def say(text: str, code: int = 0) -> str:
    """A shell command that prints text and exits with code, standing in for a tool."""
    return f"printf '%s\\n' {shlex.quote(text)}; exit {code}"


def write_config(repo: Path, commands: dict) -> None:
    config = repo / ".sdlc" / "config.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps({"version": 1, "commands": commands}))


def by_name(payload: dict) -> dict:
    return {result["name"]: result for result in payload["results"]}


def assert_gone(pid: int) -> None:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    os.kill(pid, signal.SIGKILL)
    pytest.fail("a process the check started outlived the runner")


def test_run_reports_each_configured_check_named_after_its_kind(tmp_path):
    write_config(
        tmp_path,
        {"test": say("3 passed in 0.01s"), "lint": say("Found 2 errors.", 1), "build": ""},
    )

    code, payload = run_script("checks.py", "run", tmp_path)

    assert code == 0
    assert set(payload) == RUN_KEYS
    assert payload["ok"] is False
    assert payload["mode"] == "checks-run"
    assert payload["ran"] is True
    assert payload["reason"] == ""
    assert [result["name"] for result in payload["results"]] == ["test", "lint"]
    for result in payload["results"]:
        assert set(result) == RESULT_KEYS
        assert isinstance(result["duration_ms"], int) and result["duration_ms"] >= 0
    test, lint = by_name(payload)["test"], by_name(payload)["lint"]
    assert test["passed"] is True and test["exit_code"] == 0 and test["failures"] == 0
    assert test["tail"] == ["3 passed in 0.01s"]
    assert lint["passed"] is False and lint["exit_code"] == 1 and lint["failures"] == 2
    assert payload["skipped"] == [
        {"name": "build", "reason": "commands.build is empty"},
        {"name": "typecheck", "reason": "commands.typecheck is empty"},
        {"name": "format", "reason": "commands.format is empty"},
    ]
    assert payload["next_action"] == f"Fix the 2 failure(s) `{lint['command']}` reports."


def test_run_is_ok_when_every_check_passes(tmp_path):
    write_config(tmp_path, {"test": say("1 passed in 0.01s"), "lint": say("All checks passed!")})

    code, payload = run_script("checks.py", "run", tmp_path)

    assert code == 0
    assert payload["ok"] is True
    assert [result["passed"] for result in payload["results"]] == [True, True]
    assert payload["next_action"] == "All checks passed."


def test_run_without_config_or_commands_runs_nothing_and_exits_zero(tmp_path):
    code, payload = run_script("checks.py", "run", tmp_path)

    assert code == 0
    assert payload == {
        "ok": False,
        "mode": "checks-run",
        "ran": False,
        "reason": NO_CONFIG,
        "results": [],
        "skipped": [],
        "next_action": "Run /shipshape-init to set up checks, or pass --command=<command>.",
    }


def test_run_with_no_command_set_runs_nothing(tmp_path):
    write_config(tmp_path, {"test": "", "lint": ""})

    code, payload = run_script("checks.py", "run", tmp_path)

    assert code == 0
    assert payload["ok"] is False
    assert payload["ran"] is False
    assert payload["reason"] == NOTHING_SET
    assert payload["results"] == []
    assert [item["name"] for item in payload["skipped"]] == [
        "test",
        "lint",
        "build",
        "typecheck",
        "format",
    ]


def test_run_skips_the_placeholder_render_writes_for_a_repo_without_tests(tmp_path):
    repo = init_repo("repo-empty", tmp_path)

    code, payload = run_script("checks.py", "run", repo)

    assert code == 0, payload
    assert payload["ok"] is False
    assert payload["ran"] is False
    assert payload["reason"] == NOTHING_SET
    assert {
        "name": "test",
        "reason": "commands.test is the placeholder for a repo without tests",
    } in payload["skipped"]


def test_run_commands_replace_the_config_and_name_each_check_after_its_command(tmp_path):
    write_config(tmp_path, {"test": say("from the config", 1), "lint": say("from the config", 1)})
    first, second = say("from a flag"), say("also from a flag")

    code, payload = run_script(
        "checks.py", "run", tmp_path, f"--command={first}", f"--command={second}"
    )

    assert code == 0, payload
    assert [result["name"] for result in payload["results"]] == [first, second]
    assert [result["command"] for result in payload["results"]] == [first, second]
    assert by_name(payload)[first]["tail"] == ["from a flag"]
    assert payload["ok"] is True
    assert payload["skipped"] == []


def test_run_keeps_a_command_with_an_equals_sign_whole_and_runs_a_repeat_once(tmp_path):
    command = "EXAMPLE=1 printenv EXAMPLE; echo once >> ran.log"

    code, payload = run_script(
        "checks.py", "run", tmp_path, f"--command={command}", f"--command={command}"
    )

    assert code == 0, payload
    assert [result["name"] for result in payload["results"]] == [command]
    assert payload["results"][0]["tail"] == ["1"]
    assert (tmp_path / "ran.log").read_text().splitlines() == ["once"]


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("FAILED tests/test_a.py::test_x - assert 1 == 2\n2 failed, 40 passed in 3.05s", 2),
        ("==== 1 failed, 3 passed, 1 warning in 0.12s ====", 1),
        ("==== 2 errors in 0.12s ====", 2),
        ("==== 3 passed, 1 warning, 1 error in 0.05s ====", 1),
        ("Test Suites: 1 failed, 2 passed, 3 total\nTests:       3 failed, 9 passed, 12 total", 3),
        (" Test Files  1 failed | 4 passed (5)\n      Tests  2 failed | 40 passed (42)", 2),
        ("\x1b[31m      Tests  \x1b[1m4 failed\x1b[22m\x1b[39m | 40 passed (44)", 4),
        (
            "--- FAIL: TestA (0.00s)\n--- FAIL: TestB (0.00s)\n"
            "    --- FAIL: TestB/sub (0.00s)\nFAIL\texample.com/app\t0.01s",
            2,
        ),
        ("test result: FAILED. 40 passed; 3 failed; 0 ignored; 0 measured; 0 filtered out", 3),
        (
            "test result: FAILED. 3 passed; 2 failed; 0 ignored; 0 measured; 0 filtered out\n"
            "test result: ok. 5 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out\n"
            "test result: FAILED. 1 passed; 4 failed; 0 ignored; 0 measured; 0 filtered out",
            6,
        ),
        (
            "a.py:3: error: Incompatible types\nFound 4 errors in 2 files (checked 9 source files)",
            4,
        ),
        ("src/a.ts(3,1): error TS2322: Type mismatch.\nFound 5 errors in 3 files.", 5),
        ("a.py:1:1: F401 `os` imported but unused\nFound 1 error.", 1),
        ("/app/src/a.js\n  3:1  error  'x' is unused\n\n✖ 7 problems (6 errors, 1 warning)", 6),
        ("something broke", None),
    ],
)
def test_run_counts_the_failures_a_tool_reports(tmp_path, output, expected):
    code, payload = run_script("checks.py", "run", tmp_path, f"--command={say(output, 1)}")

    assert code == 0
    result = payload["results"][0]
    assert result["passed"] is False and result["exit_code"] == 1
    assert result["failures"] == expected


@pytest.mark.parametrize("cannot_run", [126, 127])
def test_a_command_the_shell_could_not_run_reports_no_failure_count(tmp_path, cannot_run):
    command = say("Found 3 errors.", cannot_run)

    code, payload = run_script("checks.py", "run", tmp_path, f"--command={command}")

    assert code == 0
    result = payload["results"][0]
    assert result["passed"] is False and result["exit_code"] == cannot_run
    assert result["failures"] is None


def test_run_counts_failures_after_a_long_run_of_blank_lines_in_linear_time(tmp_path):
    lines = f"{PYTHON} -c 'print(\"\\n\" * {BLANK_LINES})'; exit 1"

    code, payload = run_script("checks.py", "run", tmp_path, f"--command={lines}")

    assert code == 0, payload
    result = payload["results"][0]
    assert result["exit_code"] == 1 and result["failures"] is None
    assert result["duration_ms"] < BLANK_LINES_BUDGET_MS


def test_run_reads_only_the_last_mebibyte_of_output(tmp_path):
    summary_then_filler = (
        f'{PYTHON} -c \'import sys; print("Found 9 errors in 1 file"); '
        'sys.stdout.write("x" * (3 << 20)); print(); print("last")\'; exit 1'
    )

    code, payload = run_script("checks.py", "run", tmp_path, f"--command={summary_then_filler}")

    assert code == 0, payload
    [result] = payload["results"]
    assert result["tail"][-1] == "last"
    assert result["failures"] is None


def test_run_keeps_only_the_last_lines_of_output(tmp_path):
    lines = f"{PYTHON} -c 'for i in range(30): print(i)'"

    code, payload = run_script("checks.py", "run", tmp_path, f"--command={lines}")

    assert code == 0, payload
    assert payload["results"][0]["tail"] == [str(i) for i in range(30 - TAIL_LINES, 30)]


def test_run_reports_a_missing_program_as_a_failed_check(tmp_path, monkeypatch):
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    monkeypatch.setenv("PATH", str(empty_bin))

    code, payload = run_script("checks.py", "run", tmp_path, "--command=ruff check .")

    assert code == 0
    assert payload["ran"] is True and payload["ok"] is False
    result = payload["results"][0]
    assert result["passed"] is False
    assert result["exit_code"] == 127
    assert result["failures"] is None
    assert (
        payload["next_action"] == "Install what `ruff check .` calls: the shell could not find it."
    )


def test_run_reports_a_file_that_cannot_be_executed_as_a_failed_check(tmp_path):
    (tmp_path / "tool.sh").write_text("#!/bin/sh\nexit 0\n")

    code, payload = run_script("checks.py", "run", tmp_path, "--command=./tool.sh")

    assert code == 0
    result = payload["results"][0]
    assert result["passed"] is False and result["exit_code"] == 126
    assert result["failures"] is None


def test_run_stops_at_its_budget_and_kills_what_the_check_started(tmp_path):
    started = time.monotonic()

    code, payload = run_script(
        "checks.py",
        "run",
        tmp_path,
        f"--command={SLOW}",
        "--command=echo second >> ran.log",
        "--timeout=1",
    )

    assert code == 0
    assert time.monotonic() - started < 10
    assert payload["ran"] is True and payload["ok"] is False
    [result] = payload["results"]
    assert result["name"] == SLOW
    assert result["passed"] is False and result["exit_code"] is None
    assert result["failures"] is None
    assert result["tail"][-1] == BUDGET_LINE
    assert payload["skipped"] == [
        {
            "name": "echo second >> ran.log",
            "reason": "not reached: the time budget for the checks ran out",
        }
    ]
    assert not (tmp_path / "ran.log").exists()
    assert_gone(int((tmp_path / "child.pid").read_text()))


def test_a_check_that_leaves_a_child_holding_its_output_passes_at_once(tmp_path):
    started = time.monotonic()

    code, payload = run_script(
        "checks.py", "run", tmp_path, f"--command={LEAVES_A_CHILD}", "--timeout=30"
    )

    assert code == 0, payload
    assert time.monotonic() - started < 10
    [result] = payload["results"]
    assert result["passed"] is True and result["exit_code"] == 0
    assert result["tail"] == ["done"]
    assert payload["ok"] is True
    assert_gone(int((tmp_path / "child.pid").read_text()))


def test_a_stop_answers_while_a_child_outside_the_group_holds_the_output(tmp_path):
    proc = subprocess.Popen(
        [
            sys.executable,
            str(SCRIPTS / "checks.py"),
            "run",
            str(tmp_path),
            f"--command={ESCAPES_THE_GROUP}",
            "--timeout=60",
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    child_pid = tmp_path / "child.pid"
    try:
        deadline = time.monotonic() + 10
        while not (child_pid.exists() and child_pid.read_text().strip()):
            assert time.monotonic() < deadline, "the check never started"
            time.sleep(0.05)

        proc.send_signal(signal.SIGTERM)
        out, _ = proc.communicate(timeout=10)
    finally:
        proc.kill()
        if child_pid.exists() and child_pid.read_text().strip():
            with contextlib.suppress(ProcessLookupError):
                os.kill(int(child_pid.read_text()), signal.SIGKILL)

    assert proc.returncode == 0
    [result] = json.loads(out)["results"]
    assert result["passed"] is False and result["failures"] is None
    assert result["tail"][-1] == STOPPED_LINE


def test_a_stop_kills_the_running_check_and_still_answers(tmp_path):
    """How a caller starts the script: python3 -I -B, by absolute path, from another folder."""
    repo = tmp_path / "repo"
    repo.mkdir()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-I",
            "-B",
            str(SCRIPTS / "checks.py"),
            "run",
            str(repo),
            f"--command={SLOW}",
            "--command=echo second >> ran.log",
        ],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        text=True,
    )
    child_pid = repo / "child.pid"
    deadline = time.monotonic() + 10
    while not (child_pid.exists() and child_pid.read_text().strip()):
        assert time.monotonic() < deadline, "the check never started"
        time.sleep(0.05)

    proc.send_signal(signal.SIGTERM)
    out, _ = proc.communicate(timeout=10)

    assert proc.returncode == 0
    payload = json.loads(out)
    [result] = payload["results"]
    assert result["passed"] is False and result["failures"] is None
    assert result["tail"][-1] == STOPPED_LINE
    assert payload["skipped"] == [
        {"name": "echo second >> ran.log", "reason": "not reached: the runner was asked to stop"}
    ]
    assert not (repo / "ran.log").exists()
    assert_gone(int(child_pid.read_text()))


def test_run_gives_a_check_no_input(tmp_path):
    # An open pipe nobody writes to: a check that inherited it would block on read.
    reader, writer = os.pipe()
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "checks.py"),
                "run",
                str(tmp_path),
                "--command=cat",
                "--timeout=5",
            ],
            stdin=reader,
            capture_output=True,
            text=True,
        )
    finally:
        os.close(reader)
        os.close(writer)

    assert proc.returncode == 0, proc.stdout
    assert json.loads(proc.stdout)["results"][0]["passed"] is True


def test_run_merges_standard_error_into_the_tail(tmp_path):
    code, payload = run_script("checks.py", "run", tmp_path, "--command=echo out; echo err >&2")

    assert code == 0, payload
    assert payload["results"][0]["tail"] == ["out", "err"]


def test_run_works_in_isolated_mode_from_another_folder(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    proc = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(SCRIPTS / "checks.py"),
            "run",
            str(repo),
            f"--command={say('1 passed in 0.01s')}",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["results"][0]["passed"] is True


def test_run_with_an_unreadable_config_is_a_json_error(tmp_path):
    config = tmp_path / ".sdlc" / "config.json"
    config.parent.mkdir()
    config.write_text("not json")

    code, payload = run_script("checks.py", "run", tmp_path)

    assert code == 2
    assert set(payload) == {"ok", "mode", "error", "next_action"}
    assert payload["ok"] is False
    assert ".sdlc/config.json" in payload["error"]


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["frob", "{repo}"],
        ["prove", "{repo}"],
        ["run"],
        ["run", "{repo}", "--command"],
        ["run", "{repo}", "--command="],
        ["run", "{repo}", "--command=  "],
        ["run", "{repo}", "--check", "test=pytest"],
        ["run", "{repo}", "--timeout=0"],
        ["run", "{repo}", "--timeout=soon"],
        ["run", "{repo}/missing"],
    ],
)
def test_usage_errors_are_json_with_exit_two(tmp_path, args):
    code, payload = run_script("checks.py", *[arg.replace("{repo}", str(tmp_path)) for arg in args])

    assert code == 2
    assert set(payload) == {"ok", "mode", "error", "next_action"}
    assert payload["ok"] is False
    assert payload["error"]
    assert payload["next_action"]
