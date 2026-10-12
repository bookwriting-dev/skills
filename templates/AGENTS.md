# __SERIES_TITLE__

A book project using the [Open Storycraft](https://storycraft.lanternkey.fyi/) skill library.

Canon lives in `Wiki/`. Prose lives in `Chapters/`. Skills live in `.agents/skills/`. Do not invent a parallel manuscript folder, and do not treat a previous chapter as Wiki canon.

## Project Type

This project is: **__PROJECT_TYPE__** (FICTION, NONFICTION, or HYBRID — set by `new-book.sh --type`; edit here if the project changes).

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

## How to start a book (FICTION)

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
15. `review-panel` per act and before calling the book done (persona reads, verified findings → `Wiki/Review/`); `drift-check` at part boundaries for book-level drift the per-chapter gates cannot see

`fiction-story-sparks` is only for an explicit prompt, card-style idea, or writing exercise. Do not use it to start or rewrite this book unless asked. For a second book, run `fiction-series-outline` first to refresh `Wiki/Story/series-arc.md` and honor the handoff inventory and inter-book promise map; the already-canonical series-level steps (genre, audience, theme, series synopsis, characters, world, style) are skipped unless the book needs new entries, and the book starts at its own synopsis in `Wiki/Story/Book-N/`.

## How to start a book (NONFICTION)

Run these skills in order unless the user skips a step:

1. `nonfiction-concept` → `Wiki/Concept/thesis.md`
2. `nonfiction-audience` → `Wiki/Concept/audience.md`
3. `nonfiction-structure` → `Wiki/Concept/structure.md`
4. `nonfiction-chapter-plan` → `Wiki/Outline/Book-N/plan.md`
5. `nonfiction-writechapter` → `Chapters/Book-N/Chapter-NNN.md`
6. `nonfiction-factcheck` → `_Edits/Book-N/Chapter-NNN_FactCheck.md`
7. `nonfiction-clarity-edit` → `_Edits/Book-N/Chapter-NNN_ClarityEdit.md`
8. `promise-tracker` → `Wiki/Story/Book-N/promises.yaml` (track claims/promises as chapters land)
9. `review-panel` → `Wiki/Review/` (personas; per part and before calling the book done)
10. `drift-check` → book-level audit at part boundaries

For a second book, refresh the shared concept/structure/audience in `Wiki/Concept/` as needed; the book starts at its own chapter plan in `Wiki/Outline/Book-N/`.

## Chapter files

Default path: `Chapters/Book-N/Chapter-NNN.md` (three-digit). Put the chapter title inside the file, with the POV name(s) beneath the title. Review reports go to `_Edits/Book-N/Chapter-NNN_Review.md` (three-digit, matching the chapter).

## Naming and place generation

When inventing proper nouns or locations, route to the specific generator:
- **People / character names:** `name-generator`. Do not freehand names. Before a generated name enters canon, collision-check it against existing fiction, games, and brands; deliberately anonymous characters stay unnamed.
- **Town / settlement names:** `town-generator` (lexical naming only).
- **Full settlement profiles:** `fantasy-settlement` (complete dossier with population, economy, districts, security).
- **Scene-bearing sites / landmarks:** `fiction-places` (ruins, rooms, wilderness sites, tactical locations; not full towns).

**Non-fiction:** proper nouns are real — never run the generators. Names, places, and terms come from research with sources, and `nonfiction-factcheck` audits them.

## Editing

Do not run a kill pass or full edit unless the user asked for revision.

Structural review findings — required beats missing or misfired, wrong POV architecture, a canon breach baked through the chapter — are not editing jobs: fix the scene plan or brief and re-draft the chapter with `fiction-writechapter` (fiction) or `nonfiction-writechapter` (non-fiction). Editing passes are for localizable problems.

Route editing and review tasks using this decision tree:

**Fiction:**
- **Story structure / causality / "does this chapter move?":** `fiction-dev-editor`. Diagnose scene beats, pacing, and causality before touching lines.
- **Chapter gate (default review):** `fiction-reviewchapter`. Full 10-criteria gate checking canon assertions, Chekhov setups, character consistency, and prose rules.
- **Dialogue-only failure (samey, interview-like, expository):** `fiction-dialogue`. Diagnose conversation architecture and speaker stakes before diction.
- **Blind POV / voice test:** `coldread`. Read-only, run in isolation before rule-loaded review so house rules do not prime the reader.
- **Loose ends and unpaid setups:** `fiction-promises`. Audits the per-book Chekhov ledger (`promises.yaml`).
- **Sentence-level revision (default):** `fiction-full-editor`. Scans micro-level craft, AI-isms, and line edits in one pass. Use layer-specific scanners (`fiction-line-editor`, `fiction-prose-editor`, `fiction-aiism-editor`) only when specifically targeting that single layer.
- **Applying approved review/edit fixes:** `fiction-revise`. Applies user-approved items from `_Edits/` reports in place with strict quote verification, minimal perturbation, and a change ledger.
- **Recurring model crutches (default):** `kill-chapter`. Runs all seven kill passes consecutively in place (similes, person-who, opinion-personification, the-whole, crutch, soft, flat). Use single-kill passes (`kill-crutch WORD`, `kill-simile`, `kill-the-whole`, `kill-person-who`, `kill-opinion-personification`) only when targeting a specific token.
- **Book-level drift / back-half flatness / formula openers:** `drift-check` across part boundaries and chapters.
- **Reader reaction / persona reads:** `review-panel`. Multi-persona qualitative reads with verified citations.

**Non-Fiction:**
- **Structural / argument flow / "does this chapter prove?":** `nonfiction-dev-editor`. Diagnose argument architecture, claim scaffolding, and cognitive load before sentence edits.
- **Chapter gate (default review):** `nonfiction-factcheck` + `nonfiction-clarity-edit`. Fact/evidence verification first, then the clarity pass (jargon density, abstraction ladder, cognitive load, signposting).
- **Fact / evidence failure:** `nonfiction-factcheck`. Verifies every claim against the book's research corpus and cited sources.
- **Blind clarity / voice test:** `coldread`. Read-only, run in isolation before rule-loaded review so house rules do not prime the reader.
- **Unsupported claims / missing evidence:** `promise-tracker`. Audits the per-book promise/claim ledger (`promises.yaml`).
- **Sentence-level revision (default):** `nonfiction-clarity-edit`. Scans micro-level clarity, jargon, passive voice, and line edits in one pass.
- **Applying approved review/edit fixes:** `fiction-revise`. Report-driven and book-agnostic — it applies user-approved items from any `_Edits/Chapter-NNN_*.md` report with strict quote verification and a change ledger.
- **Recurring clarity crutches:** run the targeted passes — `nominalization-hunt`, `kill-passive`, `kill-hedge`, `kill-acronym`. Use a single pass when targeting one pattern.
- **Book-level drift / argument coherence / thesis alignment:** `drift-check` across part boundaries and chapters.
- **Reader reaction / persona reads:** `reader-persona-review` (or `review-panel`). Multi-persona qualitative reads with verified citations.

## Skill index

### Fiction skills

**Plan the promise:** `fiction-story-sparks`, `fiction-series-outline`, `fiction-genre`, `fiction-audience`, `fiction-theme`, `fiction-synopsis`

**Build the people:** `fiction-characters`, `fiction-psych`, `fiction-dialogue`, `fiction-voiceprompt`, `name-generator`

**Build the world:** `fiction-world`, `fiction-places`, `fiction-factions`, `fiction-polities`, `fiction-religions`, `town-generator`, `fantasy-settlement`

**Shape the book:** `fiction-outline`, `fiction-divergence`, `fiction-scenes`, `fiction-style`, `fiction-writechapter`

**Workflow & Orchestration:** `chapter-pipeline`, `gate-check`, `book-status`, `canon-guard`

**Review the story (decision tree):**
- Blind voice read: `coldread`
- Structural / developmental: `fiction-dev-editor`
- Comprehensive chapter gate: `gate-check`, `fiction-reviewchapter`
- Chekhov promise ledger: `fiction-promises`
- Reader persona panel: `reader-persona-review`, `review-panel`
- Multi-book consistency: `series-continuity`

**Edit the prose (decision tree):**
- Default full sentence edit: `fiction-full-editor`
- Apply approved report edits: `fiction-revise`
- Single-layer passes: `fiction-line-editor`, `fiction-prose-editor`, `fiction-aiism-editor`
- Targeted scans: `levelup`, `fragment-hunter`, `nominalization-hunt`, `kill-hedge`, `kill-passive`, `kill-acronym`

**Remove the tells (decision tree):**
- Default 7-pass crutch orchestrator: `kill-chapter`
- Targeted kill passes: `kill-simile`, `kill-person-who`, `kill-opinion-personification`, `kill-the-whole`, `kill-crutch` (covers `kill-soft` and `kill-flat`)
- Statistical & drift diagnostics: `drift-check`, `burstiness-check`, `pangram`

**Publish & Package:**
- Manuscript compile & export: `compile-manuscript`
- Marketing & publishing kit: `book-packaging`

### Non-Fiction skills

**Plan the thesis:** `nonfiction-concept`, `nonfiction-audience`, `nonfiction-structure`, `nonfiction-research`

**Shape the book:** `nonfiction-chapter-plan`, `nonfiction-writechapter`

**Review the argument (decision tree):**
- Blind clarity read: `coldread`
- Structural / developmental: `nonfiction-dev-editor`
- Comprehensive chapter gate: `nonfiction-factcheck` + `nonfiction-clarity-edit`
- Fact & evidence verification: `nonfiction-factcheck`
- Promise / claim ledger: `promise-tracker`
- Reader persona panel: `reader-persona-review`, `review-panel`

**Edit the prose (decision tree):**
- Default full sentence edit: `nonfiction-clarity-edit`
- Apply approved report edits: `fiction-revise` (report-driven, book-agnostic)
- Targeted scans: `levelup`, `fragment-hunter`, `nominalization-hunt`, `kill-hedge`, `kill-passive`, `kill-acronym`

**Remove the tells (decision tree):**
- Recurring clarity crutches: `nominalization-hunt`, `kill-passive`, `kill-hedge`, `kill-acronym`
- Statistical & drift diagnostics: `drift-check`, `burstiness-check`, `pangram`

**Publish & Package:**
- Manuscript compile & export: `compile-manuscript`
- Marketing & publishing kit: `book-packaging`

**Make your own:** `skill-builder`

(End of file)

