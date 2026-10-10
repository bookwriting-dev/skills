# __SERIES_TITLE__

A fiction project using the [Open Storycraft](https://storycraft.lanternkey.fyi/) skill library.

Canon lives in `Wiki/`. Prose lives in `Chapters/`. Skills live in `.agents/skills/`. Do not invent a parallel manuscript folder, and do not treat a previous chapter as Wiki canon.

## Books and shared canon

This repo holds a series, so everything is either **shared series canon** or **per-book**. Shared canon never moves into a book folder; per-book work never sits loose at a root.

- **Shared (Wiki root):** `Wiki/Characters/`, `Wiki/World/`, `Wiki/Style/`, `Wiki/Story/theme.md`, `Wiki/Story/synopsis.md` (the series synopsis), `Wiki/Story/series-arc.md` (the series-level plan maintained by `fiction-series-outline`), `Wiki/Story/active-context.md` (the working log for the whole series), and `Wiki/Review/` (the series review panel — build it when Book 1 reaches review).
- **Per-book (`Book-N/` subfolders):** every book gets the same five slots, whether or not they are filled yet — `Wiki/Story/Book-N/` (book synopsis, revision plans, `promises.yaml` — the Chekhov ledger), `Wiki/Outline/Book-N/` (outline + `Chapter_NN_Scene.md` beats + `surprise-ledger.md`), `Wiki/Psych/Book-N/`, `Chapters/Book-N/`, `_Edits/Book-N/`.
- Older entries in `active-context.md` may cite pre-reorg root paths (e.g. `Chapters/Chapter-035.md`); the moved location is under `Book-N/`.

## Folder layout

```
.
├── AGENTS.md                 # this file — project-wide writing rules
├── CLAUDE.md                 # one-line import of AGENTS.md
├── .agents/skills/           # the skill library + companion files
├── Wiki/                     # series canon
│   ├── Story/                # theme, series synopsis, series arc, active context
│   │   └── Book-N/           # per-book: synopsis, revision plans, promises.yaml
│   ├── Characters/           # one file per character (series-wide)
│   ├── Outline/
│   │   └── Book-N/           # outline.md + Chapter_NN_Scene.md beats + surprise-ledger.md
│   ├── Psych/
│   │   └── Book-N/           # Chapter_NN_Psych.md
│   ├── Style/                # genre, audience, style/review/voice guides
│   ├── Review/               # series review panel: panel.md + personas
│   └── World/                # setting, places, factions, polities, religions
├── Chapters/
│   └── Book-N/               # Chapter-001.md …
└── _Edits/
    └── Book-N/               # Chapter-NNN_Review.md, sanity checks
```

## Authority

1. The user's current instructions.
2. This file (`AGENTS.md`).
3. Established Wiki files for this book.
4. The invoked skill's instructions.
5. Generic defaults in a skill.

If Wiki and a draft disagree, Wiki wins until the user explicitly changes canon. If a skill would create a proper noun that is not in Wiki, stop and say so rather than inventing it.

## How to start a book

Run these skills in order unless the user skips a step:

1. `fiction-genre` → `Wiki/Style/genre.md`
2. `fiction-audience` → `Wiki/Style/audience.md`
3. `fiction-theme` → `Wiki/Story/theme.md`
4. `fiction-synopsis` → `Wiki/Story/synopsis.md`
5. `fiction-series-outline` → `Wiki/Story/series-arc.md` (at series inception; refresh before planning each later book)
6. `fiction-characters` → `Wiki/Characters/`
7. `fiction-world` (and `fiction-places` / `fiction-factions` / `fiction-polities` / `fiction-religions` as needed)
8. `fiction-outline` → `Wiki/Outline/Book-N/outline.md`
9. `fiction-divergence` → beat-the-defaults pass over the outline, plus the per-act surprise ledger
10. `fiction-psych` → `Wiki/Psych/Book-N/`
11. `fiction-scenes` → chapter beat plans
12. `fiction-style` + `fiction-voiceprompt`
13. `fiction-writechapter` → `Chapters/Book-N/Chapter-NNN.md`
14. `fiction-reviewchapter` (its review audits the `promises.yaml` ledger; then line/prose/kill skills as needed)
15. `fiction-review-panel` per act and before calling the book done (persona reads, verified findings → `Wiki/Review/`); `drift-check` at part boundaries for book-level drift the per-chapter gates cannot see

`fiction-story-sparks` is only for an explicit prompt, card-style idea, or writing exercise. Do not use it to start or rewrite this book unless asked. For a second book, run `fiction-series-outline` first to refresh `Wiki/Story/series-arc.md` and honor the handoff inventory and inter-book promise map; the already-canonical series-level steps (genre, audience, theme, series synopsis, characters, world, style) are skipped unless the book needs new entries, and the book starts at its own synopsis in `Wiki/Story/Book-N/`.

## Chapter files

Default path: `Chapters/Book-N/Chapter-NNN.md` (three-digit). Put the chapter title inside the file, with the POV name(s) beneath the title. Review reports go to `_Edits/Book-N/Chapter-NNN_Review.md` (three-digit, matching the chapter).

## Naming

When a skill must invent a proper name, use `name-generator` (people) or `town-generator` (settlements). Do not freehand names. Before a generated name enters canon, collision-check it against existing fiction, games, and brands; deliberately anonymous characters stay unnamed.

## Editing

Story-level problems go to `fiction-dev-editor` or `fiction-reviewchapter`. Loose ends and unpaid setups go to `fiction-promises`. Sentence-level problems go to `fiction-line-editor`, `fiction-prose-editor`, or `fiction-full-editor`. Recurring model crutches go to the `kill-*` skills. Book-level drift — pet words, rising construction density, template openers and closers — goes to `drift-check`. Reader-reaction findings come from `fiction-review-panel`. Do not run a kill pass or full edit unless the user asked for revision. Structural review findings — required beats missing or misfired, wrong POV architecture, a canon breach baked through the chapter — are not editing jobs: fix the scene plan or brief and re-draft the chapter with `fiction-writechapter`. Editing passes are for localizable problems.

## Skill index

**Plan the promise:** `fiction-story-sparks`, `fiction-series-outline`, `fiction-genre`, `fiction-audience`, `fiction-theme`, `fiction-synopsis`

**Build the people:** `fiction-characters`, `fiction-psych`, `fiction-dialogue`, `fiction-voiceprompt`

**Build the world:** `fiction-world`, `fiction-places`, `fiction-factions`, `fiction-polities`, `fiction-religions`, `name-generator`, `town-generator`, `fantasy-settlement`

**Shape the book:** `fiction-outline`, `fiction-divergence`, `fiction-scenes`, `fiction-style`, `fiction-writechapter`

**Review the story:** `coldread`, `fiction-dev-editor`, `fiction-reviewchapter`, `fiction-promises`, `fiction-review-panel`

**Edit the prose:** `fiction-line-editor`, `fiction-prose-editor`, `fiction-full-editor`, `levelup`, `fragment-hunter`, `nominalization-hunt`

**Remove the tells:** `fiction-aiism-editor`, `burstiness-check`, `drift-check`, `pangram`, `kill-chapter`, `kill-simile`, `kill-crutch`, `kill-soft`, `kill-flat`, `kill-the-whole`, `kill-person-who`, `kill-opinion-personification`

**Make your own:** `skill-builder`
