---
name: shipshape-init
description: Set up a proper software delivery process (SDLC) in the current git repository — scan the project, ask a few plain-language questions, preview exactly what will be created, then write it. Use when the user says "set up this repo", "shipshape init", "get this project shipshape", or "add CI / proper process to this repo".
disable-model-invocation: true
---

# shipshape-init

Onboard the current repository onto a proper delivery process. Works for any
project and any person — the user may not be a software engineer, so follow
the voice rules in [references/voice.md](references/voice.md) for everything
you say.

This skill sequences scripts; it contains no logic of its own. Every script
prints JSON — branch on the JSON, and translate it for the user.

## Steps

1. **Preflight.** Check the basics and explain any gap in plain words before
   going further:

   ```bash
   python3 --version && git -C . rev-parse --show-toplevel
   ```

   - No `python3`: stop and explain how to install it (macOS: `xcode-select --install`
     or Homebrew; Windows: python.org installer).
   - Not a git repository: offer to run `git init -b main` first and explain in
     one sentence what a git repository is.

2. **Scan the project.**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/detect.py" . > /tmp/shipshape-detect.json
   cat /tmp/shipshape-detect.json
   ```

   If `existing_sdlc.config_present` is `true`, this repo is already set up —
   say so, and switch to repair/upgrade mode: skip the interview, keep the
   existing `.sdlc/config.json`, and go straight to step 5.

3. **Confirm what was found.** Summarize the scan in two or three sentences
   ("This looks like a Python project that uses pytest for its tests — is
   that right?"). Confidence below "high" means ask, don't assert.

4. **Interview, then write the config.** Ask the questions in
   [references/interview.md](references/interview.md) — a handful, outcomes
   not tools. Then:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render.py" init-config . \
     --detect /tmp/shipshape-detect.json \
     --set workflow_style=<trunk|pr> --set profile=<solo|team> \
     --set commands.test="<confirmed test command>"
   ```

   Pass a `--set` for every answer that differs from the detected default.

5. **Preview — the one plan gate.**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render.py" plan .
   ```

   Present the plan in plain language: each file that will be created, one
   line each, what it is and why ("`.github/workflows/ci.yml` — runs your
   tests automatically on GitHub after every change"). List `conflicts`
   separately: those files exist already and will NOT be touched. Then pause
   once for a go-ahead. This is the only routine pause.

6. **Apply.**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render.py" apply .
   ```

   Report what was written. For each conflict the user wants replaced anyway,
   confirm per file, then re-run apply with `--force <path>`.

7. **Finish the design doc.** Open `docs/sdlc/design.md`, write the "What
   this project is" and "Structure" sections from what you learned in the
   scan, in plain language. This file is written once and then belongs to
   the user.

8. **Close.** Tell the user, in this order: what now protects them, where
   the plan of record lives (`docs/sdlc/harness.md`), and the one next thing
   to do (usually: commit these new files, or run `/shipshape-doctor` once it
   ships). If the repo has a GitHub remote, mention the CI check will appear
   on their next push.

## Don't

- Don't write or overwrite anything before the step-5 plan gate.
- Don't ever overwrite a conflicted file without a per-file confirmation.
- Don't assert a detection guess as fact — confidence below "high" gets a
  question, not a statement.
- Don't use jargon without a parenthetical explanation on first use.
- Don't dump raw JSON or command output at the user — always translate.
- Don't commit or push; suggest it as the next step and let the user decide.
- Don't skip the interview for an empty repo — those users need the process
  most; the kit works fine with zero code.
