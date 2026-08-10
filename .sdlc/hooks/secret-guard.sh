#!/usr/bin/env bash
# What this is: a safety net that checks changes for secrets (passwords,
# API keys, credential files) before they can enter history. It runs two
# ways: as a pre-commit hook on your computer (checks what you're about to
# commit), and with --range A..B in CI (checks a pushed or proposed change,
# including ones written by AI agents). If it blocks a commit, it tells you
# why. To bypass in a genuine false alarm:
#   git commit --no-verify
# Safe to edit: yes, but keep both layers — the file check and the content check.
# managed-by: shipshape v0.2.1
set -u

root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# Mode: staged index (default, pre-commit) or a commit range (CI).
range=""
if [ "${1:-}" = "--range" ]; then
  range="${2:?usage: secret-guard.sh [--range A..B]}"
fi
if [ -n "$range" ]; then
  changed="$(git diff --name-only --diff-filter=ACM "$range")"
  diff_text() { git diff -U0 "$range"; }
else
  changed="$(git diff --cached --name-only --diff-filter=ACM)"
  diff_text() { git diff --cached -U0; }
fi
[ -z "$changed" ] && exit 0
blocked=0

# Layer 1: whole files that should never enter history.
while IFS= read -r f; do
  case "$f" in
    *.pem|*.key|*id_rsa*|*id_ed25519*|*.p12|*.pfx|.env|*/.env|.env.*|*credentials.json|*serviceaccount*.json)
      echo "BLOCKED: '$f' looks like a credential or key file. Files like this" >&2
      echo "  should stay out of git entirely (add it to .gitignore instead)." >&2
      blocked=1
      ;;
  esac
done <<< "$changed"

# Layer 2: newly added lines that match well-known secret patterns.
patterns='AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,}|xox[baprs]-[A-Za-z0-9-]{10,}|sk_live_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{35}|-----BEGIN [A-Z ]*PRIVATE KEY-----'
matches="$(diff_text | grep -E '^\+' | grep -vE '^\+\+\+' | grep -cE "$patterns" || true)"
if [ "${matches:-0}" -gt 0 ]; then
  echo "BLOCKED: $matches added line(s) look like an API key, token, or private key." >&2
  echo "  If this got committed, anyone with repo access could use it." >&2
  echo "  Remove the secret and store it outside git (an ignored .env file)." >&2
  blocked=1
fi

# Optional extra denylist: one string per line in .sdlc/hooks/denylist.txt
# (keep that file out of git — it may itself contain sensitive words).
denylist="$root/.sdlc/hooks/denylist.txt"
if [ -f "$denylist" ]; then
  hits="$(diff_text | grep -E '^\+' | grep -vE '^\+\+\+' | grep -cFf "$denylist" || true)"
  if [ "${hits:-0}" -gt 0 ]; then
    echo "BLOCKED: $hits added line(s) match your private denylist." >&2
    blocked=1
  fi
fi

if [ "$blocked" -eq 1 ]; then
  echo "" >&2
  if [ -n "$range" ]; then
    echo "This change contains something that looks like a secret. Remove it" >&2
    echo "before merging — and if it was real, rotate it (change the key or" >&2
    echo "password) first: deleting the line does not un-leak it." >&2
  else
    echo "Nothing was committed. Fix the lines above and try again," >&2
    echo "or use 'git commit --no-verify' if you are sure this is a false alarm." >&2
  fi
  exit 1
fi
exit 0
