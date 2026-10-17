#!/usr/bin/env bash
# Scaffold a new book/series project from this skill library.
#
# Usage:
#   ./new-book.sh <folder-slug> ["Series Title"] [--type fiction|nonfiction|hybrid] [--import <path>]
#   BOOKS_DIR=/some/parent ./new-book.sh my-series --type nonfiction
#   ./new-book.sh my-series "Series Title" --import /path/to/manuscript.md
#
# Creates the project folder with the shared Wiki slots, Book 1's five
# per-book slots, the _Intake staging area, a pinned copy of skills/ at
# .agents/skills/, and the AGENTS.md + CLAUDE.md instruction files.
# --type sets the rendered project-type line and adds the non-fiction Wiki
# slots. --import copies an existing manuscript into _Intake/Book-1/raw-manuscript/
# for reverse-engineering.
set -euo pipefail

LIBRARY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOOKS_DIR="${BOOKS_DIR:-$HOME/Projects/Books}"

SLUG=""
TITLE=""
PROJECT_TYPE="fiction"
IMPORT_SOURCE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --type)
      [[ $# -ge 2 ]] || { echo "error: --type needs a value (fiction|nonfiction|hybrid)" >&2; exit 1; }
      PROJECT_TYPE="$2"; shift 2 ;;
    --type=*)
      PROJECT_TYPE="${1#--type=}"; shift ;;
    --import)
      [[ $# -ge 2 ]] || { echo "error: --import needs a path to an existing manuscript" >&2; exit 1; }
      IMPORT_SOURCE="$2"; shift 2 ;;
    --import=*)
      IMPORT_SOURCE="${1#--import=}"; shift ;;
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
  echo "usage: new-book.sh <folder-slug> [\"Series Title\"] [--type fiction|nonfiction|hybrid] [--import <path>]" >&2
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

# Record which library revision this project pinned, so `tools/update-project.sh`
# (and the author) can tell at a glance when the project is behind.
LIB_VERSION="$(cat "$LIBRARY_DIR/VERSION" 2>/dev/null || echo unknown)"
LIB_COMMIT="$(git -C "$LIBRARY_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)"
LIB_COUNT="$(find "$TARGET/.agents/skills" -name SKILL.md | wc -l | tr -d ' ')"
cat > "$TARGET/.agents/skills/.storycraft-source" <<EOF
library: storycraft-skills
version: $LIB_VERSION
commit: $LIB_COMMIT
skills: $LIB_COUNT
pinned: $(date +%Y-%m-%d)
source: $LIBRARY_DIR
EOF

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
  "$TARGET/_Edits/Book-1" \
  "$TARGET/_Intake/Book-1/raw-notes"

# Intake templates: inspirational staging for series and Book 1.
sed "s/__SERIES_TITLE__/$TITLE/g" \
  "$LIBRARY_DIR/templates/series-brief.md" > "$TARGET/_Intake/series-brief.md"
sed -e "s/__SERIES_TITLE__/$TITLE/g" -e "s/__BOOK_NUM__/1/g" \
  "$LIBRARY_DIR/templates/book-premise.md" > "$TARGET/_Intake/Book-1/premise.md"

# If an existing manuscript was supplied, stage it in _Intake/Book-1/raw-manuscript/
if [[ -n "$IMPORT_SOURCE" ]]; then
  if [[ ! -e "$IMPORT_SOURCE" ]]; then
    echo "error: import path does not exist: $IMPORT_SOURCE" >&2
    exit 1
  fi
  mkdir -p "$TARGET/_Intake/Book-1/raw-manuscript"
  if [[ -d "$IMPORT_SOURCE" ]]; then
    cp -R "$IMPORT_SOURCE"/* "$TARGET/_Intake/Book-1/raw-manuscript/"
  else
    cp "$IMPORT_SOURCE" "$TARGET/_Intake/Book-1/raw-manuscript/"
  fi
  echo "Imported raw manuscript to _Intake/Book-1/raw-manuscript/"
fi

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
if [[ -n "$IMPORT_SOURCE" ]]; then
  echo "  2. Reverse-engineer existing manuscript:"
  echo "     Run 'book-reverse-engineer' to analyze the text, extract Wiki canon, promises, and findings."
  echo "  3. Review _Edits/Book-1/reverse-analysis.md, approve canon decisions, then run the import pass."
elif [[ "$PROJECT_TYPE" == "fiction" ]]; then
  echo "  2. Fill out or add notes to _Intake/series-brief.md (or drop notes in _Intake/Book-1/raw-notes/)"
  echo "  3. Planning skills in order (they ingest _Intake first): fiction-genre, fiction-audience, fiction-theme, fiction-synopsis, fiction-series-outline"
  echo "  4. Then characters, world, outline, divergence, psych, scenes, style + voiceprompt, writechapter, reviewchapter"
elif [[ "$PROJECT_TYPE" == "nonfiction" ]]; then
  echo "  2. Fill out or add notes to _Intake/series-brief.md"
  echo "  3. Planning skills in order: nonfiction-concept, nonfiction-audience, nonfiction-structure"
  echo "  4. Then chapter-plan, writechapter, factcheck, clarity-edit; promise-tracker as chapters land"
else
  echo "  2. Hybrid project: fiction planning order for the narrative, non-fiction planning order for the argument (see AGENTS.md routing)"
fi
