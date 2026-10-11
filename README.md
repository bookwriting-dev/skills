# storycraft-skills

Our fiction skill library — forked from [Open Storycraft](https://storycraft.lanternkey.fyi/) and independently developed. At the fork point it was the upstream's 42 skills; everything since is ours. See [CHANGELOG.md](CHANGELOG.md) for what we've changed and added, and why.

Each fiction project gets a pinned copy of `skills/` at `.agents/skills/` when scaffolded — skills stay project-local so every repo keeps its own git history and can fork its library freely.

## Layout

```
storycraft-skills/
├── skills/            # the skill library (ours since the 2026-10-10 fork)
├── templates/         # AGENTS.md + CLAUDE.md skeletons (__SERIES_TITLE__ placeholder)
├── new-book.sh        # scaffold a new series project
├── sync-check.sh      # diff against upstream to catch drift worth pulling
└── docs/              # DEVELOPER.md (library internals) · USER.md (workflow + catalog)
```

## Documentation

- **[docs/USER.md](docs/USER.md)** — the writing workflow from the outside: project layout, the fiction and non-fiction pipelines, the editing decision tree, all 59 skills with what they do and what to say to trigger them.
- **[docs/DEVELOPER.md](docs/DEVELOPER.md)** — the library from the inside: skill anatomy and frontmatter contract, worker/orchestrator conventions, the change loop (version bump → CHANGELOG → manifest → template wiring), sync-check policy, and known gaps.

## Usage

```bash
./new-book.sh my-series "My Series Title"              # → ~/Projects/Books/my-series
BOOKS_DIR=/some/where ./new-book.sh my-series          # → /some/where/my-series
./new-book.sh my-thesis "My Thesis" --type nonfiction  # or hybrid — adds Wiki/Concept + Wiki/Research
```

The script creates the shared Wiki slots (`Characters/`, `World/`, `Style/`, `Review/`, `Story/`), Book 1's five per-book slots (`Story/Book-1/`, `Outline/Book-1/`, `Psych/Book-1/`, `Chapters/Book-1/`, `_Edits/Book-1/`), copies the skill library in, renders the two instruction files, and makes the initial git commit. From there, start the book with the planning skills in AGENTS.md's order (`fiction-genre` first).

## Lineage

- Fork origin: vendored from the mermaid project's `.agents/skills/` at its commit dc010ca (2026-09-11, project start) — at that point a verbatim copy of Open Storycraft.
- Verified against the upstream ZIP (`open-storycraft-structured.zip`, downloaded 2026-10-10): the only differences from upstream were our own pre-fork passes recorded in the CHANGELOG. Nothing upstream was dropped.
- Upstream has no public repo or changelog — the ZIP is its only distribution channel. Run `./sync-check.sh` to re-check for upstream drift; any differing file not accounted for in the CHANGELOG is upstream movement to review, not an obligation to take.
- This repo is the source of truth for our library. Changes are ordinary development: add a CHANGELOG entry, bump the skill's version in its frontmatter, and go. There is no re-apply-the-deltas ritual anymore.
