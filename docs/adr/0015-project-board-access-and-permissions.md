# 0015 — Project board access and permissions

Date: 2026-11-06

## Status

Accepted

## Context

[ADR 0014](0014-optional-github-project-board.md) made an optional GitHub
Project board. Two of its instructions do not match GitHub's published
surface. The Actions `permissions` key has no `projects` scope, so a
workflow that declares `projects: write` is rejected before the health
check runs. `ProjectV2` has no field that reads a person's current role,
and `ProjectV2ActorEdge` has no `role`. `updateProjectV2Collaborators`
sets a role even when that is lower than the role the person already has.

The rest of ADR 0014 still holds: the flag defaults off, apply only adds,
the separate `SHIPSHAPE_PROJECT_TOKEN` secret is how a weekly run adds a
card, and the doctor warns instead of failing when the board cannot be
seen.

## Decision

1. The project-board workflow variant does not declare `projects: write`.
   Its Actions permissions stay `contents: read` and `issues: write`.
   Adding the health issue to the board uses `SHIPSHAPE_PROJECT_TOKEN`
   when that secret exists. The doctor treats the variant as wired only
   when the workflow names that secret and `gh project item-add`, and
   does not declare `projects: write`.
2. `access-plan` and `access-apply` do not read or write project
   membership. A public board still covers read. Every other case returns
   `action: manual`, the role that matches the repository permission, and
   the project Settings path. They do not call
   `updateProjectV2Collaborators`.
3. Project, item, and open-issue reads follow every result page. A list
   that does not end is an error and changes nothing.
4. A failed `gh` command is JSON on stdout, including the board record
   when the failure happens after the board was created.

## Consequences

- Someone's board role is changed only by a person, in project settings.
- A weekly run without `SHIPSHAPE_PROJECT_TOKEN` still opens the health
  issue and says why the card was not added.
- ADR 0014's creation, field, and doctor behavior remain in force except
  where this record replaces them.
