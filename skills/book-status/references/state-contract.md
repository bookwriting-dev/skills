# Storycraft state contract, schema version 1

The bundled runtime is `../scripts/project_state.py`, invoked with Python 3. It has no third-party dependencies. All commands put --root ROOT and --book Book-N before the subcommand. Paths persisted in records are project-relative; paths escaping root, including symlinks, are rejected. A copied skill lacking book-status must report UNKNOWN/install the full pinned library. Never replace a missing helper with a guessed current verdict.

## Review lifecycle

Before reading source, create a JSON spec: schema_version 1, report (relative report filename), verdict (initially WARN), and paths (all inputs to be consumed, including draft, predecessor, scene plan, applicable canon/style/knowledge/preferences and reviewing skill/reference files). Include a directory when discovery through that directory affects the answer; include expected missing files to detect their later creation. Include the relevant skill directory to invalidate changed review rules. Never include the output report or its metadata in its own input dependencies.

Run `project_state.py --root ROOT prepare --spec SPEC.json --output _Edits/Book-N/review-inputs.json`. Use a unique run-specific output for simultaneous reviews. Read/review those exact inputs. Give findings stable IDs, exact quotes, category, blocking status, and proposed local repair. Record the final verdict in the prepared spec without replacing its inputs. Write the normal report. Run `snapshot --spec PREPARED.json --output _Edits/Book-N/Chapter-NNN_Type.meta.json`. Completion compares the captured inputs with current content and refuses stale runs. The report body is also hashed. Spec files may live outside root; persisted artifacts always stay inside root.

Run `check --meta PATH` or `validate` for freshness. CURRENT means inputs and report match, not that a literary judgment is correct. STALE lists changed evidence. UNKNOWN means no metadata. Exit 0 means a successful operation (including a successful check returning STALE); exit 2 means invalid input, conflict, missing dependency, or I/O error. Consumers must inspect freshness and verdict, not merely the process exit code. Hashes are SHA-256 over exact bytes; directory dependencies include recursive relative filenames and hashes. Moving a whole project preserves validity. Whole-file/directory dependencies intentionally allow conservative invalidation.

## Finding dispositions

Use `disposition --spec ITEM.json`: schema_version 1, finding_id, report, disposition (applied/rejected/deferred/superseded), reason, source quote, and before/after hashes when applicable. Records append to `_Edits/Book-N/decisions.jsonl` under a fail-fast lock. Last explicit disposition for the same report hash and finding ID controls. Pending blocking items prevent Done even with an old PASS. Missing legacy dispositions require inspection; timestamps cannot establish resolution. Never equate a rejection with a reusable preference.

## Pipeline journal

Use `pipeline --run Chapter-NNN --action record --spec STEP.json` with schema_version 1, id, status (running/complete), inputs (the prepare evidence array), and outputs (current evidence array for completed work). Call prepare separately on output paths to obtain output evidence. `pipeline --run Chapter-NNN --action list` returns reusable only for completed steps whose inputs and outputs still match. Never resume a running step blindly; inspect actual files, reconcile partial harvest/edits, and then record new evidence. A later step that consumes mutable ledgers can invalidate earlier completed steps; reconcile against intended outcomes instead of re-applying edits automatically.

## Other records

Editorial memory, knowledge, reading, and campaigns use the templates shipped with their owning skills. `memory --action list --scope SCOPE` returns series plus exact scope; collect applicable ancestors explicitly. Only active records apply. Knowledge positions are integer arrays; as-of uses story order for characters and reading order for reader. Truth status is not derived from epistemic state. Source hashes and exact quotes are mandatory for knowledge.

`draft-packet --chapter N [--window 3] [--output _Edits/Book-N/packets/Chapter-NNN_DraftPacket.json]` compiles a deterministic pre-draft packet for Chapter N: scene plan metadata, extracted psychological interiority (`what_they_wont_say` and `show_dont_tell_gaps` from `Chapter_NN_Psych.md`), POV-matched voice prompts (`voice_prompt_<POV>.md` with `voice_prompt.md` fallback), chapter-sliced `relationship_checkpoints` (`chapter_start <= N <= chapter_end`), the immediate continuity tail from Chapter N-1, confirmed `knowledge_as_of` state at `[N, 0]`, applicable active `editorial_decisions`, and a rolling N-chapter `cooling_list` (somatic hotspots, repeated content 3-grams, repeated similes, and recent openers/closers with callouts and fenced blocks stripped).

Reading packets contain current text, reader brief, and prior sealed reaction only. Sealing requires coordinator-verified isolated input evidence. Prior checkpoints are immutable. If earlier text changes, fork a run; do not amend history. Preparation is not proof of actual model isolation.

Campaign tasks use explicit files, dependency IDs, and current check metadata. Source snapshots are recovery aids, not an automatic rollback authorization. Restore only unchanged campaign output and reverse dependency order. A task can be complete while its checks subsequently become stale; status must show that distinction.

## Storage and migration

Every object has schema_version 1. Unsupported future schemas fail; do not coerce. Writes use same-directory temporary files, fsync, atomic replacement, and exclusive lockfiles for mutations. A stale lock requires inspecting the owner PID and files before manual removal; no timeout steals another writer's lock. Record templates are examples requiring actual source evidence, not valid production findings.

Legacy reports stay UNKNOWN until re-reviewed. Never produce current metadata retrospectively from current sources for an old report. Ledger initialization is lazy and existing content is never re-seeded. Library updates must preserve project source, book instructions, preferences, decisions, and locally changed skill files.
