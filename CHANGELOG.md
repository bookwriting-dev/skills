# Changelog

Our changes to the library, newest first. Skill versions live in each SKILL.md's frontmatter and bump with every change; entries here record the why.

## 2026-10-23 — Fix: `chapter-pipeline` can now finish its own loop

Rationale: the 2026-10-19 product review found that the one skill whose entire
job is "run the chapter loop" structurally could not complete it — its gate
could never PASS, its polish step could be a no-op, and it looked for a scene
file under a name nothing writes. First of the review's Tier 0 trust fixes.

### Fixed

- **`skills/chapter-pipeline` 1.0.0 → 1.1.0:**
  - Scene-file glob corrected to `Chapter_NN_Scene.md` — the authority spelling
    `fiction-scenes` actually writes (`templates/AGENTS.md` layout). The old
    `Chapter_[NN]_Scene.md` matched nothing in a standard scaffold.
  - New step 3 runs `fiction-promises` between drafting and the gate, so new
    setups/payoffs are registered before `gate-check` requires them — the gate
    can now PASS on chapters that set things up.
  - The polish step completes: `kill-chapter` (edits in place), or
    `fiction-aiism-editor` followed by `fiction-revise` applying the approved
    items — the report alone was never polish.
  - "Major beat gap" and halt-worthy `WARN` are now defined (an outline
    `what_must_happen` directive with no scene; canon/continuity/ledger WARN),
    so "halts on genuine blockers" is decidable.

### Verified

- `make check` green after the change (74 skills, 0 errors, 0 warnings).

## 2026-10-22 — Added: `kanban-board` — a per-book production board

Rationale: a book is produced one chapter at a time through a fixed sequence
(outline beat → scene plan → draft → review/gate → revise), but nothing in a
project shows that sequence at a glance — `book-status` reports metrics, not
workflow position, and the alternative is scrolling directories. `kanban-board`
renders the pipeline as a board: one card per chapter in Backlog / Ready /
Drafting / Review / Done, placed mechanically from what exists on disk. The
board is a regenerated view, never source of truth; the skill is a read-only
diagnostic except for the board file itself.

### Added

- **`skills/kanban-board/`** (1.0.0, cross-cutting) — renders and refreshes
  `Wiki/Story/Book-N/kanban.md` from the outline, scene plans, chapter drafts,
  gate/review reports, and the promise ledger, with per-column next-move
  routing (`fiction-scenes`, `fiction-writechapter`, `chapter-pipeline`,
  `gate-check`, `fiction-revise`, `fiction-promises`). Non-fiction variant
  keys off the chapter plan and the factcheck/clarity-edit reports, with
  `Done` requiring the clarity-edit pass.
- **`templates/kanban-board.md`** — the starter board `new-book.sh` renders
  into `Wiki/Story/Book-1/kanban.md`, so every new book begins with a board;
  later books get theirs on the skill's first run.

### Changed

- **`new-book.sh`** — validates the new template with the other required
  templates and renders the Book-1 starter board.
- **`tools/smoke-new-book.sh`** — asserts the board exists in the scaffold,
  the title rendered into it, and no placeholder left behind.
- **`skills/book-status`** 1.0.0 → 1.0.1 — points at `kanban-board` for the
  per-chapter workflow view (the two read the same on-disk state; one is
  metrics, one is position).
- **`templates/AGENTS.md`** — `kanban.md` in the folder layout and per-book
  slots; `kanban-board` in the Workflow & Orchestration index.
- **docs** — USER.md catalog entry and recipe; skill counts updated to 74 in
  README/USER/DEVELOPER.
- **`sync-manifest.txt`** — registered the two new files. **`VERSION`** →
  2026.10.22.

### Verified

- `make check` green after the change: 74 skills, 0 errors, 0 warnings;
  inventory current; smoke passing including the new board assertions.

## 2026-10-18 — Fix: two silent data-destroying bugs in the shell scripts, and close the CI gaps that hid them

Rationale: a review of the toolchain found two bugs that both destroy user work
silently — and both survived for the life of the repo because they lived in shell,
which nothing in the project ever executed or checked. `make check` claimed to
"syntax-check every script" while globbing `*.py` only, and CI ran the three tools
individually instead of `make check`, so the Makefile itself was untested. This
release fixes both bugs, adds real shell coverage (a `bash -n` pass plus an
end-to-end smoke test of the scaffolder), and makes CI run the target developers
run. No skill bodies changed; this is toolchain and process only.

### Fixed

- **`new-book.sh` — a title containing `/` or `&` destroyed the scaffold.** The title was interpolated raw into `sed "s/__SERIES_TITLE__/$TITLE/g"`. A `/` aborted `sed` with "bad flag in substitute command" *after* the project directory had already been created; the exists-check then refused the retry, so the run was unrecoverable and left a half-project on disk with no `AGENTS.md`, no `CLAUDE.md`, and no git repo. `&` was worse — it expanded to the whole match and silently corrupted three rendered files. Fixed by escaping the replacement for a `|` delimiter, rejecting multi-line titles up front, and validating every input (including `--import`) **before** touching the filesystem.
- **`new-book.sh` — a failed run now rolls back.** An `ERR`/`INT`/`TERM` trap removes the partially-built project so the command is always retryable. The trap is cleared once the scaffold is complete, so nothing can delete a finished project.
- **`new-book.sh` — `--import` of an empty directory no longer aborts, and dotfiles are now staged.** `cp -R "$src"/*` with no `nullglob` failed on an empty directory; with `nullglob`/`dotglob` an empty import is a clean no-op with a note, and `.hidden-chapters/` and other dotfile content (a git repo, a dotfile-strewn manuscript) are imported instead of silently skipped.
- **`tools/update-project.sh` — `--apply --prune` could delete the wrong thing and report success.** The `Only in …` branches parsed by stripping up to the first `": "`, which dropped the leading directory: `Only in <proj>/skills/book-status: references` parsed as `references`, so `rm -f` targeted a nonexistent path, the real file survived, and the script still printed "Applied". (The `Files …` branch two lines above already did this correctly.) Fixed by rebuilding the path from the known skills-root prefix — `diff -rq` reports the *innermost* differing directory, not the root, so a first attempt that only stripped the root prefix still mis-parsed. `--prune` now distinguishes files from directories, counts what it actually removed, and warns if a listed path was absent.

### Added

- **`tools/smoke-new-book.sh`** — runs `new-book.sh` end-to-end in a temp dir and asserts the tree it promises: pinned library, rendered `AGENTS.md`/`CLAUDE.md`, version pin, chapter and world slots, skill count matching the library, project-type slots, `--import` staging including dotfiles, the rollback/retry contract, and titles containing `sed` metacharacters (`/`, `&`, `\`, `|`). 27 assertions; `SMOKE_KEEP=1` keeps the scratch dir. Verified to fail with 5 errors against the pre-fix `new-book.sh`, so it is a real regression test and not a tautology.
- **`make smoke`**, wired into `make check`.

### Changed

- **`tools/compile-check.py`** — now also runs `bash -n` over `new-book.sh`, `sync-check.sh`, and `tools/update-project.sh`, and reports a non-UTF-8 Python file as a clean diagnostic instead of a raw traceback.
- **`.github/workflows/ci.yml`** — runs `make check` (one target, not three ad-hoc tool invocations) so the Makefile cannot drift from what CI enforces, and adds a `macos-latest` leg alongside Ubuntu: darwin is the primary authoring platform and `sync-check.sh` parses BSD `diff -rq` output, a different format from GNU diff.
- **`Makefile`** — added `inventory-check` and `smoke` targets; `check` is now the full gate.
- **`sync-manifest.txt`** — registered `tools/smoke-new-book.sh`.
- **`README.md` / `docs/DEVELOPER.md`** — toolchain table, layout, and change loop now describe the shell syntax check, the smoke test, and the macOS CI leg.

### Verified

- `make check` green: 73 skills, 0 errors, 0 warnings; inventory current; 18 Python files + 3 shell scripts syntax-clean; smoke 27/27. Ran clean three times consecutively (the smoke test's temp-dir cleanup is deterministic after disabling git's background auto-maintenance, which raced `rm -rf` with ENOTEMPTY).
- Each fix reproduced before and after: the `/`-in-title crash and the unrecoverable retry, the `&` corruption, backslash/pipe titles, the `--import` empty-dir and dotfile cases, and the `update-project.sh` path-flattening bug (including the whole-forked-skill-directory and spaces-in-filenames cases, verified end-to-end against a real scaffolded project). Temp dirs removed; repo tree clean.

## 2026-10-16 — Toolchain: self-checking library, generated inventory, project version pin

Rationale: the 2026-10-11 audit was excellent but manual, and the same three bug classes kept recurring — docs drifting from frontmatter, duplicate/superseded skills with no boundary, and dead file paths. This release makes the audit mechanical and gives projects a way to take updates: a linter that enforces the frontmatter/path/doc-drift contract, a generator that renders the catalog from frontmatter so it cannot drift, CI that runs both on every push, and a version pin plus updater for scaffolded projects. It also fixes the doc drift the new tools immediately caught.

### Added

- **`tools/lint-skills.py`** — stdlib-only linter enforcing the audit's invariants: `name` == folder, quoted semver, category enum, description length/chars, resolvable `references/`/`assets/`/`scripts/`/`data/` paths, orphaned bundled files, phantom skill names, `docs/USER.md` catalog versions vs frontmatter, and the "N skills" count in README/USER/DEVELOPER vs the real count. Errors fail; warnings pass unless `--strict`.
- **`tools/gen-inventory.py`** + **`docs/SKILL-INVENTORY.md`** — the catalog generated from frontmatter (name, version, category, summary); `--check` fails if the committed file is stale.
- **`tools/skill_lib.py`** — shared frontmatter loader for the two tools.
- **`tools/compile-check.py`** — side-effect-free syntax check for every Python file in `tools/` and `skills/` (in-memory `compile()`, no `__pycache__` written, so the filesystem diff `sync-check.sh` stays clean).
- **`tools/update-project.sh`** — reports how a project's pinned `.agents/skills/` differs from the library and, with `--apply`, copies the library in (additive; `--prune` deletes removed files) and rewrites the project's pin.
- **`Makefile`** (`make check` / `lint` / `inventory` / `compile`) and **`.github/workflows/ci.yml`** — the same gate locally and on push/PR.
- **`VERSION`** — library revision, written into each project's pin.

### Changed

- **`new-book.sh`** — writes `.agents/skills/.storycraft-source` (library name, version, commit, skill count, pin date, source path) so a project records what it pinned and `tools/update-project.sh` can report how far behind it is.
- **`docs/USER.md`** — fixed the skill-count drift ("All 72 skills" → 73) and two catalog versions the 2026-10-14 release missed (`fiction-genre` 3.2.1 → 3.2.2, `fiction-synopsis` 5.2.2 → 5.2.3); the non-fiction section no longer claims research/source management and a developmental editor are unbuilt (both shipped 2026-10-12 — only a non-fiction revise skill remains); house rule 7 documents `tools/update-project.sh`; the catalog now points at `docs/SKILL-INVENTORY.md`.
- **`docs/DEVELOPER.md`** — adds a Toolchain section and folds `make check` into the change loop; repository layout updated; "still open, by choice" corrected to the single unbuilt non-fiction layer.
- **`README.md`** — corrected counts, documented the tools and the update flow.
- **`review-panel` 1.1.1 → 1.1.2** and **`reader-persona-review` 1.0.0 → 1.0.1** — each now states explicitly what it is *not* and when to reach for the other (the two persona-panel skills overlapped with no boundary, so the agent could not disambiguate).
- **`fiction-promises` 1.1.0 → 1.1.1** and **`promise-tracker` 1.0.1 → 1.0.2** — each now names the other as the fiction-only / unified variant sharing the same ledger, so the two ledgers are not run on one book at once.

### Verified

- `make check` green: 73 skills, 0 errors, 0 warnings; inventory current; all 18 scripts syntax-check clean. `sync-check.sh` still exits 0 (\"everything is accounted for\").
- `new-book.sh` scaffolded into a temp dir, pin written; `tools/update-project.sh` correctly reported a changed file and a project-only file, `--apply` reverted the drift and kept the local file, and rewrote the pin. Temp dir removed.


## 2026-10-14 — Inception & Reverse-Engineering Suite: _Intake/ Staging & book-reverse-engineer

Rationale: Book projects previously suffered from two structural intake gaps: (1) Cold-start friction where planning skills interrogated authors in a vacuum before asking for their raw ideas, while dropping raw notes into `Wiki/` risked polluting binding canon with uncommitted brainstorms; (2) Lack of a pathway to bring existing manuscripts drafted without Storycraft discipline into the system, forcing authors to either edit without canon gates or painstakingly author `Wiki/` files and scene outlines by hand. This release introduces a dedicated `_Intake/` staging area for creative briefs and raw materials, integrates intake pre-population into planning skills, adds `--import <path>` support to `new-book.sh`, and adds the `book-reverse-engineer` skill (powered by zero-dependency `manuscriptkit.py` and `findings.py`) to inspect existing drafts, infer `Wiki/` canon and Chekhov ledgers, flag contradictions for human review, and seed defect backlogs in `_Edits/Book-N/findings.yaml` for surgical repair. Scale expands from 72 to 73 skills.

### Added

- **`_Intake/` Staging Architecture** — Dedicated staging folder (`_Intake/series-brief.md`, `_Intake/Book-N/premise.md`, `_Intake/Book-N/raw-notes/`, and `_Intake/Book-N/raw-manuscript/`). Explicitly defined as authorial inspiration/staging (advisory, not binding canon).
- **`templates/series-brief.md`** & **`templates/book-premise.md`** — Inception brief skeletons capturing loglines, comp titles, tropes, tonal guardrails, non-negotiables, and conflict drivers.
- **`new-book.sh --import <path>`** — Flags existing manuscript file or directory, copies it to `_Intake/Book-1/raw-manuscript/`, and outputs immediate reverse-engineering next steps.
- **`book-reverse-engineer` 1.0.0** — Two-phase skill to analyze undisciplined manuscripts and retrofit them into Storycraft:
  - *Analyze (Read-Only)*: Scans chapter prose, extracts character rosters, world systems, timeline chronology, retrofitted chapter beat plans, Chekhov promises, and voice DNA into `_Edits/Book-N/reverse-analysis.md`. Flags discrepancies (`CANON CONFLICT`, `DROPPED THREAD`, `CANON GAP`, `VOICE BREAK`, `LOW CONFIDENCE`).
  - *Checkpoint*: Mandatory pause for human review of discrepancies.
  - *Import*: Populates authoritative `Wiki/Characters/`, `Wiki/World/`, `Wiki/Style/`, `Wiki/Story/synopsis.md`, `promises.yaml`, `Wiki/Outline/Book-N/` beat files, and generates a structured defect backlog in `_Edits/Book-N/findings.yaml` via `findings.py`.
- **`skills/book-reverse-engineer/scripts/manuscriptkit.py`** — Host-neutral Python stdlib script for unit splitting, boundary detection, word counting, and `--export-chapters` into `Chapters/Book-N/Chapter-NNN.md`.
- **`skills/book-reverse-engineer/scripts/findings.py`** — Host-neutral Python stdlib script parsing confidence tags and conflicts into YAML defect rows.
- **`skills/book-reverse-engineer/references/reverse-schema.md`** — Contract and markdown schema for `reverse-analysis.md`.

### Changed

- **`fiction-genre` 3.2.1 → 3.2.2** — Checks `_Intake/series-brief.md` first to pre-fill genre, subgenre, tropes, and title for author confirmation.
- **`fiction-synopsis` 5.2.2 → 5.2.3** — Checks `_Intake/` for creative briefs and raw braindumps to seed the synopsis worker without demanding a cold braindump.
- **`new-book.sh`** — Scaffolds `_Intake/` directory and renders intake templates automatically.
- **`templates/AGENTS.md`** — Added `_Intake/` to layout and authority rules; added explicit Path A (Greenfield) and Path B (Brownfield Reverse-Engineering) workflows; indexed `book-reverse-engineer`.
- **`docs/USER.md`** & **`docs/DEVELOPER.md`** — Documented `_Intake/` and `book-reverse-engineer`, updated script inventory, and bumped skill scale to 73.
- **`sync-manifest.txt`** — Registered new templates; zero upstream drift verified via `sync-check.sh`.


## 2026-10-13 — LitRPG & Progression Fantasy Suite: Mechanics, Ledger & Audits

Rationale: The library provided comprehensive craft, editing, and pipeline orchestration for general fiction, but lacked support for the core requirements of LitRPG and Progression Fantasy: power system design, mathematical sanity, deterministic numeric tracking, and audiobook/e-reader safe status box conventions. Furthermore, standard prose linters and sentence burstiness metrics penalized in-game status notifications and stat-analysis vocabulary. This release adds dedicated system design and progression audit skills, wires numeric checks into `gate-check`, teaches prose linters to respect system callouts, and establishes `Wiki/World/Systems/` as the canonical home for game rules and character ledgers. Scale expands from 70 to 72 skills.

### Added

- **`litrpg-system` 1.0.0** — Designs and balances RPG/magic systems, power curves, class trees, and character sheets. Populates `Wiki/World/Systems/` (`system-rules.md`, `classes-skills.md`, `encounters-loot.md`), seeds character sheets in `Wiki/Characters/<Name>_sheet.md`, and initializes `Wiki/World/Systems/ledger.yaml`. References: `system-design-principles.md` (no-free-lunch rule, dopamine cadence), `stat-box-guide.md` (UI callout standards), `progression-curves.md` (quadratic/tiered/exponential formulas), `encounter-and-dungeon-guide.md` (threat tiers, boss phases). Assets: `system-rules-template.md`, `character-sheet-template.md`, `ledger-template.yaml`.
- **`litrpg-audit` 1.0.0** — Deterministic numeric continuity auditor for LitRPG chapters. Runs `scripts/stat_audit.py` (zero-dependency Python stdlib) to verify stat point arithmetic (earned vs allocated), level curve milestones, skill unlock legality, derived pool math (HP/MP vs CON/INT), and status box brevity. References: `audit-rules.md`.
- **`skills/litrpg-audit/scripts/stat_audit.py`** — Host-neutral script parsing chapter text and validating numbers against `ledger.yaml` with JSON and Markdown reporting.

### Changed

- **`gate-check` 1.0.0 → 1.1.0** — Added Pillar 7 (LitRPG & Numeric Continuity). Automatically invokes `stat_audit.py` when system rules or `ledger.yaml` exist, blocking gate passage on mathematical contradictions or unearned abilities.
- **`burstiness-check` 1.3.1 → 1.4.0** — Updated `references/measure.py` to filter out Markdown callout blocks (`> ...`) and code fences (` ``` ... ``` `) so in-game status screens and stat tables do not distort narrative sentence-length variance or trigger false-positive repetition hotspots.
- **`fiction-aiism-editor` 1.4.0 → 1.4.1** — Updated `references/aiism-criteria.md` with an explicit LitRPG/Progression exception for diegetic quantitative analysis, stat allocation debates, and build optimization inside system callouts.
- **`fiction-genre` 3.2.0 → 3.2.1** — Updated `references/fantasy-litrpg.md` with direct references to the new `litrpg-system`, `litrpg-audit`, and status box formatting guide.
- **`templates/AGENTS.md`** & **`docs/USER.md`** & **`docs/DEVELOPER.md`** — Documented the LitRPG workflow, updated editing decision trees, cataloged both new skills, and bumped library scale from 70 to 72 skills.
- **`sync-manifest.txt`** — Registered `skills/fiction-genre/references/fantasy-litrpg.md` and verified zero upstream drift (`sync-check.sh` passes with exit code 0).


Rationale: the library covered writing through packaging (`book-packaging` stops at the blurb, metadata, and cover brief) but nothing for promoting a finished book. One skill rather than three, because the workflow (audience, hooks, content pillars, calendar, captions) is shared and only the platform rules differ; those live in per-platform reference files that can be updated without touching the skill. Scale 69 → 70 skills.

### Added

- **`social-media-marketing` 1.0.0** — Facebook, Instagram, and TikTok marketing for launch campaigns (pre-launch, launch week, post-launch) and ongoing content. Organic-first; paid ads (Meta and TikTok) are an opt-in layer. Reads genre, audience, synopsis, and packaging files; writes `Wiki/Marketing/` strategy, calendar, content, optional ads plan, and retrospectives. References: `tiktok.md`, `instagram.md`, `facebook.md`, `launch-phases.md`, `paid-ads.md`, `measurement.md`.
- **`templates/AGENTS.md`** & **`docs/USER.md`** & **`docs/DEVELOPER.md`** — routed and cataloged the new skill; skill count updated.

## 2026-10-12 — Workflow Expansion: 10 New Skills Added
 
 Rationale: complete the end-to-end writing, editing, gatekeeping, review, and publishing lifecycle. Incorporates persona-driven reader reviews, automated pipeline orchestration, continuity enforcement, manuscript packaging, and non-fiction research and developmental editing into the library. Scale expanded from 59 to 69 skills.
 
 ### Added
 
 - **`reader-persona-review` 1.0.0** — multi-perspective reader critiques across 123 archetypes and preset panels (anti-AI sweep, pacing, puzzle fairness) with synthesis.
 - **`gate-check` 1.0.0** — unified chapter readiness gate checking canon integrity, scene beats, Chekhov promises, and machine cadence.
 - **`book-status` 1.0.0** — manuscript dashboard for word counts, gate status, open promises, and review health.
 - **`chapter-pipeline` 1.0.0** — automated scene → draft → gate → polish orchestrator.
 - **`canon-guard` 1.0.0** — safeguard for locked canon files with chapter impact analysis before intentional updates.
 - **`series-continuity` 1.0.0** — multi-book continuity scanner checking character state persistence, solved secrets, and chronology.
 - **`compile-manuscript` 1.0.0** — chapter stitching, scene break standardization, front/back matter compilation, and export generation.
 - **`book-packaging` 1.0.0** — publishing kit generator: back-cover blurbs, query letters, Amazon retail metadata, and artist cover briefs.
 - **`nonfiction-research` 1.0.0** — citation vaults, claims matrices, and primary source organization in `Wiki/Research/`.
 - **`nonfiction-dev-editor` 1.0.0** — non-fiction developmental editor diagnosing argument flow, thesis scaffolding, and cognitive load.
 
- **`templates/AGENTS.md`** & **`docs/USER.md`** — rewired to index and route the 10 new skills across fiction and non-fiction decision trees.


Rationale: addresses the remaining observations logged in the 2026-10-11 audit ledger. `fiction-outline` now supports multi-book series workflows by accepting per-book synopses (`Wiki/Story/Book-N/synopsis.md`) with fallback to the root series synopsis, and `fiction-synopsis` points location references to the standard `Wiki/World/Locations/` layout.

### Changed

- **`fiction-outline` 5.3.0 → 5.3.1** — `Step 1` input search accepts `**/Wiki/Story/Book-N/synopsis.md` (for individual books in a series) as well as `**/Wiki/Story/synopsis.md` (root/standalone synopsis), prioritizing the book-specific synopsis when present.
- **`fiction-synopsis` 5.2.1 → 5.2.2** — updated `locations_in_play` output reference to `Wiki/World/Locations/` (or legacy `Wiki/Locations/`), aligning with the current `fiction-world` layout.
- **`docs/USER.md`** — synced catalog versions for `fiction-outline` and `fiction-synopsis`.

## 2026-10-11 — Skill audit, batch 9: wiring layer + final sweep

Rationale: the audit's closing pass over the doc layer, the workflow template, the scaffolder, and the sync gate — plus the verification sweep across all 59 skills. The reference graph is clean: zero broken paths (two `skill-builder/guide.md` hits are tutorial examples inside sample skill layouts), zero dangling skill-name references, and no phantom components anywhere. `templates/AGENTS.md`'s workflow, decision trees, and index already matched the library after the fixes above; no template rewiring was needed beyond one word.

### Changed

- **`docs/USER.md`** — fixed the stale `fiction-review-panel` name in the decision tree's fiction column (the rename completed 2026-10-11 but missed this row); synced every catalog version with frontmatter after this audit's bumps (29 rows); the ten kill-pass singles now carry versions in the catalog like every other skill (they were the only unversioned rows).
- **`docs/DEVELOPER.md`** — the "still open, by choice" note said eight non-fiction skills remain unbuilt and "the workflow routes around them"; reworded to the current truth: three layers remain unbuilt (research/source management, a non-fiction developmental editor, a non-fiction revise skill) on top of the seven-skill workflow that does exist. Documented the new `ours (deleted)` sync classification.
- **`templates/AGENTS.md`** — intro line "A fiction project using…" → "A book project using…"; the old wording contradicted itself on every `--type nonfiction` scaffold.
- **`sync-check.sh` — deletion-aware classification.** An upstream-only path under a subdirectory was classified `fork addition` with a mangled name, so a file we deliberately deleted looked like unexplained noise (and a genuinely new upstream file in a new subdirectory would have been silently swallowed). Upstream-only entries now classify file-by-file: manifest-listed → `ours (deleted)` (the manifest entry is the tombstone; keep it when you delete an inherited file), anything else → `NEW UPSTREAM` with the correct path. Directory-level `Only in` lines expand and classify per file.
- **`sync-manifest.txt`** — registered 18 previously-unlisted fork-modified files and 10 deletion tombstones. The unregistered files made `sync-check.sh` report 17 lines of phantom "UPSTREAM DRIFT": inspection showed the upstream ZIP is unchanged since the fork — every diff was our own earlier change (R0's removal of the legacy routing fields, the quoted-version normalization, this audit's edits) that had simply never been entered in the manifest. **Zero genuine upstream drift.** The gate now exits 0: everything accounted for.

### Verified

- `new-book.sh` scaffolded both project types into temp dirs (fiction and `--type nonfiction`: type line rendered, `Wiki/Concept/` + `Wiki/Research/` created, 59 skills copied, template rendered) and both were deleted afterward.
- Programmatic sweep across all 59 skills: every relative path in every SKILL.md, reference file, and backticked invocation resolves; every backticked skill name in SKILL.mds, docs, and the template matches a real skill or is a documented-unbuilt/category mention in DEVELOPER.md's reconciliation record; all 59 frontmatter versions match the USER.md catalog.

## 2026-10-11 — Skill audit, batch 8: diagnostics, utilities, meta

Rationale: per-skill dead-ends audit continued. The headline change: `pangram` claimed to be a never-edit diagnostic while its body was full of rewrite instructions ("replace common collocations", "inject imperfection intentionally") built on the exact perplexity/burstiness theory of AI detection that the Pangram technical report — cited by our own `burstiness-check` — explicitly debunks. Rewritten as the diagnostic its description always claimed to be.

### Changed

- **`pangram` 1.0.0 → 2.0.0** — rewritten from a rewrite-advisory pass into a true diagnostic: all eight measures now report numbers and flagged locations only, with routing to `fiction-aiism-editor` (phrasing tells — the likelier real detector trigger per the paper), `fiction-prose-editor` (mechanics), and `burstiness-check` (cross-chapter baseline); the mechanism caveat now states what Pangram actually is (a learned-tells classifier, not a perplexity/burstiness classifier); the "inject unpredictability" advice is gone, per burstiness-check's own warning about detector-dodging rewrites. Major bump: behavior change.
- **`burstiness-check` 1.3.0 → 1.3.1** — removed a stray word from a `measure.py` validation comment ("Cross-book validation (Black two contrasting projects…").
- **`name-generator` 1.1.0 → 1.2.0** — wired in its own orphaned `references/culture-map.md` (previously consumed only cross-skill by the world-building skills, its own SKILL.md never mentioned it) and documented the `scrape.py` corpus-refresh workflow, including `--batch urls.txt`.
- **`town-generator` 1.0.0 → 1.1.0** — surfaced `generate_town.py`/`epithet.py` (previously invoked only by `fiction-world` and `culture-map.md`, never by the skill itself) with the epithet/prefix invocation; documented the corpus-refresh workflow; added `scripts/urls.txt` (registered in the manifest) so the documented `--batch` mode actually has its input file — the name-generator copy had it, this one didn't.
- **`fantasy-settlement` 1.0.0 → 1.0.1** — removed an unused `import math`; `generate_town.py` also lost an unused `DATA` variable (no version bump — it's town-generator's file, covered by that skill's bump).

### Verified

- All four scripts smoke-tested: `generate.py` (Markov names), `generate_town.py` (epithet flags accepted), `generate_settlement.py` (dossier renders), `measure.py` (JSON report). `skill-builder` audited clean — its `guide.md` path mentions are generic tutorial examples, not repo references.

## 2026-10-11 — Skill audit, batch 7: non-fiction

Rationale: per-skill dead-ends audit continued. The non-fiction planning trio ran on a folder scheme (`Wiki/Concept/concept.md`, `Wiki/Audience/audience.md`, `Wiki/Structure/structure.md`) that nothing else in the library uses — AGENTS.md, USER.md, the new-book skeleton (`Wiki/Concept/`), and the review skills all expect `Wiki/Concept/thesis.md` / `audience.md` / `structure.md`. Worse, `nonfiction-concept` *required* an audience profile while the documented workflow runs concept first — a circular dead end at step 1 of every new non-fiction project.

### Changed

- **`nonfiction-concept` 1.0.0 → 1.1.0** — output is now `Wiki/Concept/thesis.md` (the path AGENTS.md, USER.md, and the template layout all document); the audience file is recommended-not-required, resolving the concept↔audience ordering cycle (the workflow starts at concept; audience reads the thesis afterward); dropped the optional `Wiki/Concept/big-idea.md` input (no skill produces it); downstream list corrected from "outline" to "chapter-plan"; description no longer says "after running nonfiction-audience".
- **`nonfiction-audience` 1.0.0 → 1.1.0** — output moved from `Wiki/Audience/audience.md` (a folder the scaffold never creates) to `Wiki/Concept/audience.md`; reads the concept from `Wiki/Concept/thesis.md`; assumptions file and structure input moved to `Wiki/Concept/` accordingly.
- **`nonfiction-structure` 1.0.0 → 1.1.0** — output moved from `Wiki/Structure/structure.md` to `Wiki/Concept/structure.md`; reads `thesis.md` + `audience.md` from `Wiki/Concept/`; the closing handoff "use `nonfiction-outline`" — a skill that does not exist — now hands to `nonfiction-chapter-plan`; the validation checklist's phantom `audience.transform` field now cites the concept's reader-transformation milestones.
- **`nonfiction-chapter-plan` 1.0.0 → 1.0.1** — default plan path `Wiki/Outline/Chapter_[NN]_Plan.md` → `Wiki/Outline/Book-N/Chapter_[NN]_Plan.md` when no project convention exists (same pre-reorg fix as fiction-scenes).
- **`nonfiction-writechapter` 1.0.0 → 1.0.1** — wired in its two orphaned reference files: `evidence-presentation.md` (evidence-variety templates) and `signposting-patterns.md` (signposting pattern library), both of which expand rules the skill already states in prose.
- **`nonfiction-factcheck` 1.0.0 → 1.1.0** — report saves to `_Edits/Book-N/Chapter-NNN_FactCheck.md` (was `_Edits/` root); the closing "ask if they want fixes applied" now offers `fiction-revise`, which is the documented non-fiction route for report-driven fixes.
- **`nonfiction-clarity-edit` 1.0.0 → 1.1.0** — report saves to `_Edits/Book-N/Chapter-NNN_ClarityEdit.md`; the chapter-plan lookup glob fixed from `Chapter-[NN]_Plan.md` (hyphen) to `Chapter_[NN]_Plan.md` (underscore), matching the chapter-plan default so the plan is actually found; fix application routed through `fiction-revise`.

## 2026-10-11 — Skill audit, batch 6: kill passes (all 11)

Rationale: per-skill dead-ends audit continued. One dead end in eleven skills: `kill-acronym` sent readers to `Wiki/Style/voice.md`, a file no skill in the library writes. Everything else passed: the five fiction singles carry their rules inline, the orchestrator's seven `references/` rule-sets all exist, and the three non-fiction passes' reference files resolve and contain their documented token lists. The inline-vs-references asymmetry between the fiction and non-fiction singles tracks when each was written and is deliberate.

### Changed

- **`kill-acronym` 1.0.0 → 1.0.1** — the KEEP guidance cited `Wiki/Style/voice.md` (no such convention; the canonical files are `style_guide.md` and `voice_prompt.md`); now cites `Wiki/Style/style_guide.md` and `Wiki/Style/audience.md`.

## 2026-10-11 — Skill audit, batch 5: edit the prose

Rationale: per-skill dead-ends audit continued (full-editor, revise, the three single-layer editors, levelup, fragment-hunter, nominalization-hunt). One shared defect across six report-writing editors: all saved reports to a pre-reorg `_Edits/` root or a legacy `Reviews/` folder, and none routed fix application through `fiction-revise`. `fiction-revise` itself passed clean.

### Changed

- **`fiction-full-editor` 1.1.0 → 1.2.0, `fiction-line-editor` 5.1.0 → 5.2.0, `fiction-prose-editor` 1.2.0 → 1.3.0, `fiction-aiism-editor` 1.3.0 → 1.4.0, `levelup` 1.0.0 → 1.1.0, `fragment-hunter` 1.0.0 → 1.1.0** — reports now save to `_Edits/Book-N/Chapter-NNN_<Type>.md`, matching the AGENTS.md layout and `fiction-revise`'s default report search; the closing "ask if they want to apply fixes" now offers `fiction-revise` (quote verification, minimal perturbation, change ledger) instead of implying inline edits from a scan pass. fragment-hunter's own apply step keeps its kill-confirmation flow and additionally offers the revise route.
- **`nominalization-hunt` 1.0.0 → 1.1.0** — removed the phantom "or when fiction-masteragent invokes the nominalization pass" from the description (no such skill or pipeline); scope generalized to "chapters (fiction or non-fiction)", matching the workflow trees that already route it for both; added the missing application path (approved rewrites route through `fiction-revise` or direct per-item confirmation) so the scan's proposals no longer dead-end in conversation.

### Verified

- fragment-hunter's embedded Pass-1 extraction script runs and behaves as documented (catches genuine 1–3-word sentences, overfires on abbreviation splits and italic thought by design — Pass 2 judges).

### Notes

- `sync-manifest.txt`: registered `fiction-full-editor`, `fiction-line-editor`, `levelup`, `fragment-hunter` SKILL.md files (now fork-modified); manifest re-sorted.

## 2026-10-11 — Skill audit, batch 4: review the story + cross-cutting

Rationale: per-skill dead-ends audit continued. The headline fix: `drift-check` had been promising four non-fiction metrics since the non-fiction expansion — and the 1.1.0 bump recorded them as shipped — but `drift.py` only ever implemented the five fiction metrics. Also: `fiction-reviewchapter` still audited against synopsis tables the synopsis generator stopped producing, and saved reviews to a pre-reorg path.

### Changed

- **`drift-check` 1.1.0 → 1.2.0** — `drift.py` now implements the four promised non-fiction proxies: claim density (assertion sentences per 1k, falling = drift toward summary), evidence-to-claim ratio (evidence sentences per claim), abstraction ladder (abstract-noun endings per 1k vs concrete anchors per 1k, narrowing when abstracts rise or anchors fall in the back half), and reintroduced-definition detection (definition patterns applied to a term already defined in an earlier chapter). Also fixed the dead code in the specifics metric — `re.search(r'[.!?]"?$', "")` tested a literal empty string, and word tokens carry no punctuation at all, so sentence-initial capitals were never excluded; capitalization is now judged against the raw text. Verified on synthetic chapters (falling evidence ratio, narrowing ladder, and a ch1→ch2 reintroduction all detected).
- **`fiction-reviewchapter` 2.5.0 → 2.6.0** — the genre-compliance step extracted `### Contract Validation` / `### Mandatory Beat Sequence` / `### Twist Map` from the synopsis, but the current `fiction-synopsis` emits `## Trope Payoff Plan` and no such tables, so two of the five criterion-10 checks silently no-op'd on every modern project. The chapter's trope obligations now come from the outline's per-chapter `trope_obligations` entry, and scheduled twists come from the divergence pass's `surprise-ledger.md` (old synopsis tables still honored as fallback). Also: the outline glob now matches `Wiki/Outline/Book-N/outline.md`; reviews save to `_Edits/Book-N/Chapter-NNN_Review.md` per the AGENTS.md layout; and the closing offer no longer applies edits inline — it routes to `fiction-revise`, whose quote-verification and change ledger exist precisely for that step.
- **`review-panel` 1.1.0 → 1.1.1** — wired in the orphaned `references/nonfiction-personas.md`: the four non-fiction seats' full persona files (with copy-ready prompt blocks) were shipped in the non-fiction expansion but never referenced; the SKILL.md summarized the seats inline and said nothing about the file. Step 1 now points to it.
- **`promise-tracker` 1.0.0 → 1.0.1** — removed `references/promise-criteria.md`, `promise-kinds-fiction.md`, `promise-kinds-nonfiction.md`: three thin summaries fully duplicated by the SKILL.md body, referenced by nothing (manifest entries removed).

### Verified

- `fiction-promises` and `promise-tracker` scripts pass their documented behavior on a test ledger (`--chapter` bucketing with deferred exclusion; `--final` exits 1 on unpaid, undeferred promises). `fiction-promises` 1.1.0 and `fiction-dev-editor` 2.0.0 and `coldread` 1.0.1 audited clean.

## 2026-10-11 — Skill audit, batch 3: shape the book

Rationale: per-skill dead-ends audit continued (outline, divergence, scenes, style, writechapter). divergence passed clean; the other four carried pre-reorg paths, phantom pipeline references, a backwards handoff, or legacy files from the abandoned JSON pipeline.

### Changed

- **`fiction-outline` 5.2.0 → 5.3.0** — output path `Wiki/Outline/outline.md` → `Wiki/Outline/Book-N/outline.md` (the skill predated the Book-N reorg and was writing every outline outside the layout divergence, psych, writechapter, and reviewchapter all read from); world input now globs `**/Wiki/World/**/*.md` alongside the legacy per-type folders; the next-step handoff includes `fiction-divergence` (which the workflow order places between outline and scenes); removed the orphaned `references/twist-principles.md`.
- **`fiction-scenes` 4.0.0 → 4.0.1** — default scene-plan path `Wiki/Outline/Chapter_[NN]_Scene.md` → `Wiki/Outline/Book-N/Chapter_[NN]_Scene.md` when no project convention exists. (Project authority already handled the layout; the stale default is what remained.)
- **`fiction-style` 7.0.1 → 7.1.0** — "downstream prompt compilers" (a pipeline component that does not exist) now names the real consumers (`fiction-writechapter`, `fiction-voiceprompt`, the review/editing passes); the closing handoff "Next: use `fiction-characters`" — which sent the user back to planning step 6 after style runs at step 12 — now points to `fiction-voiceprompt` then `fiction-writechapter`; description's position hint updated from "after running fiction-synopsis" to the style + voice step.
- **`fiction-synopsis` 5.2.0 → 5.2.1** — `references/twist-principles.md` upgraded to the richer variant that had been sitting unreferenced in `fiction-outline/references/` (adds the weak/strong twist table, the twist-to-character matching, and the external-problem + internal-crisis formula). The canonical, referenced copy keeps the best content; the orphan copy is gone.
- **`fiction-writechapter` 4.1.0 → 4.1.1** — removed five inherited files from the abandoned JSON pipeline (`references/active-context-guide.md`, `common-pitfalls.md`, `json-active-context-schema.json`, `universal-quality-rules.md`, `assets/active-context-template.md`): they reference `theme.json`/`synopsis.json`/`[WorkingTitle]_characters.csv` artifacts that no longer exist and instruct the writing pass to maintain `motif_register`/`genre_beat_tracker` — exactly what the current skill forbids ("do not recalculate motif cadence, genre architecture… during the writing pass"). The skill's inline minimal active-context spec is the authority.

### Notes

- `sync-manifest.txt`: registered `skills/fiction-scenes/SKILL.md` and `skills/fiction-synopsis/references/twist-principles.md` (now fork-modified).

## 2026-10-11 — Skill audit, batch 2: build the people + build the world

Rationale: per-skill dead-ends audit (all 59 skills walked, batched by role). This batch: the nine people/world skills. The seven others passed clean; three had dead ends — two inherited file sets still described an output format the library abandoned, and `fiction-psych` still pointed at a pipeline component that does not exist and at pre-reorg paths.

### Changed

- **`fiction-psych` 2.0.0 → 2.1.0** — removed the phantom `fiction-masteragent` / "prompt compiler" pipeline references (the real downstream consumer is `fiction-writechapter`, which reads the psych document for interior movement); fixed the project-finding glob to `**/Wiki/Outline/**/outline.md` (the old `**/Wiki/Outline/outline.md` could not match the current `Wiki/Outline/Book-N/` layout); psych output now writes to `Wiki/Psych/Book-N/Chapter_[NN]_Psych.md`, matching the AGENTS.md folder layout it silently contradicted; the next-step chain now names the actual workflow order (scenes → style + voiceprompt → writechapter).
- **`fiction-characters` 3.1.0 → 3.1.1** — removed `references/csv-schema.md` and `assets/character-template.csv`: stale 21-column CSV output contract from a pre-Markdown era whose fields (Items, Abilities, Race, Uniform/Typical Attire) and single `characters.md` summary file contradict the current one-Markdown-file-per-character + `json-schema.json` design. Never referenced by the skill.
- **`fiction-world` 5.1.0 → 5.1.1** — removed `assets/faction-template.md` and `assets/location-template.md`: hand-fill templates in a `### Who/Want/Method` structure that matches no current output contract (the skill's file format is `frontmatter` + `## snake_case` sections, fully specified inline and in `references/json-schema.json`). Never referenced by the skill; following them would produce files in the wrong format.

### Notes

- All four removed files were inherited from upstream at the vendoring commit and appear in no manifest, template, doc, or SKILL.md. `sync-check.sh` classifies upstream-only paths as fork additions (exit 0), so the deletions cannot false-trigger the drift gate; the "Only in upstream subdir" classification prints a mislabeled line for deleted inherited files — cosmetic script gap, logged for the wiring batch.

## 2026-10-11 (later) — Documentation reconciliation

Rationale: a docs-vs-repo audit (see `docs/DEVELOPER.md`) found that the non-fiction expansion entry below overclaimed several items that never shipped in `e84222e`, and that `templates/AGENTS.md` referenced eight skills that don't exist. This pass makes the documentation layer match the library. The eight unbuilt non-fiction skills (`nonfiction-research`, `nonfiction-style`, `nonfiction-dev-editor`, `nonfiction-reviewchapter`, `nonfiction-revise`, `nonfiction-sources`, `nonfiction-claims`, `nonfiction-terminology`) were **un-referenced, not built** — building them is a separate design decision; the non-fiction workflow runs end to end on the seven skills that exist.

### Added

- **`new-book.sh --type fiction|nonfiction|hybrid`** — sets the rendered AGENTS.md project-type line and creates `Wiki/Concept/` + `Wiki/Research/` for nonfiction/hybrid projects; fiction scaffolds are unchanged. (The entry below claimed this flag; here it actually is.)
- **`.gitignore`** (`__pycache__/`, `*.pyc`, `.DS_Store`) and removal of the tracked `promise-tracker/scripts/__pycache__/` artifact.
- **`docs/USER.md`** and **`docs/DEVELOPER.md`** — user- and developer-POV documentation of the library as it is, linked from the README.

### Changed

- **`review-panel` — rename completed** (`skills/fiction-review-panel/` → `skills/review-panel/`), 1.0.0 → 1.1.0: the frontmatter `name:` had been renamed without the directory, title, or version; all three now agree.
- **`drift-check` 1.0.0 → 1.1.0** — the version bump for the non-fiction metrics delivered below (the metrics shipped; the bump didn't).
- **`coldread` 1.0.0 → 1.0.1** — description generalized to "chapter or section (fiction or non-fiction)"; the isolation mechanism was already claim-agnostic.
- **`templates/AGENTS.md`** — removed every reference to the eight unbuilt non-fiction skills: the NONFICTION workflow, editing decision tree, and skill index now name only existing skills (chapter gate = `nonfiction-factcheck` + `nonfiction-clarity-edit`; structural problems re-plan with `nonfiction-chapter-plan` and re-draft; approved report fixes apply via `fiction-revise`, which is report-driven and book-agnostic). The project-type line is now a `__PROJECT_TYPE__` placeholder rendered by `new-book.sh --type`.
- **`sync-manifest.txt`** — corrected the three misnamed `promise-tracker/references/` entries, completed the `review-panel` path rename, removed the two template files that never existed, deduplicated one entry.
- **`CHANGELOG.md`** — the non-fiction expansion entry below corrected to record what `e84222e` actually shipped.

## 2026-10-11 — Non-fiction expansion + generalized skills

> Corrected after a docs-vs-repo audit: this entry originally also claimed `nonfiction-research`, the `review-panel` rename + version bump, `templates/NONFICTION_AGENTS.md` / `HYBRID_AGENTS.md`, and a `new-book.sh --type` flag. None of those shipped in `e84222e`; what actually landed is recorded below, and the follow-ups are in the reconciliation entry above.

Rationale: added full non-fiction support to the library and generalized three existing skills to work across project types. The library was fiction-only; this adds the planning, writing, editing, and quality-gate skills needed for non-fiction books while keeping all existing fiction functionality intact.

### Added

- **`nonfiction-concept` 1.0.0** — define the book's central argument/thesis, target reader transformation, and "big idea". Outputs to `Wiki/Concept/thesis.md`.
- **`nonfiction-audience` 1.0.0** — map reader's current knowledge, objections, and required prerequisites across 5 archetypes. Outputs to `Wiki/Concept/audience.md`.
- **`nonfiction-structure` 1.0.0** — choose and scaffold the argument architecture (problem-solution, chronological, conceptual, hybrid). Outputs to `Wiki/Concept/structure.md`.
- **`nonfiction-chapter-plan` 1.0.0** — beat-sheet equivalent: each chapter's claim, evidence, transition, reader takeaway. Outputs to `Wiki/Outline/Book-N/plan.md`.
- **`nonfiction-writechapter` 1.0.0** — draft with explanatory clarity, signposting, concrete examples, varied evidence types. Outputs to `Chapters/Book-N/Chapter-NNN.md`.
- **`nonfiction-factcheck` 1.0.0** — verify every claim, quote, statistic; flag unsupported assertions. Outputs to `_Edits/Book-N/Chapter-NNN_FactCheck.md`.
- **`nonfiction-clarity-edit` 1.0.0** — the fiction-full-editor equivalent: sentence-level pass for jargon density, abstraction ladder, cognitive load, and signposting. Outputs to `_Edits/Book-N/Chapter-NNN_ClarityEdit.md`.
- **`kill-hedge` 1.0.0** — remove hedge words and qualifiers that weaken claims.
- **`kill-passive` 1.0.0** — convert passive voice to active voice for clarity and authority.
- **`kill-acronym` 1.0.0** — flag unexplained initialisms and acronyms on first use.
- **`promise-tracker` 1.0.0** — unified version of `fiction-promises` that works for both fiction (Chekhov's gun) and non-fiction (thesis threads, unresolved tensions). Maintains `Wiki/Story/Book-N/promises.yaml`.

### Changed

- **`fiction-review-panel` — generalized to support non-fiction personas** (subject-matter expert, intelligent novice, skeptic/practitioner, editorial gatekeeper) via `references/nonfiction-personas.md`. The rename to `review-panel` is completed in the reconciliation entry above.
- **`drift-check` 1.0.0 → 1.1.0** — added non-fiction drift metrics: claim density, evidence-to-claim ratio, abstraction ladder variance, definition reintroduce rate.
- **`templates/AGENTS.md`** — added project-type routing (FICTION/NONFICTION/HYBRID), non-fiction workflow, and non-fiction skill index.
- **`sync-manifest.txt`** — registered the new files.

## 2026-10-10 — Library consolidation (R0, R1, R2, R3.2, R4 harvest)

Rationale: intra-library audit of all 47 skills (`AUDIT-REPORT-2026-10-10.md` — since removed from the repo; read it with `git show e84222e^:AUDIT-REPORT-2026-10-10.md`). Resolves workflow authority contradictions, consolidates the `kill-*` family into a true 7-pass orchestrator, establishes `fiction-full-editor` as the default sentence-level pass, introduces `fiction-revise` for controlled patch application, disambiguates the 4 generator skills, and establishes a routing decision tree in `templates/AGENTS.md`.

### Added

- **`fiction-revise` 1.0.0** — dedicated in-place revision skill that applies user-approved items from review/edit reports (`_Edits/Chapter-NNN_*.md`) directly to chapter files with exact-quote verification, minimal perturbation, a change ledger, and scrap-vs-patch guards.
- **`kill-chapter/references/` rule-sets** — added `the-whole.md`, `person-who.md`, and `opinion-personification.md` so the orchestrator runs all 7 pass rule-sets consecutively.

### Changed

- **`kill-chapter` 1.0.0 → 2.0.0** — upgraded orchestrator to execute all seven kill passes in sequence (simile, person-who, opinion-personification, the-whole, crutch, soft, flat) with unified reporting and consecutive-not-parallel safety.
- **`kill-soft` & `kill-flat`** — descriptions updated to document `kill-crutch WORD` as the generalized single-word pass while retaining dedicated passes for backwards compatibility.
- **Editing stack triage (R2)** — `fiction-full-editor` 1.0.0 → 1.1.0 established as the default sentence-level editing pass with explicit cross-criteria line deduplication; narrowed scopes of `fiction-line-editor` (5.0.0 → 5.1.0), `fiction-prose-editor` (1.1.0 → 1.2.0), and `fiction-aiism-editor` (1.2.0 → 1.3.0) to isolate specific layers when requested.
- **Metadata and workflow normalization (R0)** — removed legacy `workflow-position`, `requires`, and `next-skill` frontmatter fields from 16 skills, establishing `templates/AGENTS.md` as the single authoritative workflow order. Added standard `metadata:` blocks to `coldread`, `fiction-dialogue`, `nominalization-hunt`, and `pangram`. Normalized all skill versions to quoted strings.
- **Generator disambiguation (R4)** — disambiguated trigger descriptions across `name-generator` (people names), `town-generator` (settlement names), `fantasy-settlement` (full settlement dossiers), and `fiction-places` (scene-bearing sites/landmarks).
- **`templates/AGENTS.md`** — rewritten §"Naming and place generation", §"Editing", and Skill index into an explicit routing decision tree.

## 2026-10-10 — Persona-panel harvest (Click Next to Continue)

Rationale: read the twelve-persona review panel built for *Click Next to Continue* (nonfiction) and all twelve verified persona reports, and harvested what transfers to fiction. Three findings shaped this release: (1) the machine tell that survives a clean lint is **house style executed at superhuman uniformity** — dies, not sentences; (2) **quality drifts monotonically toward the back of long manuscripts** while per-chapter gates stay green (rising construction density, concentrating pet words, thinning specifics — four of twelve personas found the same gradient independently); (3) **the book mis-quoting itself** (false callbacks, un-anchored coined terms) is the highest-yield continuity finding in long works.

### Added

- **`fiction-review-panel` 1.0.0** — builds and runs the persona review panel the AGENTS.md layout already promised (`Wiki/Review/panel.md` + `personas/`) but no skill ever built. Encodes the panel design rules the *Click Next* run validated: a persona is a stake + a way of being wrong about THIS book + fixed output flags; never blend; count, don't gesture; **grep-verify every quoted line before filing** (persona passes hallucinate — multiple quote corrections per report in the source run); positive ledger required; lane discipline; cross-persona synthesis for contradictions and gradients. Eight fiction-tuned archetype seats plus an optional hostile advocate.
- **`drift-check` 1.0.0** — diagnostic-only book-level drift audit with `references/drift.py` (tested): pet-word ledger (hot-in-one-chapter or back-half concentration), negation-pivot density trend, opener formula clusters, closer die detection including **noun-swapped dies** (same stop-word frame, fresh content words — verified against a planted case token-overlap alone misses), and specifics-density trend. Finds what per-chapter gates cannot: the gradient.
- **`fiction-reviewchapter/references/panel-harvest-criteria.md`** — eight verified failure modes from the panel run: narrator absolutes ("a true tendency written as a law"), authority without scars, structural problems solved by individual conscience, the quotable line as the risk spot, gloss discipline failing at distance and under compression, the idealized baseline, the sting and its repair grammar, the parable arc.

### Changed

- **`fiction-reviewchapter` 2.4.0 → 2.5.0** — Step 5 now audits the book's internal references: every callback to a specific prior moment is a canon assertion, verified against the chapter where it supposedly happened (false callbacks are worse than unsupported details — the book trained the reader to trust its references). Reads the new criteria file in Step 2.
- **`fiction-promises` 1.0.0 → 1.1.0** — explicit forward references ("that was the last quiet morning") are the loudest promises there is; harvest them with `loud` weight and a `payoff_by_ch` near the deadline the text itself named.
- **`fiction-aiism-editor` 1.1.0 → 1.2.0** — two new criteria categories: self-announcing narration (the docent: "little did she know," narration pointing at its own craft) and noun-swapped dies within a chapter.
- **`templates/AGENTS.md`** — workflow step 15 (panel per act + drift-check at part boundaries), both new skills in the skill index, editing-section routing, and the Wiki/Review panel description now names its builder.
- **`sync-manifest.txt`** — the five new files registered.

## 2026-10-10 — Fork declaration + first owned release

**Ownership.** This library is now ours, not a tracked-deltas copy of upstream. Two pre-fork passes (below) were recorded as deltas against the upstream ZIP; from here on, changes are ordinary development recorded in this file.

Rationale for the fork and the additions: research consensus 2024–2026 is that LLM fiction's core weakness is not surface style (which the kill-* / aiism / burstiness family already fights) but **idea-level and structural sameness** — novelty, surprise, and diversity shortfalls, and convergence on repetitive structural templates. The additions below target that layer, plus two house-keeping gaps: no setup/payoff bookkeeping, and no series-level planning.

### Added

- **`fiction-divergence` 1.0.0** — anti-convergence pass over an outline or beat plan. Generates three candidates per planned beat (default, inversion, cost-shift), selects least-expected-but-earned, checks the outline's skeleton against the genre's default template, and maintains a per-act surprise ledger. Directly targets the homogenization/convergence findings.
- **`fiction-promises` 1.0.0** — the Chekhov ledger, ported from our book-scaffold plugin and adapted to the Wiki layout. Every setup the text makes (object with weight, unanswered question, mentioned skill, threat, debt) tracked in `Wiki/Story/Book-N/promises.yaml` with a required `payoff_by_ch`; buckets overdue / due / undated. Includes a standalone `scripts/promises.py` (no plugin dependencies).
- **`fiction-series-outline` 1.0.0** — series-level planning: per-book dramatic-question stack, inter-book promise map (where `deferred_to_series` setups land), character arc spans across books, escalation plan, handoff inventory. The library was strictly single-book before.
- **`sync-check.sh`** — downloads the upstream ZIP, diffs it against `skills/`, and classifies each difference as ours (expected, per CHANGELOG) or upstream drift to review.
- **`templates/AGENTS.md`** — new skills registered in the start-of-book workflow, the per-chapter loop, and the skill index; `Wiki/Story/series-arc.md` and the per-book `promises.yaml` added to the canon layout.

### Changed

- **`fiction-outline` 5.1.0 → 5.2.0** — setup-and-consequence binding: every chapter's central conflict must bind to an earlier setup (or the premise situation) and leave a consequence a later chapter can use. Conflict from nowhere, or resolution into nothing, is a merge/cut candidate. Grounded in the narrative-planning literature (conflict injection, binding/consequence operations).
- **`fiction-reviewchapter` 2.3.0 → 2.4.0** — new Step 6: audit the Chekhov ledger. Harvests new promises from the chapter as a reader would, records on-the-page payoffs (both `paid_in_ch` and `paid_how`, or neither), and reports overdue/due/undated promises in the review.

## 2026-10-10 — Second confidently-wrong harvest pass (pre-fork)

Rationale: 13-chapter cross-walk of *Confidently Wrong* against this library. Full ledger in the mermaid project's memory (`skill-updates-2026-10-10`) and ZCode memory (`confidently-wrong-audit`).

- `fiction-reviewchapter` 2.3.0: canon-assertion audit step — unsupported specifics against the Wiki are findings.
- `fiction-story-sparks` 1.2.0: forced domain-collision lever for generic premises.
- `fiction-style` 7.0.1 + `fiction-aiism-editor` 1.1.0: marketing-register buzzword additions to `critical-donts.md` / `aiism-criteria.md`.
- `fiction-prose-editor` 1.1.0: cadence-flatline flag — 3+ consecutive same-length sentences in `prose-criteria.md`.
- `templates/AGENTS.md`: scrap-vs-patch rule in Editing.

## 2026-10-10 — First trilogy-lessons pass (pre-fork)

- `fiction-writechapter` 4.1.0: count/date + verbatim-dup completion checks, per-section POV markers, worker-brief rule-binding clause, two-sided word-floor rule.
- `fiction-reviewchapter` 2.2.0: book-layout world paths, tolerant genre-contract extraction, page-verification step.
- `fiction-world` 5.1.0: defers to the book's world layout.
- `name-generator` 1.1.0: canonization collision check.
