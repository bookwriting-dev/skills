# Storycraft state contract, schema version 1

The bundled runtime is `../scripts/project_state.py`, invoked with Python 3. It has no third-party dependencies. All commands put --root ROOT and --book Book-N before the subcommand. Paths persisted in records are project-relative; paths escaping root, including symlinks, are rejected. A copied skill lacking book-status must report UNKNOWN/install the full pinned library. Never replace a missing helper with a guessed current verdict.

## Review lifecycle

Before reading source, create a JSON spec: schema_version 1, report (relative report filename), verdict (initially WARN), and paths (all inputs to be consumed, including draft, predecessor, scene plan, applicable canon/style/knowledge/preferences and reviewing skill/reference files). Include a directory when discovery through that directory affects the answer; include expected missing files to detect their later creation. Include the relevant skill directory to invalidate changed review rules. Never include the output report or its metadata in its own input dependencies.

Run `project_state.py --root ROOT prepare --spec SPEC.json --output _Edits/Book-N/review-inputs.json`. Use a unique run-specific output for simultaneous reviews. Read/review those exact inputs. Give findings stable IDs, exact quotes, category, blocking status, and proposed local repair. Record the final verdict in the prepared spec without replacing its inputs. Write the normal report. Run `snapshot --spec PREPARED.json --output _Edits/Book-N/Chapter-NNN_Type.meta.json`. Completion compares the captured inputs with current content and refuses stale runs. The report body is also hashed. Spec files may live outside root; persisted artifacts always stay inside root.

Run `check --meta PATH` or `validate` for freshness. CURRENT means inputs and report match, not that a literary judgment is correct. STALE lists changed evidence. UNKNOWN means no metadata. Exit 0 means a successful operation (including a successful check returning STALE); exit 2 means invalid input, conflict, missing dependency, or I/O error. Consumers must inspect freshness and verdict, not merely the process exit code. Hashes are SHA-256 over exact bytes; directory dependencies include recursive relative filenames and hashes. Moving a whole project preserves validity. Whole-file/directory dependencies intentionally allow conservative invalidation.

## Finding dispositions

Use `disposition --spec ITEM.json`: schema_version 1, finding_id, report, disposition (applied/rejected/deferred/superseded), reason, source quote, and before/after hashes when applicable. Records append to `_Edits/Book-N/decisions.jsonl` under a fail-fast lock. Last explicit disposition for the same report hash and finding ID controls. Pending blocking items prevent Done even with an old PASS. Missing legacy dispositions require inspection; timestamps cannot establish resolution. Never equate a rejection with a reusable preference.

## Pipeline journal

Use `pipeline --run RUN-ID --action record --spec STEP.json` with a `pipeline_step` schema-version-2 record: stable step `id`, matching `operation_id`, `idempotency_key`, declared `completion_profile`, `stage_role`, identified `subjects`, `constraints`, authorized write paths, status, pre-operation inputs, and post-operation outputs for completion. `transform_paths` names authorized in-place mutations; completion must provide exact before/after evidence in `transformations`. Keep immutable checkpoints/reports in `outputs`, not the mutable manuscript path. Later stages may supersede a transformation's after-hash without erasing its completed history, while the checkpoint/output artifacts and untouched dependencies remain current. Call prepare separately to capture evidence. The journal binds one run manifest and rejects profile, subject, constraint, or write-scope changes during completion. Legacy schema-version-1 histories remain readable but are not promoted to reusable current evidence without a compatible migration. `pipeline --run RUN-ID --action list` returns reusable only for completed steps whose immutable outputs and untouched inputs still match. Never resume a running step blindly; inspect actual files, reconcile partial harvest/edits, then record a new attempt. A later step that consumes mutable ledgers can invalidate earlier completed checks; reconcile intended outcomes instead of re-applying edits automatically.

The shared readiness evaluator treats `draft_verified` as the lightweight current-check profile. `full_editorial_candidate` and `independent_editorial_gate` require a linked operation journal with all named, reusable stages in order; a lone PASS review cannot satisfy either. The independent profile additionally requires a verified isolation status, permitted-input manifest hash, sealed-reaction hash, and the independent-reader stage first. An unavailable or unproven condition remains ineligible/pending, not silently waived.

## Atomic ledger generations

Series-wide `relationship-events.json` and `knowledge-events.json` writes are committed through [ledger_store.py](../scripts/ledger_store.py), not direct multi-file replacement. The current generation is named by `.storycraft/ledger-current.json`; its immutable contents are under `_Edits/_ledger-generations/`. Readers must resolve a ledger through that pointer and verify its digest. The pointer replacement is the commit boundary: an orphan prepared generation is not current and must not be consumed. Inspect with [ledger_transaction.py](../scripts/ledger_transaction.py) `--status`; retry an identical transaction ID safely, but a different payload under that ID is a conflict. Supply the expected generation and source evidence for every multi-ledger transaction. Preserve abandoned generations for diagnosis; never delete or rewrite them as a recovery shortcut.

## Manifest-resolved chapter packets

`project_manifest.py::resolve_chapter` resolves a stable chapter ID, display label, or canonical path. `draft-packet` uses the manifest's reading order, predecessor, manuscript path, optional scene-plan/psych paths, and declared style authority. Legacy numbered layouts are adapted read-only. If chronology cannot be mapped from a custom display label, legacy integer relationship/knowledge checkpoints remain unresolved rather than treating reading order as story time. Conflicting style-guide aliases are included as an explicit conflict and are not silently selected.

## Other records

Editorial memory, knowledge, reading, and campaigns use the templates shipped with their owning skills. `memory --action list --scope SCOPE` returns series plus exact scope; collect applicable ancestors explicitly. Only active records apply. Knowledge positions are integer arrays; as-of uses story order for characters and reading order for reader. Truth status is not derived from epistemic state. Source hashes and exact quotes are mandatory for knowledge.

`workflow` returns `project_type`, `required_checks`, and the policy input paths for review receipts. Defaults come from AGENTS.md. The book manifest can set `required_checks`. The exporter also accepts an explicit delivery-specific override.

`register-chapters --spec SPEC.json` writes a v2 project manifest from a v1 specification. For conventional chapters provide `{"schema_version":1,"chapters":[{"number":1},{"number":2}]}`. Custom entries supply `id`, `display_label`, `path`, and `reading_order` under `"chapter_order":"declared"`. Entries can also specify predecessor, scene and psych paths, and a report stem. Re-registering the same plan is idempotent. A full outline revision may set `"replace_expected":true` to remove older unwritten entries it omits. Existing drafts stay registered. The resolved chapter format and draft packet expose `report_stem` to review producers.

`draft-packet --chapter N [--window 3] [--output _Edits/Book-N/packets/Chapter-NNN_DraftPacket.json]` compiles a deterministic pre-draft packet for Chapter N: scene plan metadata, extracted psychological interiority (`what_they_wont_say` and `show_dont_tell_gaps` from `Chapter_NN_Psych.md`), POV-matched voice prompts (`voice_prompt_<POV>.md` with `voice_prompt.md` fallback), chapter-sliced `relationship_checkpoints` (`chapter_start <= N <= chapter_end`), the immediate continuity tail from Chapter N-1, confirmed `knowledge_as_of` state at `[N, 0]`, applicable active `editorial_decisions`, and a rolling N-chapter `cooling_list` (somatic hotspots, repeated content 3-grams, repeated similes, and recent openers/closers with callouts and fenced blocks stripped).

Packets also include the heading and POV convention and sourced claims for the scene plan's continuity keys. See [book continuity review](continuity-review.md) for the claim schema, chapter-format checks, and whole-book export coverage rules.

Reading packets contain current text, reader brief, and prior sealed reaction only. Sealing requires coordinator-verified isolated input evidence. Prior checkpoints are immutable. If earlier text changes, fork a run; do not amend history. Preparation is not proof of actual model isolation.

Campaign tasks use explicit files, dependency IDs, and current check metadata. Source snapshots are recovery aids, not an automatic rollback authorization. Restore only unchanged campaign output and reverse dependency order. A task can be complete while its checks subsequently become stale; status must show that distinction.

## Storage and migration

Every object has schema_version 1. Unsupported future schemas fail; do not coerce. Writes use same-directory temporary files, fsync, atomic replacement, and exclusive lockfiles for mutations. A stale lock requires inspecting the owner PID and files before manual removal; no timeout steals another writer's lock. Record templates are examples requiring actual source evidence, not valid production findings.

Legacy reports stay UNKNOWN until re-reviewed. Never produce current metadata retrospectively from current sources for an old report. Ledger initialization is lazy and existing content is never re-seeded. Library updates must preserve project source, book instructions, preferences, decisions, and locally changed skill files.

Draft packets include a `scenes` array. Each entry owns its POV, private voice file, knowledge, and applicable scoped decisions. For the series event ledger, scene-level **Story order:** and **Reader order:** select evidence on separate axes. Missing chronology stays unresolved. The packet's top-level POV fields summarize the chapter for legacy callers.

`style-policy [--simile-count N]` reads the book's review guide. It supplies chapter and paragraph limits, approved examples, and punctuation rules. Capture its input paths and include the applicable scoped editorial decisions in the editing brief.
