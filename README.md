# storycraft-skills

Canonical copy of the [Open Storycraft](https://storycraft.lanternkey.fyi/) fiction skill library, plus the scaffolding that turns it into a new series project. Each fiction project gets a pinned copy of `skills/` at `.agents/skills/` when scaffolded — skills stay project-local so every repo keeps its own git history and can fork its library freely.

## Layout

```
storycraft-skills/
├── skills/            # the 42 Storycraft skills (verbatim copies)
├── templates/         # AGENTS.md + CLAUDE.md skeletons (__SERIES_TITLE__ placeholder)
└── new-book.sh        # scaffold a new series project
```

## Usage

```bash
./new-book.sh my-series "My Series Title"        # → ~/Projects/Books/my-series
BOOKS_DIR=/some/where ./new-book.sh my-series    # → /some/where/my-series
```

The script creates the shared Wiki slots (`Characters/`, `World/`, `Style/`, `Review/`, `Story/`), Book 1's five per-book slots (`Story/Book-1/`, `Outline/Book-1/`, `Psych/Book-1/`, `Chapters/Book-1/`, `_Edits/Book-1/`), copies the skill library in, renders the two instruction files, and makes the initial git commit. From there, start the book with the planning skills in AGENTS.md's order (`fiction-genre` first).

## Provenance

- Vendored from the mermaid project's `.agents/skills/` at its commit dc010ca (2026-09-11, project start).
- First trilogy-lessons pass applied 2026-10-10: `fiction-writechapter` 4.1.0 (count/date + verbatim-dup completion checks, per-section POV markers, worker-brief rule-binding clause, two-sided word-floor rule), `fiction-reviewchapter` 2.2.0 (book-layout world paths, tolerant genre-contract extraction, page-verification step), `fiction-world` 5.1.0 (defers to the book's world layout), `name-generator` 1.1.0 (canonization collision check).
- If you ever re-sync `skills/` from upstream, re-apply those four deltas — the full rationale is recorded in the mermaid project's memory (`skill-updates-2026-10-10`).
