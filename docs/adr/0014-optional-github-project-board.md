# 0014 — Optional GitHub Project board

Date: 2026-11-04

## Status

Accepted

## Context

Shipshape sets up the GitHub side of delivery, but open work had nowhere to
live except a hand-built board. An earlier `features.project_board` key was
removed because it selected no behavior. [0002](../research/0002-shipshape-vs-ai-native-sdlc.md)
recorded that removal. Issue #14 asks for the key to select a real,
optional Projects v2 board.

Repository access and project access are different. Linking a board to a
repository does not invite repository collaborators onto a user-owned
project. GitHub's built-in Actions token also cannot manage Projects, so a
weekly job cannot honestly claim it re-checked the live board.

## Decision

1. `features.project_board` is a boolean and defaults to false. Absent means
   off. The doctor check `project board` is omitted while it is off.
   `project.number`, `project.owner`, and `project.title` record the board
   so a later run reuses it.
2. `scripts/project_board.py` plans read-only and applies by adding only.
   The title is `<project_name> delivery`. It links the board to the
   repository, adds single-select fields Owner (the configured owners, plus
   `external`) and Gate (`build`, `release`, `pilot`) when those names are
   missing, and adds open issues that are not already on the board.
   "Blocked by" stays in issue text. Existing fields, options, items, and
   titles are not renamed or deleted.
3. The scheduled health workflow has a second variant, selected when the
   feature is on. It declares `projects: write` and runs
   `gh project item-add` for the health issue. If that add fails, the job
   stays green and the summary says how to refresh a local `project` scope
   or set the repository secret `SHIPSHAPE_PROJECT_TOKEN`.
4. The doctor check WARNs, and does not FAIL, when the feature is on but no
   board is linked, the recorded board is gone, or the token lacks the
   project scope. The scope next step is `gh auth refresh -s project`.
   On GitHub Actions the built-in token cannot see Projects, so a recorded
   number plus the workflow wiring is PASS and the detail says the live
   board was not re-checked.
5. `/shipshape-access` invites the same person to the board when the feature
   is on and their project role is below the repository permission. A public
   board already covers read. A higher existing role is left alone.

## Consequences

- Creating the board is a confirmed GitHub change, like branch protection.
  Turning the feature off stops managing the workflow variant and does not
  delete the board.
- Weekly addition to a user-owned board needs a classic token with the
  `project` scope in `SHIPSHAPE_PROJECT_TOKEN`. Until that secret exists,
  the health issue is still opened and the summary says why the card was
  not added.
- The consumer doctor and the plugin doctor both implement the check and
  must keep the same status and next step.
- Stdlib-only JSON output is preserved
  ([ADR 0002](0002-python-stdlib-scripts.md)); the workflow variant is
  token-only and never-clobber
  ([ADR 0003](0003-token-substitution-templates.md)).
