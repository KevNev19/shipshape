#!/usr/bin/env bash
# Thin wrappers around the GitHub CLI for shipshape skills. Every mutation is
# a single explicit command the skill shows the user before running. Failures
# print a plain-English fallback ("here's what to click instead") because
# branch protection APIs vary by GitHub plan and token scope.
#
# Usage:
#   gh_helpers.sh protect <branch> [--require-review]   apply protection to a branch
#   gh_helpers.sh protection-status <branch>            show current protection
set -euo pipefail

fallback() {
  echo "Could not change branch protection automatically (plan or permission limits)." >&2
  echo "Do it by hand instead: GitHub -> your repository -> Settings -> Branches ->" >&2
  echo "'Add branch ruleset', target '$1', and enable 'Require status checks to pass'." >&2
}

repo_slug() {
  gh repo view --json nameWithOwner --jq .nameWithOwner
}

cmd="${1:-}"
case "$cmd" in
  protect)
    branch="${2:?usage: gh_helpers.sh protect <branch> [--require-review]}"
    slug="$(repo_slug)"
    reviews="null"
    if [ "${3:-}" = "--require-review" ]; then
      reviews='{"required_approving_review_count":1}'
    fi
    if gh api --method PUT "repos/$slug/branches/$branch/protection" \
      --input - <<EOF
{
  "required_status_checks": {"strict": true, "contexts": ["test"]},
  "enforce_admins": false,
  "required_pull_request_reviews": $reviews,
  "restrictions": null
}
EOF
    then
      echo "Branch '$branch' is now protected (CI must pass before changes land)."
    else
      fallback "$branch"
      exit 1
    fi
    ;;
  protection-status)
    branch="${2:?usage: gh_helpers.sh protection-status <branch>}"
    slug="$(repo_slug)"
    gh api "repos/$slug/branches/$branch/protection" 2>/dev/null \
      || echo '{"protected": false}'
    ;;
  *)
    echo "usage: gh_helpers.sh protect|protection-status <branch>" >&2
    exit 2
    ;;
esac
