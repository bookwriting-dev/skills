#!/usr/bin/env bash
# Update a project's pinned skill library from this repo.
#
# A project gets a *pinned copy* of skills/ at .agents/skills/ when scaffolded
# (see new-book.sh); changes here do not propagate automatically. This script
# shows what would change and, with --apply, copies the current library in.
#
# Usage:
#   tools/update-project.sh <project-dir>            # report only (dry run)
#   tools/update-project.sh <project-dir> --apply    # copy library in, rewrite pin
#   tools/update-project.sh <project-dir> --prune    # with --apply: delete removed files
#
# Update is additive by default: new and changed skill files are copied; files
# that exist only in the project (a local fork of a skill) are reported but left
# alone unless --prune is given. The project's .agents/skills/.storycraft-source
# pin is rewritten on --apply.
set -euo pipefail

LIBRARY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIB_SKILLS="$LIBRARY_DIR/skills"

APPLY=0
PRUNE=0
PROJECT=""

for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --prune) PRUNE=1 ;;
    -*) echo "error: unknown flag: $arg" >&2; exit 2 ;;
    *) if [[ -z "$PROJECT" ]]; then PROJECT="$arg"; else echo "error: unexpected argument: $arg" >&2; exit 2; fi ;;
  esac
done

if [[ -z "$PROJECT" ]]; then
  echo "usage: tools/update-project.sh <project-dir> [--apply] [--prune]" >&2
  exit 2
fi
if [[ ! -d "$PROJECT" ]]; then
  echo "error: project directory not found: $PROJECT" >&2
  exit 2
fi
PROJ_SKILLS="$PROJECT/.agents/skills"
if [[ ! -d "$PROJ_SKILLS" ]]; then
  echo "error: $PROJ_SKILLS not found — is $PROJECT a scaffolded book project?" >&2
  exit 2
fi
if [[ ! -d "$LIB_SKILLS" ]]; then
  echo "error: library skills/ not found at $LIB_SKILLS" >&2
  exit 2
fi

echo "Library: $LIBRARY_DIR (version $(cat "$LIBRARY_DIR/VERSION" 2>/dev/null || echo unknown))"
if [[ -f "$PROJ_SKILLS/.storycraft-source" ]]; then
  echo "Project pin:"
  sed 's/^/  /' "$PROJ_SKILLS/.storycraft-source"
else
  echo "Project pin: (none — predates version pinning)"
fi
echo

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
: > "$TMP/add"; : > "$TMP/chg"; : > "$TMP/rem"

# `diff -rq` prints one of:
#   Files <lib>/a and <proj>/a differ
#   Only in <some/dir>: <name>
#   Only in <some/dir>: <name>       (same shape, but <some/dir> is the
#                                     *innermost* differing directory, not
#                                     necessarily the root we diffed)
#
# Every branch must rebuild a path relative to the skills root by stripping a
# *known* prefix. Stripping up to the first ": " instead would silently drop the
# leading directory — `Only in <proj>/skills/book-status: references` would parse
# as `references`, and --apply --prune would then rm -f a path that does not
# exist, report success, and leave the file in place.
#
# $1 = the whole diff line, $2 = the skills root that line is relative to.
relpath() {
  local head="$1" root="$2" dir name
  head="${head#Only in }"
  dir="${head%%: *}"            # longest ": *"-suffixed tail = the name(s)
  name="${head#*: }"            # shortest prefix = "dir: "
  dir="${dir#"$root"}"          # exact-prefix strip; leaves "/sub/dir" or ""
  dir="${dir#/}"               # "" when dir == root, else the sub-path
  printf '%s\n' "${dir:+$dir/}$name"
}

while IFS= read -r line; do
  case "$line" in
    "Files "*)
      rel="${line#Files }"; rel="${rel%% and *}"; rel="${rel#"$LIB_SKILLS"/}"
      printf '%s\n' "$rel" >> "$TMP/chg" ;;
    "Only in $LIB_SKILLS/"*|"Only in $LIB_SKILLS: "*)
      rel="$(relpath "$line" "$LIB_SKILLS")"
      [[ "$rel" == ".storycraft-source" ]] || printf '%s\n' "$rel" >> "$TMP/add" ;;
    "Only in $PROJ_SKILLS/"*|"Only in $PROJ_SKILLS: "*)
      rel="$(relpath "$line" "$PROJ_SKILLS")"
      [[ "$rel" == ".storycraft-source" ]] || printf '%s\n' "$rel" >> "$TMP/rem" ;;
  esac
done < <(diff -rq -x .storycraft-source "$LIB_SKILLS" "$PROJ_SKILLS" || true)

n_add=$(wc -l < "$TMP/add" | tr -d ' ')
n_chg=$(wc -l < "$TMP/chg" | tr -d ' ')
n_rem=$(wc -l < "$TMP/rem" | tr -d ' ')

report() {
  echo "$1 ($2):"
  if [[ "$2" -eq 0 ]]; then
    echo "  (none)"
  else
    sed 's/^/  /' "$3"
  fi
}
report "New skills/files    " "$n_add" "$TMP/add"
report "Changed skill files " "$n_chg" "$TMP/chg"
report "Only in project     " "$n_rem" "$TMP/rem"
echo

total=$(( n_add + n_chg ))

if [[ "$APPLY" -eq 0 ]]; then
  echo "Dry run. Re-run with --apply to copy the library in (additive)."
  [[ "$PRUNE" -eq 1 ]] && echo "(--prune given: project-only files would be deleted on --apply)"
  exit 0
fi

# Additive copy: overwrite changed files, add new ones, leave project-only files.
cp -R "$LIB_SKILLS/." "$PROJ_SKILLS/"

if [[ "$PRUNE" -eq 1 && "$n_rem" -gt 0 ]]; then
  pruned=0
  missed=0
  while IFS= read -r rel; do
    target="$PROJ_SKILLS/$rel"
    if [[ -d "$target" ]]; then
      # diff reports a directory here only when the whole subtree is project-only
      # (e.g. a locally forked skill folder). Removing it is what --prune means.
      rm -rf "$target"; pruned=$(( pruned + 1 ))
    elif [[ -e "$target" ]]; then
      rm -f "$target"; pruned=$(( pruned + 1 ))
    else
      # Should be unreachable: every path in $TMP/rem came from this diff run.
      echo "warn: listed for pruning but not found, skipping: $rel" >&2
      missed=$(( missed + 1 ))
    fi
  done < "$TMP/rem"
  # clean up now-empty directories
  find "$PROJ_SKILLS" -type d -empty -delete 2>/dev/null || true
  echo "Pruned $pruned project-only path(s)."
  [[ "$missed" -eq 0 ]] || echo "warn: $missed path(s) were listed but absent; nothing deleted." >&2
fi

# Rewrite the pin.
LIB_VERSION="$(cat "$LIBRARY_DIR/VERSION" 2>/dev/null || echo unknown)"
LIB_COMMIT="$(git -C "$LIBRARY_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)"
LIB_COUNT="$(find "$LIB_SKILLS" -name SKILL.md | wc -l | tr -d ' ')"
cat > "$PROJ_SKILLS/.storycraft-source" <<EOF
library: storycraft-skills
version: $LIB_VERSION
commit: $LIB_COMMIT
skills: $LIB_COUNT
pinned: $(date +%Y-%m-%d)
source: $LIBRARY_DIR
EOF

echo "Applied: $total file(s) updated, pin rewritten."
echo "Review and commit in the project repo:"
echo "  cd $PROJECT && git add .agents/skills && git commit -m 'chore: update skill library'"
