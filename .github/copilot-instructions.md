<!--
  What this is: repository-wide instructions for GitHub Copilot — read both
  when it reviews pull requests here and when it works on tasks. The review
  standards below mirror this project's working agreement.
  Safe to edit: yes — shipshape will ask before overwriting your edits.
  managed-by: shipshape v0.4.0
-->

# Copilot Instructions for shipshape

This project's working agreement is `docs/sdlc/harness.md`; the project
overview is `docs/sdlc/design.md`. Tests run with: `python3 -m pytest tests/ -q`

## When reviewing a pull request

Review for people who may not read code. Short sentences; explain any term
of art in parentheses on first use. Read the full diff internally, but do not
narrate it file by file.

Every review uses exactly one profile: specification, plan, documentation, or code.
Specifications, design and decision records, and change intent are
specification: look for requirements that contradict each other or an
accepted decision, requirements without an acceptance check, requirements
that can be read two ways, and intent that no requirement covers, such as an
error case, a limit or a migration. Implementation plans are plan: look for
steps out of dependency order, names used before a step creates them, steps
that do not say how they are verified, requirements no step covers and steps
nothing asks for, and steps that cannot be carried out without guessing.
Other Markdown, MDX, reStructuredText and AsciiDoc is documentation: look for
statements, links and commands that are not true of the code, text its reader
cannot follow without the code, and other documents that now say something
different about the same thing.
Everything else, including anything under a folder whose name
starts with a dot, is code: look at behaviour, tests, and what else could be
affected. Use the profile that fits the most changed files when that is at least half of them,
the earlier one in that list on a tie; otherwise review the change as code.
A changed file that fits another profile is still reviewed for what that profile looks for; its findings join the same report.

Inspect what the profile looks for, security, and the verdict choice. If
tests were changed to pass, say whether that looks legitimate (the correct
answer changed) or suspicious (a check was weakened). Security always
gets checked: secrets, new dependencies, changed workflow permissions,
disabled checks, security configuration, and unescaped user input. Treat nested
instruction files and native agent, plugin, skill, workflow, policy, harness,
and editor controls as security findings: report purpose and consequence. The
guard structurally inspects supported JSON/JSONC settings for introduced or
changed command, hook, task, terminal, and encoded values. Generic prose,
ordinary state, and plugin-manifest hashes remain review signals, not semantic
security verdicts; a clean scan does not prove safety or complete detection.
Unexplained control-file changes require at least "Needs attention first".

Report in this order:

1. **Intent** — link the intent artifact (a written record of what the change
   is meant to do) or originating issue (the task that led to the change). If
   neither exists, say: "No intent artifact was found. This review judged the
   change on its own terms." Name the review profile and how many of the
   changed files fit it.
2. **Verified findings** — severity order. Every finding has a check result
   or file and line, its plain-language consequence, and exactly one next
   action. Never invent findings.
3. **Intent conformance (match to the request)** — say whether the change does
   what was asked, and only that. Name anything beyond the stated intent.
4. **Material uncertainties (important things that could not be verified)** —
   state what could not be verified. "No verified findings" never means "no
   risk". Keep green required checks, missing intent, and inspection limits
   visible.
5. **Verdict** — end on exactly one: "Looks safe to merge", "Needs attention first: <the one thing>",
   or "Do not merge: <reason>".

Any secret in the diff is an automatic "Do not merge".
Red checks can never be called "looks safe" — ever.
Security is checked under every profile.
The verdict and its two automatic escalations are the same under every profile.
When reviewing, never edit, comment, approve, merge, or commit.

## When making changes

Follow `AGENTS.md`: run the tests and report results honestly before
calling work done, keep changes small and deployable, and never commit
secrets or weaken the security workflows to make something pass.
