# gh recipes — access management

## Permission mapping (plain English → GitHub)

| User says                          | Permission | What it allows |
|------------------------------------|------------|----------------|
| "can look", "read only", "viewer"  | `pull`     | See the code, open issues |
| "can contribute", "works on this"  | `push`     | Everything above + push changes |
| "runs the project", "full control" | `admin`    | Everything above + settings, access, deletion |

Between two levels, pick the lower and say why.

## Commands (all via gh_helpers.sh)

Use the `SHIPSHAPE_ROOT` absolute bundle path resolved and exported by the
parent skill's Bundle path step.

```bash
bash "${SHIPSHAPE_ROOT}/scripts/gh_helpers.sh" list-collaborators
bash "${SHIPSHAPE_ROOT}/scripts/gh_helpers.sh" add-collaborator <user> <pull|push|admin>
bash "${SHIPSHAPE_ROOT}/scripts/gh_helpers.sh" remove-collaborator <user>
bash "${SHIPSHAPE_ROOT}/scripts/gh_helpers.sh" protection-plan <branch> trunk
bash "${SHIPSHAPE_ROOT}/scripts/gh_helpers.sh" protect <branch> trunk
bash "${SHIPSHAPE_ROOT}/scripts/gh_helpers.sh" protection-plan <branch> pr --codeql-enabled --require-review
bash "${SHIPSHAPE_ROOT}/scripts/gh_helpers.sh" protect <branch> pr --codeql-enabled --require-review
bash "${SHIPSHAPE_ROOT}/scripts/gh_helpers.sh" protection-plan <branch> pr --tiered-review --codeql-enabled
bash "${SHIPSHAPE_ROOT}/scripts/gh_helpers.sh" protect <branch> pr --tiered-review --codeql-enabled
bash "${SHIPSHAPE_ROOT}/scripts/gh_helpers.sh" protection-status <branch>
```

Always run and show `protection-plan` first. It is read-only. After the user
approves that exact proposal, repeat the same arguments with `protect`.

- `trunk` adds deletion and non-fast-forward safeguards only. CI runs after a
  direct push and is not a pre-landing gate.
- `pr` provisions strict source-bound status gates. Use `--tiered-review` only
  for the configured opt-in; omit `--require-review` in that lane so qualifying
  documentation can use its narrow automatic authority.
- Existing classic protection, reviews, checks, restrictions, bypasses, and
  unrelated rulesets are preserved. An unfamiliar same-name rule is a refusal,
  not permission to replace it.

## Project board

Repository access does not include a GitHub Project (the board of issues).
When `features.project_board` is true, a public board already covers read
access. For any other role, access is not changed. GitHub's project API
does not show the person's current role, and setting a role could lower it.

| Repository permission | Board role | Plain words |
|-----------------------|------------|-------------|
| `pull`                | `READER`   | can look |
| `push`                | `WRITER`   | can update the board |
| `admin`               | `ADMIN`    | can also invite other people |

```bash
python3 "${SHIPSHAPE_ROOT}/scripts/project_board.py" access-plan \
  --repo . --user <user> --permission <pull|push|admin>
python3 "${SHIPSHAPE_ROOT}/scripts/project_board.py" access-apply \
  --repo . --user <user> --permission <pull|push|admin>
```

Show `access-plan` first. It does not change membership. If the action is
`manual`, do not run `access-apply`. Tell the person the role and the
project Settings path. Do not lower someone's access, and do not remove
anyone.

If the JSON `error` is `missing_project_scope`, the repository change still
stands. Say so, then the one next step: `gh auth refresh -s project`.
If the invite itself fails, the click path is the project, Settings, Manage
access.

## Known failure modes

- Private repo on a free plan: ruleset APIs may refuse → the script
  prints the Settings-page fallback; relay it.
- Missing `admin` permission on the repo: collaborator changes fail → the
  user needs the repository owner to do it or to grant them admin.
- Organization repos: team-based access is out of scope in v1 — point the
  user at Settings → Collaborators and teams.
