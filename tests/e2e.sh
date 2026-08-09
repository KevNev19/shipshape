#!/usr/bin/env bash
# End-to-end check of the shipshape pipeline against a scratch consumer repo.
# The mechanical half runs here; the interactive half (plugin install inside
# Claude Code) is printed as instructions at the end, because plugin trust
# approval cannot be scripted.
set -euo pipefail

KIT="$(cd "$(dirname "$0")/.." && pwd)"
scratch="${TMPDIR:-/tmp}/shipshape-e2e-$$"
consumer="$scratch/consumer"
trap 'rm -rf "$scratch"' EXIT

mkdir -p "$consumer/src"
cd "$consumer"
git init -qb main
printf '[project]\nname = "e2e-demo"\nversion = "0.1.0"\n\n[tool.pytest.ini_options]\ntestpaths = ["tests"]\n' > pyproject.toml
mkdir tests
printf 'def test_truth():\n    assert True\n' > tests/test_truth.py

echo "== detect =="
python3 "$KIT/scripts/detect.py" . --no-network > detect.json
python3 -c "import json; d=json.load(open('detect.json')); assert d['languages'][0]['name']=='python', d"

echo "== init-config + apply =="
python3 "$KIT/scripts/render.py" init-config . --detect detect.json > /dev/null
python3 "$KIT/scripts/render.py" apply . > apply.json
python3 -c "import json; r=json.load(open('apply.json')); assert r['ok'] and len(r['written'])>=10, r"

echo "== hook install + guard blocks a planted key =="
bash .sdlc/hooks/install.sh > /dev/null
key="AKIA""IOSFODNN7EXAMPLE"
printf 'ACCESS_KEY = "%s"\n' "$key" > src/config.py
git add src/config.py
if bash .sdlc/hooks/secret-guard.sh 2>/dev/null; then
  echo "FAIL: guard did not block a planted key" >&2
  exit 1
fi
git reset -q

echo "== idempotent re-apply =="
python3 "$KIT/scripts/render.py" apply . > apply2.json
python3 -c "import json; r=json.load(open('apply2.json')); assert r['written']==[], r"

echo "== doctor =="
python3 "$KIT/scripts/doctor.py" . > doctor.json \
  || { echo "FAIL: doctor reported failures" >&2; cat doctor.json >&2; exit 1; }
python3 -c "import json; d=json.load(open('doctor.json')); assert d['ok'] and d['counts']['FAIL']==0, d"

echo ""
echo "All mechanical checks passed."
echo ""
echo "Interactive half (once, by hand):"
echo "  1. cd into any test repo and open Claude Code"
echo "  2. /plugin marketplace add $KIT"
echo "  3. /plugin install shipshape@shipshape"
echo "  4. run /shipshape-init and answer the questions"
