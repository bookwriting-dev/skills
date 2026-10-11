#!/usr/bin/env bash
# Scaffold a new book/series project from this skill library.
#
# Usage:
#   ./new-book.sh <folder-slug> ["Series Title"] [--type fiction|nonfiction|hybrid]
#   BOOKS_DIR=/some/parent ./new-book.sh my-series --type nonfiction
#
# Creates the project folder with the shared Wiki slots, Book 1's five
# per-book slots, a pinned copy of skills/ at .agents/skills/, and the
# AGENTS.md + CLAUDE.md instruction files. --type sets the rendered
# project-type line and adds the non-fiction Wiki slots (Wiki/Concept/,
# Wiki/Research/) for nonfiction and hybrid projects.
set -euo pipefail

LIBRARY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOOKS_DIR="${BOOKS_DIR:-$HOME/Projects/Books}"

SLUG=""
TITLE=""
PROJECT_TYPE="fiction"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --type)
      [[ $# -ge 2 ]] || { echo "error: --type needs a value (fiction|nonfiction|hybrid)" >&2; exit 1; }
      PROJECT_TYPE="$2"; shift 2 ;;
    --type=*)
      PROJECT_TYPE="${1#--type=}"; shift ;;
    -*)
      echo "error: unknown flag: $1" >&2; exit 1 ;;
    *)
      if [[ -z "$SLUG" ]]; then SLUG="$1"
      elif [[ -z "$TITLE" ]]; then TITLE="$1"
      else echo "error: unexpected argument: $1" >&2; exit 1
      fi
      shift ;;
  esac
done

if [[ -z "$SLUG" ]]; then
  echo "usage: new-book.sh <folder-slug> [\"Series Title\"] [--type fiction|nonfiction|hybrid]" >&2
  exit 1
fi
if [[ "$SLUG" == */* || "$SLUG" == .* ]]; then
  echo "error: folder slug must be a plain name (no slashes, no leading dot): $SLUG" >&2
  exit 1
fi
case "$PROJECT_TYPE" in
  fiction|nonfiction|hybrid) ;;
  *) echo "error: --type must be fiction, nonfiction, or hybrid: $PROJECT_TYPE" >&2; exit 1 ;;
esac
TITLE="${TITLE:-$SLUG}"
TYPE_UPPER="$(printf '%s' "$PROJECT_TYPE" | tr '[:lower:]' '[:upper:]')"

TARGET="$BOOKS_DIR/$SLUG"
if [[ -e "$TARGET" ]]; then
  echo "error: $TARGET already exists" >&2
  exit 1
fi

echo "Scaffolding \"$TITLE\" ($PROJECT_TYPE) in $TARGET"
mkdir -p "$TARGET/.agents"

# Skill library: pinned copy, not a symlink — each project versions its own.
cp -R "$LIBRARY_DIR/skills" "$TARGET/.agents/skills"

# Wiki skeleton: shared slots + Book 1's five per-book slots.
mkdir -p \
  "$TARGET/Wiki/Story/Book-1" \
  "$TARGET/Wiki/Characters" \
  "$TARGET/Wiki/Style" \
  "$TARGET/Wiki/Review" \
  "$TARGET/Wiki/Outline/Book-1" \
  "$TARGET/Wiki/Psych/Book-1" \
  "$TARGET/Wiki/World/Places" \
  "$TARGET/Wiki/World/Factions" \
  "$TARGET/Wiki/World/Systems" \
  "$TARGET/Wiki/World/Events" \
  "$TARGET/Chapters/Book-1" \
  "$TARGET/_Edits/Book-1"

# Non-fiction slots (the workflow template expects them for NONFICTION/HYBRID).
if [[ "$PROJECT_TYPE" != "fiction" ]]; then
  mkdir -p "$TARGET/Wiki/Concept" "$TARGET/Wiki/Research"
fi

sed -e "s/__SERIES_TITLE__/$TITLE/g" -e "s/__PROJECT_TYPE__/$TYPE_UPPER/g" \
  "$LIBRARY_DIR/templates/AGENTS.md" > "$TARGET/AGENTS.md"
sed "s/__SERIES_TITLE__/$TITLE/g" "$LIBRARY_DIR/templates/CLAUDE.md" > "$TARGET/CLAUDE.md"

# git: prefer a working git; fall back to the Xcode binary (CLT license block).
GIT_BIN=""
if command -v git >/dev/null 2>&1 && git --version >/dev/null 2>&1; then
  GIT_BIN="git"
elif [[ -x "/Applications/Xcode.app/Contents/Developer/usr/bin/git" ]]; then
  GIT_BIN="/Applications/Xcode.app/Contents/Developer/usr/bin/git"
fi

if [[ -n "$GIT_BIN" ]]; then
  (
    cd "$TARGET"
    "$GIT_BIN" init -b main >/dev/null 2>&1 || "$GIT_BIN" init >/dev/null
    "$GIT_BIN" add -A
    "$GIT_BIN" commit -m "chore: scaffold $TITLE from storycraft-skills" >/dev/null 2>&1 \
      || echo "note: initial commit failed — check git user.name/email; files are staged" >&2
  )
else
  echo "note: no working git found; $TARGET created without a repository" >&2
fi

echo
echo "Done. Next steps (see AGENTS.md):"
echo "  1. cd $TARGET"
if [[ "$PROJECT_TYPE" == "fiction" ]]; then
  echo "  2. Planning skills in order: fiction-genre, fiction-audience, fiction-theme, fiction-synopsis, fiction-series-outline"
  echo "  3. Then characters, world, outline, divergence, psych, scenes, style + voiceprompt, writechapter, reviewchapter"
elif [[ "$PROJECT_TYPE" == "nonfiction" ]]; then
  echo "  2. Planning skills in order: nonfiction-concept, nonfiction-audience, nonfiction-structure"
  echo "  3. Then chapter-plan, writechapter, factcheck, clarity-edit; promise-tracker as chapters land"
else
  echo "  2. Hybrid project: fiction planning order for the narrative, non-fiction planning order for the argument (see AGENTS.md routing)"
fi
