#!/usr/bin/env python3
"""Create or refresh an optional GitHub Projects board (ADR 0002: stdlib only).

Planning is read-only. Applying adds one board when none is recorded, then
adds only missing fields and open issues. It never renames or deletes a
field or item a person already added. "Blocked by" stays in issue text.

Stdout is one JSON object. A token without the project scope is a plain
next step, not a crash.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
REPO_RE = re.compile(rf"^{LOGIN_RE.pattern[1:-1]}/[A-Za-z0-9._-]{{1,100}}$")
ISSUE_URL_RE = re.compile(r"/issues/(\d+)$")
OWNER_FIELD = "Owner"
GATE_FIELD = "Gate"
GATE_OPTIONS = ("build", "release", "pilot")
ROLE_FOR_PERMISSION = {"pull": "READER", "push": "WRITER", "admin": "ADMIN"}
SCOPE_MARKERS = (
    "missing required scope",
    "read:project",
    "project scope",
    "gh auth refresh",
    "resource not accessible by integration",
)
SCOPE_MESSAGE = (
    "GitHub needs permission to manage Projects (the board of issues). "
    "Run `gh auth refresh -s project`, then try again."
)
SCOPE_NEXT = "run `gh auth refresh -s project`"
CLICK_PATH = "Open the project, choose Settings, then Manage access, and invite them there."
PAGE_SIZE = 100
PAGE_CAP = 20


class BoardError(Exception):
    def __init__(self, payload: dict, code: int = 1):
        super().__init__(payload.get("message", "project board request failed"))
        self.payload = payload
        self.code = code


class CommandFailed(BoardError):
    """A gh failure that still has a JSON payload, so callers can recover it."""

    def __init__(self, stdout: str, stderr: str):
        self.stdout = stdout
        self.stderr = stderr
        self.text = f"{stderr}\n{stdout}"
        super().__init__(
            fail(
                "github_command_failed",
                "GitHub's command line tool did not finish the board request.",
                "Run `gh auth status`, then try again.",
                detail=safe_detail(self.text),
            )
        )


def scope_payload(project: dict | None = None) -> dict:
    payload = {
        "ok": False,
        "error": "missing_project_scope",
        "message": SCOPE_MESSAGE,
        "next_action": SCOPE_NEXT,
    }
    if project is not None:
        payload["project"] = project
    return payload


def fail(error: str, message: str, next_action: str, **extra) -> dict:
    return {"ok": False, "error": error, "message": message, "next_action": next_action, **extra}


def is_scope_error(text: str) -> bool:
    lowered = text.casefold()
    return any(marker in lowered for marker in SCOPE_MARKERS)


def safe_detail(text: str) -> str:
    compact = " ".join(text.split())
    if re.search(r"\b(?:ghp_|github_pat_|gho_|ghu_|ghs_)[A-Za-z0-9_]+", compact):
        return "GitHub returned text that looked like a credential, so it was left out."
    return compact[:300]


def run_gh(args: list[str], stdin: str | None = None) -> str:
    try:
        completed = subprocess.run(
            ["gh", *args],
            input=stdin,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError as error:
        raise BoardError(
            fail(
                "gh_missing",
                "GitHub's command line tool is not available, so the board could not be changed.",
                "Install gh, run `gh auth login`, then run `gh auth refresh -s project`.",
            )
        ) from error
    except subprocess.TimeoutExpired as error:
        raise BoardError(
            fail(
                "gh_timeout",
                "GitHub's command line tool timed out before the board could be checked.",
                "Run the command again once GitHub answers.",
            )
        ) from error
    except OSError as error:
        raise BoardError(
            fail(
                "gh_unavailable",
                "GitHub's command line tool could not be started.",
                "Install gh, then run the command again.",
            )
        ) from error
    if completed.returncode != 0:
        text = f"{completed.stderr}\n{completed.stdout}"
        if is_scope_error(text):
            raise BoardError(scope_payload())
        raise CommandFailed(completed.stdout, completed.stderr)
    return completed.stdout


def parse_json(text: str) -> object:
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise BoardError(
            fail(
                "bad_response",
                "GitHub returned something that was not a project record.",
                "Run `gh auth status`, then try again.",
            )
        ) from error


def load_config(repo: Path) -> dict:
    path = repo / ".sdlc" / "config.json"
    if not path.is_file():
        raise BoardError(
            fail(
                "not_set_up",
                "This folder has no shipshape setup yet, so there is no board setting to use.",
                "Run /shipshape-init.",
            )
        )
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BoardError(
            fail(
                "invalid_config",
                "`.sdlc/config.json` could not be read, so the board was left alone.",
                "Run /shipshape-customize and correct the setup file.",
            )
        ) from error
    if not isinstance(config, dict):
        raise BoardError(
            fail(
                "invalid_config",
                "`.sdlc/config.json` is not a JSON object, so the board was left alone.",
                "Run /shipshape-customize and correct the setup file.",
            )
        )
    return config


def repository_slug(config: dict) -> tuple[str, str]:
    repository = config.get("repo")
    slug = repository.get("owner_repo") if isinstance(repository, dict) else ""
    if not isinstance(slug, str) or REPO_RE.fullmatch(slug) is None:
        raise BoardError(
            fail(
                "no_repository",
                "This folder is not connected to GitHub yet, so there is nowhere to put the board.",
                "Connect the GitHub remote, then run /shipshape-customize again.",
            )
        )
    owner, name = slug.split("/", 1)
    return owner, name


def board_title(config: dict, repo_name: str) -> str:
    raw = config.get("project_name")
    name = " ".join(raw.split()) if isinstance(raw, str) else ""
    if not name:
        name = repo_name
    return f"{name} delivery"[:120]


def owner_options(config: dict) -> list[str]:
    options: list[str] = []
    owners = config.get("owners")
    if isinstance(owners, dict):
        for value in owners.values():
            if not isinstance(value, str):
                continue
            login = value[1:] if value.startswith("@") else value
            if LOGIN_RE.fullmatch(login) and login not in options:
                options.append(login)
    if "external" not in options:
        options.append("external")
    return options


def recorded_project(config: dict) -> tuple[str, int] | None:
    project = config.get("project")
    if not isinstance(project, dict):
        return None
    number = project.get("number")
    owner = project.get("owner")
    if type(number) is not int or number < 1 or not isinstance(owner, str):
        return None
    if LOGIN_RE.fullmatch(owner) is None:
        return None
    return owner, number


def project_record(owner: str, number: int, title: str, url: str) -> dict:
    return {"number": number, "owner": owner, "title": title, "url": url}


def config_set(record: dict) -> dict:
    return {
        "project.number": record["number"],
        "project.owner": record["owner"],
        "project.title": record["title"],
    }


def as_projects(payload: object) -> list[dict]:
    if isinstance(payload, dict):
        payload = payload.get("projects", [])
    if not isinstance(payload, list):
        raise BoardError(
            fail(
                "bad_response",
                "GitHub returned a project list that could not be read.",
                "Run `gh auth status`, then try again.",
            )
        )
    return [item for item in payload if isinstance(item, dict)]


def _page_or_stop(page_info: object, seen: int) -> str | None:
    if not isinstance(page_info, dict) or page_info.get("hasNextPage") is not True:
        return None
    cursor = page_info.get("endCursor")
    if not isinstance(cursor, str) or not cursor:
        raise BoardError(
            fail(
                "bad_response",
                "GitHub said another page of results exists but did not give a way to read it.",
                "Run `gh auth status`, then try again.",
            )
        )
    if seen >= PAGE_CAP:
        raise BoardError(
            fail(
                "truncated",
                "GitHub returned more results than this check will read, so nothing was changed.",
                "Finish the remaining items by hand.",
            )
        )
    return cursor


def list_projects(owner: str) -> list[dict]:
    """Every open and closed project for this owner, following GraphQL pages.

    ProjectV2 has no collaborators field. Listing uses projectsV2, which does.
    """
    query = """
    query($login: String!, $after: String) {
      user(login: $login) {
        projectsV2(first: PAGE_SIZE, after: $after) {
          pageInfo { hasNextPage endCursor }
          nodes { number title closed url }
        }
      }
      organization(login: $login) {
        projectsV2(first: PAGE_SIZE, after: $after) {
          pageInfo { hasNextPage endCursor }
          nodes { number title closed url }
        }
      }
    }
    """.replace("PAGE_SIZE", str(PAGE_SIZE))
    collected: list[dict] = []
    cursor: str | None = None
    seen = 0
    while True:
        data = graphql(query, {"login": owner, "after": cursor})
        connection = None
        for root in ("user", "organization"):
            node = data.get(root)
            if isinstance(node, dict) and isinstance(node.get("projectsV2"), dict):
                connection = node["projectsV2"]
                break
        if connection is None:
            raise BoardError(
                fail(
                    "bad_response",
                    "GitHub did not return a project list for that owner.",
                    "Run `gh auth status`, then try again.",
                )
            )
        collected.extend(as_projects(connection.get("nodes")))
        seen += 1
        cursor = _page_or_stop(connection.get("pageInfo"), seen)
        if cursor is None:
            return collected


def view_project(owner: str, number: int) -> dict | None:
    try:
        payload = parse_json(
            run_gh(["project", "view", str(number), "--owner", owner, "--format", "json"])
        )
    except CommandFailed as error:
        if is_scope_error(error.text):
            raise BoardError(scope_payload()) from error
        lowered = error.text.casefold()
        if "could not resolve" in lowered or "not found" in lowered or "http 404" in lowered:
            return None
        raise BoardError(
            fail(
                "github_command_failed",
                "GitHub could not show the project board.",
                "Run `gh auth status`, then try again.",
                detail=safe_detail(error.text),
            )
        ) from error
    if not isinstance(payload, dict) or payload.get("number") != number:
        raise BoardError(
            fail(
                "bad_response",
                "GitHub returned a project record that did not match the requested board.",
                "Run /shipshape-customize to create the board.",
            )
        )
    return payload


def find_by_title(owner: str, title: str) -> dict | None:
    matches = []
    for item in list_projects(owner):
        number = item.get("number")
        open_board = item.get("title") == title and item.get("closed") is not True
        if open_board and isinstance(number, int):
            matches.append(item)
    if not matches:
        return None
    return min(matches, key=lambda item: item["number"])


def record_from_payload(owner: str, payload: dict, fallback_title: str) -> dict:
    number = payload.get("number")
    title = payload.get("title") if isinstance(payload.get("title"), str) else fallback_title
    url = payload.get("url") if isinstance(payload.get("url"), str) else ""
    if type(number) is not int:
        raise BoardError(
            fail(
                "bad_response",
                "GitHub created or found a board but did not return its number.",
                "Run /shipshape-customize again and keep the printed project number.",
            )
        )
    return project_record(owner, number, title, url)


def desired_fields(config: dict) -> list[dict]:
    return [
        {"name": OWNER_FIELD, "options": owner_options(config)},
        {"name": GATE_FIELD, "options": list(GATE_OPTIONS)},
    ]


def field_names(owner: str, number: int) -> list[str]:
    payload = parse_json(
        run_gh(
            [
                "project",
                "field-list",
                str(number),
                "--owner",
                owner,
                "--limit",
                "50",
                "--format",
                "json",
            ]
        )
    )
    if isinstance(payload, dict):
        payload = payload.get("fields", [])
    if not isinstance(payload, list):
        raise BoardError(
            fail(
                "bad_response",
                "GitHub returned a field list that could not be read.",
                "Run `gh auth status`, then try again.",
            )
        )
    names = []
    for item in payload:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            names.append(item["name"])
    return names


def item_urls(owner: str, number: int) -> set[str]:
    viewed = view_project(owner, number)
    project_id = viewed.get("id") if isinstance(viewed, dict) else None
    if not isinstance(project_id, str) or not project_id:
        raise BoardError(
            fail(
                "bad_response",
                "GitHub showed the board but not the id needed to read its items.",
                "Run `gh auth status`, then try again.",
            )
        )
    query = """
    query($id: ID!, $after: String) {
      node(id: $id) {
        ... on ProjectV2 {
          items(first: PAGE_SIZE, after: $after) {
            pageInfo { hasNextPage endCursor }
            nodes { content { ... on Issue { url } } }
          }
        }
      }
    }
    """.replace("PAGE_SIZE", str(PAGE_SIZE))
    urls: set[str] = set()
    cursor: str | None = None
    seen = 0
    while True:
        data = graphql(query, {"id": project_id, "after": cursor})
        node = data.get("node")
        connection = node.get("items") if isinstance(node, dict) else None
        if not isinstance(connection, dict):
            raise BoardError(
                fail(
                    "bad_response",
                    "GitHub returned a board item list that could not be read.",
                    "Run `gh auth status`, then try again.",
                )
            )
        for item in connection.get("nodes") or []:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            url = content.get("url") if isinstance(content, dict) else None
            if isinstance(url, str):
                urls.add(url.rstrip("/"))
        seen += 1
        cursor = _page_or_stop(connection.get("pageInfo"), seen)
        if cursor is None:
            return urls


def open_issues(repository: str) -> list[tuple[int, str]]:
    issues: list[tuple[int, str]] = []
    for page in range(1, PAGE_CAP + 1):
        payload = parse_json(
            run_gh(
                [
                    "api",
                    f"repos/{repository}/issues?state=open&per_page={PAGE_SIZE}&page={page}",
                ]
            )
        )
        if not isinstance(payload, list):
            raise BoardError(
                fail(
                    "bad_response",
                    "GitHub returned an issue list that could not be read.",
                    "Run `gh auth status`, then try again.",
                )
            )
        for item in payload:
            if not isinstance(item, dict) or "pull_request" in item:
                continue
            html_url = item.get("html_url")
            raw_url = html_url if isinstance(html_url, str) else item.get("url")
            if not isinstance(raw_url, str):
                continue
            url = raw_url.rstrip("/")
            match = ISSUE_URL_RE.search(url)
            if match is None:
                continue
            number = int(match.group(1))
            if item.get("number") == number or "number" not in item:
                issues.append((number, url))
        if len(payload) < PAGE_SIZE:
            return issues
    raise BoardError(
        fail(
            "truncated",
            "GitHub returned more open issues than this check will read, so nothing was added.",
            "Add the remaining issues from the project board.",
        )
    )


def issues_to_add(repository: str, present: set[str]) -> list[tuple[int, str]]:
    return [(number, url) for number, url in open_issues(repository) if url not in present]


def resolve_project(config: dict, owner: str, title: str) -> tuple[dict | None, bool]:
    """Return the live project and whether the recorded number was missing."""
    recorded = recorded_project(config)
    if recorded is not None:
        recorded_owner, number = recorded
        found = view_project(recorded_owner, number)
        if found is not None:
            return found, False
        titled = find_by_title(owner, title)
        return titled, True
    return find_by_title(owner, title), False


def fields_to_add(config: dict, existing: list[str]) -> list[dict]:
    present = set(existing)
    return [field for field in desired_fields(config) if field["name"] not in present]


def plan_board(repo: Path) -> dict:
    config = load_config(repo)
    if config.get("features", {}).get("project_board") is not True:
        return {"ok": True, "action": "skipped", "reason": "features.project_board is off"}
    owner, repo_name = repository_slug(config)
    repository = f"{owner}/{repo_name}"
    title = board_title(config, repo_name)
    found, recorded_missing = resolve_project(config, owner, title)
    if found is None:
        pending_issues = issues_to_add(repository, set())
        return {
            "ok": True,
            "action": "create",
            "owner": owner,
            "repository": repository,
            "title": title,
            "fields_to_add": desired_fields(config),
            "issues_to_add": [number for number, _url in pending_issues],
            "blocked_by": "left in issue text; not a board field",
            "recorded_project_missing": recorded_missing,
        }
    live_owner = found.get("owner") if isinstance(found.get("owner"), str) else owner
    if isinstance(found.get("owner"), dict) and isinstance(found["owner"].get("login"), str):
        live_owner = found["owner"]["login"]
    number = found["number"]
    record = record_from_payload(live_owner, found, title)
    existing = field_names(live_owner, number)
    pending = issues_to_add(repository, item_urls(live_owner, number))
    return {
        "ok": True,
        "action": "update",
        "owner": live_owner,
        "repository": repository,
        "title": record["title"],
        "project": record,
        "fields_to_add": fields_to_add(config, existing),
        "fields_kept": existing,
        "issues_to_add": [item for item, _url in pending],
        "blocked_by": "left in issue text; not a board field",
        "recorded_project_missing": recorded_missing,
    }


def create_project(owner: str, title: str) -> dict:
    payload = parse_json(
        run_gh(["project", "create", "--owner", owner, "--title", title, "--format", "json"])
    )
    if not isinstance(payload, dict):
        raise BoardError(
            fail(
                "bad_response",
                "GitHub did not confirm the new board.",
                "Run /shipshape-customize again.",
            )
        )
    return payload


def link_project(owner: str, number: int, repository: str) -> None:
    try:
        run_gh(["project", "link", str(number), "--owner", owner, "--repo", repository])
    except CommandFailed as error:
        if "already" in error.text.casefold():
            return
        raise BoardError(
            fail(
                "github_command_failed",
                "The board exists, but it could not be linked to the repository.",
                "Open the repository's Projects tab and link the board by hand.",
                detail=safe_detail(error.text),
            )
        ) from error


def add_field(owner: str, number: int, field: dict) -> None:
    options = ",".join(field["options"])
    try:
        run_gh(
            [
                "project",
                "field-create",
                str(number),
                "--owner",
                owner,
                "--name",
                field["name"],
                "--data-type",
                "SINGLE_SELECT",
                "--single-select-options",
                options,
                "--format",
                "json",
            ]
        )
    except CommandFailed as error:
        if "already" in error.text.casefold():
            return
        raise BoardError(
            fail(
                "github_command_failed",
                f"The {field['name']} column could not be added. Existing columns were left alone.",
                "Add the column from the project board if you still want it.",
                detail=safe_detail(error.text),
            )
        ) from error


def add_issue(owner: str, number: int, url: str) -> bool:
    try:
        run_gh(
            [
                "project",
                "item-add",
                str(number),
                "--owner",
                owner,
                "--url",
                url,
                "--format",
                "json",
            ]
        )
    except CommandFailed as error:
        if "already" in error.text.casefold():
            return False
        raise BoardError(
            fail(
                "github_command_failed",
                "An open issue could not be added. Issues already on the board were left in place.",
                "Open the board and add the remaining issue by hand.",
                detail=safe_detail(error.text),
            )
        ) from error
    return True


def apply_board(repo: Path) -> dict:
    config = load_config(repo)
    if config.get("features", {}).get("project_board") is not True:
        return {"ok": True, "action": "skipped", "reason": "features.project_board is off"}
    owner, repo_name = repository_slug(config)
    repository = f"{owner}/{repo_name}"
    title = board_title(config, repo_name)
    found, recorded_missing = resolve_project(config, owner, title)
    created = False
    if found is None:
        found = create_project(owner, title)
        created = True
    live_owner = owner
    if isinstance(found.get("owner"), str):
        live_owner = found["owner"]
    elif isinstance(found.get("owner"), dict) and isinstance(found["owner"].get("login"), str):
        live_owner = found["owner"]["login"]
    record = record_from_payload(live_owner, found, title)
    try:
        link_project(live_owner, record["number"], repository)
        existing = field_names(live_owner, record["number"])
        added_fields = []
        for field in fields_to_add(config, existing):
            add_field(live_owner, record["number"], field)
            added_fields.append(field["name"])
        present = item_urls(live_owner, record["number"])
        added_issues = []
        for number, url in issues_to_add(repository, present):
            if add_issue(live_owner, record["number"], url):
                added_issues.append(number)
    except BoardError as error:
        error.payload["project"] = record
        error.payload["config_set"] = config_set(record)
        raise
    return {
        "ok": True,
        "action": "created" if created else "updated",
        "project": record,
        "config_set": config_set(record),
        "fields_added": added_fields,
        "fields_kept": existing,
        "issues_added": added_issues,
        "blocked_by": "left in issue text; not a board field",
        "recorded_project_missing": recorded_missing,
    }


def graphql(query: str, variables: dict) -> dict:
    try:
        body = json.dumps({"query": query, "variables": variables})
        text = run_gh(["api", "graphql", "--input", "-"], stdin=body)
    except CommandFailed as error:
        if is_scope_error(error.text):
            raise BoardError(scope_payload()) from error
        raise BoardError(
            fail(
                "github_command_failed",
                "GitHub could not update who can see the project board.",
                CLICK_PATH,
                detail=safe_detail(error.text),
            )
        ) from error
    payload = parse_json(text)
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        message = ""
        if isinstance(payload, dict) and payload.get("errors"):
            message = json.dumps(payload["errors"])
        if is_scope_error(message):
            raise BoardError(scope_payload())
        raise BoardError(
            fail(
                "github_command_failed",
                "GitHub could not update who can see the project board.",
                CLICK_PATH,
                detail=safe_detail(message),
            )
        )
    return payload["data"]


def project_access(repo: Path, user: str, permission: str, *, mutate: bool) -> dict:
    if not isinstance(user, str) or LOGIN_RE.fullmatch(user) is None:
        raise BoardError(
            fail(
                "invalid_user",
                "The board invite needs the person's exact GitHub login, without an @.",
                "Confirm the login, then ask again.",
            )
        )
    role = ROLE_FOR_PERMISSION[permission]
    config = load_config(repo)
    if config.get("features", {}).get("project_board") is not True:
        return {"ok": True, "action": "skipped", "reason": "features.project_board is off"}
    recorded = recorded_project(config)
    if recorded is None:
        raise BoardError(
            fail(
                "no_board",
                "The project board is turned on, but no board is linked yet.",
                "Run /shipshape-customize to create the board.",
            )
        )
    owner, number = recorded
    found = view_project(owner, number)
    if found is None:
        raise BoardError(
            fail(
                "no_board",
                f"Project #{number} is recorded, but GitHub has no board with that number.",
                "Run /shipshape-customize to create the board.",
            )
        )
    if found.get("public") is True and role == "READER":
        return {
            "ok": True,
            "action": "already_covered",
            "user": user,
            "role": role,
            "reason": "This project is public, so looking at it needs no invite.",
        }
    # ProjectV2 has no field that reads a person's current role, and
    # updateProjectV2Collaborators would set a role even when that lowers it.
    # Neither plan nor apply changes membership.
    del mutate
    return {
        "ok": True,
        "action": "manual",
        "user": user,
        "role": role,
        "reason": (
            "GitHub's project API does not show this person's current board role, "
            f"so access was not changed. Invite {user} with {role.lower()} access "
            "if they do not already have it."
        ),
        "next_action": CLICK_PATH,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="project_board.py")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "apply"):
        command = sub.add_parser(name)
        command.add_argument("--repo", required=True)
    for name in ("access-plan", "access-apply"):
        command = sub.add_parser(name)
        command.add_argument("--repo", required=True)
        command.add_argument("--user", required=True)
        command.add_argument("--permission", required=True, choices=sorted(ROLE_FOR_PERMISSION))
    args = parser.parse_args(argv)
    repo = Path(args.repo)
    if not repo.is_dir():
        print(
            json.dumps(
                fail(
                    "not_a_repository",
                    "The repository path is not a folder.",
                    "Pass the repository folder.",
                )
            )
        )
        return 2
    try:
        if args.command == "plan":
            payload = plan_board(repo)
        elif args.command == "apply":
            payload = apply_board(repo)
        else:
            payload = project_access(
                repo,
                args.user,
                args.permission,
                mutate=args.command == "access-apply",
            )
    except BoardError as error:
        print(json.dumps(error.payload, indent=2))
        return error.code
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
