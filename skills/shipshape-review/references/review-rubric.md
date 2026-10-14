# Review rubric

Work through these steps internally. Do not use them as report headings
or narrate the diff file by file. Send the output through the
[finding contract](finding-contract.md), ordered by verified finding severity.

## 0. Profile

- Take the profile chosen under section 0 of the finding contract and its
  lenses (the questions to ask for that profile) from
  [profiles.json](profiles.json). The step is done when every lens has an
  answer backed by the evidence that profile accepts.
- Under `code`, steps 1 to 3 below are its lenses spelled out.
- Under `specification`, `plan` or `documentation`, its lenses take the place
  of steps 1 and 2. Steps 3 and 4 apply under every profile.
- A changed file that fits another profile is still reviewed for what that
  profile looks for, using that profile's lenses; its findings join the same
  report.

## 1. Behaviour

- What does the change actually do (not what the title says)?
- Does anything change for existing users/data (renames, removals, format
  changes, migrations)?
- Are there tests for the new behaviour? Were existing tests changed to
  pass — and if so, is that legitimate (the correct answer changed) or
  suspicious (weakening a check)?
- Each test-integrity finding (a deleted or skipped test, a removed or
  loosened assertion) gets that question. When the intent explains it, its
  next action is to confirm the explanation; when nothing does, it requires
  at least "Needs attention first".

## 2. Blast radius

- What depends on the changed code? Public interfaces > internals.
- Error handling: what happens when the new code gets bad input or a
  dependency fails?
- Anything irreversible: deletions, data rewrites, one-way migrations.

## 3. Security (always check, always report)

- New secrets or credentials in the diff — keys, tokens, passwords,
  connection strings. Any hit is an automatic "Do not merge".
- New dependencies: are they real, maintained, and needed?
- Changed workflow permissions, disabled checks, or edits to security
  configuration (the secret guard, CodeQL, branch protection).
- Automation and policy controls at any depth are security findings:
  `AGENTS.md`, `CLAUDE.md`, `SKILL.md`, `.agents/`, `.codex/`, `.claude/`,
  Claude/Codex plugin metadata, `.github/agents/`, `.github/workflows/`,
  `.github/copilot-instructions.md`, `.sdlc/`, `docs/agents/`, `docs/sdlc/`,
  harness documents, and editor automation (`.vscode/`,
  `.idea/runConfigurations/`, `.zed/`, `.fleet/run.json`, `.devcontainer/`).
  Check both rename names and mode-only changes. Report purpose and
  consequence. Unexplained control changes require at least "Needs attention
  first" and remain human-reviewed.
- Secret and control scanners use finite patterns. A pass cannot guarantee
  detection; a hit can be a false positive. Verify the diff itself.
- Input handling: anything user-supplied reaching a shell, a query, a file
  path, or HTML unescaped.

## 4. Verdict calibration

- "Looks safe to merge" — exact applicable checks green, no security notes,
  risks explained and acceptable. Green is evidence about configured checks,
  not proof of safety.
- "Needs attention first" — one fixable thing stands between this and safe.
- "Do not merge" — failing checks the author didn't explain, a secret in
  the diff, or an unexplained irreversible action.
