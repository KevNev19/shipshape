# gh recipes — access management

## Permission mapping (plain English → GitHub)

| User says                          | Permission | What it allows |
|------------------------------------|------------|----------------|
| "can look", "read only", "viewer"  | `pull`     | See the code, open issues |
| "can contribute", "works on this"  | `push`     | Everything above + push changes |
| "runs the project", "full control" | `admin`    | Everything above + settings, access, deletion |

Between two levels, pick the lower and say why.

## Commands (all via gh_helpers.sh)

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/gh_helpers.sh" list-collaborators
bash "${CLAUDE_PLUGIN_ROOT}/scripts/gh_helpers.sh" add-collaborator <user> <pull|push|admin>
bash "${CLAUDE_PLUGIN_ROOT}/scripts/gh_helpers.sh" remove-collaborator <user>
bash "${CLAUDE_PLUGIN_ROOT}/scripts/gh_helpers.sh" protect <branch>                  # trunk style: CI must pass
bash "${CLAUDE_PLUGIN_ROOT}/scripts/gh_helpers.sh" protect <branch> --require-review # pr style: + one approval
bash "${CLAUDE_PLUGIN_ROOT}/scripts/gh_helpers.sh" protection-status <branch>
```

## Known failure modes

- Private repo on a free plan: branch protection API may refuse → the script
  prints the Settings-page fallback; relay it.
- Missing `admin` permission on the repo: collaborator changes fail → the
  user needs the repository owner to do it or to grant them admin.
- Organization repos: team-based access is out of scope in v1 — point the
  user at Settings → Collaborators and teams.
