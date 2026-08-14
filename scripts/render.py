#!/usr/bin/env python3
"""Template renderer for shipshape (ADR 0003: {{TOKEN}} substitution, no engine).

Three subcommands, all emitting one JSON object on stdout (skills branch on
the JSON and do the talking):

    render.py init-config <repo> --detect FILE [--set key=value]...
        Write <repo>/.sdlc/config.json from templates/sdlc/config.json
        defaults merged with detection output and explicit overrides.

    render.py plan <repo>
        Dry run. Classify every applicable template as write / regenerate /
        skip / conflict without touching anything.

    render.py apply <repo> [--force <dest>]...
        Perform the writes and regenerates from the plan. Conflicted files
        are NEVER touched unless their dest path is named with --force.

Drift contract: .sdlc/state.json records the sha256 of every file as
shipshape wrote it. A file whose current hash no longer matches was edited
by the user and becomes a conflict — shipshape never clobbers it silently.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = KIT_ROOT / "templates"
TOKEN_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")

# Fallback when a repo has no detectable test command: CI still runs and
# tells the user what to do instead of failing mysteriously.
NO_TESTS_CMD = 'echo "No tests configured yet - see docs/sdlc/harness.md"'


def fail(message: str) -> int:
    print(json.dumps({"ok": False, "error": message}))
    return 1


def kit_version() -> str:
    manifest = KIT_ROOT / ".claude-plugin" / "plugin.json"
    return json.loads(manifest.read_text())["version"]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def set_dotted(config: dict, dotted_key: str, raw_value: str) -> None:
    """Apply one --set override like features.codeql=false or commands.test=pytest."""
    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError:
        value = raw_value
    node = config
    keys = dotted_key.split(".")
    for key in keys[:-1]:
        node = node.setdefault(key, {})
    node[keys[-1]] = value


def cmd_init_config(repo: Path, detect_file: Path, overrides: list[str]) -> int:
    config = load_json(TEMPLATES_DIR / "sdlc" / "config.json")
    detected = load_json(detect_file)

    config["kit_version"] = kit_version()
    config["project_name"] = detected.get("root", repo.name) or repo.name
    config["languages"] = [
        lang["name"]
        for lang in detected.get("languages", [])
        if lang.get("confidence") in ("high", "medium")
    ]
    git_info = detected.get("git", {})
    config["default_branch"] = git_info.get("default_branch") or "main"
    config["repo"]["owner_repo"] = git_info.get("owner_repo", "")
    owner_repo = config["repo"]["owner_repo"]
    if owner_repo and "/" in owner_repo:
        config["owners"]["default"] = "@" + owner_repo.split("/")[0]
    config["commands"]["test"] = detected.get("test_command_guess") or NO_TESTS_CMD

    for override in overrides:
        if "=" not in override:
            return fail(f"--set expects key=value, got: {override}")
        key, _, value = override.partition("=")
        set_dotted(config, key, value)

    config_path = repo / ".sdlc" / "config.json"
    existed = config_path.is_file()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "action": "replaced" if existed else "created",
                "config_path": str(config_path),
                "config": config,
            },
            indent=2,
        )
    )
    return 0


# CodeQL analysis language per detected primary language (unsupported => "").
CODEQL_LANGUAGES = {
    "python": "python",
    "node": "javascript-typescript",
    "go": "go",
    "java": "java-kotlin",
    "ruby": "ruby",
    "csharp": "csharp",
}

DEPENDABOT_ECOSYSTEMS = {
    "python": "pip",
    "node": "npm",
    "go": "gomod",
    "rust": "cargo",
    "ruby": "bundler",
    "java": "gradle",
}


def dependabot_updates(languages: list[str]) -> str:
    """Build the dependabot `updates:` list body: GitHub Actions always,
    plus one ecosystem per configured language that has one."""
    ecosystems = ["github-actions"] + [
        DEPENDABOT_ECOSYSTEMS[lang] for lang in languages if lang in DEPENDABOT_ECOSYSTEMS
    ]
    blocks = [
        f'  - package-ecosystem: "{eco}"\n'
        '    directory: "/"\n'
        "    schedule:\n"
        '      interval: "weekly"'
        for eco in ecosystems
    ]
    return "\n".join(blocks)


def build_tokens(config: dict) -> dict[str, str]:
    languages = config.get("languages", [])
    toolchain = config.get("toolchain", {})
    primary = languages[0] if languages else "none"
    return {
        "CODEQL_LANGUAGE": CODEQL_LANGUAGES.get(primary, ""),
        "DEPENDABOT_UPDATES": dependabot_updates(languages),
        "PROJECT_NAME": config.get("project_name", ""),
        "KIT_VERSION": config.get("kit_version") or kit_version(),
        "DEFAULT_BRANCH": config.get("default_branch", "main"),
        "WORKFLOW_STYLE": config.get("workflow_style", "trunk"),
        "PROFILE": config.get("profile", "solo"),
        "TEST_CMD": config.get("commands", {}).get("test", ""),
        "LINT_CMD": config.get("commands", {}).get("lint", ""),
        "PRIMARY_LANGUAGE": languages[0] if languages else "none",
        "LANGUAGES_SUMMARY": ", ".join(languages) if languages else "none detected yet",
        "PYTHON_VERSION": str(toolchain.get("python", "3.12")),
        "NODE_VERSION": str(toolchain.get("node", "20")),
        "GO_VERSION": str(toolchain.get("go", "1.22")),
        "OWNER_REPO": config.get("repo", {}).get("owner_repo", ""),
        "CODEOWNERS_DEFAULT": config.get("owners", {}).get("default", ""),
    }


def entry_applies(entry: dict, config: dict) -> bool:
    flag = entry.get("feature_flag")
    if flag and not config.get("features", {}).get(flag, False):
        return False
    languages = config.get("languages", [])
    primary = languages[0] if languages else "none"
    # Derived conditions: collaboration = anyone besides the owner is involved.
    collaboration = config.get("profile") == "team" or config.get("workflow_style") == "pr"
    has_owner = bool(config.get("owners", {}).get("default"))
    for key, expected in entry.get("when", {}).items():
        if key == "primary_language" and primary != expected:
            return False
        if key == "primary_language_in" and primary not in expected:
            return False
        if key == "primary_language_not_in" and primary in expected:
            return False
        if key == "workflow_style" and config.get("workflow_style") != expected:
            return False
        if key == "profile" and config.get("profile") != expected:
            return False
        if key == "collaboration" and collaboration != expected:
            return False
        if key == "has_owner" and has_owner != expected:
            return False
    return True


def render_template(src: Path, tokens: dict[str, str]) -> tuple[str, list[str]]:
    """Substitute tokens; return (text, problems). Empty values count as missing
    because a blank in a command or branch name produces broken output."""
    text = src.read_text(encoding="utf-8")
    needed = set(TOKEN_RE.findall(text))
    problems = [f"token {name} has no value" for name in sorted(needed) if not tokens.get(name)]
    for name in needed:
        value = tokens.get(name)
        if value:
            text = text.replace("{{" + name + "}}", value)
    if not problems and TOKEN_RE.search(text):
        problems.append(f"unsubstituted tokens remain in {src.name}")
    return text, problems


def load_state(repo: Path) -> dict:
    state_path = repo / ".sdlc" / "state.json"
    if state_path.is_file():
        return load_json(state_path)
    return {"kit_version": "", "files": {}}


def compute_plan(repo: Path, config: dict) -> dict:
    manifest = load_json(TEMPLATES_DIR / "manifest.json")
    tokens = build_tokens(config)
    state = load_state(repo)
    plan = {
        "ok": True,
        "writes": [],
        "regenerates": [],
        "removals": [],
        "skips": [],
        "conflicts": [],
        "errors": [],
        "rendered": {},
        "meta": {},
    }
    for entry in manifest["templates"]:
        if not entry_applies(entry, config):
            if not entry.get("remove_when_inapplicable"):
                continue
            dest = entry["dest"]
            dest_path = repo / dest
            if not dest_path.is_file():
                continue
            recorded = state["files"].get(dest)
            if recorded is None:
                plan["conflicts"].append(
                    {
                        "path": dest,
                        "reason": (
                            "inactive managed path already exists but was not written by shipshape"
                        ),
                        "action": "remove",
                    }
                )
                continue
            current_hash = sha256_text(dest_path.read_text(encoding="utf-8"))
            if current_hash != recorded["sha256"]:
                plan["conflicts"].append(
                    {
                        "path": dest,
                        "reason": "inactive managed file was edited since shipshape wrote it",
                        "action": "remove",
                    }
                )
                continue
            plan["removals"].append({"path": dest, "pillar": entry["pillar"]})
            continue
        dest = entry["dest"]
        rendered, problems = render_template(TEMPLATES_DIR / entry["src"], tokens)
        if problems:
            plan["errors"].append({"path": dest, "problems": problems})
            plan["ok"] = False
            continue
        plan["rendered"][dest] = rendered
        # Applicable-entry metadata; keyed by dest so apply never picks up a
        # sibling variant's template name for the same destination.
        plan["meta"][dest] = {"template": entry["src"], "mode": entry.get("mode")}
        dest_path = repo / dest
        recorded = state["files"].get(dest)
        write_once = entry.get("overwrite_policy") == "write-once"

        if not dest_path.is_file():
            plan["writes"].append({"path": dest, "pillar": entry["pillar"]})
            continue
        if recorded is None:
            plan["conflicts"].append(
                {"path": dest, "reason": "file already exists and was not written by shipshape"}
            )
            continue
        current_hash = sha256_text(dest_path.read_text(encoding="utf-8"))
        if current_hash != recorded["sha256"]:
            plan["conflicts"].append(
                {"path": dest, "reason": "edited since shipshape last wrote it"}
            )
            continue
        if write_once:
            plan["skips"].append({"path": dest, "reason": "write-once, already present"})
        elif rendered == dest_path.read_text(encoding="utf-8"):
            plan["skips"].append({"path": dest, "reason": "up to date"})
        else:
            plan["regenerates"].append({"path": dest, "pillar": entry["pillar"]})
    return plan


def public_plan(plan: dict) -> dict:
    return {key: value for key, value in plan.items() if key not in ("rendered", "meta")}


def cmd_plan(repo: Path, config: dict) -> int:
    print(json.dumps(public_plan(compute_plan(repo, config)), indent=2))
    return 0


def cmd_apply(repo: Path, config: dict, force: list[str]) -> int:
    plan = compute_plan(repo, config)
    if not plan["ok"]:
        print(json.dumps(public_plan(plan), indent=2))
        return 1
    state = load_state(repo)
    state["kit_version"] = kit_version()

    to_write = [item["path"] for item in plan["writes"] + plan["regenerates"]]
    forced, forced_removals, refused = [], [], []
    for conflict in plan["conflicts"]:
        if conflict["path"] in force:
            if conflict.get("action") == "remove":
                forced_removals.append(conflict["path"])
            else:
                forced.append(conflict["path"])
        else:
            refused.append(conflict)
    unknown_force = sorted(set(force) - set(forced) - set(forced_removals))
    if unknown_force:
        return fail(f"--force paths not in conflict list: {unknown_force}")

    removed = []
    for dest in [item["path"] for item in plan["removals"]] + forced_removals:
        dest_path = repo / dest
        if dest_path.is_file():
            dest_path.unlink()
        state["files"].pop(dest, None)
        removed.append(dest)

    written = []
    for dest in to_write + forced:
        content = plan["rendered"][dest]
        dest_path = repo / dest
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(content, encoding="utf-8")
        mode = plan["meta"][dest]["mode"]
        if mode:
            dest_path.chmod(int(mode, 8))
        state["files"][dest] = {
            "template": plan["meta"][dest]["template"],
            "sha256": sha256_text(content),
            "kit_version": state["kit_version"],
        }
        written.append(dest)

    state_path = repo / ".sdlc" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "written": written,
                "removed": removed,
                "forced": forced + forced_removals,
                "skipped": plan["skips"],
                "conflicts_untouched": refused,
            },
            indent=2,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="render.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init-config")
    p_init.add_argument("repo")
    p_init.add_argument("--detect", required=True)
    p_init.add_argument("--set", action="append", default=[], dest="overrides")

    p_set = sub.add_parser("set-config")
    p_set.add_argument("repo")
    p_set.add_argument("--set", action="append", default=[], dest="overrides", required=True)

    p_plan = sub.add_parser("plan")
    p_plan.add_argument("repo")

    p_apply = sub.add_parser("apply")
    p_apply.add_argument("repo")
    p_apply.add_argument("--force", action="append", default=[])

    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        return fail(f"not a directory: {repo}")

    if args.command == "init-config":
        detect_file = Path(args.detect)
        if not detect_file.is_file():
            return fail(f"detect file not found: {detect_file}")
        return cmd_init_config(repo, detect_file, args.overrides)

    config_path = repo / ".sdlc" / "config.json"
    if not config_path.is_file():
        return fail(
            "no .sdlc/config.json in this repo - run init-config first "
            "(or /shipshape-init from Claude Code)"
        )
    config = load_json(config_path)
    if args.command == "set-config":
        for override in args.overrides:
            if "=" not in override:
                return fail(f"--set expects key=value, got: {override}")
            key, _, value = override.partition("=")
            set_dotted(config, key, value)
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"ok": True, "config": config}, indent=2))
        return 0
    if args.command == "plan":
        return cmd_plan(repo, config)
    return cmd_apply(repo, config, args.force)


if __name__ == "__main__":
    sys.exit(main())
