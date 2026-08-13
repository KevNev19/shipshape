# Review rubric

Work through these in order; the report follows the same order.

## 1. Behaviour

- What does the change actually do (not what the title says)?
- Does anything change for existing users/data (renames, removals, format
  changes, migrations)?
- Are there tests for the new behaviour? Were existing tests changed to
  pass — and if so, is that legitimate (the correct answer changed) or
  suspicious (weakening a check)?

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
- Changes under `.claude/`, `.vscode/`, `.github/agents/`,
  `.github/copilot-instructions.md`, `AGENTS.md`, `CLAUDE.md`, or `.sdlc/hooks/`
  are security findings: report purpose and consequence. Unexplained
  control-file changes require at least "Needs attention first".
- Input handling: anything user-supplied reaching a shell, a query, a file
  path, or HTML unescaped.

## 4. Verdict calibration

- "Looks safe to merge" — checks green, no security notes, risks are
  explained and acceptable.
- "Needs attention first" — one fixable thing stands between this and safe.
- "Do not merge" — failing checks the author didn't explain, a secret in
  the diff, or an unexplained irreversible action.
