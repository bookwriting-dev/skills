# Changelog

Our changes to the library, newest first. Skill versions live in each SKILL.md's frontmatter and bump with every change; entries here record the why.

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
