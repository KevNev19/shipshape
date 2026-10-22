#!/usr/bin/env python3
# What this is: runs this repository's checks (tests, lint, build, typecheck,
# format) once each and prints one JSON result; its "ok" says whether all passed.
# Safe to edit: yes — shipshape will ask before overwriting your edits.
# managed-by: shipshape v0.4.0
"""Run a repository's checks once each (ADR 0002: stdlib only, JSON-only stdout).

Usage:
    python3 checks.py run <repo> [--command=<command>]... [--timeout=SECONDS]

Prints exactly one JSON object on stdout and never prose:
{"ok", "mode": "checks-run", "ran", "reason", "results": [{"name", "command",
"passed", "exit_code", "failures", "tail", "duration_ms"}], "skipped":
[{"name", "reason"}], "next_action"}.

Without --command it runs the commands .sdlc/config.json sets (commands.test,
lint, build, typecheck and format), each named after its kind; an empty
command is skipped, and so is the placeholder render.py writes for a repo
without tests. --command flags replace the config for that run, so a repo
without .sdlc/config.json runs as well; each of those checks is named after
its command. With nothing to run, "ran" is false, "reason" says why and
"results" is empty; otherwise "ran" is true and "reason" is empty.

Per check: whether it passed; "failures", 0 for a passing check, the count
the tool's summary states for a failing one, and null when it states none;
and "tail", the last TAIL_LINES lines of its merged output, each cut to
TAIL_LINE_WIDTH characters and no more of them than fit in TAIL_MAX_CHARS.
Both are read from the last MAX_OUTPUT_BYTES of that output. A command the
shell could not run (exit 126 or 127) or that could not start is a failed
check. "ok" is true only when checks ran, none was left unreached and every
one passed; "next_action" names any check not reached and why.

--timeout is one budget for the whole run (default 1800 seconds). Each
command runs through the shell in the repo, with no input, in a process group
of its own, writing to a temporary file rather than a pipe, so a process that
outlives the command cannot keep the runner waiting. When the command exits,
the runner kills whatever it left running in its group. When the budget ends,
when a check's output passes MAX_WRITTEN_BYTES, or when the runner gets
SIGTERM, SIGINT, SIGHUP or SIGQUIT, it kills the running command's group, so
nothing the check started outlives it, reports that check failed with
"failures": null and a last tail line saying why it stopped, lists the checks
it did not reach under "skipped" instead of "results", and prints its answer.
A signal the runner was started ignoring, as under nohup, stays ignored. On
Linux the runner adopts and reaps what it kills, so nothing stays a zombie
where PID 1 reaps nothing, as in a container without an init. Windows has no
process groups: taskkill ends the process tree of a check still running when
the budget ends or a stop arrives, and what a finished check leaves behind is
not found.

Exit 0 whenever an answer is printed, whatever the checks reported; read "ok"
to gate on them. A usage error, or a config that cannot be read, prints
{"ok": false, "mode": "checks-run", "error": ..., "next_action": ...} and
exits 2.

This file imports nothing from the other kit scripts: callers may run it with
`python3 -I`, which leaves the script's folder off sys.path, and the consumer
copy (.sdlc/scripts/checks.py, from templates/scripts/checks.py.tmpl) is this
file under a managed header.
"""

import argparse
import contextlib
import json
import math
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

MODE = "checks-run"
CHECK_KINDS = ("test", "lint", "build", "typecheck", "format")
CONFIG_PATH = Path(".sdlc") / "config.json"
# What render.py init-config writes for a repo without tests; running it proves nothing.
NO_TESTS_CMD = 'echo "No tests configured yet - see docs/sdlc/harness.md"'
TAIL_LINES = 20
DEFAULT_RUN_TIMEOUT_SECONDS = 1800.0
KILL_WAIT_SECONDS = 5.0
# How often to look again for a killed group member to reap.
REAP_POLL_SECONDS = 0.01
# Linux prctl options that set and read whether this process adopts what its
# descendants orphan (a child subreaper), as an init does.
PR_SET_CHILD_SUBREAPER = 36
PR_GET_CHILD_SUBREAPER = 37
MAX_OUTPUT_BYTES = 1 << 20
# A check that writes more output than this is ended: its file is on disk,
# and on Linux a tmpfs /tmp is memory.
MAX_WRITTEN_BYTES = 64 << 20
# How often to look at the size of a running check's output.
OUTPUT_POLL_SECONDS = 0.05
# The widest tail line, and the most characters all tail lines take together:
# one long line, such as a minified bundle, must not fill the answer.
TAIL_LINE_WIDTH = 2000
TAIL_MAX_CHARS = 10_000
CUT_MARK = "..."
NOT_EXECUTABLE_EXIT = 126
NOT_FOUND_EXIT = 127
USAGE_EXIT = 2
# The signals that stop the runner: SIGTERM, Ctrl-C's SIGINT, the SIGHUP of a
# closed terminal or a dropped ssh session, and SIGQUIT, none of which reaches a
# check leading a session of its own. Windows has only SIGTERM and SIGINT.
STOP_SIGNALS = tuple(
    getattr(signal, name)
    for name in ("SIGTERM", "SIGINT", "SIGHUP", "SIGQUIT")
    if hasattr(signal, name)
)
MS_PER_SECOND = 1000
# ESC introduces the ANSI color sequences some test tools print in summaries.
ANSI_ESCAPE = re.compile(chr(27) + r"\[[0-9;?]*[A-Za-z]")

# Summary lines that say how many failures a tool found, per tool family. The
# first family that matches decides: a pattern with a group gives the number in
# its last match, or the sum of its matches for a family in SUMMED_FAMILIES;
# one without counts its matches (go test prints a line per failing test and
# no total). mypy and tsc come before ruff, whose summary line is the shorter
# form of theirs. A pytest summary that names both failed tests and errors
# counts the failed tests; "pytest errors" covers the summary of a run that
# only errored (collection or fixture errors). Blanks are [ \t], never \s,
# which runs across line ends and takes quadratic time on a run of blank lines.
FAILURE_COUNT_PATTERNS: dict[str, re.Pattern[str]] = {
    "pytest": re.compile(r"^=*[ \t]*(\d+) failed\b.* in [\d.]+s\b", re.MULTILINE),
    "pytest errors": re.compile(r"^=*[ \t]*(?:\d+ \w+, )*(\d+) errors? in [\d.]+s\b", re.MULTILINE),
    "jest or vitest": re.compile(r"^[ \t]*Tests:?[ \t]+(\d+) failed\b", re.MULTILINE),
    "go test": re.compile(r"^--- FAIL: ", re.MULTILINE),
    "cargo test": re.compile(r"^test result: FAILED\. \d+ passed; (\d+) failed;", re.MULTILINE),
    "mypy or tsc": re.compile(r"^Found (\d+) errors? in ", re.MULTILINE),
    "ruff": re.compile(r"^Found (\d+) errors?\b", re.MULTILINE),
    "eslint": re.compile(r"\b\d+ problems? \((\d+) errors?\b"),
}
# cargo test prints a summary per test binary, and with --no-fail-fast it goes
# on past a failing one, so its counts add up.
SUMMED_FAMILIES = {"cargo test"}

USAGE = "Use: checks.py run <repo> [--command=<command>]... [--timeout=SECONDS]."
NO_CONFIG_REASON = "no .sdlc/config.json and no --command given"
NO_CONFIG_NEXT_ACTION = "Run /shipshape-init to set up checks, or pass --command=<command>."
NOTHING_SET_REASON = "no command is set in .sdlc/config.json"
NOTHING_SET_NEXT_ACTION = (
    "Set a check with render.py set-config <repo> --set commands.<kind>=<command>."
)
BUDGET_LINE = "stopped: the time budget for the checks ran out"
STOPPED_LINE = "stopped: the runner was asked to stop"
OUTPUT_LINE = f"stopped: output over {MAX_WRITTEN_BYTES >> 20} MiB"
NOT_REACHED = "not reached: "
NOT_REACHED_BUDGET = f"{NOT_REACHED}the time budget for the checks ran out"
NOT_REACHED_STOPPED = f"{NOT_REACHED}the runner was asked to stop"
NOTHING_RAN_NEXT_ACTION = "No check ran; run them again."


class ArgumentError(Exception):
    """Raised when the command line does not match the JSON-only contract."""


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ArgumentError(message)


class ConfigError(Exception):
    """Raised when .sdlc/config.json exists but cannot be read as JSON."""


class StopRequest:
    """A stop signal (STOP_SIGNALS) while checks run: kill the running
    command's process group, so nothing the check started outlives the runner,
    and start no other check."""

    def __init__(self) -> None:
        self.requested = False
        self.process: subprocess.Popen | None = None

    def __call__(self, signum, frame) -> None:
        self.requested = True
        if self.process is not None:
            _kill_group(self.process)


STOP = StopRequest()


def _kill_group(process: subprocess.Popen) -> None:
    """Kill a command and everything it started: it leads a session of its own,
    and on Windows, which has no process groups, taskkill ends its process tree
    while it runs."""
    if hasattr(os, "killpg"):
        with contextlib.suppress(OSError):
            os.killpg(process.pid, signal.SIGKILL)
    elif process.poll() is None:
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=KILL_WAIT_SECONDS,
                check=False,
            )
    with contextlib.suppress(OSError):
        process.kill()


def _reap_group(process: subprocess.Popen) -> None:
    """Reap what is left of a killed command's process group: the members this
    process adopted while _adopting_orphans held, for at most KILL_WAIT_SECONDS.
    A member it did not adopt is its own parent's to reap."""
    if not hasattr(os, "killpg"):
        return
    deadline = time.monotonic() + KILL_WAIT_SECONDS
    while True:
        try:
            pid, _ = os.waitpid(-process.pid, os.WNOHANG)
        except ChildProcessError:
            return
        if pid:
            continue
        if time.monotonic() >= deadline:
            return
        # A member forked while the group was being killed is killed too.
        with contextlib.suppress(OSError):
            os.killpg(process.pid, signal.SIGKILL)
        time.sleep(REAP_POLL_SECONDS)


@contextlib.contextmanager
def _adopting_orphans():
    """On Linux, make this process the reaper of what its commands orphan for
    the length of the block, so _reap_group can reap a killed group where PID 1
    reaps nothing, as in a container without an init. Elsewhere, or without
    ctypes, the block runs as it is."""
    if not sys.platform.startswith("linux"):
        yield
        return
    try:
        # Imported here: a Python built without ctypes still runs the checks.
        import ctypes

        prctl = ctypes.CDLL(None, use_errno=True).prctl
        previous = ctypes.c_int(0)
        prctl(PR_GET_CHILD_SUBREAPER, ctypes.byref(previous), *[ctypes.c_ulong(0)] * 3)
        prctl(PR_SET_CHILD_SUBREAPER, ctypes.c_ulong(1), *[ctypes.c_ulong(0)] * 3)
    except (ImportError, OSError, AttributeError):
        yield
        return
    try:
        yield
    finally:
        prctl(PR_SET_CHILD_SUBREAPER, ctypes.c_ulong(previous.value), *[ctypes.c_ulong(0)] * 3)


def count_failures(output: str) -> int | None:
    """The failure count a tool's summary states, or None when no known summary appears."""
    for family, pattern in FAILURE_COUNT_PATTERNS.items():
        matches = pattern.findall(output)
        if not matches:
            continue
        if not pattern.groups:
            return len(matches)
        if family in SUMMED_FAMILIES:
            return sum(int(match) for match in matches)
        return int(matches[-1])
    return None


def _clean_output(raw: bytes) -> str:
    return ANSI_ESCAPE.sub("", raw.decode("utf-8", errors="replace"))


def _result(
    command: str, started: float, exit_code: int | None, output: str, why: str = ""
) -> dict:
    """One check's answer; `why` names what ended a command that did not finish."""
    passed = exit_code == 0 and not why
    if passed:
        failures = 0
    elif why or exit_code in (NOT_EXECUTABLE_EXIT, NOT_FOUND_EXIT):
        failures = None
    else:
        failures = count_failures(output)
    lines = [line.rstrip() for line in output.rstrip().splitlines()]
    if why:
        lines.append(why)
    return {
        "command": command,
        "passed": passed,
        "exit_code": exit_code,
        "failures": failures,
        "tail": _tail(lines),
        "duration_ms": round((time.monotonic() - started) * MS_PER_SECOND),
    }


def _tail(lines: list[str]) -> list[str]:
    """The last TAIL_LINES lines, each cut to TAIL_LINE_WIDTH characters, and
    only as many of them as fit in TAIL_MAX_CHARS; the last line always stays."""
    tail: list[str] = []
    size = 0
    for line in reversed(lines[-TAIL_LINES:]):
        if len(line) > TAIL_LINE_WIDTH:
            line = line[:TAIL_LINE_WIDTH] + CUT_MARK
        size += len(line)
        if tail and size > TAIL_MAX_CHARS:
            break
        tail.append(line)
    return tail[::-1]


def _read_tail(sink) -> bytes:
    """The last MAX_OUTPUT_BYTES of what a check wrote."""
    size = sink.seek(0, os.SEEK_END)
    sink.seek(max(0, size - MAX_OUTPUT_BYTES))
    return sink.read()


def _start_command(command: str, **kwargs):
    """Start one repository command in its own session.

    POSIX uses the same shell program CPython uses for a command string:
    `/bin/sh -c`, or `/system/bin/sh` on Android. Windows keeps the platform
    shell, because cmd quoting is not the same as an argument list.
    """
    if os.name == "nt":
        return subprocess.Popen(command, **kwargs, **{"shell": os.name == "nt"})
    shell = "/system/bin/sh" if hasattr(sys, "getandroidapilevel") else "/bin/sh"
    return subprocess.Popen([shell, "-c", command], **kwargs)


def run_command(repo: Path, command: str, timeout: float) -> dict:
    """Run one check command once through the shell in the repo, within `timeout`
    seconds, and say what happened."""
    started = time.monotonic()
    # A file, not a pipe: a process the check leaves behind cannot hold the runner
    # waiting for end of output, and a chatty check cannot fill the runner's memory.
    try:
        sink = tempfile.TemporaryFile()
    except OSError as error:
        return _result(command, started, None, "", f"could not start: {error}")
    with sink:
        try:
            process = _start_command(
                command,
                cwd=repo,
                stdin=subprocess.DEVNULL,
                stdout=sink,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        # A NUL byte in the command is a ValueError, not an OSError.
        except (OSError, ValueError) as error:
            return _result(command, started, None, "", f"could not start: {error}")
        STOP.process = process
        try:
            if STOP.requested:
                _kill_group(process)
            why = _wait(process, sink, timeout)
        finally:
            STOP.process = None
            # Whatever the check left running in its group ends with it, however
            # the wait ended, an exception included.
            _kill_group(process)
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=KILL_WAIT_SECONDS)
            _reap_group(process)
        try:
            raw = _read_tail(sink)
        except OSError as error:
            return _result(command, started, None, "", f"could not read its output: {error}")
    if not why and STOP.requested:
        why = STOPPED_LINE
    return _result(command, started, None if why else process.returncode, _clean_output(raw), why)


def _wait(process: subprocess.Popen, sink, timeout: float) -> str:
    """Wait at most `timeout` seconds for the check to exit, looking at the size
    of its output as it runs: "" when it exited, else the line saying why it was
    ended (BUDGET_LINE or OUTPUT_LINE)."""
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        try:
            process.wait(timeout=max(0.0, min(OUTPUT_POLL_SECONDS, remaining)))
            return ""
        except subprocess.TimeoutExpired:
            pass
        if os.fstat(sink.fileno()).st_size > MAX_WRITTEN_BYTES:
            return OUTPUT_LINE
        if remaining <= OUTPUT_POLL_SECONDS:
            return BUDGET_LINE


def load_checks(repo: Path) -> dict[str, str] | None:
    """The command per check kind in .sdlc/config.json, or None when the repo has no config.

    Raises ConfigError when the config exists but cannot be read as JSON.
    """
    path = repo / CONFIG_PATH
    if not path.is_file():
        return None
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ConfigError(str(error)) from error
    commands = config.get("commands") if isinstance(config, dict) else None
    if not isinstance(commands, dict):
        commands = {}
    found = {}
    for kind in CHECK_KINDS:
        command = commands.get(kind)
        found[kind] = command.strip() if isinstance(command, str) else ""
    return found


def _skip_reason(kind: str, command: str) -> str:
    if not command:
        return f"commands.{kind} is empty"
    if command == NO_TESTS_CMD:
        return f"commands.{kind} is the placeholder for a repo without tests"
    return ""


def _unreached(skipped: list[dict]) -> list[dict]:
    """The checks a stop or the budget kept from running."""
    return [item for item in skipped if item["reason"].startswith(NOT_REACHED)]


def _next_action(results: list[dict], skipped: list[dict]) -> str:
    """What to do first: fix the first failing check, then run any check not
    reached; "All checks passed." only when every check ran and passed."""
    actions = [_fix_first_failure(results)]
    unreached = _unreached(skipped)
    if unreached:
        names = ", ".join(f"`{item['name']}`" for item in unreached)
        why = unreached[0]["reason"].removeprefix(NOT_REACHED)
        actions.append(f"Not reached ({why}): {names}; run the checks again.")
    action = " ".join(filter(None, actions))
    if action:
        return action
    return "All checks passed." if results else NOTHING_RAN_NEXT_ACTION


def _fix_first_failure(results: list[dict]) -> str:
    for result in results:
        if result["passed"]:
            continue
        command, code = result["command"], result["exit_code"]
        if code is None and result["tail"][-1] == OUTPUT_LINE:
            return (
                f"Make `{command}` print less: its output went over {MAX_WRITTEN_BYTES >> 20} MiB."
            )
        if code is None:
            return f"`{command}` did not finish ({result['tail'][-1]}); run it again."
        if code == NOT_FOUND_EXIT:
            return f"Install what `{command}` calls: the shell could not find it."
        if code == NOT_EXECUTABLE_EXIT:
            return f"Make `{command}` executable: the shell could not run it."
        if result["failures"] is not None:
            return f"Fix the {result['failures']} failure(s) `{command}` reports."
        return f"Fix what `{command}` reports (exit {code})."
    return ""


def _report(results: list[dict], skipped: list[dict], reason: str, next_action: str) -> dict:
    ran = bool(results)
    return {
        "ok": ran and not _unreached(skipped) and all(result["passed"] for result in results),
        "mode": MODE,
        "ran": ran,
        "reason": "" if ran else reason,
        "results": results,
        "skipped": skipped,
        "next_action": next_action or _next_action(results, skipped),
    }


def _configured(repo: Path) -> tuple[list[tuple[str, str]], list[dict]] | None:
    """The config's checks as (name, command) pairs and the ones it skips; None without a config."""
    configured = load_checks(repo)
    if configured is None:
        return None
    checks, skipped = [], []
    for kind, command in configured.items():
        reason = _skip_reason(kind, command)
        if reason:
            skipped.append({"name": kind, "reason": reason})
        else:
            checks.append((kind, command))
    return checks, skipped


def run(repo: Path, commands: list[str] | None, timeout: float) -> dict:
    """Run each check once inside one budget of `timeout` seconds: the given
    commands, each named after itself, or with None the config's, each named
    after its kind."""
    if commands is None:
        found = _configured(repo)
        if found is None:
            return _report([], [], NO_CONFIG_REASON, NO_CONFIG_NEXT_ACTION)
        checks, skipped = found
        if not checks:
            return _report([], skipped, NOTHING_SET_REASON, NOTHING_SET_NEXT_ACTION)
    else:
        checks, skipped = [(command, command) for command in dict.fromkeys(commands)], []
    deadline = time.monotonic() + timeout
    results: list[dict] = []
    with _adopting_orphans():
        for index, (name, command) in enumerate(checks):
            remaining = deadline - time.monotonic()
            if STOP.requested or remaining <= 0:
                reason = NOT_REACHED_STOPPED if STOP.requested else NOT_REACHED_BUDGET
                skipped += [{"name": rest, "reason": reason} for rest, _ in checks[index:]]
                break
            results.append({"name": name, **run_command(repo, command, remaining)})
    # Only a stop before the first check leaves no results to report.
    return _report(results, skipped, NOT_REACHED_STOPPED, "")


def _usage_error(error: str, next_action: str = USAGE) -> int:
    print(json.dumps({"ok": False, "mode": MODE, "error": error, "next_action": next_action}))
    return USAGE_EXIT


def _parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(prog="checks.py", add_help=False, allow_abbrev=False)
    commands = parser.add_subparsers(dest="mode", required=True)
    run_parser = commands.add_parser("run", add_help=False, allow_abbrev=False)
    run_parser.add_argument("repo")
    run_parser.add_argument("--command", action="append", dest="commands")
    run_parser.add_argument("--timeout", type=float, default=DEFAULT_RUN_TIMEOUT_SECONDS)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    except ArgumentError as error:
        return _usage_error(str(error))
    if not (math.isfinite(args.timeout) and args.timeout > 0):
        return _usage_error("--timeout must be a positive number of seconds")
    commands = None
    if args.commands is not None:
        commands = [command.strip() for command in args.commands]
        if not all(commands):
            return _usage_error("--command needs a command, as in --command=<command>")
    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        return _usage_error(f"not a directory: {repo}")
    for number in STOP_SIGNALS:
        # A signal the caller ignored on purpose (nohup, a shell's background job)
        # stays ignored.
        if signal.getsignal(number) is not signal.SIG_IGN:
            signal.signal(number, STOP)
    try:
        result = run(repo, commands, args.timeout)
    except ConfigError as error:
        return _usage_error(
            f"cannot read {CONFIG_PATH}: {error}",
            f"Fix {CONFIG_PATH}, or pass --command=<command>, and try again.",
        )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
