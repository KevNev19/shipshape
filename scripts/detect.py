#!/usr/bin/env python3
"""Repo scanner for shipshape (ADR 0002: Python 3 stdlib only, no pip).

Scans a directory and emits one JSON object on stdout describing what the
project is made of: languages, package managers, frameworks, test runners,
existing CI, hooks, and git state. Skills branch on this JSON and do the
talking; this script never prints prose.

Usage:
    python3 detect.py <repo-path> [--no-network]

--no-network skips the `gh auth status` probe (used by tests and offline runs).
"""

import json
import re
import subprocess
import sys
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
    "yarn.lock": "yarn",
    "pnpm-lock.yaml": "pnpm",
    "bun.lockb": "bun",
    "uv.lock": "uv",
    "poetry.lock": "poetry",
    "Pipfile.lock": "pipenv",
    "Cargo.lock": "cargo",
    "Gemfile.lock": "bundler",
    "go.sum": "go modules",
}

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


def detect_package_managers(root: Path) -> list[str]:
    found = {
        manager for lockfile, manager in LOCKFILE_MANAGERS.items() if (root / lockfile).is_file()
    }
    # A package.json without any JS lockfile still implies npm.
    js_managers = {"npm", "yarn", "pnpm", "bun"}
    if (root / "package.json").is_file() and not (found & js_managers):
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
    # Guess follows language confidence order, not runner alphabetical order.
    guess = ""
    for entry in languages:
        for runner in runners:
            if RUNNER_LANGUAGE.get(runner) == entry["name"]:
                guess = TEST_COMMANDS[runner]
                break
        if guess:
            break
    if not guess and runners:
        guess = TEST_COMMANDS.get(runners[0], "")
    return runners, guess


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
    return {
        "root": root.name,
        "languages": languages,
        "package_managers": detect_package_managers(root),
        "frameworks": _scan_markers(root, FRAMEWORK_MARKERS),
        "test_runners": test_runners,
        "test_command_guess": test_guess,
        "ci": detect_ci(root),
        "hooks": detect_hooks(root),
        "git": detect_git(root, no_network),
        "existing_sdlc": detect_existing_sdlc(root),
    }


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if len(args) != 1:
        print(json.dumps({"error": "usage: detect.py <repo-path> [--no-network]"}))
        return 2
    root = Path(args[0]).resolve()
    if not root.is_dir():
        print(json.dumps({"error": f"not a directory: {root}"}))
        return 2
    result = detect(root, no_network="--no-network" in flags)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
