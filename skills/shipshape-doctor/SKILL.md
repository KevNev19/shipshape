---
name: shipshape-doctor
description: Read-only health check of a repository's SDLC setup — security guardrails first, then process files, drift, and version staleness, ending with the one thing to do next. Use when the user says "shipshape doctor", "is my repo set up properly", "check this repo's setup", or "is everything still protected".
---

# shipshape-doctor

Report the health of the current repository's setup in plain language.
Strictly read-only: this skill never writes, fixes, or installs anything —
it recommends, and other skills act. Follow the voice rules in
[../shipshape-init/references/voice.md](../shipshape-init/references/voice.md).

## Steps

1. **Run the check.**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" .
   ```

   If the JSON says `set_up: false`, tell the user this repo has no
   shipshape setup yet and that `/shipshape-init` is the next step. Stop.

2. **Render the scorecard.** Security section first, always. One line per
   check: the status word (PASS / WARN / FAIL), the check name, and the
   detail translated per the voice rules. Lead the summary with security:
   "Your secret guard is active and CI is green" beats a table of counts.

3. **Branch protection (only if `gh` is available and authenticated).**

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/gh_helpers.sh" protection-status <default-branch>
   ```

   Report `"protected": false` as a WARN in the security section: changes
   can land even when the automated tests fail. If `gh` is missing or not
   logged in, say the check was skipped and why — never guess.

4. **Close with the one next action** from the JSON's `next_action` field —
   one thing, not a list. If everything passes, say so plainly and stop.

## Don't

- Don't fix anything, however small — doctor diagnoses, init/customize treat.
- Don't bury a FAIL under a wall of PASSes; failures lead.
- Don't report a user-edited managed file as a problem — editing their own
  files is fine and the report says so.
- Don't dump the raw JSON; translate it.
- Don't invent checks the script didn't run.
