"""Check detection: detect.py proposes one command per kind of check.

The contract under test: the "checks" key is a list with one entry per kind
found, in the order test, lint, build, typecheck, format, each naming the
kind, the command, whether it is proven, the source that revealed it, a
confidence and a language. Only a high-confidence language proposes checks;
the primary language wins a kind two languages could fill; the test check
uses the package-manager command init-config stores; a package.json script
that rewrites files or never exits is never proposed, whether the flag is in
its own shell words, a command string it passes on, a pre or post script or a
script it names or matches by glob, and neither is one that runs a shell,
expands a variable, runs other packages' scripts or names a chain of scripts
deeper than the screen follows. A plain scan never runs a command, so every
check is unproven; --prove runs each command once inside one budget, with no
input and offline under --no-network, kills and reaps what it left running,
answers when stopped by SIGTERM, SIGINT or SIGHUP, and marks the ones that
ran, whether they passed or not.
"""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from conftest import FIXTURES, SCRIPTS, left_unreaped, linux_only, run_script

from scripts import detect

CHECK_KINDS = ("test", "lint", "build", "typecheck", "format")
CHECK_KEYS = {"name", "command", "proven", "source", "confidence", "language"}
CONFIDENCES = {"high", "medium", "low"}
GOFMT = 'out=$(gofmt -l .) && ! echo "$out" | grep .'
SETUP_PY = "from setuptools import setup\n\nsetup()\n"
CARGO_TOML = '[package]\nname = "example"\nversion = "0.1.0"\nedition = "2021"\n'
# A python repo whose test, lint, typecheck and format checks call pytest, ruff and mypy.
PYTHON_TOOLS_REPO = {
    "pyproject.toml": '[project]\nname = "example"\n\n[tool.ruff]\n\n[tool.mypy]\n',
    "tests/test_example.py": "def test_example():\n    assert True\n",
}
# A stand-in for a tool that starts a child, records its pid and waits for it.
SLOW_TOOL = "sleep 60 & echo $! > child.pid; wait"
# A stand-in for a tool that exits at once and leaves a child running.
LEAVES_A_CHILD = "sleep 60 & echo $! > child.pid"
# A stand-in for a tool that records the offline settings it was given.
RECORDS_OFFLINE_ENV = (
    'printf \'%s|%s|%s\\n\' "$CARGO_NET_OFFLINE" "$GOPROXY" "$npm_config_offline" > env.log'
)
OFFLINE_VARIABLES = ("CARGO_NET_OFFLINE", "GOPROXY", "npm_config_offline")


def write_repo(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root


def fake_tools(tmp_path: Path, monkeypatch, tools: dict[str, str]) -> None:
    """Shell scripts standing in for the tools the proposed commands call, first on PATH."""
    bin_dir = tmp_path / "fake-bin"
    bin_dir.mkdir()
    for name, body in tools.items():
        tool = bin_dir / name
        tool.write_text(f"#!/bin/sh\n{body}\n")
        tool.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")


def assert_gone(pid: int) -> None:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    os.kill(pid, signal.SIGKILL)
    pytest.fail("a process the proposed command started outlived the prove step")


def scan(repo: Path, *flags: str) -> dict:
    code, payload = run_script("detect.py", repo, "--no-network", *flags)
    assert code == 0, payload
    return payload


def table(payload: dict) -> dict:
    """The proposed checks keyed by kind, each without its name."""
    return {
        entry["name"]: {key: value for key, value in entry.items() if key != "name"}
        for entry in payload["checks"]
    }


def check(command: str, source: str, confidence: str, language: str) -> dict:
    return {
        "command": command,
        "proven": False,
        "source": source,
        "confidence": confidence,
        "language": language,
    }


def test_python_tool_tables_propose_lint_format_and_typecheck(tmp_path):
    repo = write_repo(
        tmp_path,
        {
            "pyproject.toml": (
                '[project]\nname = "example"\n\n'
                "[tool.ruff]\nline-length = 100\n\n"
                "[tool.mypy]\nstrict = true\n"
            ),
            "tests/test_example.py": "def test_example():\n    assert True\n",
        },
    )

    payload = scan(repo)

    assert [entry["name"] for entry in payload["checks"]] == ["test", "lint", "typecheck", "format"]
    assert table(payload) == {
        "test": check("pytest", "tests/", "medium", "python"),
        "lint": check("ruff check .", "pyproject.toml:[tool.ruff]", "high", "python"),
        "typecheck": check("mypy .", "pyproject.toml:[tool.mypy]", "high", "python"),
        "format": check("ruff format --check .", "pyproject.toml:[tool.ruff]", "high", "python"),
    }


def test_a_tool_subtable_counts_as_its_configuration(tmp_path):
    repo = write_repo(
        tmp_path,
        {"pyproject.toml": '[project]\nname = "example"\n\n[tool.ruff.lint]\nselect = ["E"]\n'},
    )

    lint = table(scan(repo))["lint"]

    assert lint == check("ruff check .", "pyproject.toml:[tool.ruff]", "high", "python")


def test_a_table_named_only_in_a_comment_proposes_nothing(tmp_path):
    repo = write_repo(
        tmp_path,
        {"pyproject.toml": '[project]\nname = "example"\n# add [tool.mypy] later\n'},
    )

    assert "typecheck" not in table(scan(repo))


def test_a_table_sharing_only_a_name_prefix_with_a_tool_proposes_nothing(tmp_path):
    repo = write_repo(
        tmp_path,
        {"pyproject.toml": "[tool.mypyc]\nopt_level = 3\n\n[tool.ruffian]\nstrict = true\n"},
    )

    assert scan(repo)["checks"] == []


def test_black_is_the_formatter_when_black_and_ruff_are_both_configured(tmp_path):
    repo = write_repo(
        tmp_path,
        {"pyproject.toml": "[tool.ruff]\nline-length = 88\n\n[tool.black]\nline-length = 88\n"},
    )

    checks = table(scan(repo))

    assert checks["format"] == check(
        "black --check .", "pyproject.toml:[tool.black]", "high", "python"
    )
    assert checks["lint"]["command"] == "ruff check ."


@pytest.mark.parametrize(
    ("filename", "kind", "command"),
    [
        ("ruff.toml", "lint", "ruff check ."),
        (".ruff.toml", "format", "ruff format --check ."),
        (".flake8", "lint", "flake8 ."),
        ("mypy.ini", "typecheck", "mypy ."),
        ("pyrightconfig.json", "typecheck", "pyright"),
    ],
)
def test_a_python_tool_config_file_proposes_its_check(tmp_path, filename, kind, command):
    repo = write_repo(tmp_path, {"setup.py": SETUP_PY, filename: "\n"})

    assert table(scan(repo))[kind] == check(command, filename, "high", "python")


@pytest.mark.parametrize(
    ("lockfile", "runner"),
    [
        ("pnpm-lock.yaml", "pnpm"),
        ("yarn.lock", "yarn"),
        ("bun.lockb", "bun"),
        (None, "npm"),
    ],
)
def test_node_scripts_propose_checks_through_the_projects_runner(tmp_path, lockfile, runner):
    package = {
        "name": "example",
        "scripts": {
            "test": "vitest run",
            "lint": "eslint .",
            "build": "tsc -p .",
            "typecheck": "tsc --noEmit",
            "format": "prettier --write .",
            "format:check": "prettier --check .",
        },
        "devDependencies": {"vitest": "^2.0.0"},
    }
    files = {"package.json": json.dumps(package)}
    if lockfile:
        files[lockfile] = "\n"
    repo = write_repo(tmp_path, files)

    payload = scan(repo)

    assert table(payload) == {
        "test": check(
            "bun run test" if runner == "bun" else f"{runner} test",
            "package.json",
            "high",
            "node",
        ),
        "lint": check(f"{runner} run lint", "package.json:scripts.lint", "high", "node"),
        "build": check(f"{runner} run build", "package.json:scripts.build", "high", "node"),
        "typecheck": check(
            f"{runner} run typecheck", "package.json:scripts.typecheck", "high", "node"
        ),
        "format": check(
            f"{runner} run format:check", "package.json:scripts.format:check", "high", "node"
        ),
    }
    assert payload["test_command_guess"] == "npm test"


def test_node_scripts_that_delegate_to_unsafe_scripts_are_never_proposed(tmp_path):
    package = {
        "name": "example",
        "scripts": {
            "lint": "npm run lint:middle",
            "lint:middle": "pnpm run lint:cycle",
            "lint:cycle": "yarn run lint:middle && npm run lint:fix",
            "lint:fix": "eslint . --fix",
            "build": "npm run build:part",
            "build:part": "tsc -p .",
        },
    }
    repo = write_repo(tmp_path, {"package.json": json.dumps(package)})

    checks = table(scan(repo))

    assert "lint" not in checks
    assert checks["build"]["command"] == "npm run build"


@pytest.mark.parametrize(
    ("lockfile", "runner"),
    [
        (None, "npm"),
        ("pnpm-lock.yaml", "pnpm"),
        ("yarn.lock", "yarn"),
        ("bun.lockb", "bun"),
    ],
)
@pytest.mark.parametrize(
    ("hook", "body"),
    [
        ("prelint", "eslint . '--fix'"),
        ("postlint", "eslint . --fix; echo done"),
        ("prelint:delegated", "eslint . --fix"),
        ("postlint:delegated", "eslint . --watch"),
    ],
)
def test_node_check_screens_lifecycle_hooks_for_selected_and_delegated_scripts(
    tmp_path, lockfile, runner, hook, body
):
    package = {
        "name": "example",
        "scripts": {
            "lint": "npm run lint:delegated",
            "lint:delegated": "eslint .",
            hook: body,
        },
    }
    files = {"package.json": json.dumps(package)}
    if lockfile:
        files[lockfile] = "\n"
    repo = write_repo(tmp_path, files)

    assert "lint" not in table(scan(repo))


@pytest.mark.parametrize(
    "script",
    ["eslint . --fix; echo done", "eslint . '--fix'", "eslint . --fix=src"],
)
def test_node_script_flag_screening_respects_shell_tokens(tmp_path, script):
    repo = write_repo(
        tmp_path,
        {"package.json": json.dumps({"name": "example", "scripts": {"lint": script}})},
    )

    assert "lint" not in table(scan(repo))


def node_checks(tmp_path: Path, scripts: dict[str, str]) -> dict[str, dict]:
    package = {"name": "example", "scripts": scripts}
    return table(scan(write_repo(tmp_path, {"package.json": json.dumps(package)})))


@pytest.mark.parametrize(
    "script",
    [
        "eslint . --fix>lint.log",
        "(eslint . --fix)",
        "eslint . --fix&&echo done",
        "echo `eslint . --fix`",
        "echo $(eslint . --fix)",
    ],
)
def test_shell_punctuation_cannot_hide_a_rejected_flag(tmp_path, script):
    assert "lint" not in node_checks(tmp_path, {"lint": script})


@pytest.mark.parametrize(
    "script",
    [
        "eslint . --fi\\\nx",
        'eslint . "--fi\\\nx"',
        "eslint . $(cat .lint-flags)",
        "eslint . `cat .lint-flags`",
        "eslint . --fi?",
        "eslint . -[w]",
        "eslint . --{fix,}",
        "eslint . -{w..w}",
        "eslint . {a,b}{a,b}{a,b}{a,b}{a,b}{a,b}{a,b}{a,b}{a,b}",
        "run-s lint:{js,fix}",
    ],
)
def test_a_shell_expansion_cannot_hide_a_rejected_flag(tmp_path, script):
    """The shell joins `--fi`, a backslash-newline and `x` into --fix, expands
    `--{fix,}` into --fix and --, puts a command's output in place of `$(...)`,
    and turns `--fi?` into a file named --fix; shlex does none of that."""
    scripts = {"lint": script, "lint:js": "eslint .", "lint:fix": "eslint . --fix"}

    assert "lint" not in node_checks(tmp_path, scripts)


@pytest.mark.parametrize(
    "script",
    ["prettier --check 'src/**/*.{ts,tsx,json}'", "prettier --check --ignore-path=**/.gitignore ."],
)
def test_a_pattern_that_cannot_make_a_rejected_flag_is_still_proposed(tmp_path, script):
    checks = node_checks(tmp_path, {"format:check": script})

    assert checks["format"] == check(
        "npm run format:check", "package.json:scripts.format:check", "high", "node"
    )


@pytest.mark.parametrize(
    "script",
    [
        "sh -c 'eslint . --fix'",
        "bash -c 'eslint .'",
        "/bin/sh ./lint.sh",
        "eval eslint .",
        "npx -c 'eslint . --fix'",
        "concurrently 'eslint . --fix' 'tsc'",
        "node -e \"require('child_process').execSync('eslint . --fix')\"",
        "eslint . $LINT_FLAGS",
    ],
)
def test_a_script_running_shell_code_the_screen_cannot_read_is_never_proposed(tmp_path, script):
    assert "lint" not in node_checks(tmp_path, {"lint": script})


@pytest.mark.parametrize(
    "script",
    [
        "run-s lint:fix",
        "npm-run-all 'lint:*'",
        "concurrently 'npm run lint:fix'",
        "run-s 'lint:fi?'",
        "run-s 'lint:fi[x]'",
        "run-s 'lint:fi[^y]'",
        "run-s 'lint:fi\\x'",
        "run-s 'lint:@(fix)'",
        "run-s 'lint:fi[[:alpha:]]'",
        "concurrently npm:lint:fix",
        "concurrently 'npm:lint:*'",
    ],
)
def test_a_script_named_through_any_runner_is_screened(tmp_path, script):
    """npm-run-all reads a name as a minimatch glob, with ?, [...], a backslash
    escape and extglob groups, and concurrently reads npm:<script>."""
    assert "lint" not in node_checks(tmp_path, {"lint": script, "lint:fix": "eslint . --fix"})


@pytest.mark.parametrize(
    "script",
    [
        "npm run lint --workspaces",
        "npm run lint --workspace=pkg",
        "npm run lint -ws",
        "pnpm -r run lint",
        "pnpm -C sub lint",
        "pnpm --filter app lint",
        "npm --prefix sub run lint",
        "yarn workspaces foreach run lint",
        "npm_config_workspaces=true npm run lint",
    ],
)
def test_a_script_running_other_packages_scripts_is_never_proposed(tmp_path, script):
    """The screen reads only the root package.json, so a script that runs the
    scripts of other packages cannot be called safe."""
    assert "lint" not in node_checks(tmp_path, {"lint": script})


def test_mochas_require_flag_is_not_read_as_a_recursive_run(tmp_path):
    package = {
        "name": "example",
        "scripts": {"test": "mocha -r ts-node/register"},
        "devDependencies": {"mocha": "^10.0.0"},
    }
    repo = write_repo(tmp_path, {"package.json": json.dumps(package)})

    payload = scan(repo)

    assert payload["test_command_guess"] == "npm test"
    assert table(payload)["test"] == check("npm test", "package.json", "high", "node")


@pytest.mark.parametrize(
    ("depth", "proposed"),
    [(detect.MAX_SCRIPT_DEPTH, True), (detect.MAX_SCRIPT_DEPTH + 1, False), (1000, False)],
)
def test_a_script_chain_deeper_than_the_screen_follows_is_not_proposed(tmp_path, depth, proposed):
    """A chain of scripts each running the next once ran the scan out of stack,
    so it printed a traceback and no JSON."""
    scripts = {f"lint:{level}": f"npm run lint:{level + 1}" for level in range(1, depth)}
    scripts.update({"lint": "npm run lint:1", f"lint:{depth}": "eslint .", "build": "tsc -p ."})

    checks = node_checks(tmp_path, scripts)

    assert ("lint" in checks) is proposed
    assert checks["build"]["command"] == "npm run build"


@pytest.mark.parametrize(
    "script",
    [
        "eslint . && tsc --noEmit",
        "eslint -c .eslintrc.json . 2>&1",
        "concurrently 'eslint .' 'tsc --noEmit'",
        "run-s lint:js",
        "run-s 'lint:j?'",
        "concurrently npm:lint:js",
    ],
)
def test_a_safe_script_using_shell_syntax_is_still_proposed(tmp_path, script):
    checks = node_checks(tmp_path, {"lint": script, "lint:js": "eslint ."})

    assert checks["lint"] == check("npm run lint", "package.json:scripts.lint", "high", "node")


def test_safe_node_script_cycle_does_not_recurse_forever(tmp_path):
    package = {
        "name": "example",
        "scripts": {
            "lint": "npm run lint:shared",
            "lint:shared": "pnpm run lint",
        },
    }
    repo = write_repo(tmp_path, {"package.json": json.dumps(package)})

    assert table(scan(repo))["lint"] == check(
        "npm run lint", "package.json:scripts.lint", "high", "node"
    )


@pytest.mark.parametrize(
    ("runner", "watcher"),
    [
        ("vitest", "vitest --watch"),
        ("vitest", "vitest watch"),
        ("vitest", "vitest dev"),
        ("jest", "jest --watchAll"),
        ("jest", "jest --watch-all"),
    ],
)
def test_an_unsafe_node_test_script_is_not_guessed_or_proposed(tmp_path, runner, watcher):
    package = {
        "name": "example",
        "scripts": {"test": "npm run test:watch", "test:watch": watcher},
        "devDependencies": {runner: "^2.0.0"},
    }
    repo = write_repo(tmp_path, {"package.json": json.dumps(package)})

    payload = scan(repo)

    assert payload["test_command_guess"] == ""
    assert "test" not in table(payload)


def test_an_unsafe_node_test_script_does_not_hide_a_go_test_check(tmp_path):
    repo = write_repo(
        tmp_path,
        {
            "go.mod": "module example.com/app\n\ngo 1.22\n",
            "package.json": json.dumps(
                {
                    "name": "example",
                    "scripts": {"test": "vitest --watch"},
                    "devDependencies": {"vitest": "^2.0.0"},
                }
            ),
        },
    )

    payload = scan(repo)

    assert payload["test_command_guess"] == "go test ./..."
    assert table(payload)["test"] == check("go test ./...", "go.mod", "medium", "go")


def test_an_unsafe_node_test_script_lets_another_languages_runner_be_guessed(tmp_path):
    """Node sorts before Python, so the Node runner was the guess and nothing
    replaced it once its test script was dropped."""
    package = {
        "name": "example",
        "scripts": {"test": "vitest --watch"},
        "devDependencies": {"vitest": "^2.0.0"},
    }
    repo = write_repo(
        tmp_path,
        {
            "package.json": json.dumps(package),
            "pyproject.toml": '[project]\nname = "example"\n',
            "tests/test_example.py": "def test_example():\n    assert True\n",
        },
    )

    payload = scan(repo)

    assert payload["test_runners"] == ["pytest", "vitest"]
    assert payload["test_command_guess"] == "pytest"
    assert table(payload)["test"] == check("pytest", "tests/", "medium", "python")


@pytest.mark.parametrize(
    "lint_script", ["eslint . --fix", "biome check --apply .", "jest --watchAll"]
)
def test_node_scripts_that_rewrite_files_or_watch_are_never_proposed(tmp_path, lint_script):
    package = {
        "name": "example",
        "scripts": {
            "lint": lint_script,
            "format": "prettier --write .",
            "build": "tsc --watch",
            "typecheck": "tsc --noEmit -w",
        },
    }
    repo = write_repo(
        tmp_path,
        {
            "package.json": json.dumps(package),
            "eslint.config.js": "export default [];\n",
            ".prettierrc": "{}\n",
            "tsconfig.json": "{}\n",
        },
    )

    assert table(scan(repo)) == {
        "lint": check("node_modules/.bin/eslint .", "eslint.config.js", "high", "node"),
        "typecheck": check("node_modules/.bin/tsc --noEmit", "tsconfig.json", "high", "node"),
        "format": check("node_modules/.bin/prettier --check .", ".prettierrc", "high", "node"),
    }


def test_a_check_only_format_name_wins_over_a_check_only_format_script(tmp_path):
    package = {
        "name": "example",
        "scripts": {"format": "prettier --check .", "format:check": "prettier --check src"},
    }
    repo = write_repo(tmp_path, {"package.json": json.dumps(package)})

    assert table(scan(repo))["format"] == check(
        "npm run format:check", "package.json:scripts.format:check", "high", "node"
    )


def test_a_node_test_script_with_no_known_runner_proposes_no_test_check(tmp_path):
    package = {"name": "example", "scripts": {"test": "node --test", "lint": "eslint ."}}
    repo = write_repo(tmp_path, {"package.json": json.dumps(package)})

    payload = scan(repo)

    assert payload["test_command_guess"] == ""
    assert table(payload) == {
        "lint": check("npm run lint", "package.json:scripts.lint", "high", "node")
    }


def test_a_package_json_that_does_not_parse_still_scans(tmp_path):
    repo = write_repo(tmp_path, {"package.json": "{ not json", "tsconfig.json": "{}\n"})

    payload = scan(repo)

    assert payload["languages"][0]["name"] == "node"
    assert table(payload) == {
        "typecheck": check("node_modules/.bin/tsc --noEmit", "tsconfig.json", "high", "node")
    }


def test_go_proposes_its_toolchain_checks_and_a_configured_linter(tmp_path):
    repo = write_repo(
        tmp_path,
        {"go.mod": "module example.com/app\n\ngo 1.22\n", ".golangci.yml": "run:\n  timeout: 5m\n"},
    )

    assert table(scan(repo)) == {
        "test": check("go test ./...", "go.mod", "medium", "go"),
        "lint": check("golangci-lint run", ".golangci.yml", "high", "go"),
        "build": check("go build ./...", "go.mod", "medium", "go"),
        "format": check(GOFMT, "go.mod", "medium", "go"),
    }


def test_rust_proposes_cargo_checks_and_honours_a_rustfmt_config(tmp_path):
    repo = write_repo(tmp_path, {"Cargo.toml": CARGO_TOML, "rustfmt.toml": "max_width = 100\n"})

    assert table(scan(repo)) == {
        "test": check("cargo test", "Cargo.toml", "medium", "rust"),
        "lint": check("cargo clippy -- -D warnings", "Cargo.toml", "medium", "rust"),
        "build": check("cargo build", "Cargo.toml", "medium", "rust"),
        "typecheck": check("cargo check", "Cargo.toml", "medium", "rust"),
        "format": check("cargo fmt --check", "rustfmt.toml", "high", "rust"),
    }


@pytest.mark.parametrize(
    ("config", "extension"),
    [(".flake8", ".py"), ("tsconfig.json", ".ts")],
)
def test_a_tool_config_without_a_manifest_proposes_no_checks(tmp_path, config, extension):
    files = {config: "{}\n", **{f"src/{name}{extension}": "\n" for name in ("a", "b", "c")}}
    repo = write_repo(tmp_path, files)

    payload = scan(repo)

    assert [entry["confidence"] for entry in payload["languages"]] == ["medium"]
    assert payload["checks"] == []


def test_a_language_below_high_confidence_proposes_no_checks(tmp_path):
    repo = write_repo(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "example"\n',
            "tools/a.go": "package tools\n",
            "tools/b.go": "package tools\n",
            "tools/c.go": "package tools\n",
        },
    )

    payload = scan(repo)

    confidence = {entry["name"]: entry["confidence"] for entry in payload["languages"]}
    assert confidence == {"python": "high", "go": "medium"}
    assert payload["checks"] == []


def test_the_primary_language_wins_a_kind_both_languages_could_fill(tmp_path):
    package = {"name": "example", "scripts": {"lint": "eslint ."}}
    repo = write_repo(
        tmp_path,
        {"package.json": json.dumps(package), "pyproject.toml": "[tool.ruff]\n\n[tool.mypy]\n"},
    )

    checks = table(scan(repo))

    assert checks["lint"] == check("npm run lint", "package.json:scripts.lint", "high", "node")
    assert checks["typecheck"] == check("mypy .", "pyproject.toml:[tool.mypy]", "high", "python")
    assert checks["format"]["language"] == "python"


FIXTURE_COMMANDS = {
    "repo-empty": {},
    "repo-go": {
        "test": "go test ./...",
        "lint": "go vet ./...",
        "build": "go build ./...",
        "format": GOFMT,
    },
    "repo-mixed": {"test": "npm test"},
    "repo-node": {"test": "npm test"},
    "repo-python": {"test": "pytest"},
    "repo-rust": {
        "test": "cargo test",
        "lint": "cargo clippy -- -D warnings",
        "build": "cargo build",
        "typecheck": "cargo check",
        "format": "cargo fmt --check",
    },
}


@pytest.mark.parametrize("fixture", sorted(FIXTURE_COMMANDS))
def test_every_fixture_reports_the_checks_its_ecosystem_has(fixture):
    payload = scan(FIXTURES / fixture)

    checks = payload["checks"]
    assert [entry["name"] for entry in checks] == [
        kind for kind in CHECK_KINDS if kind in FIXTURE_COMMANDS[fixture]
    ]
    for entry in checks:
        assert set(entry) == CHECK_KEYS
        assert entry["proven"] is False
        assert entry["confidence"] in CONFIDENCES
    commands = {entry["name"]: entry["command"] for entry in checks}
    assert commands == FIXTURE_COMMANDS[fixture]
    assert commands.get("test", "") == payload["test_command_guess"]


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        ("repo-python", check("pytest", "pyproject.toml", "high", "python")),
        ("repo-node", check("npm test", "package.json", "high", "node")),
        ("repo-go", check("go test ./...", "go.mod", "medium", "go")),
    ],
)
def test_the_test_check_names_where_its_runner_was_found(fixture, expected):
    assert table(scan(FIXTURES / fixture))["test"] == expected


def test_a_scan_without_prove_runs_no_command(tmp_path, monkeypatch):
    repo = write_repo(tmp_path / "repo", PYTHON_TOOLS_REPO)
    ran = "echo ran >> ran.log"
    fake_tools(tmp_path, monkeypatch, {"pytest": ran, "ruff": ran, "mypy": ran})

    payload = scan(repo)

    assert [entry["proven"] for entry in payload["checks"]] == [False, False, False, False]
    assert not (repo / "ran.log").exists()


@pytest.mark.parametrize("cannot_run", [126, 127])
def test_prove_marks_each_command_that_ran_whether_it_passed_or_failed(
    tmp_path, monkeypatch, cannot_run
):
    repo = write_repo(tmp_path / "repo", PYTHON_TOOLS_REPO)
    fake_tools(
        tmp_path,
        monkeypatch,
        {
            "pytest": "echo pytest >> ran.log",
            "ruff": 'echo "ruff $1" >> ran.log; exit 1',
            "mypy": f"exit {cannot_run}",
        },
    )

    payload = scan(repo, "--prove")

    proven = {entry["name"]: entry["proven"] for entry in payload["checks"]}
    assert proven == {"test": True, "lint": True, "typecheck": False, "format": True}
    assert (repo / "ran.log").read_text().splitlines() == ["pytest", "ruff check", "ruff format"]


def test_prove_stops_at_its_budget_and_kills_what_the_command_started(tmp_path, monkeypatch):
    repo = write_repo(tmp_path / "repo", PYTHON_TOOLS_REPO)
    ran = "echo ran >> ran.log"
    fake_tools(tmp_path, monkeypatch, {"pytest": SLOW_TOOL, "ruff": ran, "mypy": ran})
    started = time.monotonic()

    payload = scan(repo, "--prove", "--timeout=1")

    assert time.monotonic() - started < 10
    assert [entry["proven"] for entry in payload["checks"]] == [False, False, False, False]
    assert not (repo / "ran.log").exists()
    assert_gone(int((repo / "child.pid").read_text()))


def test_prove_kills_what_a_finished_command_left_running(tmp_path, monkeypatch):
    repo = write_repo(tmp_path / "repo", PYTHON_TOOLS_REPO)
    fake_tools(
        tmp_path, monkeypatch, {"pytest": LEAVES_A_CHILD, "ruff": "exit 0", "mypy": "exit 0"}
    )

    payload = scan(repo, "--prove", "--timeout=30")

    assert [entry["proven"] for entry in payload["checks"]] == [True, True, True, True]
    assert_gone(int((repo / "child.pid").read_text()))


@linux_only
@pytest.mark.parametrize(
    ("tool", "budget"),
    [(LEAVES_A_CHILD, "--timeout=30"), (SLOW_TOOL, "--timeout=1")],
    ids=["finished", "out of budget"],
)
def test_prove_reaps_what_it_kills_where_pid_1_reaps_nothing(tmp_path, monkeypatch, tool, budget):
    repo = write_repo(tmp_path / "repo", PYTHON_TOOLS_REPO)
    fake_tools(tmp_path, monkeypatch, {"pytest": tool, "ruff": "exit 0", "mypy": "exit 0"})
    scan_command = [sys.executable, str(SCRIPTS / "detect.py"), str(repo), "--no-network"]

    assert not left_unreaped(repo / "child.pid", *scan_command, "--prove", budget)


def test_prove_ends_the_process_tree_where_there_are_no_process_groups(monkeypatch):
    """Windows has no os.killpg; taskkill /T ends a running command's tree."""
    calls = []

    class RunningCommand:
        pid = 4321

        def poll(self):
            return None

        def kill(self):
            calls.append("kill")

    monkeypatch.delattr(detect.os, "killpg")
    monkeypatch.setattr(detect.subprocess, "run", lambda args, **kwargs: calls.append(args))

    detect._kill_group(RunningCommand())

    assert calls == [["taskkill", "/F", "/T", "/PID", "4321"], "kill"]


def test_prove_gives_a_command_no_input(tmp_path, monkeypatch):
    repo = write_repo(tmp_path / "repo", PYTHON_TOOLS_REPO)
    fake_tools(tmp_path, monkeypatch, {"pytest": "cat", "ruff": "exit 0", "mypy": "exit 0"})
    # An open pipe nobody writes to: a command that inherited it would block on read.
    reader, writer = os.pipe()
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "detect.py"),
                str(repo),
                "--no-network",
                "--prove",
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
    assert table(json.loads(proc.stdout))["test"]["proven"] is True


@pytest.mark.parametrize(
    ("flags", "recorded"),
    [(["--no-network"], "true|off|true"), ([], "||")],
)
def test_prove_without_network_runs_commands_offline(tmp_path, monkeypatch, flags, recorded):
    """The repo has no git remote, so a scan without --no-network probes nothing either."""
    repo = write_repo(tmp_path / "repo", PYTHON_TOOLS_REPO)
    fake_tools(
        tmp_path, monkeypatch, {"pytest": RECORDS_OFFLINE_ENV, "ruff": "exit 0", "mypy": "exit 0"}
    )
    for variable in OFFLINE_VARIABLES:
        monkeypatch.delenv(variable, raising=False)

    code, payload = run_script("detect.py", repo, "--prove", *flags)

    assert code == 0, payload
    assert table(payload)["test"]["proven"] is True
    assert (repo / "env.log").read_text() == f"{recorded}\n"


def start_proving(repo: Path, cwd: Path, signum: int, disposition) -> subprocess.Popen:
    """Start the scan as a caller does, with python3 -I -B, by absolute path,
    from another folder, `signum` set to `disposition` as it starts, and wait
    until the proposed test command has written child.pid."""
    proc = subprocess.Popen(
        [
            sys.executable,
            "-I",
            "-B",
            str(SCRIPTS / "detect.py"),
            str(repo),
            "--no-network",
            "--prove",
        ],
        cwd=cwd,
        stdout=subprocess.PIPE,
        text=True,
        preexec_fn=lambda: signal.signal(signum, disposition),
    )
    child_pid = repo / "child.pid"
    deadline = time.monotonic() + 10
    while not (child_pid.exists() and child_pid.read_text().strip()):
        assert time.monotonic() < deadline, "the proposed command never started"
        time.sleep(0.05)
    return proc


STOP_SIGNAL_NAMES = ("SIGTERM", "SIGINT", "SIGHUP")


@pytest.mark.parametrize("name", STOP_SIGNAL_NAMES)
def test_prove_answers_and_kills_the_running_command_when_it_is_stopped(
    tmp_path, monkeypatch, name
):
    """Ctrl-C and a closed terminal reach the scan but not the command, which
    leads a session of its own."""
    if not hasattr(signal, name):
        pytest.skip(f"no {name} here")
    signum = getattr(signal, name)
    repo = write_repo(tmp_path / "repo", PYTHON_TOOLS_REPO)
    ran = "echo ran >> ran.log"
    fake_tools(tmp_path, monkeypatch, {"pytest": SLOW_TOOL, "ruff": ran, "mypy": ran})
    proc = start_proving(repo, tmp_path, signum, signal.SIG_DFL)

    proc.send_signal(signum)
    out, _ = proc.communicate(timeout=10)

    assert proc.returncode == 0
    assert [entry["proven"] for entry in json.loads(out)["checks"]] == [False, False, False, False]
    assert not (repo / "ran.log").exists()
    assert_gone(int((repo / "child.pid").read_text()))


@pytest.mark.skipif(not hasattr(signal, "SIGHUP"), reason="no SIGHUP here")
def test_prove_keeps_ignoring_a_signal_the_caller_ignored(tmp_path, monkeypatch):
    """nohup starts the scan with SIGHUP ignored, so a hangup must not stop it."""
    repo = write_repo(tmp_path / "repo", PYTHON_TOOLS_REPO)
    ran = "echo ran >> ran.log"
    fake_tools(
        tmp_path,
        monkeypatch,
        {"pytest": "echo $$ > child.pid; sleep 1", "ruff": ran, "mypy": ran},
    )
    proc = start_proving(repo, tmp_path, signal.SIGHUP, signal.SIG_IGN)

    proc.send_signal(signal.SIGHUP)
    out, _ = proc.communicate(timeout=30)

    assert proc.returncode == 0
    assert [entry["proven"] for entry in json.loads(out)["checks"]] == [True, True, True, True]


def test_a_scan_runs_in_isolated_mode_from_another_folder(tmp_path):
    repo = write_repo(tmp_path / "repo", PYTHON_TOOLS_REPO)

    proc = subprocess.run(
        [sys.executable, "-I", "-B", str(SCRIPTS / "detect.py"), str(repo), "--no-network"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr
    assert [entry["name"] for entry in json.loads(proc.stdout)["checks"]] == [
        "test",
        "lint",
        "typecheck",
        "format",
    ]


@pytest.mark.parametrize(
    "flags",
    [
        ["--timeout=0"],
        ["--timeout=soon"],
        ["--timeout"],
        ["--timeout=1", "--timeout=2"],
        ["--timeout=inf"],
        ["--timeout=nan"],
    ],
)
def test_a_bad_budget_is_a_json_usage_error(tmp_path, flags):
    code, payload = run_script("detect.py", tmp_path, "--prove", *flags)

    assert code == 2
    assert set(payload) == {"error"}
