# Security & Quality Report — 2026-08-10

## TL;DR
Security posture is incomplete this week: there is one open high-severity CodeQL alert, and the issue data for Dependabot and secret scanning is unavailable because GitHub returned 403 errors. Quality posture is mostly healthy: 14 of 15 finished default-branch runs passed (93%), but this reporting workflow had one recent failure and five newer runs were still queued or running when the data was gathered. The single most important action is to fix the high-severity URL sanitization alert in `scripts/detect.py:282`.

## Security

### CodeQL
- **Incomplete URL substring sanitization** — `scripts/detect.py:282`  
  **What it is:** The code appears to rely on a partial text check for a web address instead of a strict validation step.  
  **Why it matters:** A bad input could be treated as trusted when it is not, which can send the tool to the wrong destination or make it act on unsafe content.  
  **Severity:** High.  
  **Recommended action:** Replace substring-style checks with strict URL parsing and exact validation of the allowed destination, then add tests for tricky inputs.

### Dependabot
- The issue data for Dependabot alerts is unavailable: GitHub returned `403 Resource not accessible by integration`, so this report cannot list or assess open dependency alerts this week.

### Secret scanning
- The issue data for secret scanning alerts is unavailable: GitHub returned `403 Resource not accessible by integration`, so this report cannot list or assess open secret exposure alerts this week.

## Quality
- **Recent run pass rate:** 14 of 15 finished runs on the default branch passed (93%). Five additional runs were still queued or in progress when the issue data was gathered.
- **Recurring failures:** No recurring failure pattern is visible in the issue data. The only failed finished run listed is `.github/workflows/security-quality-report.yml` at `2026-08-10T21:41:44Z`.
- **Workflows lacking explicit permissions:** The issue data does not include this information, so this report cannot verify it.
- **Open PRs older than a week:** None are listed in the issue data.

## Trend
- No previous report exists under `docs/reports/`, so a better/worse/unchanged comparison is not available yet.

## Top 3 actions
1. Fix the high-severity CodeQL alert in `scripts/detect.py:282` by using strict URL validation and tests for hostile inputs.
2. Restore report access to Dependabot alert data so future weekly reports can show the real dependency risk instead of an access error.
3. Restore report access to secret scanning data, and include workflow-permissions results in the issue data so next week's report is complete.
