---
name: shipshape-doctor
description: Read-only health check of a repository's SDLC setup — security guardrails first, then process files, drift, and version staleness, ending with the one thing to do next. Use when the user says "shipshape doctor", "is my repo set up properly", "check this repo's setup", or "is everything still protected".
---

# shipshape-doctor

Report the health of the current repository's setup in plain language.
Strictly read-only: this skill never writes, fixes, or installs anything —
it recommends, and other skills act. Follow the voice rules in
[../shipshape-init/references/voice.md](../shipshape-init/references/voice.md).

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

1. **Run the check.**

   ```bash
   python3 "${SHIPSHAPE_ROOT}/scripts/doctor.py" .
   ```

   If the JSON says `set_up: false`, tell the user this repo has no
   shipshape setup yet and that `/shipshape-init` is the next step. Stop.

2. **Render the bounded scorecard.** Security leads. Give each check's status,
   name, and translated detail without widening the claim. Static hook wiring
   is not an observed scanner run; workflow/configuration presence is not a
   successful run or an alert query. For ordinary trunk setup, say CI is
   configured after push and provides no proved pre-landing enforcement.
   Treat `features.branch_protection` as local intent until the `remote
   protection` check verifies the configured trunk, ordinary PR, or tiered PR
   mode through the shared read-only inspector. Missing helper, CLI, API, or
   exact-typed configuration evidence is not proof and must remain a failure
   or an explicitly unknown result.
   A partial setup apply is incomplete; report its pending conflicts/errors,
   rather than folding them into the harmless user-edit case.
   If a `test quality` check is present and off, say it is off and do not
   scan the tests yourself. If it warns about an incomplete scan, say which
   file could not be read and that this is not a clean result. If it warns
   about assertion-free tests, say it found Python tests with no recognized
   assertion, that the warning does not block a merge, that it does not run
   mutation testing, and that assertions living in a helper can be missed.
   A meaningless assertion such as `assert True` can still pass.
   The `remote protection` result also checks that the privileged auto-merge
   workflow is present only for a valid tiered PR configuration; helper
   presence by itself grants no authority.
   The `project board` check is absent when that feature is off. When it is
   on, PASS means a linked board was confirmed on your computer and the
   weekly health check is set to add its issue. That does not prove an item
   was added. WARN that names `gh auth refresh -s project` means this login
   cannot manage Projects (the board of issues). Say that in plain words and
   do not call it a failure. A weekly run's built-in token cannot see
   Projects, so that run does not pretend it re-checked the live board.

3. **Close with the one next action** from the JSON's `next_action` field —
   one thing, not a list. If everything passes, say so plainly and stop.

## Don't

- Don't fix anything, however small — doctor diagnoses, init/customize treat.
- Don't bury a FAIL under a wall of PASSes; failures lead.
- Don't report ordinary drift after a completed setup as a problem — editing
  managed files is fine. A conflict recorded by a partial apply is incomplete,
  not ordinary drift.
- Don't dump the raw JSON; translate it.
- Don't invent checks the script didn't run.

## Costs

Run this only when the user asks what verification cost, how much CI used,
or says "shipshape doctor costs". Do not run it during an ordinary health
check: it needs `GITHUB_TOKEN` and it calls GitHub.

Read `repo.owner_repo` from `.sdlc/config.json`. If that value is empty, ask
which `owner/repo` to summarize and stop.

```bash
python3 "${SHIPSHAPE_ROOT}/scripts/verification_cost.py" summarize <owner/repo> --days 30
```

Translate the JSON before any raw detail. If `ok` is false, say the
`next_action` and stop. The zero counts in that object were not measured.
When `ok` is true, say the window, the number of runs, attempts, retried
runs, and minutes. When `landed_changes` is a number, say minutes per
landed change. When it is missing, say the landed count is unknown and do
not invent a rate. Landed changes are commits that
reached the default branch, including direct pushes. `merged_changes` counts
merged pull requests only, so it undercounts a repository that pushes
straight to its main branch. Do not add those two counts together.

`estimated_cost.status` stays `unknown` unless the JSON says otherwise.
Never invent a price, a currency, or a budget.

If `retried_runs` is greater than zero, say a retry makes a green result
harder to trust. End with the JSON `next_action` as the one next step.

Completion criterion: the user heard the counts, whether money is unknown,
and one next action.
