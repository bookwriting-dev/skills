#!/usr/bin/env bash
# Eval harness: run the library's scripts against fixtures with known defects.
#
# make check proves the library is well-formed; this proves its scripts
# *behave*. Two behavioral contracts, both previously broken and invisible
# to the shape gate:
#
#   1. Prose extraction. The fixture chapters carry a fenced stat block and
#      LitRPG callouts holding sentinel tokens (ZORBAXICUS*). USER.md
#      promises the diagnostics ignore these blocks; if a sentinel reaches
#      any diagnostic's output, the promise is broken. (drift-check had
#      exactly this bug until 2026-10-23 — callouts and fenced content
#      flowed into every metric.)
#
#   2. Ledger behavior. Both ledger skills' promises.py run against a
#      mixed-format fixture ledger (ch12 / Chapter 12 / sec2.1 / ch3.5).
#      Report wording may differ between the two skills, but the
#      status->id mapping must be identical, and the overdue set must be
#      exactly {P003, P005}: the section-referenced deadlines only read as
#      overdue under the unified first-integer chapter parser. The old
#      concatenating parser read 'sec3.2' as chapter 32 and 'ch3.5' as 35,
#      silently clearing both debts — reintroduce it and this eval goes red.
#
# PyYAML is the ledger scripts' only optional dependency. With it, the full
# behavioral check runs; without it the check is SKIPPED with a loud notice
# (CI installs PyYAML, so the gate always runs it there).
#
# Usage:
#   tools/eval-skills.sh
set -euo pipefail

LIBRARY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURES="$LIBRARY_DIR/tools/eval-fixtures"
DRIFT="$LIBRARY_DIR/skills/drift-check/references/drift.py"
MEASURE="$LIBRARY_DIR/skills/burstiness-check/references/measure.py"
LEDGER_FICTION="$LIBRARY_DIR/skills/fiction-promises/scripts/promises.py"
LEDGER_UNIFIED="$LIBRARY_DIR/skills/promise-tracker/scripts/promises.py"

# The scripts are imported by compile-check; never let a stray __pycache__
# dirty the tree (sync-check.sh would report it as a fork addition).
export PYTHONDONTWRITEBYTECODE=1

PASS=0
FAIL=0
ok()  { PASS=$((PASS + 1)); echo "  ok   $1"; }
bad() { FAIL=$((FAIL + 1)); echo "  FAIL $1" >&2; }

# --- 1. prose extraction: callouts and fences are UI, not prose ----------

echo "eval: prose extraction (sentinels must not reach any diagnostic)"

if DRIFT_OUT="$(python3 "$DRIFT" \
    "$FIXTURES/chapter-callouts.md" "$FIXTURES/chapter-monotone.md")"; then
  ok "drift.py runs on callout-bearing chapters"
else
  bad "drift.py runs on callout-bearing chapters"
  DRIFT_OUT=""
fi
if [[ -n "$DRIFT_OUT" ]] && grep -q "ZORBAXICUS" <<<"$DRIFT_OUT"; then
  bad "drift.py output is free of fence/callout sentinels (a sentinel leaked into the metrics)"
else
  ok "drift.py output is free of fence/callout sentinels"
fi

if MEASURE_OUT="$(python3 "$MEASURE" "$FIXTURES/chapter-callouts.md")"; then
  ok "measure.py runs on the callout fixture"
else
  bad "measure.py runs on the callout fixture"
  MEASURE_OUT=""
fi
if [[ -n "$MEASURE_OUT" ]] && grep -q "ZORBAXICUS" <<<"$MEASURE_OUT"; then
  bad "measure.py output is free of fence/callout sentinels"
else
  ok "measure.py output is free of fence/callout sentinels"
fi
# The callout fixture has 4 prose sentences; if extraction counted the yaml
# block or the callout, the count jumps well past that.
if python3 - "$MEASURE_OUT" <<'PY' >/dev/null 2>&1
import json, sys
d = json.loads(sys.argv[1] or "{}")
assert 4 <= d.get("sentence_count", 0) <= 6, d.get("sentence_count")
PY
then ok "measure.py counts the callout fixture's prose sentences (4-6), not its apparatus"
else bad "measure.py sentence count on the callout fixture is off (fence/callout counted?)"
fi

# The monotone fixture must be flagged: uniform length, one dominant opener.
if MONO_OUT="$(python3 "$MEASURE" "$FIXTURES/chapter-monotone.md")" \
   && python3 - "$MONO_OUT" <<'PY' >/dev/null 2>&1
import json, sys
d = json.loads(sys.argv[1])
assert d["sentence_length_variance_bucket"] == "LOW", d["sentence_length_variance_bucket"]
top = d["top_openers"][0]
assert top["word"] == "she" and top["pct"] == 100.0, top
assert d["longest_same_opener_run"] == 13, d["longest_same_opener_run"]
assert d["repetition_hotspots"], "no repetition hotspot on a fixture built from one"
PY
then ok "measure.py flags the monotone fixture (LOW variance, 100% single opener, run of 13)"
else bad "measure.py did not flag the monotone fixture as expected"
fi

# --- 2. ledger behavior: both skills, same ledger, same verdicts ---------

echo "eval: promise ledger behavior (mixed-format deadlines)"

# Reduce a report to a sorted "STATUS id" list: section headers start with
# two spaces + an uppercase label; promise lines are deeper-indented and
# start with the id (or '?'). Wording above those lines may differ between
# the two skills; this mapping may not.
normalize() {
  awk '/^  [A-Z]/ { sec = $1 } /^ +(P[0-9]+|\?) \[/ { print sec, $1 }' <<<"$1" | sort
}

if python3 -c "import yaml" 2>/dev/null; then
  A="$(python3 "$LEDGER_FICTION" --ledger "$FIXTURES/promises-ledger.yaml" --chapter ch5)"
  B="$(python3 "$LEDGER_UNIFIED" --ledger "$FIXTURES/promises-ledger.yaml" --chapter ch5)"
  if [[ "$(normalize "$A")" == "$(normalize "$B")" ]]; then
    ok "both ledger skills produce the same status->id mapping on the fixture"
  else
    bad "ledger skills disagree on the fixture's status->id mapping"
    diff <(normalize "$A") <(normalize "$B") >&2 || true
  fi
  EXPECTED_OVERDUE="$(printf 'OVERDUE P003\nOVERDUE P005\n')"
  for pair in "fiction-promises:$A" "promise-tracker:$B"; do
    name="${pair%%:*}"
    out="${pair#*:}"
    overdue="$(normalize "$out" | grep '^OVERDUE' || true)"
    if [[ "$overdue" == "$EXPECTED_OVERDUE" ]]; then
      ok "$name: section deadlines read correctly (overdue = P003, P005 — not chapters 32/35)"
    else
      bad "$name: overdue set wrong (got '$(echo $overdue | tr '\n' ' ')', want 'P003 P005') — chapter_number() regression?"
    fi
    if grep -q "5 promise(s), 1 paid" <<<"$out"; then
      ok "$name: header tallies the whole fixture ledger (5 promises, 1 paid)"
    else
      bad "$name: header does not tally the fixture ledger"
    fi
  done
else
  echo "  SKIP ledger behavioral checks: PyYAML not importable." >&2
  echo "       CI installs it; locally: python3 -m pip install PyYAML" >&2
  # Even without yaml, both skills must degrade identically: same exit code,
  # and both must say the problem out loud rather than crash. (This exact
  # check once caught fiction-promises' script missing its exec bit.)
  A_RC=0; A_OUT="$("$LEDGER_FICTION" --ledger "$FIXTURES/promises-ledger.yaml" --chapter ch5 2>&1)" || A_RC=$?
  B_RC=0; B_OUT="$("$LEDGER_UNIFIED" --ledger "$FIXTURES/promises-ledger.yaml" --chapter ch5 2>&1)" || B_RC=$?
  if [[ "$A_RC" == "$B_RC" && "$A_OUT" == *"PyYAML"* && "$B_OUT" == *"PyYAML"* ]]; then
    ok "both ledger skills degrade identically without PyYAML (rc=$A_RC, problem stated)"
  else
    bad "ledger skills diverge without PyYAML (rc $A_RC vs $B_RC, or the problem went unstated)"
  fi
fi

echo "eval-skills: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
