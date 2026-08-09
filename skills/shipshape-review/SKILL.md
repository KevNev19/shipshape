---
name: shipshape-review
description: Explain a change in plain language — what it does, what could break, anything security-relevant, and a clear "looks safe" or "needs attention" verdict with reasons. Works on a pull request, a branch, or uncommitted changes. Use when the user says "review this change", "review PR 12", "what does this change do", "is this safe to merge", or "explain this diff".
disable-model-invocation: true
---

# shipshape-review

Translate a change and its automated-check results for someone who may not
read code. Strictly read-only — this skill never edits, commits, merges, or
approves. Follow
[../shipshape-init/references/voice.md](../shipshape-init/references/voice.md);
the checklist lives in [references/review-rubric.md](references/review-rubric.md).

## Steps

1. **Get the change.** In order of what the user pointed at:
   - a PR number → `gh pr view <n>` and `gh pr diff <n>`
   - a branch → `git diff <default-branch>...<branch>`
   - otherwise → uncommitted work: `git diff` plus `git diff --cached`
   If the diff is empty, say so and stop.

2. **Get the check results** (PRs only): `gh pr checks <n>`. For a failing
   check, fetch the failed step's log tail (`gh run view --log-failed`) and
   find the first real error line.

3. **Read the whole diff** and work through the rubric. For large diffs,
   group by area rather than file-by-file.

4. **Report, in this order:**
   - **What this change does** — two or three sentences, plain language.
   - **Automated checks** — PASS or FAIL; for FAIL, the failing line
     translated ("the login test expected X and got Y").
   - **What could break** — the riskiest one to three things, each with why.
   - **Security notes** — anything from the rubric's security list, or
     "nothing security-relevant".
   - **Verdict** — exactly one of: "Looks safe to merge", "Needs attention
     first: <the one thing>", or "Do not merge: <reason>". Tests failing or
     a secret in the diff always means one of the latter two.

## Don't

- Don't merge, approve, comment on, or edit anything — report only.
- Don't give a verdict without having read the full diff and check results.
- Don't say "looks safe" when checks are red — ever.
- Don't drown the user in per-file commentary; lead with the three things
  that matter.
- Don't assume intent — if the change's purpose is unclear, say so and ask.
