#!/usr/bin/env bash
# Scaffold a new fiction series project from this skill library.
#
# Usage:
#   ./new-book.sh <folder-slug> ["Series Title"]
#   BOOKS_DIR=/some/parent ./new-book.sh my-series "My Series"
#
# Creates the project folder with the shared Wiki slots, Book 1's five
# per-book slots, a pinned copy of skills/ at .agents/skills/, and the
# AGENTS.md + CLAUDE.md instruction files.
set -euo pipefail

LIBRARY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOOKS_DIR="${BOOKS_DIR:-$HOME/Projects/Books}"

SLUG="${1:-}"
TITLE="${2:-$SLUG}"

if [[ -z "$SLUG" ]]; then
  echo "usage: new-book.sh <folder-slug> [\"Series Title\"]" >&2
  exit 1
fi
if [[ "$SLUG" == */* || "$SLUG" == .* ]]; then
  echo "error: folder slug must be a plain name (no slashes, no leading dot): $SLUG" >&2
  exit 1
fi

TARGET="$BOOKS_DIR/$SLUG"
if [[ -e "$TARGET" ]]; then
  echo "error: $TARGET already exists" >&2
  exit 1
fi

echo "Scaffolding \"$TITLE\" in $TARGET"
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

sed "s/__SERIES_TITLE__/$TITLE/g" "$LIBRARY_DIR/templates/AGENTS.md" > "$TARGET/AGENTS.md"
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
echo "  2. Planning skills in order: fiction-genre, fiction-audience, fiction-theme, fiction-synopsis"
echo "  3. Then characters, world, outline, psych, scenes, style + voiceprompt, writechapter, reviewchapter"
