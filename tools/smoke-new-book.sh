#!/usr/bin/env bash
# Smoke test: new-book.sh must actually produce a usable project.
#
# The scaffolder is the one script whose failure is invisible — nothing else in
# the repo imports it, and a bug in it (a title containing "/" used to abort the
# run *after* creating the directory, leaving a half-project that could not be
# retried) produced no CI failure for months. This exercises the real script
# end-to-end and asserts the tree it promises.
#
# Runs in a temp dir; leaves the repo tree untouched.
#
# Usage:
#   tools/smoke-new-book.sh
#   SMOKE_KEEP=1 tools/smoke-new-book.sh   # leave the scratch dir for inspection
set -euo pipefail

# Each scaffold commits the whole pinned library (~1k files). On a real repo that
# is enough for git to kick off background auto-maintenance, which then races the
# scratch-dir cleanup below and makes `rm -rf` fail with ENOTEMPTY. These are
# throwaway repos; turn the background work off so cleanup is deterministic.
export GIT_CONFIG_COUNT=2
export GIT_CONFIG_KEY_0=gc.auto        GIT_CONFIG_VALUE_0=0
export GIT_CONFIG_KEY_1=maintenance.auto GIT_CONFIG_VALUE_1=false

LIBRARY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NEW_BOOK="$LIBRARY_DIR/new-book.sh"
TMP="$(mktemp -d)"
if [[ "${SMOKE_KEEP:-0}" == "1" ]]; then
  trap 'echo "smoke: scratch dir kept at $TMP"' EXIT
else
  trap 'rm -rf "$TMP"' EXIT
fi

pass=0
fail=0

ok()   { pass=$(( pass + 1 )); printf '  ok   %s\n' "$1"; }
bad()  { fail=$(( fail + 1 )); printf '  FAIL %s\n' "$1" >&2; }

expect_file() {
  if [[ -f "$1" ]]; then ok "$2"; else bad "$2 (missing: $1)"; fi
}
expect_dir() {
  if [[ -d "$1" ]]; then ok "$2"; else bad "$2 (missing dir: $1)"; fi
}
# All needles here are literal strings, so match fixed-string (-F): a needle
# containing a backslash (e.g. a title with `\s`) would otherwise be read as a
# BRE escape and silently fail to match correct output.
expect_grep() {
  if grep -qF -- "$2" "$1" 2>/dev/null; then ok "$3"; else bad "$3 (no match for '$2' in $1)"; fi
}
expect_eq() {
  if [[ "$2" == "$3" ]]; then ok "$1"; else bad "$1 (got '$2', want '$3')"; fi
}

# --- 1. the ordinary case -------------------------------------------------
echo "smoke: fiction scaffold"
BOOKS_DIR="$TMP" "$NEW_BOOK" basic "Basic Book" >/dev/null 2>&1 \
  || { echo "  FAIL new-book.sh exited non-zero for the ordinary case" >&2; exit 1; }
P="$TMP/basic"
expect_dir  "$P/.agents/skills"           "pinned skill library"
expect_file "$P/AGENTS.md"                "rendered AGENTS.md"
expect_file "$P/CLAUDE.md"                "rendered CLAUDE.md"
expect_file "$P/_Intake/series-brief.md"  "rendered series brief"
expect_file "$P/_Intake/Book-1/premise.md" "rendered book premise"
expect_file "$P/Wiki/Story/Book-1/kanban.md" "starter kanban board"
expect_grep "$P/Wiki/Story/Book-1/kanban.md" "Basic Book" "title rendered into kanban board"
expect_file "$P/.agents/skills/.storycraft-source" "version pin"
expect_dir  "$P/Chapters/Book-1"          "chapter slot"
expect_file "$P/_Edits/Book-1/continuity/.enabled" "fiction continuity enabled"
expect_dir  "$P/Wiki/World/Places"        "world slot"
expect_eq   "skill count matches library" \
  "$(find "$P/.agents/skills" -name SKILL.md | wc -l | tr -d ' ')" \
  "$(find "$LIBRARY_DIR/skills" -name SKILL.md | wc -l | tr -d ' ')"
expect_grep "$P/.agents/skills/.storycraft-source" "version:" "pin records a version"
expect_grep "$P/AGENTS.md" "Basic Book"    "title rendered into AGENTS.md"
expect_grep "$P/AGENTS.md" "STORYCRAFT-MANAGED:START" "AGENTS.md has managed start marker"
expect_grep "$P/AGENTS.md" "STORYCRAFT-MANAGED:END"   "AGENTS.md has managed end marker"
if find "$P/.agents/skills" -type d -name "__pycache__" | grep -q .; then
  bad "no __pycache__ inside pinned .agents/skills"
else
  ok "no __pycache__ inside pinned .agents/skills"
fi
if grep -rq "__SERIES_TITLE__" "$P/AGENTS.md" "$P/CLAUDE.md" "$P/_Intake" "$P/Wiki/Story/Book-1/kanban.md"; then
  bad "no unrendered placeholders left behind"
else
  ok "no unrendered placeholders left behind"
fi

# --- 2. titles that break naive sed substitution ---------------------------
# A title with "/" or "&" used to abort the scaffold *after* mkdir, leaving a
# directory that the exists-check then refused to overwrite — unrecoverable.
echo "smoke: titles containing sed metacharacters"
BOOKS_DIR="$TMP" "$NEW_BOOK" nasty "Wheel of Time / Storm & Thunder" >/dev/null 2>&1 \
  && ok "new-book.sh survives / and & in the title" \
  || bad "new-book.sh survives / and & in the title"
expect_grep "$TMP/nasty/AGENTS.md" "Wheel of Time / Storm & Thunder" \
  "awkward title rendered verbatim (not expanded, not truncated)"
if grep -rq "__SERIES_TITLE__" "$TMP/nasty/AGENTS.md" 2>/dev/null; then
  bad "awkward title left no placeholder"
else
  ok "awkward title left no placeholder"
fi

# Backslash and the sed delimiter itself. The backslash case is subtle: the
# replacement is escaped for sed AND then interpolated inside a double-quoted
# string, so a regression here shows up as a silently dropped or doubled
# backslash rather than an error.
BOOKS_DIR="$TMP" "$NEW_BOOK" escaped 'Back\slash & Pipe|Title' >/dev/null 2>&1 \
  && ok "new-book.sh survives backslash and pipe in the title" \
  || bad "new-book.sh survives backslash and pipe in the title"
expect_grep "$TMP/escaped/AGENTS.md" 'Back\slash & Pipe|Title' \
  "backslash/pipe title rendered with exactly one backslash"

# --- 3. a failed run must leave nothing behind, and be retryable -----------
echo "smoke: failed run rolls back"
if BOOKS_DIR="$TMP" "$NEW_BOOK" rollback "Rollback" --import /nonexistent/path.md >/dev/null 2>&1; then
  bad "missing --import path is rejected"
else
  ok "missing --import path is rejected"
fi
if [[ -e "$TMP/rollback" ]]; then
  bad "failed run left no partial project"
else
  ok "failed run left no partial project"
fi
BOOKS_DIR="$TMP" "$NEW_BOOK" rollback "Rollback" >/dev/null 2>&1 \
  && ok "retry after failure succeeds" \
  || bad "retry after failure succeeds"

# --- 4. existing directory is still refused -------------------------------
echo "smoke: existing directory refused"
if BOOKS_DIR="$TMP" "$NEW_BOOK" basic "Basic Book" >/dev/null 2>&1; then
  bad "existing project directory is refused"
else
  ok "existing project directory is refused"
fi

# --- 5. non-fiction adds its slots; fiction does not -----------------------
echo "smoke: project types"
BOOKS_DIR="$TMP" "$NEW_BOOK" nf "Non Fiction Book" --type nonfiction >/dev/null 2>&1
expect_dir "$TMP/nf/Wiki/Concept"   "nonfiction has Wiki/Concept"
expect_dir "$TMP/nf/Wiki/Research"  "nonfiction has Wiki/Research"
expect_grep "$TMP/nf/AGENTS.md" "NONFICTION" "nonfiction type rendered"
BOOKS_DIR="$TMP" "$NEW_BOOK" hy "Hybrid Book" --type hybrid >/dev/null 2>&1
expect_dir "$TMP/hy/Wiki/Concept"   "hybrid has Wiki/Concept"
expect_dir "$TMP/hy/Wiki/Research"  "hybrid has Wiki/Research"
expect_file "$TMP/hy/_Edits/Book-1/continuity/.enabled" "hybrid continuity enabled"
expect_grep "$TMP/hy/AGENTS.md" "HYBRID" "hybrid type rendered"
if [[ -e "$TMP/basic/Wiki/Concept" ]]; then
  bad "fiction project has no Wiki/Concept"
else
  ok "fiction project has no Wiki/Concept"
fi

# --- 6. --import stages a manuscript, including dotfiles ------------------
echo "smoke: --import staging"
mkdir -p "$TMP/ms/.hidden-chapters"
printf 'chapter one\n' > "$TMP/ms/.hidden-chapters/ch01.md"
printf 'notes\n' > "$TMP/ms/notes.md"
BOOKS_DIR="$TMP" "$NEW_BOOK" imported "Imported Book" --import "$TMP/ms" >/dev/null 2>&1
expect_file "$TMP/imported/_Intake/Book-1/raw-manuscript/.hidden-chapters/ch01.md" \
  "import stages dotfile subdirectories"
expect_file "$TMP/imported/_Intake/Book-1/raw-manuscript/notes.md" "import stages plain files"

echo "smoke-new-book: $pass passed, $fail failed"
[[ "$fail" -eq 0 ]] || exit 1
