# 0012 — Checks: detect, prove, run, and guard test integrity

Date: 2026-10-14

## Status

Accepted

## Context

Shipshape detected one check, the test command (`test_command_guess`), and
stored it in `commands.test`. `commands.lint` existed, but nothing filled
it or read it, and nothing in the kit ran a check. Whoever builds a change,
a person or an agent, needs more than that to know whether the change broke
something: the repository's lint, build, typecheck and format checks as
well as its tests; proof that each proposed command runs on this machine;
one machine-readable result per check, with a failure count that can be
compared before and after a change; and a way to see that a change weakened
the tests instead of passing them. The review rubric already asks whether
existing tests were changed to pass, but only as a reviewer's judgement
over the whole diff.

## Decision

Checks become a kit capability in four parts, each a standard-library
script that prints one JSON object and runs under `python3 -I`
([ADR 0002](0002-python-stdlib-scripts.md)):

1. **Detection proposes.** `detect.py` gains a `checks` list with one
   entry per kind found (`test`, `lint`, `build`, `typecheck`, `format`),
   each `{name, command, proven, source, confidence, language}`, for
   python, node, go and rust. The evidence is the repository's own files:
   a `package.json` script, or a tool's configuration file or
   `pyproject.toml` table, is high confidence; the language manifest alone,
   for a command the toolchain provides, is medium. Only high-confidence
   languages propose checks, the primary language wins a kind two
   languages could fill, and the test entry is always the runner behind
   `test_command_guess`. A plain scan never runs a check command: it reads
   files, so the checks it proposes are deterministic and the frozen
   fixtures stay ground truth. `render.py init-config` writes each proposal
   into `commands.<kind>`, and the init interview confirms them.
2. **A prove step runs each proposal once.** `detect.py --prove` runs every
   proposed command one time, inside one time budget and in a process
   group of its own, whose leftover processes end with it, and sets
   `proven` when it ran, not when it passed, so a caller keeps only
   commands that run on this machine.
3. **A runner runs the configured checks.** `checks.py run` runs
   `commands.*`, or commands given on its command line, and reports per
   check whether it passed, the failure count when the tool prints one,
   and the last lines of its output, within one time budget that a stop
   ends without leaving a check's processes behind. It exits 0 whenever it
   printed its answer; the answer's `ok` says whether every check passed.
   Consumers get the same script as `.sdlc/scripts/checks.py` through the
   manifest, under the drift contract of
   [ADR 0003](0003-token-substitution-templates.md).
4. **A diff check guards test integrity.** `test_integrity.py` reads a diff
   (the uncommitted change, a range of commits or trees, the staged change,
   or stdin) and reports deleted test files, deleted or skipped tests, and
   removed or loosened assertions, for python, node, go and rust. Each
   finding carries a file and a line, so the findings-first review
   ([ADR 0007](0007-findings-first-review.md)) reports it as a verified
   finding.

Check commands other than `test` may be empty, and an empty token is a
render error ([ADR 0003](0003-token-substitution-templates.md)), so the
tokens `LINT_CMD`, `BUILD_CMD`, `TYPECHECK_CMD` and `FORMAT_CMD` are
offered and no template references them.

## Consequences

- This extends [ADR 0002](0002-python-stdlib-scripts.md),
  [ADR 0003](0003-token-substitution-templates.md) and
  [ADR 0007](0007-findings-first-review.md); none of them changes.
- `detect.py` output gains a key, so every frozen fixture under
  `tests/expected/` is regenerated once, with the documented command.
- One command per kind: in a repository with two languages the primary
  language's check wins, and the owner changes it through
  `commands.<kind>`.
- A node check found from a tool's configuration runs
  `node_modules/.bin/<tool>`, so a check runs only what the project
  installed and never fetches a package. A `package.json` script that
  rewrites files (`--write`, `--fix`, `--apply`) or watches (`--watch`,
  `-w`) is never proposed; `-w` is conservative, since it is also npm's
  workspace flag.
- A node `test` script with no known runner is not proposed; the owner
  sets `commands.test`.
- `--no-network` skips only the `gh auth status` probe, the scan's one
  network call. `--prove` runs the repository's own build tools, which may
  fetch dependencies, so with `--no-network` as well each proved command
  gets cargo's, go's and npm's offline settings (`CARGO_NET_OFFLINE=true`,
  `GOPROXY=off`, `npm_config_offline=true`): a command that then needs a
  download fails, which still proves it ran. Other tools keep their own
  network behaviour.
- Proving and running execute the repository's own commands, so only a
  caller that asks runs them; `shipshape-init` writes nothing into the
  repository before its plan gate and does not prove. Doctor stays
  read-only: it never runs a check.
- Built in steps: detection and the prove step land with this record; the
  runner, then the integrity check, follow as separate changes.
