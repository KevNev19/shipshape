"""The consumer checks runner is the kit's checks.py under a managed header.

templates/scripts/checks.py.tmpl must stay line-for-line the kit script after
its header, so the two can never drift; the rendered .sdlc/scripts/checks.py
is executable, carries the kit version and answers exactly as the kit's does.
"""

import json
import os
import shlex
import subprocess
import sys

from conftest import KIT_ROOT, SCRIPTS, init_repo, run_script

TEMPLATE = KIT_ROOT / "templates" / "scripts" / "checks.py.tmpl"
MANAGED_HEADER = [
    "#!/usr/bin/env python3",
    "# What this is: runs this repository's checks (tests, lint, build, typecheck,",
    '# format) once each and prints one JSON result; its "ok" says whether all passed.',
    "# Safe to edit: yes — shipshape will ask before overwriting your edits.",
    "# managed-by: shipshape v{{KIT_VERSION}}",
]


def say(text: str, code: int = 0) -> str:
    return f"printf '%s\\n' {shlex.quote(text)}; exit {code}"


def rendered_repo(tmp_path):
    repo = init_repo("repo-python", tmp_path)
    code, payload = run_script("render.py", "apply", repo)
    assert code == 0, payload
    return repo


def without_durations(payload: dict) -> dict:
    results = [
        {key: value for key, value in result.items() if key != "duration_ms"}
        for result in payload["results"]
    ]
    return {**payload, "results": results}


def test_template_is_the_kit_script_under_a_managed_header():
    kit = (SCRIPTS / "checks.py").read_text(encoding="utf-8").splitlines()
    template = TEMPLATE.read_text(encoding="utf-8").splitlines()

    assert kit[0] == MANAGED_HEADER[0]
    assert template[: len(MANAGED_HEADER)] == MANAGED_HEADER
    assert template[len(MANAGED_HEADER) :] == kit[1:]


def test_rendered_checks_is_executable_and_carries_the_kit_version(tmp_path):
    repo = rendered_repo(tmp_path)
    rendered = repo / ".sdlc" / "scripts" / "checks.py"
    version = json.loads((KIT_ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]

    assert os.access(rendered, os.X_OK), f"{rendered} is not executable"
    assert f"# managed-by: shipshape v{version}" in rendered.read_text(encoding="utf-8")


def test_rendered_and_kit_checks_give_the_same_answer(tmp_path):
    repo = rendered_repo(tmp_path)
    config_path = repo / ".sdlc" / "config.json"
    config = json.loads(config_path.read_text())
    config["commands"] = {"test": say("1 passed in 0.01s"), "lint": say("Found 2 errors.", 1)}
    config_path.write_text(json.dumps(config))

    kit_code, kit_payload = run_script("checks.py", "run", repo)
    proc = subprocess.run(
        [sys.executable, str(repo / ".sdlc" / "scripts" / "checks.py"), "run", str(repo)],
        capture_output=True,
        text=True,
    )
    rendered_payload = json.loads(proc.stdout)

    assert kit_code == proc.returncode == 0
    assert kit_payload["ok"] is False
    assert [result["name"] for result in kit_payload["results"]] == ["test", "lint"]
    assert without_durations(rendered_payload) == without_durations(kit_payload)
