"""GitHub Projects support: optional, idempotent, and quiet when the token cannot see projects."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import init_repo, prepend_to_path, run_script

CREATE_BOARD = "Run /shipshape-customize to create the board."
SCOPE_HINT = "gh auth refresh -s project"
ROOT = Path(__file__).resolve().parent.parent

FAKE_GH = r"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

root = Path(os.environ["FAKE_GH_STATE"])
calls = root / "calls.jsonl"
state_path = root / "state.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
with calls.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(sys.argv[1:]) + "\n")


def save() -> None:
    state_path.write_text(json.dumps(state), encoding="utf-8")


def flag(name: str) -> str | None:
    if name not in sys.argv:
        return None
    return sys.argv[sys.argv.index(name) + 1]


if os.environ.get("FAKE_GH_MODE") == "scope":
    sys.stderr.write(
        "error: your authentication token is missing required scopes [project]\n"
        "To request it, run: gh auth refresh -s project\n"
    )
    sys.exit(1)

args = sys.argv[1:]
if args[:2] == ["api", "graphql"]:
    command = "graphql"
elif args[0] == "api":
    command = "api"
elif len(args) > 1 and args[0] == "project":
    command = args[1]
else:
    command = args[0]
if os.environ.get("FAKE_GH_FAIL") and command == os.environ["FAKE_GH_FAIL"]:
    sys.stderr.write("HTTP 500\n")
    sys.exit(1)


def projects_for(owner: str) -> list[dict]:
    return [item for item in state["projects"] if item["owner"] == owner]


def find_project(owner: str, number: int) -> dict | None:
    for item in projects_for(owner):
        if item["number"] == number:
            return item
    return None


def key_for(owner: str, number: int) -> str:
    return f"{owner}/{number}"


if args[:2] == ["project", "list"]:
    print(json.dumps(projects_for(flag("--owner") or "")))
elif args[:2] == ["project", "view"]:
    project = find_project(flag("--owner") or "", int(args[2]))
    if project is None:
        sys.stderr.write(f"error: Could not resolve to a ProjectV2 with the number {args[2]}\n")
        sys.exit(1)
    print(json.dumps(project))
elif args[:2] == ["project", "create"]:
    owner = flag("--owner")
    title = flag("--title")
    number = 1 + max((item["number"] for item in state["projects"]), default=0)
    project = {
        "owner": owner,
        "number": number,
        "title": title,
        "id": f"PVT_{number}",
        "url": f"https://github.com/users/{owner}/projects/{number}",
        "public": False,
        "closed": False,
    }
    state["projects"].append(project)
    state["fields"].setdefault(key_for(owner, number), [{"name": "Status"}, {"name": "Title"}])
    state["items"].setdefault(key_for(owner, number), [])
    save()
    print(json.dumps(project))
elif args[:2] == ["project", "link"]:
    project = find_project(flag("--owner") or "", int(args[2]))
    state["links"][project["id"]] = flag("--repo")
    save()
elif args[:2] == ["project", "field-list"]:
    print(json.dumps(state["fields"].get(key_for(flag("--owner") or "", int(args[2])), [])))
elif args[:2] == ["project", "field-create"]:
    owner = flag("--owner") or ""
    number = int(args[2])
    name = flag("--name")
    options = (flag("--single-select-options") or "").split(",")
    field_key = key_for(owner, number)
    fields = state["fields"].setdefault(field_key, [])
    if any(item.get("name") == name for item in fields):
        sys.stderr.write(f"error: field {name} already exists\n")
        sys.exit(1)
    fields.append({"name": name, "options": options})
    save()
    print(json.dumps({"name": name, "options": options}))
elif args[:2] == ["project", "item-list"]:
    item_key = key_for(flag("--owner") or "", int(args[2]))
    print(json.dumps({"items": state["items"].get(item_key, [])}))
elif args[:2] == ["project", "item-add"]:
    owner = flag("--owner") or ""
    number = int(args[2])
    url = flag("--url")
    items = state["items"].setdefault(key_for(owner, number), [])
    if any(item.get("content", {}).get("url") == url for item in items):
        sys.stderr.write("error: item already exists on the project\n")
        sys.exit(1)
    items.append({"content": {"url": url, "type": "Issue"}})
    save()
    print(json.dumps({"content": {"url": url}}))
elif args[:2] == ["issue", "list"]:
    sys.stderr.write("unexpected issue list; open issues are read with gh api\n")
    sys.exit(2)
elif args[0] == "api" and len(args) > 1 and args[1] != "graphql":
    endpoint = args[1]
    path, _, query = endpoint.partition("?")
    params = dict(pair.split("=", 1) for pair in query.split("&") if "=" in pair)
    if "/issues" not in path:
        sys.stderr.write(f"unexpected gh api: {endpoint}\n")
        sys.exit(2)
    repo = path.removeprefix("repos/").split("/issues")[0]
    page = int(params.get("page", "1"))
    per_page = int(params.get("per_page", "100"))
    items = state["open_issues"].get(repo, [])
    start = (page - 1) * per_page
    print(json.dumps(items[start : start + per_page]))
elif args[:3] == ["api", "graphql", "--input"]:
    payload = json.loads(sys.stdin.read())
    query = payload["query"]
    variables = payload["variables"]
    with calls.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(["graphql-query", query]) + "\n")
    if "collaborators" in query or "updateProjectV2Collaborators" in query:
        print(
            json.dumps(
                {
                    "errors": [
                        {
                            "message": "Field 'collaborators' doesn't exist on type 'ProjectV2'",
                        }
                    ]
                }
            )
        )
    elif "projectsV2" in query:
        login = variables["login"]
        owned = sorted(
            (item for item in state["projects"] if item["owner"] == login),
            key=lambda item: item["number"],
        )
        after = variables.get("after")
        start = int(after) if after else 0
        chunk = owned[start : start + 100]
        end = start + len(chunk)
        stuck = state.get("projects_always_more") is True
        has_next = stuck or end < len(owned)
        nodes = [
            {
                "number": item["number"],
                "title": item["title"],
                "closed": item.get("closed", False),
                "url": item.get("url", ""),
            }
            for item in chunk
        ]
        connection = {
            "pageInfo": {"hasNextPage": has_next, "endCursor": str(end) if has_next else None},
            "nodes": nodes,
        }
        user_node = connection if state.get("owner_kind", "user") == "user" else None
        org_node = connection if state.get("owner_kind") == "organization" else None
        if user_node is None and org_node is None:
            user_node = connection
        print(
            json.dumps(
                {
                    "data": {
                        "user": None if user_node is None else {"projectsV2": user_node},
                        "organization": None if org_node is None else {"projectsV2": org_node},
                    }
                }
            )
        )
    elif "items(first:" in query:
        project_id = variables["id"]
        project = next(item for item in state["projects"] if item["id"] == project_id)
        item_key = f"{project['owner']}/{project['number']}"
        nodes = []
        for item in state["items"].get(item_key, []):
            content = item.get("content") if isinstance(item, dict) else None
            url = content.get("url") if isinstance(content, dict) else None
            nodes.append({"content": {"url": url} if url else None})
        after = variables.get("after")
        start = int(after) if after else 0
        chunk = nodes[start : start + 100]
        end = start + len(chunk)
        has_next = end < len(nodes)
        print(
            json.dumps(
                {
                    "data": {
                        "node": {
                            "items": {
                                "pageInfo": {
                                    "hasNextPage": has_next,
                                    "endCursor": str(end) if has_next else None,
                                },
                                "nodes": chunk,
                            }
                        }
                    }
                }
            )
        )
    else:
        sys.stderr.write("unexpected graphql query\n")
        sys.exit(2)
else:
    sys.stderr.write(f"unexpected gh command: {args}\n")
    sys.exit(2)
"""


@pytest.fixture(autouse=True)
def pin_doctor_subprocess_path(hermetic_doctor_path):
    return hermetic_doctor_path


def empty_state() -> dict:
    return {
        "projects": [],
        "fields": {},
        "items": {},
        "links": {},
        "open_issues": {},
        "users": {},
        "user_ids": {},
        "collaborators": {},
    }


def install_fake_gh(
    tmp_path, monkeypatch, state: dict | None = None, *, mode: str = "", fail: str = ""
):
    root = tmp_path / "gh-state"
    root.mkdir()
    (root / "state.json").write_text(json.dumps(state or empty_state()), encoding="utf-8")
    (root / "calls.jsonl").write_text("", encoding="utf-8")
    bin_dir = tmp_path / "gh-bin"
    bin_dir.mkdir()
    executable = bin_dir / "gh"
    executable.write_text(FAKE_GH, encoding="utf-8")
    executable.chmod(0o755)
    prepend_to_path(monkeypatch, bin_dir)
    monkeypatch.setenv("FAKE_GH_STATE", str(root))
    monkeypatch.setenv("FAKE_GH_MODE", mode)
    monkeypatch.setenv("FAKE_GH_FAIL", fail)
    return root


def calls(root: Path) -> list[list[str]]:
    text = (root / "calls.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line]


def write_config(root: Path, **updates) -> None:
    path = root / ".sdlc" / "config.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    config.update(updates)
    path.write_text(json.dumps(config), encoding="utf-8")


def board_repo(tmp_path) -> Path:
    repo = init_repo("repo-python", tmp_path)
    write_config(
        repo,
        project_name="hello",
        features={
            **json.loads((repo / ".sdlc" / "config.json").read_text())["features"],
            "project_board": True,
        },
        repo={"owner_repo": "octocat/hello"},
        owners={"default": "@octocat", "second": "@hubot"},
    )
    return repo


def test_project_board_defaults_off(tmp_path):
    repo = init_repo("repo-python", tmp_path)
    config = json.loads((repo / ".sdlc" / "config.json").read_text(encoding="utf-8"))

    assert config["features"]["project_board"] is False
    assert "project" not in config


def test_project_record_must_be_a_real_board(tmp_path):
    repo = init_repo("repo-python", tmp_path)

    code, payload = run_script(
        "render.py",
        "set-config",
        repo,
        "--set",
        "project.number=0",
        "--set",
        "project.owner=octocat",
        "--set",
        "project.title=hello delivery",
    )

    assert code == 1
    assert "project.number" in payload["error"]


def test_enabled_board_uses_the_project_workflow_variant(tmp_path):
    plain_root = tmp_path / "plain"
    enabled_root = tmp_path / "enabled"
    plain_root.mkdir()
    enabled_root.mkdir()
    plain = init_repo("repo-python", plain_root)
    enabled = init_repo("repo-python", enabled_root, overrides=["features.project_board=true"])
    assert run_script("render.py", "apply", plain)[0] == 0
    code, result = run_script("render.py", "apply", enabled)

    plain_workflow = (plain / ".github/workflows/shipshape-doctor.yml").read_text(encoding="utf-8")
    project_workflow = (enabled / ".github/workflows/shipshape-doctor.yml").read_text(
        encoding="utf-8"
    )
    assert code == 0, result
    assert "projects: write" not in plain_workflow
    assert "gh project item-add" not in plain_workflow
    assert "projects: write" not in project_workflow
    assert "gh label view" not in project_workflow
    assert "gh api " in project_workflow
    assert "gh project item-add" in project_workflow
    assert SCOPE_HINT in project_workflow
    assert "SHIPSHAPE_PROJECT_TOKEN" in project_workflow


def test_plan_is_read_only_and_names_fields_without_a_blocked_by_column(tmp_path, monkeypatch):
    repo = board_repo(tmp_path)
    state = empty_state()
    state["open_issues"]["octocat/hello"] = [
        {"number": 3, "url": "https://github.com/octocat/hello/issues/3"}
    ]
    root = install_fake_gh(tmp_path, monkeypatch, state)

    code, payload = run_script("project_board.py", "plan", "--repo", repo)

    assert code == 0, payload
    assert payload["action"] == "create"
    assert payload["title"] == "hello delivery"
    assert payload["owner"] == "octocat"
    assert payload["fields_to_add"] == [
        {"name": "Owner", "options": ["octocat", "hubot", "external"]},
        {"name": "Gate", "options": ["build", "release", "pilot"]},
    ]
    assert payload["issues_to_add"] == [3]
    assert "Blocked by" not in {field["name"] for field in payload["fields_to_add"]}
    mutations = {"create", "link", "field-create", "item-add", "delete"}
    assert all(call[1] not in mutations for call in calls(root))


def test_apply_creates_once_then_only_adds_what_is_missing(tmp_path, monkeypatch):
    repo = board_repo(tmp_path)
    state = empty_state()
    state["open_issues"]["octocat/hello"] = [
        {"number": 3, "url": "https://github.com/octocat/hello/issues/3"},
        {"number": 4, "url": "https://github.com/octocat/hello/pull/4"},
    ]
    root = install_fake_gh(tmp_path, monkeypatch, state)

    code, created = run_script("project_board.py", "apply", "--repo", repo)
    first_calls = calls(root)
    write_config(
        repo,
        project={
            "number": created["project"]["number"],
            "owner": created["project"]["owner"],
            "title": created["project"]["title"],
        },
    )
    (root / "calls.jsonl").write_text("", encoding="utf-8")
    code_again, updated = run_script("project_board.py", "apply", "--repo", repo)

    assert code == 0, created
    assert created["action"] == "created"
    assert created["project"]["number"] == 1
    assert created["fields_added"] == ["Owner", "Gate"]
    assert created["issues_added"] == [3]
    assert created["config_set"]["project.number"] == 1
    assert any(call[1] == "link" for call in first_calls)
    assert code_again == 0, updated
    assert updated["action"] == "updated"
    assert updated["fields_added"] == []
    assert updated["issues_added"] == []
    assert updated["project"]["number"] == 1
    assert all("delete" not in arg for call in calls(root) for arg in call)


def test_apply_keeps_fields_and_items_a_person_added(tmp_path, monkeypatch):
    repo = board_repo(tmp_path)
    write_config(repo, project={"number": 4, "owner": "octocat", "title": "renamed by hand"})
    state = empty_state()
    state["projects"].append(
        {
            "owner": "octocat",
            "number": 4,
            "title": "renamed by hand",
            "id": "PVT_4",
            "url": "https://github.com/users/octocat/projects/4",
            "public": False,
            "closed": False,
        }
    )
    state["fields"]["octocat/4"] = [
        {"name": "Status"},
        {"name": "Owner", "options": ["octocat"]},
        {"name": "Priority"},
    ]
    state["items"]["octocat/4"] = [
        {"content": {"url": "https://github.com/octocat/hello/issues/9", "type": "Issue"}}
    ]
    state["open_issues"]["octocat/hello"] = [
        {"number": 9, "url": "https://github.com/octocat/hello/issues/9"},
        {"number": 10, "url": "https://github.com/octocat/hello/issues/10"},
    ]
    root = install_fake_gh(tmp_path, monkeypatch, state)

    code, payload = run_script("project_board.py", "apply", "--repo", repo)
    saved = json.loads((root / "state.json").read_text(encoding="utf-8"))

    assert code == 0, payload
    assert payload["fields_added"] == ["Gate"]
    assert payload["fields_kept"] == ["Status", "Owner", "Priority"]
    assert payload["issues_added"] == [10]
    assert saved["projects"][0]["title"] == "renamed by hand"
    assert [field["name"] for field in saved["fields"]["octocat/4"]] == [
        "Status",
        "Owner",
        "Priority",
        "Gate",
    ]


def test_missing_project_scope_is_a_plain_next_step(tmp_path, monkeypatch):
    repo = board_repo(tmp_path)
    root = install_fake_gh(tmp_path, monkeypatch, mode="scope")

    code, payload = run_script("project_board.py", "apply", "--repo", repo)

    assert code == 1
    assert payload["ok"] is False
    assert payload["error"] == "missing_project_scope"
    assert SCOPE_HINT in payload["message"]
    assert SCOPE_HINT in payload["next_action"]
    assert "traceback" not in payload["message"].casefold()
    assert all(call[1] != "create" for call in calls(root))


def test_repository_access_does_not_cover_the_board(tmp_path, monkeypatch):
    repo = board_repo(tmp_path)
    write_config(repo, project={"number": 4, "owner": "octocat", "title": "hello delivery"})
    state = empty_state()
    state["projects"].append(
        {
            "owner": "octocat",
            "number": 4,
            "title": "hello delivery",
            "id": "PVT_4",
            "url": "https://github.com/users/octocat/projects/4",
            "public": False,
            "closed": False,
        }
    )
    state["collaborators"]["PVT_4"] = {"ada": "WRITER"}
    root = install_fake_gh(tmp_path, monkeypatch, state)

    covered, covered_payload = run_script(
        "project_board.py", "access-plan", "--repo", repo, "--user", "ada", "--permission", "push"
    )
    grant, grant_payload = run_script(
        "project_board.py", "access-plan", "--repo", repo, "--user", "sam", "--permission", "push"
    )
    (root / "calls.jsonl").write_text("", encoding="utf-8")
    applied, applied_payload = run_script(
        "project_board.py", "access-apply", "--repo", repo, "--user", "sam", "--permission", "push"
    )
    saved = json.loads((root / "state.json").read_text(encoding="utf-8"))

    assert covered == 0, covered_payload
    assert covered_payload["action"] == "manual"
    assert covered_payload["role"] == "WRITER"
    assert grant == 0, grant_payload
    assert grant_payload["action"] == "manual"
    assert grant_payload["role"] == "WRITER"
    assert "was not changed" in grant_payload["reason"]
    assert applied == 0, applied_payload
    assert applied_payload["action"] == "manual"
    assert saved["collaborators"]["PVT_4"] == {"ada": "WRITER"}
    assert all("updateProjectV2Collaborators" not in json.dumps(call) for call in calls(root))
    assert all("collaborators(" not in json.dumps(call) for call in calls(root))


def test_public_read_needs_no_second_invite(tmp_path, monkeypatch):
    repo = board_repo(tmp_path)
    write_config(repo, project={"number": 4, "owner": "octocat", "title": "hello delivery"})
    state = empty_state()
    state["projects"].append(
        {
            "owner": "octocat",
            "number": 4,
            "title": "hello delivery",
            "id": "PVT_4",
            "url": "https://github.com/users/octocat/projects/4",
            "public": True,
            "closed": False,
        }
    )
    install_fake_gh(tmp_path, monkeypatch, state)

    code, payload = run_script(
        "project_board.py", "access-plan", "--repo", repo, "--user", "sam", "--permission", "pull"
    )

    assert code == 0, payload
    assert payload["action"] == "already_covered"


def test_access_scope_failure_stays_actionable(tmp_path, monkeypatch):
    repo = board_repo(tmp_path)
    write_config(repo, project={"number": 4, "owner": "octocat", "title": "hello delivery"})
    install_fake_gh(tmp_path, monkeypatch, mode="scope")

    code, payload = run_script(
        "project_board.py", "access-apply", "--repo", repo, "--user", "sam", "--permission", "push"
    )

    assert code == 1
    assert payload["error"] == "missing_project_scope"
    assert SCOPE_HINT in payload["message"]


def healthy_repo(tmp_path):
    repo = init_repo("repo-python", tmp_path)
    code, payload = run_script("render.py", "apply", repo)
    assert code == 0, payload
    config_path = repo / ".sdlc" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["features"]["branch_protection"] = False
    config_path.write_text(json.dumps(config), encoding="utf-8")
    subprocess.run(["git", "init", "-qb", "main"], cwd=repo, check=True)
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    (hooks / "pre-commit").symlink_to("../../.sdlc/hooks/secret-guard.sh")
    return repo


def checks_by_name(payload: dict) -> dict:
    return {item["name"]: item for section in payload["sections"] for item in section["checks"]}


def enable_board(repo: Path, *, number: int | None = 4, workflow: bool = True) -> None:
    config_path = repo / ".sdlc" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["features"]["project_board"] = True
    config["repo"]["owner_repo"] = "octocat/hello"
    if number is None:
        config.pop("project", None)
    else:
        config["project"] = {"number": number, "owner": "octocat", "title": "hello delivery"}
    config_path.write_text(json.dumps(config), encoding="utf-8")
    if workflow:
        path = repo / ".github" / "workflows" / "shipshape-doctor.yml"
        text = path.read_text(encoding="utf-8")
        text = text.replace("\n  projects: write", "")
        if "SHIPSHAPE_PROJECT_TOKEN" not in text:
            text += "\n# SHIPSHAPE_PROJECT_TOKEN\n"
        if "gh project item-add" not in text:
            text += "\n# gh project item-add\n"
        path.write_text(text, encoding="utf-8")


def install_doctor_gh(tmp_path, monkeypatch, script: str) -> None:
    bin_dir = tmp_path / "doctor-gh"
    bin_dir.mkdir()
    executable = bin_dir / "gh"
    executable.write_text(script, encoding="utf-8")
    executable.chmod(0o755)
    prepend_to_path(monkeypatch, bin_dir)


def test_doctor_skips_the_board_when_the_feature_is_off(tmp_path):
    repo = healthy_repo(tmp_path)
    config_path = repo / ".sdlc" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["features"]["project_board"] = False
    config_path.write_text(json.dumps(config), encoding="utf-8")

    code, payload = run_script("doctor.py", repo)
    checks = checks_by_name(payload)

    assert code == 0, payload
    assert "project board" not in checks
    assert checks["unused settings"]["status"] == "PASS"


def test_doctor_warns_when_the_board_is_not_linked(tmp_path):
    repo = healthy_repo(tmp_path)
    enable_board(repo, number=None, workflow=False)

    code, payload = run_script("doctor.py", repo)
    check = checks_by_name(payload)["project board"]

    assert code == 0, payload
    assert check["status"] == "WARN"
    assert check["next_action"] == CREATE_BOARD


def test_doctor_passes_when_the_linked_board_receives_health_issues(tmp_path, monkeypatch):
    repo = healthy_repo(tmp_path)
    enable_board(repo)
    install_doctor_gh(
        tmp_path,
        monkeypatch,
        '#!/bin/sh\nprintf \'%s\\n\' \'{"number": 4, "id": "PVT_4"}\'\n',
    )

    code, payload = run_script("doctor.py", repo)
    check = checks_by_name(payload)["project board"]

    assert code == 0, payload
    assert check["status"] == "PASS"
    assert "project #4" in check["detail"]
    assert "does not prove an item was added" in check["detail"]


def test_doctor_warns_instead_of_failing_when_the_token_lacks_project_scope(tmp_path, monkeypatch):
    repo = healthy_repo(tmp_path)
    enable_board(repo)
    install_doctor_gh(
        tmp_path,
        monkeypatch,
        "#!/bin/sh\n"
        "echo 'error: your authentication token is missing required scopes [project]' >&2\n"
        "echo 'To request it, run: gh auth refresh -s project' >&2\n"
        "exit 1\n",
    )

    code, payload = run_script("doctor.py", repo)
    check = checks_by_name(payload)["project board"]

    assert code == 0, payload
    assert check["status"] == "WARN"
    assert SCOPE_HINT in check["detail"]
    assert SCOPE_HINT in check["next_action"]
    assert payload["counts"]["FAIL"] == 0


def test_doctor_warns_when_the_recorded_board_is_gone(tmp_path, monkeypatch):
    repo = healthy_repo(tmp_path)
    enable_board(repo)
    install_doctor_gh(
        tmp_path,
        monkeypatch,
        "#!/bin/sh\necho 'error: Could not resolve to a ProjectV2 with the number 4' >&2\nexit 1\n",
    )

    code, payload = run_script("doctor.py", repo)
    check = checks_by_name(payload)["project board"]

    assert code == 0, payload
    assert check["status"] == "WARN"
    assert check["next_action"] == CREATE_BOARD


def test_actions_doctor_does_not_treat_the_builtin_token_as_a_missing_board(tmp_path, monkeypatch):
    repo = healthy_repo(tmp_path)
    enable_board(repo)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    code, payload = run_script("doctor.py", repo)
    check = checks_by_name(payload)["project board"]

    assert code == 0, payload
    assert check["status"] == "PASS"
    assert "built-in" in check["detail"]


def test_rendered_and_plugin_doctors_agree_on_the_project_board(tmp_path, monkeypatch):
    repo = healthy_repo(tmp_path)
    enable_board(repo)
    install_doctor_gh(
        tmp_path,
        monkeypatch,
        '#!/bin/sh\nprintf \'%s\\n\' \'{"number": 4, "id": "PVT_4"}\'\n',
    )

    plugin_code, plugin_payload = run_script("doctor.py", repo)
    rendered = subprocess.run(
        [sys.executable, str(repo / ".sdlc" / "scripts" / "doctor.py"), str(repo)],
        capture_output=True,
        text=True,
        check=False,
    )
    rendered_payload = json.loads(rendered.stdout)

    assert plugin_code == rendered.returncode == 0
    assert (
        checks_by_name(plugin_payload)["project board"]
        == checks_by_name(rendered_payload)["project board"]
    )


def test_skills_and_glossary_explain_the_board_and_the_scope_hint():
    customize = (ROOT / "skills/shipshape-customize/SKILL.md").read_text(encoding="utf-8")
    access = (ROOT / "skills/shipshape-access/SKILL.md").read_text(encoding="utf-8")
    doctor = (ROOT / "skills/shipshape-doctor/SKILL.md").read_text(encoding="utf-8")
    recipes = (ROOT / "skills/shipshape-access/references/gh-recipes.md").read_text(
        encoding="utf-8"
    )
    glossary = (ROOT / "templates/docs/glossary.md.tmpl").read_text(encoding="utf-8")

    assert "scripts/project_board.py" in customize
    assert "scripts/project_board.py" in access
    assert SCOPE_HINT in customize
    assert SCOPE_HINT in access
    assert SCOPE_HINT in doctor
    assert "project board" in doctor.casefold()
    assert "access-plan" in recipes
    assert "manual" in access
    assert "not changed" in recipes.casefold()
    assert "**Project board**" in glossary
    assert (ROOT / "docs/adr/0014-optional-github-project-board.md").is_file()
    assert (ROOT / "docs/adr/0015-project-board-access-and-permissions.md").is_file()


def test_a_board_past_the_first_page_is_reused(tmp_path, monkeypatch):
    repo = board_repo(tmp_path)
    state = empty_state()
    state["projects"] = [
        {
            "owner": "octocat",
            "number": number,
            "title": "hello delivery" if number == 101 else f"other {number}",
            "id": f"PVT_{number}",
            "url": f"https://github.com/users/octocat/projects/{number}",
            "public": False,
            "closed": False,
        }
        for number in range(1, 102)
    ]
    root = install_fake_gh(tmp_path, monkeypatch, state)

    code, payload = run_script("project_board.py", "plan", "--repo", repo)

    assert code == 0, payload
    assert payload["action"] == "update"
    assert payload["project"]["number"] == 101
    assert all(call[:2] != ["project", "create"] for call in calls(root))


def test_open_issues_past_the_first_page_are_added(tmp_path, monkeypatch):
    repo = board_repo(tmp_path)
    state = empty_state()
    state["open_issues"]["octocat/hello"] = [
        {"number": number, "url": f"https://github.com/octocat/hello/issues/{number}"}
        for number in range(1, 102)
    ]
    root = install_fake_gh(tmp_path, monkeypatch, state)

    code, payload = run_script("project_board.py", "apply", "--repo", repo)

    assert code == 0, payload
    assert 101 in payload["issues_added"]
    assert any("page=2" in arg for call in calls(root) for arg in call)


def test_a_project_list_that_does_not_end_changes_nothing(tmp_path, monkeypatch):
    repo = board_repo(tmp_path)
    state = empty_state()
    state["projects_always_more"] = True
    root = install_fake_gh(tmp_path, monkeypatch, state)

    code, payload = run_script("project_board.py", "plan", "--repo", repo)

    assert code == 1, payload
    assert payload["error"] == "truncated"
    assert all(call[:2] != ["project", "create"] for call in calls(root))


def test_gh_failure_after_create_keeps_the_board_record(tmp_path, monkeypatch):
    repo = board_repo(tmp_path)
    install_fake_gh(tmp_path, monkeypatch, fail="field-list")

    code, payload = run_script("project_board.py", "apply", "--repo", repo)

    assert code == 1, payload
    assert payload["error"] == "github_command_failed"
    assert payload["project"]["number"] == 1
    assert payload["config_set"]["project.number"] == 1
    assert "Traceback" not in json.dumps(payload)
