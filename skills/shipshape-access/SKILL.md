---
name: shipshape-access
description: Manage who can do what on this GitHub repository — invite or remove collaborators, set their access level, and protect branches — from a plain-English request. Use when the user says "give Sam access", "add my colleague to this repo", "who can push here", "remove someone's access", or "protect the main branch".
---

# shipshape-access

Turn plain-English access requests into explicit `gh` commands. Follow
[../shipshape-init/references/voice.md](../shipshape-init/references/voice.md);
recipes and permission mappings live in
[references/gh-recipes.md](references/gh-recipes.md).

Use this entrypoint only when the user requests an access or branch-protection action.

## Bundle path

Before running a bundled script, set `SHIPSHAPE_ROOT` to the actual absolute
bundle path discovered from this loaded skill: from the directory containing
this loaded `SKILL.md`, go up two parent directories. This is the Shipshape
bundle, not the target repository or current working directory. Replace the
example value with the path you discovered and keep it quoted:

```bash
export SHIPSHAPE_ROOT="/absolute/path/to/the/loaded/shipshape/bundle"
```

## Steps

1. **Preflight.**

   ```bash
   gh auth status && gh repo view --json nameWithOwner --jq .nameWithOwner
   ```

   If `gh` is missing or not logged in, explain the one-time fix
   (`brew install gh`, then `gh auth login`) and stop. If there is no GitHub
   remote, say access is managed on GitHub and this repo isn't there yet.

2. **Translate the request.** Map what the user wants to an access level
   using the table in gh-recipes.md — "can look" is `pull` (read), "can
   contribute" is `push` (write), "can administer" is `admin`. When the
   request is ambiguous ("add Sam"), ask one question: look or contribute?
   Default to the LEAST access that satisfies the request; suggesting admin
   is never the default.

3. **Show, confirm, run.** Show the exact command, one line on what it does,
   get a yes, then run it:

   ```bash
   bash "${SHIPSHAPE_ROOT}/scripts/gh_helpers.sh" add-collaborator <user> <permission>
   ```

   (Also: `remove-collaborator <user>`, `list-collaborators`,
   `protect <branch> <trunk|pr>`, `protection-status <branch>`.)

4. **Project board, when it is on.** Do this only after the repository
   invite succeeded. Read `.sdlc/config.json`. If
   `features.project_board` is not true, skip this step. Repository access
   does not include the board (a GitHub Project, the table of open issues).
   Preview with the same permission you just used for the repository:

   ```bash
   python3 "${SHIPSHAPE_ROOT}/scripts/project_board.py" access-plan \
     --repo . --user <user> --permission <pull|push|admin>
   ```

   If the action is `already_covered`, say so and do not invite them again.
   If the action is `grant`, show the same command with `access-apply`, say
   the role in plain words (read, write, or admin), get a yes, then run it.
   If the JSON `error` is `missing_project_scope`, the repository invite
   already happened. Say that. Then say the board invite needs
   `gh auth refresh -s project`. If the command cannot invite them, relay
   the click path: open the project, choose Settings, then Manage access,
   and invite them there.

5. **Report.** Say what changed and what happens next ("Sam gets an email
   invitation; access starts when they accept"). On failure, relay the
   script's here's-what-to-click fallback.

## Don't

- Don't run any mutation without showing the command and getting a yes first.
- Don't grant more access than asked for, and never default to admin.
- Don't guess usernames — confirm exact GitHub usernames; an invite to the
  wrong person is a security incident.
- Don't touch organization teams in v1; say it's collaborators-only for now.
- Don't present a failed API call as done; relay the fallback instructions.
