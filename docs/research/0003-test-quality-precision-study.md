# Test-quality scanner precision study, and a cost-prototype smoke

- Status: Research results (2026-08-14; limitations corrected 2026-09-09)
- Purpose: first real-world evidence for two research-first gates from
  [0002 — the gap analysis](0002-shipshape-vs-ai-native-sdlc.md): open
  question 1 (is stdlib-only test-quality sensing feasible with acceptable
  precision?) and the metric question behind gap 10 (which verification-cost
  measure would actually change a decision?). Changes no policy. The scanner
  remains a kit-local advisory prototype, not a `test_quality` feature.

## Method

`scripts/test_quality.py scan` was run against shallow clones of three
widely used, pytest-heavy Python codebases — flask, requests, and click —
plus shipshape's own suite. Flagged tests were categorized with AST-assisted
bulk review and manual samples. This is an observational four-repository
precision exercise: the repositories were not randomly selected, the labels
were not independently blinded, and unflagged tests were not sampled to
estimate recall.

## Before: 38 of 1,269 tests flagged (3.0%)

| Repo | Scanned | Flagged |
|---|---|---|
| flask | 392 | 17 |
| requests | 347 | 12 |
| click | 530 | 9 |
| shipshape | 94 | 0 |

Categorization of the 38 flags:

- **1 fixture false positive** — a `@pytest.fixture` named `test_apps` in
  flask's conftest; a fixture, not a test.
- **11 nested-helper false positives** — assertions live inside a function
  defined within the test body (flask's `test_session_cookie_setting`
  asserts inside an inner `run_test`; click's command-callback tests assert
  inside the callback). The scanner did not look inside nested `def`s.
- **~10 helper-delegation misses** — assertions live in a module-level
  helper the test calls (flask's `test_config.py` tests all call
  `common_object_test`, which asserts). This is the scanner's documented
  known boundary: undetectable without cross-function analysis.
- **~2 tooling artifacts** — click's `tests/typing/` files are mypy
  type-check files, not runtime tests.
- **~14 true positives** — genuinely assertion-free tests. The clearest
  cases are requests' deliberate smoke tests (`test_can_access_urllib3_attribute`
  is a bare attribute access that only fails on exception) and several
  exception-only tests (`test_decompress_gzip`, `test_unicode_get`): the
  flag is accurate; whether to strengthen them is the owning team's call.

## Fixes applied, and after: 26 of 1,268 flagged (2.1%)

The two cheap false-positive classes were fixed in the spike
(fixture-decorated `test_*` functions are excluded from scanning entirely;
assertions inside nested function definitions are credited), with three new
regression cases in `tests/test_test_quality.py`:

| Repo | Scanned | Flagged (before → after) |
|---|---|---|
| flask | 391 | 17 → 10 |
| requests | 347 | 12 → 11 |
| click | 530 | 9 → 5 |
| shipshape | 94 | 0 → 0 |

All 12 categorized false positives identified by the initial review are gone.
Of the remaining 26 flags, roughly half were genuine assertion-free tests and
half delegated assertions to helpers. That yields about 50–60% precision for
the helper-heavy repositories in this small sample. It does not support a
near-100% projection for other repositories, even when their reviewed samples
mostly assert inline.

The scan also cannot tell whether a recognized assertion is meaningful. Two
root-level counterexamples both return no flags: a test containing only
`assert True`, and a test that defines but never calls a nested function
containing `assert False`. The second follows from the earlier false-positive
fix that credits nested assertions. These examples demonstrate unmeasured
false negatives for the broader question, "can this test catch wrong code?"

## Verdict against open question 1

- **Feasible only as a bounded WARN-level assertion-absence advisory**:
  stdlib-only and fast (~1s per sampled repo). The observed flag precision is
  useful for deciding which tests to inspect, not for grading a suite.
- **Not gate-grade**: helper-delegation misses are common in mature suites
  (flask's config tests are idiomatic, not sloppy), so a FAIL or a merge
  gate on this signal would misfire. Meaningless and uncalled nested
  assertions also pass. Any use must state those heuristic gaps.
- No recall, mutation score, cross-language behavior, or general test-quality
  effect was measured. Mutation-testing sensitivity and CI cost remain open.

## Cost-prototype smoke (gap 10)

`scripts/verification_cost.py summarize KevNev19/shipshape --days 7` with a
live token: 137 runs, 140 attempts (3 retried runs), 103 minutes,
2 merged PRs, 51.5 minutes/merge; monetary cost correctly reported unknown.

The design insight: **the merged-PR denominator breaks on trunk-based
repos.** This repository lands most work as direct pushes, so 51.5
minutes/merge overstates per-change cost by roughly the ratio of pushes to
PRs (~25x here). A shipped version should denominate on pushed commits to
the default branch plus merged PRs, not merged PRs alone. Retry detection
(3 of 137 runs) worked and is the more decision-relevant signal for the
flake-DoS concern.

## Next steps

1. Keep the current prototype kit-local and advisory. Do not turn it into a
   full `test_quality` tool or a gate on this evidence.
2. Mutation-testing cost measurement (mutmut on a small real repo) is the
   remaining unstudied half of open question 1.
3. The cost prototype needs the denominator change before any further
   piloting.
