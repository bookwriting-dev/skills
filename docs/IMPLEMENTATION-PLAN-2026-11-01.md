# Implementation plan: seven Storycraft improvements

Date: 2026-11-01. Status: implemented in the working tree; validation limits are recorded in the execution record below.

This plan covers all seven improvements proposed in the conversation. It preserves the existing project-local skill distribution and builds the features as incremental releases. Paths below are relative to this repository unless explicitly labeled as book-project paths.

## Directorial brief

**Intent and stance.** Improve manuscript quality by preserving author decisions, making review evidence current and traceable, tracking information flow, testing the sequential reading experience, coordinating book-wide revision, measuring editorial restraint, and delivering verified manuscript exports. Authors consume readable reports; skills and scripts consume versioned records. Deterministic scripts own bookkeeping; agents make literary judgments with cited evidence.

**Boundaries.** Do not modify existing book projects as part of developing this library. Do not silently turn a rejected edit into a permanent style rule. Do not treat simulated reader reactions as actual reader research. Do not infer literary quality from a checksum, a prose metric, or a gate verdict. Do not expose future text or private planning to blind readers. Do not overwrite manuscript sources during export or use Git resets to undo author work. Existing untracked planning files are outside this change.

**Verified context.** The library has 74 skills and pins a full copy into each new project. `templates/AGENTS.md` owns workflow order. `chapter-pipeline` already sequences scene planning, drafting, promise harvest, gate, and polish. `fiction-revise` already verifies quotes and produces a change ledger. `book-status` and `kanban-board` use timestamps for some findings; the fiction board accepts an existing PASS as Done without content freshness. `canon-guard` has impact analysis but no durable campaign execution. `reader-persona-review` has a running-brief concept but allows some personas to inspect bibles. `compile-manuscript` currently specifies a combined Markdown output without an executable exporter. `make check` runs lint, inventory, syntax, deterministic evals, and scaffold smoke tests.

**Deliverable shape.** Seven feature workstreams, one shared contract layer, executable validation, migration guidance, and a final integration exercise. Extend existing skills where possible. Add four focused skills: `editorial-memory`, `fiction-knowledge`, `sequential-read`, and `revision-campaign`. The expected count becomes 78 if the library is otherwise unchanged; derive documentation counts from inventory at implementation time. No application UI, hosted service, model-provider dependency, or automatic deployment is required.

## Scope and implementation order

| Phase | Delivers | Depends on | Relative size |
|---|---|---|---|
| 0 | Shared contracts, migration policy, evaluation fixture skeleton | Existing library | Medium |
| 1 | Idea 2: review freshness and resumable pipeline | 0 | Large |
| 2 | Idea 1: editorial preference memory; first preservation benchmark | 1 | Large |
| 3 | Idea 3: character and reader knowledge ledger | 1 | Large |
| 4 | Idea 4: sequential blind reading | 1, 3 for later comparison only | Large |
| 5 | Idea 5: coordinated book-wide revision | 1–4 | Large |
| 6 | Idea 7: reliable manuscript delivery | 1; evaluated against campaign output | Large |
| 7 | Idea 6 completed: full preservation evaluation and integrated release | All prior phases | Medium |

Evaluation work starts in phase 0 and accompanies every feature; phase 7 completes the corpus and release comparison. Each phase must provide a usable increment. Split large phases into contract/helper, producer integration, consumer integration, and verification changes. These are relative sizes, not calendar estimates.

## Shared architecture and contracts — phase 0

### Canonical project records

Honor explicit project conventions first. New projects use these defaults:

| Book-project path | Authority and purpose |
|---|---|
| `Wiki/Style/editorial-decisions.json` | Explicit author decisions, scopes, evidence, and supersession history |
| `Wiki/Story/Book-N/knowledge.json` | Sourced knowledge and belief events; proposed events kept distinct from confirmed entries |
| `_Edits/Book-N/Chapter-NNN_<Type>.meta.json` | Sidecar recording what a saved report actually reviewed |
| `_Edits/Book-N/decisions.jsonl` | Append-only finding dispositions: applied, rejected, deferred, superseded |
| `_Edits/Book-N/pipeline/Chapter-NNN.json` | Resumable pipeline step journal |
| `_Edits/Book-N/reading/<run-id>/` | Ordered reader packets, checkpoints, reactions, and final synthesis |
| `_Edits/Book-N/campaigns/<campaign-id>/` | Revision plan, task dependencies, journal, evidence, and snapshots |
| `Chapters/Book-N/export/<profile>/` | Generated export artifacts and provenance manifest |

All machine records have `schema_version`, stable IDs, and project-relative paths. Use JSON for new structured records so bookkeeping needs only Python's standard library. Existing `promises.yaml` remains unchanged and continues to use its existing parser. Human-readable Markdown reports remain the normal author interface. Sidecars keep machine metadata out of prose and reader-facing exports.

### Shared helper ownership

- Add `skills/book-status/scripts/project_state.py`, `references/state-contract.md`, and `assets/report-meta.schema.json`. The script is a standalone CLI for hashing inputs, recording report evidence, validating state, and reporting freshness; it does not judge prose.
- Proposed interface: `project_state.py snapshot --root ROOT --spec INPUTS.json --output META.json`; `check --root ROOT --meta META.json --json`; `validate --root ROOT --book Book-N`. Define exit codes and exact record shapes before implementing consumers.
- Other skills invoke the helper through an explicit bundled-skill dependency. They must not import repository-only `tools/` modules: those do not ship into book projects.
- Extend tooling to validate declared bundled dependencies. Full-library pins contain the helper. For an individually copied or older skill set, a missing helper yields `UNKNOWN` freshness with an installation instruction, never a guessed PASS or silent weakening.
- Record relative path, existence, SHA-256, input role, and applicable section selector for each consumed input, plus relevant skill/reference versions and content hashes. Track searched directory inventories and expected-but-missing inputs so adding a new canon entry can invalidate a review.
- Begin with whole-file hashes where semantic slicing is uncertain. Explicitly allow conservative invalidation. A changed file does not prove a contradiction; it means the old review no longer establishes current correctness.
- Helpers write atomically and detect changed source hashes before recording completion. Conflicting concurrent writers retry or stop; no last-writer-wins data loss. Readers validate records before trusting them.

### Foundation deliverables and checks

Add `docs/STATE-CONTRACT.md`, `docs/MIGRATION.md`, and a tiny synthetic book under `tools/eval-fixtures/storycraft-book/`. Include a reveal, a deliberate voice choice, a real prose defect, a stale review, and an unfinished revision.

Extend `tools/eval-skills.sh` through focused Python test entry points; keep `make check` the single deterministic CI gate. Validate malformed records, unsupported schema versions, missing files, relative path containment, atomic-write failures, and duplicate IDs. No production project must be needed to run tests.

## Idea 2 — review freshness and safe resume — phase 1

### Behavior

- Keep verdict (`PASS`, `WARN`, `FAIL`) separate from freshness (`CURRENT`, `STALE`, `UNKNOWN`). A report lacking metadata is legacy/unknown, not current.
- All persistent review producers write a sidecar after successful report completion. Bind metadata to the report body's hash as well as its source inputs. Stable finding IDs distinguish multiple findings on the same line.
- Record actual inputs: target draft, relevant prior chapter, scene plan, style and canon references, promises/knowledge records when used, editorial decisions when used, and reviewing skill content. Broad reviews may conservatively depend on the whole relevant directory.
- `book-status` and `kanban-board` show stale/unknown evidence and its reason. Fiction Done requires a current PASS and no unresolved blocking findings. Define non-fiction completion explicitly as current required fact-check/clarity evidence with blocking findings resolved; merely having a clarity report is insufficient. Hybrid projects use their configured required checks and ledger owner.
- Replace timestamp-based inference of applied findings with the disposition ledger. Keep timestamps for display only. Legacy unresolved findings remain unknown until inspected.
- Persist each pipeline step's inputs, outputs, run ID, start/completion state, and disposition. Resume only completed steps whose evidence still matches. Interrupted steps are not assumed complete.
- All polish invalidates a pre-polish gate; obtain a final current gate before declaring the pipeline complete. Idempotent promise harvest must not create duplicate entries on retry. A harvest interrupted between manuscript and ledger changes requires reconciliation before continuing.

### Files and integration

Primary changes: `skills/book-status/`, `skills/kanban-board/SKILL.md`, `skills/chapter-pipeline/SKILL.md`, `skills/gate-check/SKILL.md`, `skills/fiction-reviewchapter/SKILL.md`, `skills/fiction-revise/SKILL.md`, and `templates/kanban-board.md`.

Audit every durable report writer, including the three focused fiction editors, full editor, kill passes, diagnostics, persona reviews, LitRPG audit, and non-fiction editors. Wire each relevant consumer to the same contract. Register multi-chapter reports with all target hashes. Conversational quick verdicts need no saved metadata.

### Acceptance checks

1. Editing a reviewed chapter while preserving its mtime makes its review stale; changing only the mtime does not.
2. Changing a consumed predecessor, canon file, preference, or skill reference invalidates the affected evidence; an unrelated unconsumed file does not, unless it belongs to a recorded directory dependency.
3. A legacy PASS never appears as current Done. Moving the project root preserves relative-path validity.
4. Resume after each pipeline step, including an interrupted harvest and polish, without duplicate edits, duplicate promises, or a false completion claim.
5. A report-body edit or a source change during review prevents acceptance of the old snapshot.

## Idea 1 — editorial preference memory — phase 2

### Behavior and schema

Add `skills/editorial-memory/` with `SKILL.md`, a schema/template, examples, and a standard-library decision recorder. Trigger examples: “remember this editorial choice,” “show my editing preferences,” “stop flagging this construction for this character,” and “retire that preference.”

Each decision records `id`, `status`, `scope`, `rule_category`, source finding/quote/hash, the author's decision and reason, positive/negative examples when supplied, creation time, and `supersedes`. Scopes include passage, scene, chapter, POV/character, book, and series. Status distinguishes an observed one-time decision from an explicitly reusable preference.

- Applying or rejecting an edit creates a disposition; it does not automatically create a broad preference.
- Record reusable preferences when the user explicitly expresses one. Otherwise retain the local decision and surface a proposed generalization only if useful.
- A new broad style change must explicitly supersede narrower conflicting exceptions to erase them. Unresolved rule conflicts are reported; file recency is not authority.
- Preferences never suppress factual, canon, POV-knowledge, or numeric errors. Current user direction and book instructions retain their established authority.
- Editors load only applicable preferences and explain any intentional KEEP decisions. Drafting/voice generation uses approved reusable examples; it does not copy example prose into unrelated scenes.

### Integrations

Wire `fiction-revise` and in-place kill passes to record dispositions. Wire full/line/prose/AIism editors, targeted kill skills, `levelup`, `fragment-hunter`, `nominalization-hunt`, `fiction-style`, `fiction-voiceprompt`, and fiction/non-fiction drafting and clarity editing to consult applicable preferences. Include preference hashes in affected review metadata. Preserve user-authored preference records during style refreshes and library upgrades.

### Acceptance checks

- Keeping one fragment does not exempt every fragment. A POV exception does not leak to another POV or book.
- A rejected canon repair cannot become permission to ignore a canon contradiction.
- Retired/superseded decisions stop influencing reviews; audit history remains readable.
- Re-running an editor respects an explicitly retained construction while still detecting the nearby genuine defect.
- First author-scored preservation comparison is captured before widening integration to every editor.

## Idea 3 — information and belief continuity — phase 3

### Behavior and schema

Add `skills/fiction-knowledge/` with harvest, inspect-as-of, and audit modes. Store stable fact IDs separately from events. Each event includes character/reader observer, fact ID, epistemic state (knows, suspects, believes, disbelieves, or forgets), source passage/hash, story-time position, reader chapter/scene position, confidence, and confirmation status. Facts distinguish established truth, disputed claims, and deliberately unresolved truth.

- Track story chronology separately from reading order so flashbacks and out-of-order POVs work.
- Record knowledge sources such as witnessed events, messages, testimony, and deductions. Unsupported inferred knowledge is a candidate finding, not a fabricated fact.
- Preserve false beliefs and unreliable narration. Reader exposure to a claim does not make the claim true.
- Generate state as of a selected scene from the event history. Revisions invalidate affected source events; re-harvest supersedes them without destroying history.
- Link promise IDs where useful; information exposure and payoff obligations remain distinct concepts.

Integrate harvest/audit into `fiction-writechapter`, `fiction-scenes`, `fiction-dialogue`, `gate-check`, `fiction-reviewchapter`, `canon-guard`, and `series-continuity`. Extend `chapter-pipeline` to harvest knowledge before gating. Populate existing projects incrementally; absent coverage means unknown, not a clean knowledge audit.

### Acceptance checks

The fixture must catch a character acting on a secret too early; preserve a supported deduction and an intentional false belief; distinguish reader-only information; handle a flashback; and invalidate a reveal moved to another chapter. A blind-reader worker must never receive this ledger.

## Idea 4 — sequential blind reading — phase 4

### Behavior and isolation

Add `skills/sequential-read/` with a packet builder, checkpoint schema, reading instructions, and synthesis template. Extend routing in `review-panel` and `reader-persona-review`: quick pulse stays quick pulse, existing panel stays panel, ordered spoiler-free reading selects this skill.

- Default to one neutral target-reader perspective, one chapter at a time. Allow extra perspectives explicitly; record the added run scope.
- A packet contains only current reader-facing chapter text, permitted packaging, a spoiler-free reader brief, and the previous sealed reader checkpoint. It excludes canon, knowledge ledgers, future chapters, craft instructions, and personas whose descriptions reveal plot outcomes.
- Use a fresh isolated worker/context for each step. Chapters within one run are sequential. A parent that has read the outline cannot simulate a blind pass inline. If the host cannot provide isolation, prepare packets and mark the run pending external execution; never label it a completed blind read.
- Checkpoint fields: remembered facts, expectations, predictions, questions, perceived relationship changes, emotional response, confusing passages, and desire to continue with reasons. Cap the carried memory explicitly and record truncation; memory loss from compression is a method limitation, not proof that prose failed.
- Save each reaction before exposing the next chapter. Earlier predictions remain immutable. Final comparison with actual reveals or the knowledge ledger happens only after the blind run is sealed, in a separate analysis stage.
- Resume uses ordered chapter hashes and checkpoint hashes. Editing chapter K invalidates checkpoints K onward and preserves earlier unaffected observations.

### Outputs and acceptance checks

Save `run.json`, per-chapter packet manifests, `Chapter-NNN.json`, and `synthesis.md` under the reading run directory. Label every result simulated feedback. Do not manufacture market ratings or claims about actual readers.

Test future-only sentinel exclusion from packet contents, persona definitions, and checkpoints. Inspect the actual worker input transcript in a behavioral pilot; packet tests alone cannot prove host isolation. Verify early predictions remain unchanged, later reactions can revise them, and restart from a changed chapter cannot reuse downstream memories. A small real beta-reader comparison may calibrate the method later; it is not required to ship the tool honestly.

## Idea 5 — coordinated book-wide revision — phase 5

### Behavior and schema

Add `skills/revision-campaign/`, extending the existing developmental editor and canon-guard rather than duplicating their literary criteria.

Campaign records contain the requested outcome, preserved strengths, scope/authorization, affected books, input hashes, task IDs, dependencies, proposed/applied changes, per-task state, checks, and unresolved decisions. A series-wide campaign has one owning book directory and references other books by project-relative paths.

1. Translate the author's request into observable story outcomes: for a betrayal, earlier motive/choice evidence, intermediate trust changes, reveal fairness, and consequences.
2. Read the assigned manuscript range and use canon, promises, knowledge events, preferences, and reader findings to map impact. Use semantic reading as well as text search; a changed motive can affect scenes that never name it.
3. Classify tasks as plan repair, scene re-draft, local edit, canon update, ledger reconciliation, or verification. Build an acyclic dependency graph and flag conflicting campaigns.
4. Execute authorized tasks in dependency order. Structural tasks route through `fiction-dev-editor`/`fiction-scenes` and `fiction-writechapter`; local edits route through `fiction-revise`. Preserve existing authorization; ask only for genuinely unresolved story choices or newly expanded scope.
5. Snapshot targeted files, verify expected source hashes before writes, journal actual changes, reconcile promises/knowledge, and re-gate affected chapters. Keep in-place edits sequential when they touch shared files.
6. Resume from verified task outputs. Offer restoration of campaign-owned changes only when the current file matches the campaign's expected post-edit hash; otherwise produce a conflict-aware recovery plan. Never discard later author edits.

Expose campaign blockers and changed chapters in `book-status`/`kanban-board`. Update canon-guard so impact reminders link to campaign tasks and report freshness; remove reminders only after corresponding current checks succeed.

### Acceptance checks

A synthetic betrayal revision must add an early setup, revise the middle, and adjust the payoff while preserving a marked successful scene. Interrupt and resume halfway without repeated edits. Detect external author changes, task cycles, stale reports, unresolved structural work, and cross-book consequences. Completion requires reconciled ledgers and current required checks for the affected scope, not merely all tasks marked edited.

## Idea 7 — verified manuscript delivery — phase 6

### Implementation

Expand `skills/compile-manuscript/` with `scripts/compile_manuscript.py`, export configuration/schema, profile templates, and precise instructions. Proposed interface:

`compile_manuscript.py --root ROOT --book Book-N --profile beta|submission|publication --format md|docx|epub|pdf --check`

Omitting `--check` builds the requested outputs. Support repeatable `--format`. A read-only preflight names missing converters and required inputs. Markdown assembly uses the standard library; other formats use explicitly detected Pandoc and, for PDF, a configured supported PDF engine. Record converter versions. Do not install software silently or substitute a different format when conversion is unavailable.

- Resolve authoritative sources from project conventions/configuration; sort chapter numbers numerically. Detect missing, duplicate, and ambiguous chapters. Exclude report, backup, and export directories.
- Normalize only explicitly recognized scene-break markers. Ordinary blank paragraphs, thematic rules, poetry, quotations, and intentional formatting must survive. Configure internal markers/POV labels separately from printable scene breaks.
- Strip only documented internal apparatus, such as recognized craft comments or dedicated metadata blocks. Preserve ordinary text and LitRPG stat/system blocks. Unknown metadata requires a clear preflight finding rather than broad deletion.
- Profiles define front/back matter, scene breaks, title/heading treatment, and TOC behavior. Beta emphasizes reader usability; submission uses configurable recipient requirements; publication creates the delivery package. Avoid claiming any universal submission standard.
- Build a final story state after revision before exporting. Beta exports may include unresolved warnings recorded outside the manuscript. Submission/publication defaults require current configured checks and no blocking campaign tasks. Any explicitly requested unchecked preview must be labeled in its manifest and response; it cannot count as release verification.
- Stage outputs before replacing previous exports. Source chapters stay byte-identical. Record source hashes, ordered chapter list, profile/settings, converter versions, output hashes, and warnings in `export-manifest.json`.

### Acceptance checks

Use fixtures for chapters 1/2/10, missing/duplicate numbering, Unicode names, inline emphasis, dialogue punctuation, scene breaks, internal notes, LitRPG boxes, and front/back matter. Verify chapter completeness, ordering, no leaked sentinels, preserved meaningful content, and source hashes before/after.

Verify DOCX document structure, EPUB navigation/package integrity, PDF page/text presence, and conversion failure behavior. Perform visual inspection of representative pages in each supported rendered format; structural parsing alone is insufficient. CI runs Markdown tests on every check and converter-backed tests in a documented job with explicit dependencies. Release acceptance requires real outputs for all advertised formats. Update `book-packaging`, USER workflow, and status output to link the resulting artifacts.

## Idea 6 — preservation-focused evaluations — phases 0–7

### Corpus and protocol

Add `tools/eval-fixtures/editorial-preservation/`, `tools/eval-editorial.py`, and `docs/EDITORIAL-EVALS.md`. Begin with a pilot and grow to at least 24 short cases: 12 deliberate successful choices and 12 genuine defects, paired where possible so similar surface syntax has different functions. Cover fragments, repetition, metaphor, dialect, quiet endings, interiority, and factual/knowledge violations. Include three chapter-length cases for interaction effects.

Each case contains source prose, applicable book rules/preferences, expected problem/protected spans, permissible edit scope, and rationale. Initial labels are provisional until author-reviewed. Use original synthetic prose and user-selected excerpts with permission; keep a held-out set out of skill tuning examples.

Separate deterministic execution checks from literary evaluations:

- `make check`: schemas, exact-quote support, protected-span mutation accounting, scope boundaries, stale-state handling, fixture integrity, and script behavior.
- `make eval-editorial`: provider-neutral prompt packets plus scoring of recorded model outputs; no required API key or network calls in default CI. Record model/host configuration, skill hashes, input hashes, and full candidate outputs.
- Author review: blind A/B comparisons where practical, edit acceptance, voice preservation, missed defects, and harmful interventions. Model graders can organize evidence but are not the sole quality authority.

Report harmful-edit rate on protected cases, defect detection precision/recall, accepted-edit rate, and per-category failures with sample counts. Avoid a single composite quality score. Run repeated matched baseline/candidate trials to expose variance; set the repeat count before the run.

### Release acceptance

Zero unsupported source quotes, zero out-of-scope source edits, and zero simulated-blind packets containing future-only fixtures are hard execution requirements. For literary outcomes, set category-specific tolerances after the author-reviewed pilot and before comparing candidate results; do not invent a success threshold after seeing scores. Surface every regression and require a documented decision before calling the release an improvement. If literary scoring is still pending, say behavioral evaluation is pending even when `make check` is green.

## Migration, documentation, and release discipline

- New tracking records are created on first use. Missing new artifacts do not force existing books to rebuild their Wiki or renumber chapters.
- Extend `tools/update-project.sh` with a read-only migration report listing missing helpers, legacy reports, schema upgrades, and template changes. Preserve local skill customizations: compare pinned base/local/new content where available; otherwise report conflict and retain local content. Do not overwrite book instructions or editorial memory during a library update.
- Legacy reports remain readable; freshness is unknown until re-reviewed. Do not mint current metadata from today's files for a historical review. Existing decisions/knowledge can be imported as unverified candidates with provenance.
- Schema migrations are explicit, backed up, idempotent, and reject unsupported future versions. Validate partial upgrades and mixed old/new skill sets.
- Update `new-book.sh`, `templates/AGENTS.md`, `templates/kanban-board.md`, `tools/smoke-new-book.sh`, USER/DEVELOPER docs, README, generated inventory, and sync manifest when the corresponding feature ships. New projects receive all declared helper dependencies.
- Every skill change gets the appropriate semantic version bump and CHANGELOG entry. Regenerate inventory when frontmatter changes; update `VERSION` per coherent library release. Preserve the one-line `CLAUDE.md` import convention.
- Run `make check` after each implementation slice. Add only tests that verify meaningful behavior or regression risks. Commit/push and updates to external book projects are separate actions from this planning task.

## Final integration exercise

Use one disposable fiction book and one non-fiction/hybrid project fixture:

1. Draft/review a chapter and obtain current gate evidence.
2. Keep a deliberate stylistic choice, record the preference, and verify the next edit respects its scope.
3. Harvest a secret and a false belief; detect an intentionally premature use.
4. Complete an isolated sequential reading run and retain its original predictions.
5. Execute a multi-chapter revision, interrupt it, resume it, and verify downstream freshness and reading-checkpoint invalidation.
6. Reconcile promises/knowledge and re-review the affected scope; board/status must agree on completion.
7. Produce and inspect beta DOCX, submission DOCX, publication EPUB, PDF, and Markdown outputs with manifests.
8. Run the preservation benchmark against the recorded baseline and report author-scored outcomes separately from deterministic test results.
9. Upgrade an older disposable project with local customizations; verify no author content is lost and legacy checks remain visibly unknown until refreshed.

Completion means all seven features have working producers and consumers, documented migration behavior, passing deterministic checks, recorded behavioral evaluation, and the promised export artifacts. Feature descriptions alone do not count as implementation.

## Execution record — 2026-11-01

The implementation is present in the working tree. Library revision: 2026.11.01; 78 skills. Existing book projects have not been upgraded by this work.

| Workstream | Implemented | Verification and remaining limits |
|---|---|---|
| Shared contracts | Portable state runtime, versioned records/templates, report schema, bundled dependency lint | Schema rejection, root containment, lock conflict, source/report race and moved-root regressions |
| Review freshness/resume | Prepared input evidence, current/stale/unknown checks, stable dispositions, journals, producer/consumer instructions | Content-vs-mtime tests and interrupted-step checks; literary judgments still performed by the host agent |
| Editorial memory | Scoped explicit decisions, supersession, protected correctness categories, editor/worker/drafting integration | Scope isolation, retirement, and canon-waiver rejection; author preference acceptance study pending |
| Knowledge | Sourced event history, confirmed/candidate distinction, false beliefs, story/reader positions, stale-source queries | Flashback/reader-order/duplicate/stale regressions; semantic audit remains agent work with partial coverage disclosed |
| Sequential reader | Packet builder, checkpoint sealing, source checks, bounded memory, isolation requirements | Three fresh reader agents completed a three-chapter synthetic run; early predictions retained, no future chapter supplied. Carried memory was explicitly condensed. This is simulated feedback. |
| Revision campaigns | DAG tasks, source snapshots, expected-hash start guard, check-backed completion, conflict-aware recovery | Dependency/cycle/interrupt/current-check/recovery tests; chapter-scale creative campaign evaluation remains a larger pilot |
| Manuscript delivery | Preflight, profiles/config, staged Markdown/DOCX/EPUB/PDF, provenance and safe previous package | Real Pandoc and Typst conversions passed. PDF inspected visually. DOCX/EPUB containers verified; native DOCX preview failed in the sandbox, so their visual layout approval remains pending. |
| Preservation evaluation | 24 provisional cases, neutral packets, baseline-ref support, recorded-output scoring, explicit author-pending status | Tooling executable; labels/tolerances and repeated baseline/candidate literary judgments require author validation. Synthetic chapters are short integration fixtures; author-selected full chapters remain to be added. |
| Migration | Installed-base hashes, local/unknown conflict retention, safe prune, read-only migration report | Disposable legacy/local customization tests; instruction templates are reconciled manually |

Verification commands: `make check`, `make export-eval`, and `make eval-editorial`. Real local export artifacts and isolated pilot records were generated under `/private/tmp/storycraft-export-verification/` for inspection; they are disposable, not a manuscript release. CI includes a separate explicit converter job. No claims about measured prose superiority or actual reader response are made before the pending literary evaluations.
