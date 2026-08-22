# Security & Quality Report — 2026-08-17

## TL;DR
Security posture improved since the last report: CodeQL (automated
source-code security analysis) now reports zero open alerts — the
2026-08-10 high-severity URL sanitization alert in `scripts/detect.py` was
fixed and no new ones appeared. Dependabot (dependency vulnerability
alerts) and secret-scanning data remain unavailable for the second
consecutive report because GitHub returned `403` access errors to the
workflow's token. Quality posture is fully healthy: every finished run in
the gathered window passed, the permissions audit found no workflow
without an explicit permissions block, and no pull requests are open. The
single most important action is unchanged from last week: restore report
access to the Dependabot and secret-scanning alert data.

## Security

### CodeQL
- No open alerts. The high-severity "incomplete URL substring
  sanitization" finding from the 2026-08-10 report was fixed (strict
  host matching in `scripts/detect.py`, with tests) and nothing new has
  been reported since.

### Dependabot
- Alert data is unavailable: GitHub returned `403 Resource not accessible
  by integration`, so this report cannot list or assess open dependency
  alerts this week. Second consecutive week; see Top actions.

### Secret scanning
- Alert data is unavailable for the same `403` reason. Second consecutive
  week; see Top actions.

## Quality
- **Recent run pass rate:** 19 of 19 finished runs on the default branch
  in the gathered window passed (100%); the twentieth entry was this
  reporting workflow itself, still in progress at gather time.
- **Recurring failures:** none.
- **Workflows lacking explicit permissions:** none — the audit reports
  all workflows declare explicit permissions.
- **Open PRs:** none, of any age.
- **Scheduled stewardship:** the weekly shipshape health check ran
  organically on 2026-08-19 (after this report's gather) and passed in
  6 seconds without opening an issue — the scheduled-health loop added
  by ADR 0006 is working in production.

## Trend
- **Better** than 2026-08-10: the one open high-severity CodeQL alert is
  fixed with none new; run pass rate rose from 93% to 100%; the
  permissions audit went from unverifiable to clean. The Dependabot and
  secret-scanning access gaps are **unchanged**.

## Top 3 actions
1. Restore report access to Dependabot and secret-scanning alert data
   (grant the reporting workflow's token the needed read scopes, or
   supply the `ACTIONS_PAT` secret the pipeline was designed to use) —
   two consecutive blind weeks on dependency and secret risk is the only
   gap left in the picture.
2. Decide whether the inferential half of this pipeline (agent-written
   report) should run automatically: this report was processed manually
   because no `ACTIONS_PAT` was present to assign the agent.
3. Nothing else — code security, CI health, permissions hygiene, and PR
   queue are all clean this week.
