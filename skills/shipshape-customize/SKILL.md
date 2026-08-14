---
name: shipshape-customize
description: Change how this repository's SDLC setup behaves — switch working style, turn features on or off, update the test command or reviewers — through a short Q&A, then regenerate only what's affected. Use when the user says "customize the setup", "turn off CodeQL", "switch to pull requests", "change the test command", or "update my shipshape config".
disable-model-invocation: true
---

# shipshape-customize

Edit `.sdlc/config.json` conversationally and re-render the affected files.
Never hand-edit managed files to customize — change the config, regenerate.
Follow [../shipshape-init/references/voice.md](../shipshape-init/references/voice.md).

## Steps

1. **Read the current setup.** `cat .sdlc/config.json` (if missing, point to
   `/shipshape-init` and stop). Play back the settings relevant to the
   user's request in plain language ("changes currently go straight to main,
   protected by the automated tests").

2. **Map the request to config keys.** Common ones: `workflow_style`
   (trunk/pr), `profile` (solo/team), `commands.test`, `owners.default`,
   `toolchain.*`, `features.*`. If the user asks to disable a
   consequence-gated feature (`features.codeql`, `features.secret_guard`,
   `features.dependabot`, `features.branch_protection`,
   `features.scheduled_health`): state the one-sentence consequence and
   require an explicit yes before proceeding. For security controls, name
   the lost protection (for example, "commits will no longer be checked for
   passwords or keys"). For `scheduled_health`, use: "nobody will be told
   when a protection quietly disappears."

   Enabling `features.tiered_review` has the inverse gate: before turning it
   on, state: "changes matching the two low-risk classes will merge without a
   person once checks pass" and require an explicit yes. Disabling it needs
   no consequence gate.

3. **Write the config.**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render.py" set-config . --set key=value
   ```

4. **Preview and apply.**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render.py" plan .
   ```

   Summarize what will change; on a go-ahead, `apply`. Conflicted files
   follow the usual rule: ask per file before any `--force`. Note: turning a
   feature off stops managing its files but does not delete them — offer to
   remove the now-unmanaged file, and only delete on a per-file yes. Tiered
   review is the safety exception: disabling it plans removal of the managed
   auto-merge workflow. A drifted or unowned copy remains a conflict and
   still needs per-file confirmation before removal.

5. **Report** what changed and the one next step (usually: commit).

## Don't

- Don't disable any security feature without stating the consequence and
  getting an explicit yes.
- Don't enable tiered review without stating its consequence and getting an
  explicit yes; don't gate turning it off.
- Don't edit managed files directly to satisfy a customization — config
  first, then regenerate.
- Don't delete files without a per-file confirmation.
- Don't touch settings the user didn't ask about.
