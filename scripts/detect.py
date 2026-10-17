#!/usr/bin/env python3
"""Repo scanner for shipshape (ADR 0002: Python 3 stdlib only, no pip).

Scans a directory and emits one JSON object on stdout describing what the
project is made of: languages, package managers, frameworks, test runners,
the checks it proposes (test, lint, build, typecheck, format), existing CI,
hooks, and git state. Skills branch on this JSON and do the talking; this
script never prints prose.

Usage:
    python3 detect.py <repo-path> [--no-network] [--prove] [--timeout=SECONDS]

--no-network skips the `gh auth status` probe (used by tests and offline runs);
that probe is the only network use of the scan itself.

Without --prove the scan only reads files: it never runs a command it
proposes, and every check carries "proven": false (ADR 0012). --prove runs
each proposed command once in the repo, with no input and in a process group
of its own, inside one budget for the whole step (--timeout, default 300
seconds), and marks a check proven when its command finished inside the
budget with an exit status other than 126 or 127, whether it passed or not.
A command still running when the budget ends, or when the scan gets SIGTERM,
is killed with everything it started and stays unproven, as do the commands
not reached; the scan still prints its answer and exits 0. A command that
finishes has whatever it left running in its process group killed too. On
Linux the scan adopts and reaps what it kills, so nothing stays a zombie where
PID 1 reaps nothing, as in a container without an init; on Windows, which has
no process groups, taskkill ends a running command's process tree.

The proposed commands are the project's own build tools, which may fetch
dependencies. With --prove and --no-network together, each command runs with
the offline settings of cargo, go and npm (OFFLINE_ENV) on top of the scan's
environment; a command that then needs a download fails, which still proves
it ran.
"""

import contextlib
import fnmatch
import json
import math
import os
import re
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path

WALK_CAP = 5000
SKIP_DIRS = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    "target",
    ".next",
    "vendor",
}

# Manifest files are the strongest signal: presence => high confidence.
LANGUAGE_MANIFESTS = {
    "python": ["pyproject.toml", "setup.py", "requirements.txt"],
    "node": ["package.json"],
    "go": ["go.mod"],
    "rust": ["Cargo.toml"],
    "ruby": ["Gemfile"],
    "java": ["pom.xml", "build.gradle", "build.gradle.kts"],
}

# Extension counts back up (or stand in for) manifest evidence.
LANGUAGE_EXTENSIONS = {
    "python": {".py"},
    "node": {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"},
    "go": {".go"},
    "rust": {".rs"},
    "ruby": {".rb"},
    "java": {".java", ".kt"},
    "csharp": {".cs"},
}
EXTENSION_THRESHOLD = 3

LOCKFILE_MANAGERS = {
    "package-lock.json": "npm",
    "npm-shrinkwrap.json": "npm",
    "yarn.lock": "yarn",
    "pnpm-lock.yaml": "pnpm",
    "bun.lock": "bun",
    "bun.lockb": "bun",
    "uv.lock": "uv",
    "poetry.lock": "poetry",
    "Pipfile.lock": "pipenv",
    "Cargo.lock": "cargo",
    "Gemfile.lock": "bundler",
    "go.sum": "go modules",
}

NODE_LOCKFILE_MANAGERS = {
    name: manager
    for name, manager in LOCKFILE_MANAGERS.items()
    if manager in {"npm", "yarn", "pnpm", "bun"}
}
NODE_MANAGER_LOCKFILES = {
    "npm": ["package-lock.json", "npm-shrinkwrap.json"],
    "yarn": ["yarn.lock"],
    "pnpm": ["pnpm-lock.yaml"],
    "bun": ["bun.lock", "bun.lockb"],
}
SUPPORTED_NODE_MANAGERS = set(NODE_MANAGER_LOCKFILES)
EXACT_MANAGER_VERSION_RE = re.compile(
    r"^(?:0|[1-9][0-9]*)\."
    r"(?:0|[1-9][0-9]*)\."
    r"(?:0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z.-]+)?"
    r"(?:\+[0-9A-Za-z.-]+)?$"
)

# Framework detection: substring searched inside a manifest file's text.
# package.json needles are quoted so "vite" never matches inside "vitest".
FRAMEWORK_MARKERS = {
    "package.json": {
        "react": '"react"',
        "next": '"next"',
        "express": '"express"',
        "vue": '"vue"',
        "svelte": '"svelte"',
        "vite": '"vite"',
    },
    "pyproject.toml": {
        "fastapi": "fastapi",
        "django": "django",
        "flask": "flask",
    },
    "requirements.txt": {
        "fastapi": "fastapi",
        "django": "django",
        "flask": "flask",
    },
}

TEST_RUNNER_MARKERS = {
    "package.json": {"jest": '"jest"', "vitest": '"vitest"', "mocha": '"mocha"'},
    "pyproject.toml": {"pytest": "pytest"},
}

TEST_COMMANDS = {
    "pytest": "pytest",
    "jest": "npm test",
    "vitest": "npm test",
    "mocha": "npm test",
    "go test": "go test ./...",
    "cargo test": "cargo test",
}

RUNNER_LANGUAGE = {
    "pytest": "python",
    "jest": "node",
    "vitest": "node",
    "mocha": "node",
    "go test": "go",
    "cargo test": "rust",
}

# The kinds of check detection proposes, one command each, in this order.
CHECK_KINDS = ("test", "lint", "build", "typecheck", "format")

# Where the evidence for an implicit test runner lives (detect_test_runners
# adds these without a manifest marker).
IMPLICIT_RUNNER_SOURCES = {
    "pytest": "tests/",
    "go test": "go.mod",
    "cargo test": "Cargo.toml",
}

# Checks per language and kind, strongest evidence first. Each marker is the
# evidence as the "source" field reports it, mapped to (needle or filename,
# command). A needle is a TOML table header, found when the language's first
# manifest opens that table or one of its subtables; a filename must exist at
# the repo root. A marker on the language's own manifest stands for a command
# the toolchain provides (medium confidence); any other marker is the tool's
# own configuration (high confidence).
CHECK_MARKERS = {
    "python": {
        "lint": {
            "pyproject.toml:[tool.ruff]": ("[tool.ruff]", "ruff check ."),
            "ruff.toml": ("ruff.toml", "ruff check ."),
            ".ruff.toml": (".ruff.toml", "ruff check ."),
            ".flake8": (".flake8", "flake8 ."),
        },
        "typecheck": {
            "pyproject.toml:[tool.mypy]": ("[tool.mypy]", "mypy ."),
            "mypy.ini": ("mypy.ini", "mypy ."),
            ".mypy.ini": (".mypy.ini", "mypy ."),
            "pyproject.toml:[tool.pyright]": ("[tool.pyright]", "pyright"),
            "pyrightconfig.json": ("pyrightconfig.json", "pyright"),
        },
        # A configured black is the formatter even when ruff is configured too.
        "format": {
            "pyproject.toml:[tool.black]": ("[tool.black]", "black --check ."),
            "pyproject.toml:[tool.ruff]": ("[tool.ruff]", "ruff format --check ."),
            "ruff.toml": ("ruff.toml", "ruff format --check ."),
            ".ruff.toml": (".ruff.toml", "ruff format --check ."),
        },
    },
    # node_modules/.bin runs only what the project installed: npx could fetch
    # a package from the network, or an unrelated one under the same name.
    "node": {
        "lint": {
            "eslint.config.js": ("eslint.config.js", "node_modules/.bin/eslint ."),
            "eslint.config.mjs": ("eslint.config.mjs", "node_modules/.bin/eslint ."),
            ".eslintrc.json": (".eslintrc.json", "node_modules/.bin/eslint ."),
            ".eslintrc.js": (".eslintrc.js", "node_modules/.bin/eslint ."),
        },
        "typecheck": {
            "tsconfig.json": ("tsconfig.json", "node_modules/.bin/tsc --noEmit"),
        },
        "format": {
            ".prettierrc": (".prettierrc", "node_modules/.bin/prettier --check ."),
            ".prettierrc.json": (".prettierrc.json", "node_modules/.bin/prettier --check ."),
            "prettier.config.js": ("prettier.config.js", "node_modules/.bin/prettier --check ."),
        },
    },
    "go": {
        "lint": {
            ".golangci.yml": (".golangci.yml", "golangci-lint run"),
            ".golangci.yaml": (".golangci.yaml", "golangci-lint run"),
            "go.mod": ("go.mod", "go vet ./..."),
        },
        "build": {
            "go.mod": ("go.mod", "go build ./..."),
        },
        # gofmt -l lists unformatted files and still exits 0, so the check
        # fails when the list is not empty, and shows it. The command
        # substitution keeps gofmt's own status: a pipeline would report
        # grep's, and a missing gofmt would pass instead of exiting 127.
        "format": {
            "go.mod": ("go.mod", 'out=$(gofmt -l .) && ! echo "$out" | grep .'),
        },
    },
    "rust": {
        "lint": {
            "clippy.toml": ("clippy.toml", "cargo clippy -- -D warnings"),
            ".clippy.toml": (".clippy.toml", "cargo clippy -- -D warnings"),
            "Cargo.toml": ("Cargo.toml", "cargo clippy -- -D warnings"),
        },
        "build": {
            "Cargo.toml": ("Cargo.toml", "cargo build"),
        },
        "typecheck": {
            "Cargo.toml": ("Cargo.toml", "cargo check"),
        },
        "format": {
            "rustfmt.toml": ("rustfmt.toml", "cargo fmt --check"),
            ".rustfmt.toml": (".rustfmt.toml", "cargo fmt --check"),
            "Cargo.toml": ("Cargo.toml", "cargo fmt --check"),
        },
    },
}

# package.json scripts that run each kind of check, most specific name first:
# a script named "format" often rewrites files, so check-only names win.
NODE_SCRIPTS = {
    "lint": ("lint",),
    "build": ("build",),
    "typecheck": ("typecheck", "type-check", "check-types"),
    "format": ("format:check", "check-format", "fmt:check", "format"),
}

# A script that rewrites files or watches forever is not a check. The flag list
# is closed, and -w is knowingly conservative: it is also npm's workspace flag,
# so `npm run build -w pkg` is dropped too.
NOT_A_CHECK = ("--write", "--fix", "--apply", "--watch", "-w")
# The shell's punctuation: each run of it is a word of its own however it is
# spaced, so `--fix>lint.log`, `(eslint --fix)` and `` `eslint --fix` `` still
# show the flag as a word.
SHELL_PUNCTUATION = "();<>|&`"
# A backslash before a line end: the shell drops both and joins the lines, so
# `--fi` + backslash-newline + `x` is --fix, while shlex keeps the line end.
LINE_CONTINUATION = re.compile(r"\\\r?\n")
# Brace expansion, which the shell does and shlex does not: a list such as
# `--{fix,}` becomes --fix and --. A sequence such as `{a..z}`, or a list that
# grows past BRACE_LIMIT words, is not expanded, so its script is not proposed.
BRACE_LIST = re.compile(r"\{([^{}]*,[^{}]*)\}")
BRACE_SEQUENCE = re.compile(r"\{[^{}]*\.\.[^{}]*\}")
BRACE_LIMIT = 256
# Programs that run a string as shell code: the screen cannot follow what they
# run, so a script that names one is never proposed.
SHELLS = frozenset({"sh", "bash", "zsh", "dash", "ksh", "fish", "eval"})

# A lockfile other than npm's names the runner the project's scripts expect;
# a bare package.json means npm.
NODE_RUNNERS = ("pnpm", "yarn", "bun")

# --prove: one budget for every proposed command together, in seconds.
PROVE_TIMEOUT_SECONDS = 300.0
# The shell's statuses for a command it could not run: not executable, not found.
CANNOT_RUN_EXITS = (126, 127)
# How long to wait for a killed command's process to be reaped.
KILL_WAIT_SECONDS = 5.0
# How often to look again for a killed group member to reap.
REAP_POLL_SECONDS = 0.01
# Linux prctl options that set and read whether this process adopts what its
# descendants orphan (a child subreaper), as an init does.
PR_SET_CHILD_SUBREAPER = 36
PR_GET_CHILD_SUBREAPER = 37
# --prove with --no-network: keep cargo, go, and npm (whose config pnpm also
# reads) from fetching dependencies.
OFFLINE_ENV = {
    "CARGO_NET_OFFLINE": "true",
    "GOPROXY": "off",
    "npm_config_offline": "true",
}
USAGE = "usage: detect.py <repo-path> [--no-network] [--prove] [--timeout=SECONDS]"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=10)
        return proc.returncode, proc.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


def walk_extensions(root: Path) -> dict[str, int]:
    """Count file extensions under root, capped and skipping vendor dirs."""
    counts: dict[str, int] = {}
    seen = 0
    stack = [root]
    while stack and seen < WALK_CAP:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for entry in entries:
            if seen >= WALK_CAP:
                break
            if entry.is_dir():
                if entry.name not in SKIP_DIRS and not entry.name.startswith("."):
                    stack.append(entry)
                continue
            seen += 1
            ext = entry.suffix.lower()
            if ext:
                counts[ext] = counts.get(ext, 0) + 1
    return counts


def detect_languages(root: Path, ext_counts: dict[str, int]) -> list[dict]:
    results = []
    for lang in sorted(set(LANGUAGE_MANIFESTS) | set(LANGUAGE_EXTENSIONS)):
        evidence = []
        for manifest in LANGUAGE_MANIFESTS.get(lang, []):
            if (root / manifest).is_file():
                evidence.append(manifest)
        ext_total = sum(ext_counts.get(ext, 0) for ext in LANGUAGE_EXTENSIONS.get(lang, set()))
        if ext_total:
            exts = ", ".join(sorted(LANGUAGE_EXTENSIONS.get(lang, set())))
            noun = "file" if ext_total == 1 else "files"
            evidence.append(f"{ext_total} {noun} ({exts})")
        if not evidence:
            continue
        has_manifest = any((root / m).is_file() for m in LANGUAGE_MANIFESTS.get(lang, []))
        if has_manifest:
            confidence = "high"
        elif ext_total >= EXTENSION_THRESHOLD:
            confidence = "medium"
        else:
            confidence = "low"
        results.append({"name": lang, "confidence": confidence, "evidence": evidence})
    order = {"high": 0, "medium": 1, "low": 2}
    results.sort(key=lambda r: (order[r["confidence"]], r["name"]))
    return results


def _load_package_json(root: Path) -> tuple[dict | None, str]:
    package_path = root / "package.json"
    if not package_path.is_file():
        return None, ""
    try:
        package = json.loads(package_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return None, f"cannot read package.json: {error}"
    if not isinstance(package, dict):
        return None, "package.json must contain a JSON object"
    return package, ""


def _yarn_lock_variant(root: Path) -> str:
    text = _read_text(root / "yarn.lock")
    if re.search(r"(?m)^__metadata:\s*$", text):
        return "yarn_modern"
    if "# yarn lockfile v1" in text:
        return "yarn_classic"
    return ""


def _manager_signal_error(declared: str, lock_signals: dict[str, list[str]]) -> str:
    signals = []
    if declared:
        signals.append(f"package.json packageManager declares {declared}")
    for manager in sorted(lock_signals):
        lockfiles = ", ".join(lock_signals[manager])
        signals.append(f"{lockfiles} indicate {manager}")
    return "conflicting Node package-manager signals: " + "; ".join(signals)


def detect_node_package_manager(root: Path) -> dict | None:
    """Resolve Node package-manager evidence without silently breaking ties."""
    package, package_error = _load_package_json(root)
    lock_signals: dict[str, list[str]] = {}
    for lockfile, manager in NODE_LOCKFILE_MANAGERS.items():
        if (root / lockfile).is_file():
            lock_signals.setdefault(manager, []).append(lockfile)
    for lockfiles in lock_signals.values():
        lockfiles.sort()

    if package is None and not package_error and not lock_signals:
        return None

    result = {"name": "", "version": "", "variant": "", "lockfiles": []}
    if package_error:
        result["error"] = package_error
        return result

    raw_declaration = package.get("packageManager") if package else None
    declared_name = ""
    if raw_declaration is not None:
        if not isinstance(raw_declaration, str) or "@" not in raw_declaration:
            result["error"] = (
                "package.json packageManager must be name@x.y.z with an exact safe version"
            )
            return result
        declared_name, _, version = raw_declaration.partition("@")
        result["name"] = declared_name
        if declared_name not in SUPPORTED_NODE_MANAGERS:
            result["error"] = f"unsupported Node package manager in package.json: {declared_name}"
            return result
        if not EXACT_MANAGER_VERSION_RE.fullmatch(version):
            result["error"] = (
                "package.json packageManager must use an exact safe version such as "
                f"{declared_name}@1.2.3"
            )
            return result
        result["version"] = version

    signaled_managers = set(lock_signals)
    if declared_name:
        signaled_managers.add(declared_name)
    if len(signaled_managers) > 1:
        result["error"] = _manager_signal_error(declared_name, lock_signals)
        return result

    manager = declared_name or (next(iter(signaled_managers)) if signaled_managers else "npm")
    lockfiles = lock_signals.get(manager, [])
    result["name"] = manager
    result["lockfiles"] = lockfiles
    if not lockfiles:
        expected = " or ".join(NODE_MANAGER_LOCKFILES[manager])
        if declared_name:
            result["error"] = (
                f"package.json declares {manager}, but no {expected} was found; "
                f"commit a {manager} lockfile before initializing shipshape"
            )
        else:
            result["error"] = (
                f"package.json identifies a Node project, but no {expected} was found; "
                "commit an npm lockfile before initializing shipshape"
            )
        return result
    if manager != "npm" and not declared_name:
        result["error"] = (
            f"{lockfiles[0]} selects {manager}, but fresh setup requires an exact "
            f'package.json packageManager declaration such as "packageManager": '
            f'"{manager}@1.2.3"'
        )
        return result

    if manager == "yarn":
        declared_variant = ""
        if result["version"]:
            major = int(result["version"].split(".", 1)[0])
            declared_variant = "yarn_classic" if major == 1 else "yarn_modern"
        lock_variant = _yarn_lock_variant(root)
        if declared_variant and lock_variant and declared_variant != lock_variant:
            result["error"] = (
                "conflicting Node package-manager signals: package.json declares "
                f"{declared_variant.replace('_', ' ')}, but yarn.lock is "
                f"{lock_variant.replace('_', ' ')}"
            )
            return result
        result["variant"] = declared_variant or lock_variant
        if not result["variant"]:
            result["error"] = (
                "cannot distinguish Yarn Classic from modern yarn.lock; add an exact "
                'packageManager such as "yarn@1.22.22" or "yarn@4.9.2"'
            )
            return result
    elif manager == "npm" and declared_name:
        result["variant"] = "npm_corepack"
    else:
        result["variant"] = manager
    return result


def detect_package_managers(root: Path, node_manager: dict | None = None) -> list[str]:
    found = {
        manager for lockfile, manager in LOCKFILE_MANAGERS.items() if (root / lockfile).is_file()
    }
    if node_manager and node_manager.get("name") in SUPPORTED_NODE_MANAGERS:
        found.add(node_manager["name"])
    # A package.json without any JS lockfile still implies npm.
    if (
        node_manager is None
        and (root / "package.json").is_file()
        and not (found & SUPPORTED_NODE_MANAGERS)
    ):
        found.add("npm")
    return sorted(found)


def _scan_markers(root: Path, marker_map: dict[str, dict[str, str]]) -> list[str]:
    found = set()
    for filename, markers in marker_map.items():
        text = _read_text(root / filename)
        if not text:
            continue
        for name, needle in markers.items():
            if needle in text:
                found.add(name)
    return sorted(found)


def detect_test_runners(root: Path, languages: list[dict]) -> tuple[list[str], str]:
    runners = set(_scan_markers(root, TEST_RUNNER_MARKERS))
    # Implicit built-in runners only for high-confidence languages, so stray
    # files deep in the tree can't claim the project's test command.
    high = {entry["name"] for entry in languages if entry["confidence"] == "high"}
    if "python" in high and (root / "tests").is_dir():
        runners.add("pytest")
    if "go" in high:
        runners.add("go test")
    if "rust" in high:
        runners.add("cargo test")
    runners = sorted(runners)
    # A Node test script that rewrites files or watches is not a test command:
    # the guess passes over the Node runners, so another language's runner can
    # still be the one guessed.
    candidates = runners
    if _unsafe_node_test(root):
        candidates = [runner for runner in runners if RUNNER_LANGUAGE.get(runner) != "node"]
    return runners, _guess_test_command(candidates, languages)


def _guess_test_command(runners: list[str], languages: list[dict]) -> str:
    # Guess follows language confidence order, not runner alphabetical order.
    for entry in languages:
        for runner in runners:
            if RUNNER_LANGUAGE.get(runner) == entry["name"]:
                return TEST_COMMANDS[runner]
    return TEST_COMMANDS.get(runners[0], "") if runners else ""


def _unsafe_node_test(root: Path) -> bool:
    package, _ = _load_package_json(root)
    scripts = (package or {}).get("scripts")
    return isinstance(scripts, dict) and _unsafe_node_script(scripts, "test")


def _check(command: str, source: str, confidence: str, language: str) -> dict:
    return {"command": command, "source": source, "confidence": confidence, "language": language}


def _has_toml_table(text: str, header: str) -> bool:
    """True when the TOML text opens the table `header` (like "[tool.ruff]")
    or one of its subtables (like "[tool.ruff.lint]")."""
    name = re.escape(header.strip("[]"))
    return re.search(rf"^\s*\[{name}[\].]", text, re.MULTILINE) is not None


def _marker_found(root: Path, language: str, probe: str) -> bool:
    if probe.startswith("["):
        manifest = LANGUAGE_MANIFESTS[language][0]
        return _has_toml_table(_read_text(root / manifest), probe)
    return (root / probe).is_file()


def _node_runner(package_managers: list[str]) -> str:
    for runner in NODE_RUNNERS:
        if runner in package_managers:
            return runner
    return "npm"


def _shell_words(command: str) -> list[str] | None:
    """The words the shell reads in `command`, quotes removed and each run of
    SHELL_PUNCTUATION a word of its own; None when it does not parse, or holds a
    line continuation, which shlex reads otherwise than the shell does."""
    if LINE_CONTINUATION.search(command):
        return None
    lexer = shlex.shlex(command, posix=True, punctuation_chars=SHELL_PUNCTUATION)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        return list(lexer)
    except ValueError:
        return None


def _unsafe_node_script(scripts: dict, name: str, seen: set[str] | None = None) -> bool:
    """True when running package.json script `name` could rewrite files, watch,
    or run shell code the screen cannot read: through its own words, the pre
    and post scripts a runner adds around it, or any script it names."""
    seen = set() if seen is None else seen
    if name in seen:
        return False
    seen.add(name)
    return any(
        isinstance(scripts.get(script), str) and _unsafe_command(scripts, scripts[script], seen)
        for script in (f"pre{name}", name, f"post{name}")
    )


def _unsafe_command(scripts: dict, command: str, seen: set[str]) -> bool:
    words = _shell_words(command)
    if words is None:
        return True
    for word in words:
        if set(word) <= set(SHELL_PUNCTUATION):
            continue
        expanded = _brace_words(word)
        if expanded is None or any(_unsafe_shell_word(scripts, each, seen) for each in expanded):
            return True
    return False


def _brace_words(word: str) -> list[str] | None:
    """The words brace expansion makes of `word`: [word] itself without a brace
    list, None for a brace sequence or more than BRACE_LIMIT words."""
    if BRACE_SEQUENCE.search(word):
        return None
    pending, done = [word], []
    while pending:
        current = pending.pop()
        match = BRACE_LIST.search(current)
        if match is None:
            done.append(current)
            continue
        head, tail = current[: match.start()], current[match.end() :]
        pending += [head + alternative + tail for alternative in match.group(1).split(",")]
        if len(pending) + len(done) > BRACE_LIMIT:
            return None
    return done


def _unsafe_shell_word(scripts: dict, word: str, seen: set[str]) -> bool:
    if _unsafe_word(word):
        return True
    # A quoted string with blanks or punctuation may be a command another
    # program runs (concurrently, npx -c, node -e): it is screened the same way.
    if any(char.isspace() or char in SHELL_PUNCTUATION for char in word) and (
        _unsafe_command(scripts, word, seen)
    ):
        return True
    # A word naming a script, or a glob naming several (run-s "lint:*"), may run them.
    named = (
        script
        for script in scripts
        if script == word or ("*" in word and fnmatch.fnmatchcase(script, word))
    )
    return any(_unsafe_node_script(scripts, script, seen) for script in named)


def _unsafe_word(word: str) -> bool:
    """A rewrite or watch flag, a shell, or a value the shell expands, which
    the screen cannot read."""
    return (
        word in NOT_A_CHECK
        or word.startswith(tuple(f"{flag}=" for flag in NOT_A_CHECK))
        or word.rsplit("/", 1)[-1] in SHELLS
        or ("$" in word and word != "$")
    )


def _node_script_check(root: Path, kind: str, package_managers: list[str]) -> dict | None:
    # A package.json that does not parse proposes no scripts; the scan still answers.
    package, _ = _load_package_json(root)
    scripts = (package or {}).get("scripts")
    if not isinstance(scripts, dict):
        return None
    runner = _node_runner(package_managers)
    for name in NODE_SCRIPTS.get(kind, ()):
        body = scripts.get(name)
        if isinstance(body, str) and body.strip() and not _unsafe_node_script(scripts, name):
            command = f"{runner} run {name}"
            return _check(command, f"package.json:scripts.{name}", "high", "node")
    return None


def _node_test_command(package_managers: list[str]) -> str:
    runner = _node_runner(package_managers)
    return "bun run test" if runner == "bun" else f"{runner} test"


def _language_check(
    root: Path, language: str, kind: str, package_managers: list[str]
) -> dict | None:
    if language == "node":
        script = _node_script_check(root, kind, package_managers)
        if script:
            return script
    markers = CHECK_MARKERS.get(language, {}).get(kind, {})
    for source, (probe, command) in markers.items():
        if _marker_found(root, language, probe):
            toolchain = probe == LANGUAGE_MANIFESTS[language][0]
            return _check(command, source, "medium" if toolchain else "high", language)
    return None


def _first_language_check(
    root: Path, languages: list[str], kind: str, package_managers: list[str]
) -> dict | None:
    # Languages arrive in confidence-then-name order, so the primary one wins.
    for language in languages:
        found = _language_check(root, language, kind, package_managers)
        if found:
            return found
    return None


def _test_check(
    root: Path, test_runners: list[str], test_guess: str, package_managers: list[str]
) -> dict | None:
    """The check for the runner behind test_command_guess, so the two never
    disagree after applying the project's package manager: high confidence
    when a manifest names the runner, medium when the runner is implicit."""
    if not test_guess:
        return None
    for runner in test_runners:
        if TEST_COMMANDS.get(runner) != test_guess:
            continue
        language = RUNNER_LANGUAGE[runner]
        command = _node_test_command(package_managers) if language == "node" else test_guess
        for filename, markers in TEST_RUNNER_MARKERS.items():
            needle = markers.get(runner)
            if needle and needle in _read_text(root / filename):
                return _check(command, filename, "high", language)
        return _check(command, IMPLICIT_RUNNER_SOURCES[runner], "medium", language)
    return None


def detect_checks(
    root: Path,
    languages: list[dict],
    package_managers: list[str],
    test_runners: list[str],
    test_guess: str,
) -> list[dict]:
    """Propose one command per kind of check, in CHECK_KINDS order, leaving
    out a kind nothing reveals. This reads files only; it never runs a
    command, so every check starts unproven (ADR 0012)."""
    # Only high-confidence languages propose checks, like implicit test
    # runners: stray files deep in the tree must not claim the project's checks.
    high = [entry["name"] for entry in languages if entry["confidence"] == "high"]
    checks = []
    for kind in CHECK_KINDS:
        if kind == "test":
            found = _test_check(root, test_runners, test_guess, package_managers)
        else:
            found = _first_language_check(root, high, kind, package_managers)
        if found:
            checks.append({"name": kind, **found, "proven": False})
    return checks


class _StopRequest:
    """SIGTERM during the prove step: kill the running command's process
    group, so nothing it started outlives the scan, and start no other."""

    def __init__(self) -> None:
        self.requested = False
        self.process: subprocess.Popen | None = None

    def __call__(self, signum, frame) -> None:
        self.requested = True
        if self.process is not None:
            _kill_group(self.process)


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
        # Imported here: a Python built without ctypes still scans and proves.
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


def _ran(
    root: Path, command: str, deadline: float, stop: _StopRequest, env: dict[str, str] | None
) -> bool:
    """Run one command once, in `env` (None: the scan's own environment); True
    when it finished before the deadline with an exit status other than 126 or
    127, whatever else it returned."""
    remaining = deadline - time.monotonic()
    if remaining <= 0 or stop.requested:
        return False
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=env,
        )
    except OSError:
        return False
    stop.process = process
    try:
        if stop.requested:
            _kill_group(process)
        code = process.wait(timeout=remaining)
        # Whatever the command left running in its group ends with it.
        _kill_group(process)
    except subprocess.TimeoutExpired:
        _kill_group(process)
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=KILL_WAIT_SECONDS)
        return False
    finally:
        stop.process = None
        _reap_group(process)
    return not stop.requested and code not in CANNOT_RUN_EXITS


def prove_checks(
    root: Path, checks: list[dict], timeout: float, offline: bool = False
) -> list[dict]:
    """Run each proposed command once, inside one budget of `timeout` seconds
    for the whole step, and mark the checks whose command ran. `offline` adds
    OFFLINE_ENV to each command's environment."""
    env = {**os.environ, **OFFLINE_ENV} if offline else None
    stop = _StopRequest()
    previous = signal.signal(signal.SIGTERM, stop)
    deadline = time.monotonic() + timeout
    try:
        with _adopting_orphans():
            return [
                {**check, "proven": _ran(root, check["command"], deadline, stop, env)}
                for check in checks
            ]
    finally:
        signal.signal(signal.SIGTERM, previous)


def detect_ci(root: Path) -> dict:
    workflows_dir = root / ".github" / "workflows"
    workflows = []
    has_codeql = False
    if workflows_dir.is_dir():
        for wf in sorted(workflows_dir.iterdir()):
            if wf.suffix in (".yml", ".yaml"):
                workflows.append(wf.name)
                if "codeql" in wf.name.lower() or "codeql" in _read_text(wf).lower():
                    has_codeql = True
    return {
        "github_actions": bool(workflows),
        "workflows": workflows,
        "has_codeql": has_codeql,
        "has_dependabot": (root / ".github" / "dependabot.yml").is_file(),
    }


def detect_hooks(root: Path) -> dict:
    bare_hooks = []
    hooks_dir = root / ".git" / "hooks"
    if hooks_dir.is_dir():
        for hook in sorted(hooks_dir.iterdir()):
            if hook.is_file() and not hook.name.endswith(".sample"):
                bare_hooks.append(hook.name)
    return {
        "pre_commit_framework": (root / ".pre-commit-config.yaml").is_file(),
        "bare_git_hooks": bare_hooks,
    }


def _parse_remote(url: str) -> tuple[str, str]:
    """Split a git remote URL (ssh or https form) into (host, owner/repo)."""
    match = re.match(r"(?:ssh://)?git@([^:/]+)[:/](.+)", url)
    if not match:
        match = re.match(r"https?://([^/@]+)/(.+)", url)
    if not match:
        return "", ""
    return match.group(1).lower(), match.group(2).removesuffix(".git")


def detect_git(root: Path, no_network: bool) -> dict:
    info = {
        "is_repo": False,
        "default_branch": "",
        "remote": "",
        "owner_repo": "",
        "gh_authed": None,
    }
    code, toplevel = _run(["git", "-C", str(root), "rev-parse", "--show-toplevel"])
    # A subdirectory of some other repo is not itself a repo for our purposes.
    if code != 0 or Path(toplevel).resolve() != root.resolve():
        return info
    info["is_repo"] = True
    code, branch = _run(["git", "-C", str(root), "branch", "--show-current"])
    if code == 0 and branch:
        info["default_branch"] = branch
    code, url = _run(["git", "-C", str(root), "remote", "get-url", "origin"])
    if code == 0 and url:
        host, path = _parse_remote(url)
        # Exact host match, not substring: "evilgithub.com.attacker.example"
        # must never be treated as GitHub (CodeQL: incomplete URL sanitization).
        if host == "github.com" or host.endswith(".github.com"):
            info["remote"] = "github"
            info["owner_repo"] = path
        else:
            info["remote"] = "other"
    if info["remote"] == "github" and not no_network:
        code, _ = _run(["gh", "auth", "status"])
        info["gh_authed"] = code == 0
    return info


def detect_existing_sdlc(root: Path) -> dict:
    config_path = root / ".sdlc" / "config.json"
    kit_version = None
    if config_path.is_file():
        try:
            kit_version = json.loads(_read_text(config_path)).get("kit_version")
        except (json.JSONDecodeError, AttributeError):
            kit_version = None
    return {"config_present": config_path.is_file(), "kit_version": kit_version}


def detect(root: Path, no_network: bool = False) -> dict:
    ext_counts = walk_extensions(root)
    languages = detect_languages(root, ext_counts)
    test_runners, test_guess = detect_test_runners(root, languages)
    node_manager = detect_node_package_manager(root)
    package_managers = detect_package_managers(root, node_manager)
    result = {
        "root": root.name,
        "languages": languages,
        "package_managers": package_managers,
        "frameworks": _scan_markers(root, FRAMEWORK_MARKERS),
        "test_runners": test_runners,
        "test_command_guess": test_guess,
        "checks": detect_checks(root, languages, package_managers, test_runners, test_guess),
        "ci": detect_ci(root),
        "hooks": detect_hooks(root),
        "git": detect_git(root, no_network),
        "existing_sdlc": detect_existing_sdlc(root),
    }
    if node_manager is not None:
        result["node_package_manager"] = node_manager
    return result


def _prove_timeout(flags: set[str]) -> float | None:
    """The --timeout=SECONDS budget, the default without one, None when malformed."""
    given = [flag for flag in flags if flag == "--timeout" or flag.startswith("--timeout=")]
    if not given:
        return PROVE_TIMEOUT_SECONDS
    try:
        seconds = float(given[0].partition("=")[2])
    except ValueError:
        return None
    return seconds if len(given) == 1 and math.isfinite(seconds) and seconds > 0 else None


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if len(args) != 1:
        print(json.dumps({"error": USAGE}))
        return 2
    timeout = _prove_timeout(flags)
    if timeout is None:
        print(json.dumps({"error": "--timeout must be a positive number of seconds"}))
        return 2
    root = Path(args[0]).resolve()
    if not root.is_dir():
        print(json.dumps({"error": f"not a directory: {root}"}))
        return 2
    no_network = "--no-network" in flags
    result = detect(root, no_network=no_network)
    if "--prove" in flags:
        result["checks"] = prove_checks(root, result["checks"], timeout, offline=no_network)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
