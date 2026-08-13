#!/usr/bin/env python3
"""Health check for a shipshape-managed repo (ADR 0002: stdlib only).

Emits one JSON scorecard on stdout: sections in priority order (security
first), each check PASS / WARN / FAIL with a plain-detail string, plus a
single suggested next_action. Skills translate this for the user; this
script never prints prose.

Usage:
    python3 doctor.py <repo-path>

The workflow-permissions and test-retry audits are deliberately naive text
checks. Permissions looks for a `permissions:` line anywhere in a workflow;
test retries looks for a short list of known action names and shell markers.
They flag common cases without claiming to parse YAML or shell.
"""

import json
import re
import sys
from pathlib import Path

from render import kit_version, load_json, load_state, sha256_text

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
RETRY_ACTIONS = ("nick-fields/retry", "nick-invision/retry", "wandalen/wretry.action")
SHELL_LOOP_SCAN_LIMIT = 1000  # Bound naive matches to a nearby shell loop body.
UNUSED_SETTING_MESSAGE = (
    "Remove features.project_board; this setting has never changed what shipshape installs."
)
TEST_RETRY_NEXT_ACTION = (
    "Remove the retry and fix or quarantine the flaky test so one green run means the test "
    "passed."
)


def check(name: str, status: str, detail: str, next_action: str = "") -> dict:
    return {"name": name, "status": status, "detail": detail, "next_action": next_action}


def find_test_retry_markers(text: str, test_command: str) -> list[str]:
    lowered = text.casefold()
    markers = [action for action in RETRY_ACTIONS if action in lowered]
    if not test_command:
        return markers

    escaped_command = re.escape(test_command)
    for loop in ("until", "for"):
        if re.search(
            rf"\b{loop}\b[\s\S]{{0,{SHELL_LOOP_SCAN_LIMIT}}}?{escaped_command}"
            rf"[\s\S]{{0,{SHELL_LOOP_SCAN_LIMIT}}}?\bdone\b",
            text,
            flags=re.IGNORECASE,
        ):
            markers.append(f"{loop} loop around the configured test command")

    retry_flag = re.compile(r"--(?:retries|retry|reruns)\b", flags=re.IGNORECASE)
    for line in text.splitlines():
        if test_command.casefold() in line.casefold() and retry_flag.search(line):
            markers.append("retry flag on the configured test command")
            break
    return markers


def unused_settings_check(config: dict) -> dict:
    if "project_board" in config.get("features", {}):
        return check("unused settings", WARN, UNUSED_SETTING_MESSAGE, UNUSED_SETTING_MESSAGE)
    return check("unused settings", PASS, "no unused settings")


def test_retries_check(repo: Path, config: dict) -> dict:
    workflows_dir = repo / ".github" / "workflows"
    test_command = str(config.get("commands", {}).get("test", "")).strip()
    offenders = []
    if workflows_dir.is_dir():
        for workflow in sorted(workflows_dir.glob("*.yml")):
            text = workflow.read_text(encoding="utf-8", errors="ignore")
            if find_test_retry_markers(text, test_command):
                offenders.append(workflow.name)
    if offenders:
        return check(
            "test retries",
            WARN,
            f"possible test retry markers in: {', '.join(offenders)}",
            TEST_RETRY_NEXT_ACTION,
        )
    return check("test retries", PASS, "no test retries found")


def security_checks(repo: Path, config: dict) -> list[dict]:
    checks = []
    features = config.get("features", {})

    guard = repo / ".sdlc" / "hooks" / "secret-guard.sh"
    if not features.get("secret_guard", True):
        checks.append(check("secret guard", WARN, "turned off in .sdlc/config.json"))
    elif not guard.is_file():
        checks.append(
            check(
                "secret guard",
                FAIL,
                "the commit-time secret scanner is missing",
                "re-run /shipshape-init to restore it",
            )
        )
    else:
        checks.append(check("secret guard", PASS, "secret scanner present"))

    hook = repo / ".git" / "hooks" / "pre-commit"
    if guard.is_file() and not hook.exists():
        checks.append(
            check(
                "secret guard installed",
                FAIL,
                "the scanner exists but is not active for this clone",
                "run: bash .sdlc/hooks/install.sh",
            )
        )
    elif guard.is_file():
        checks.append(check("secret guard installed", PASS, "runs on every commit here"))

    codeql = repo / ".github" / "workflows" / "codeql.yml"
    if codeql.is_file():
        checks.append(check("code scanning (CodeQL)", PASS, "workflow present"))
    elif not features.get("codeql", True):
        checks.append(check("code scanning (CodeQL)", WARN, "turned off in .sdlc/config.json"))
    else:
        checks.append(
            check(
                "code scanning (CodeQL)",
                WARN,
                "no CodeQL workflow (unsupported language, or setup incomplete)",
            )
        )

    if (repo / ".github" / "dependabot.yml").is_file():
        checks.append(check("dependency watch (Dependabot)", PASS, "configured"))
    else:
        checks.append(
            check(
                "dependency watch (Dependabot)",
                WARN,
                "no dependabot.yml — vulnerable libraries won't be flagged",
            )
        )

    workflows_dir = repo / ".github" / "workflows"
    offenders = []
    if workflows_dir.is_dir():
        for wf in sorted(workflows_dir.glob("*.yml")):
            if "permissions:" not in wf.read_text(encoding="utf-8", errors="ignore"):
                offenders.append(wf.name)
    if offenders:
        checks.append(
            check(
                "workflow permissions",
                WARN,
                f"workflows without an explicit permissions block: {', '.join(offenders)}",
                "add `permissions: contents: read` at the top of each",
            )
        )
    else:
        checks.append(check("workflow permissions", PASS, "all workflows declare permissions"))
    return checks


def setup_checks(repo: Path, config: dict, state: dict) -> list[dict]:
    checks = [unused_settings_check(config)]

    if (repo / ".github" / "workflows" / "ci.yml").is_file():
        checks.append(check("automated tests (CI)", PASS, "CI workflow present"))
    else:
        checks.append(check("automated tests (CI)", WARN, "no CI workflow found"))

    checks.append(test_retries_check(repo, config))

    drifted, missing = [], []
    for dest, record in state.get("files", {}).items():
        path = repo / dest
        if not path.is_file():
            missing.append(dest)
        elif sha256_text(path.read_text(encoding="utf-8")) != record["sha256"]:
            drifted.append(dest)
    if missing:
        checks.append(
            check(
                "managed files",
                WARN,
                f"shipshape-managed files were deleted: {', '.join(missing)}",
                "re-run /shipshape-init to restore them, or /shipshape-customize to drop them",
            )
        )
    elif drifted:
        checks.append(
            check(
                "managed files",
                PASS,
                f"present; edited by you (which is fine): {', '.join(drifted)}",
            )
        )
    else:
        checks.append(check("managed files", PASS, "all present and unmodified"))

    current = kit_version()
    written_with = state.get("kit_version", "")
    if written_with and written_with != current:
        checks.append(
            check(
                "kit version",
                WARN,
                f"set up with shipshape v{written_with}, installed is v{current}",
                "re-run /shipshape-init to upgrade the managed files",
            )
        )
    else:
        checks.append(check("kit version", PASS, f"v{current}"))
    return checks


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"ok": False, "error": "usage: doctor.py <repo-path>"}))
        return 2
    repo = Path(sys.argv[1]).resolve()
    config_path = repo / ".sdlc" / "config.json"
    if not config_path.is_file():
        print(
            json.dumps(
                {
                    "ok": False,
                    "set_up": False,
                    "error": "this repo has no shipshape setup yet",
                    "next_action": "run /shipshape-init",
                }
            )
        )
        return 1
    config = load_json(config_path)
    state = load_state(repo)

    sections = [
        {"name": "security", "checks": security_checks(repo, config)},
        {"name": "setup", "checks": setup_checks(repo, config, state)},
    ]
    all_checks = [c for section in sections for c in section["checks"]]
    counts = {s: sum(1 for c in all_checks if c["status"] == s) for s in (PASS, WARN, FAIL)}
    first_fail = next((c for c in all_checks if c["status"] == FAIL), None)
    first_warn = next((c for c in all_checks if c["status"] == WARN), None)
    if first_fail:
        next_action = first_fail["next_action"] or f"fix: {first_fail['name']}"
    elif first_warn:
        next_action = first_warn["next_action"] or f"consider: {first_warn['detail']}"
    else:
        next_action = "nothing — everything is shipshape"

    print(
        json.dumps(
            {
                "ok": counts[FAIL] == 0,
                "set_up": True,
                "counts": counts,
                "sections": sections,
                "next_action": next_action,
            },
            indent=2,
        )
    )
    return 0 if counts[FAIL] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
