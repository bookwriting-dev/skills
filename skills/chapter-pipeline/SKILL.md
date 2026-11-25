---
name: chapter-pipeline
description: "Run a declared chapter production profile from scene/plan briefing through drafting, evidence reconciliation, review, and any authorized repair across fiction, non-fiction, and hybrid books. Use when the user asks to 'run chapter pipeline', 'do chapter start to finish', 'draft outline and gate chapter', or 'execute full pipeline on chapter N'."
metadata:
  author: Storycraft Skills
  version: "1.12.0"
  bundled-dependencies: book-status, nonfiction-research
  category: fiction-writing
---

# Chapter Pipeline Orchestrator

Coordinates a declared chapter workflow for **FICTION**, **NONFICTION**, or **HYBRID** projects and reports exactly which stages ran. Prefer `storycraft_*` MCP tools (`storycraft_chapter_preflight`, `storycraft_draft_packet`, `storycraft_chapter_finalize`, `storycraft_review_begin`, `storycraft_review_finish`, `storycraft_record_disposition`, `storycraft_reanchor`, `storycraft_kanban`, `storycraft_rhythm_map`, `storycraft_promises`, `storycraft_compile`) when connected; otherwise run `project_state.py --root ROOT --book Book-N ...`. Read the project type and required reviews via `workflow` before dispatching. The command honors the scaffolded project type and any per-book review override. A completed pipeline is not author approval or publication approval. Default to `draft_verified`; use a more extensive profile only when requested or explicitly configured.

## Completion profiles and operation mode

- **`draft_verified`**: current draft, applicable plan/canon checks, reconciled relevant ledgers, and every current review named by the resolved workflow policy. Do not describe this as a developmental repair, full line edit, independent read, or publication-ready chapter.
- **`full_editorial_candidate`**: complete draft read; developmental diagnosis (`fiction-dev-editor` or `nonfiction-dev-editor`); authorized developmental repairs (plan updates via `fiction-scenes`/`nonfiction-chapter-plan` or in-scope repairs via `fiction-revise`); immutable developmental checkpoint; distinct paragraph/scene-aware line or clarity pass (`fiction-full-editor` or `nonfiction-clarity-edit`); continuous reread of the resulting full chapter; immediate predecessor/current seam reread when a predecessor exists; ledger/evidence reconciliation; and current final checks. A report without an applied repair does not satisfy a repair stage. An explicit justified no-change disposition is required when a stage finds nothing to change.
- **`independent_editorial_gate`**: first provide only approved reader-facing text and spoiler-free brief to a fresh isolated reader context; preserve the actual permitted-input manifest and seal first reactions before exposing production notes. Then run the informed assessment and required full-profile stages. If the host cannot verify isolation, mark that stage `PENDING` with `ISOLATION_UNAVAILABLE`; do not simulate an independent result. Review-only mode returns proposals without claiming applied repairs.

Distinguish **review-only** from **authorized produce/revise**. A review-only request may record findings and proposed repairs but never edits prose. Existing explicit revision authorization permits in-scope repairs without repeated approval; it does not authorize canon changes or neighboring-file writes. Record profile, operation identity, subjects, revision hashes, stage role, and outputs in the pipeline journal. Historical checkpoints remain historical evidence; final checks must cover the exact final prose and ledger generation.

## Halt conditions

The pipeline halts before downstream polish when:

- **A major plan/beat gap exists** — an outline `what_must_happen` directive has no corresponding scene in `fiction-scenes`, or a non-fiction chapter section in `Wiki/Outline/Book-N/plan.md` lacks its core claim/evidence block or carries blocking unresolved `evidence_needed` gaps. Scenes or argument blocks missing from the plan entirely are major.
- **The gate returns `FAIL`**, or a `WARN` on a canon, continuity, knowledge, factual-evidence, or promise-ledger pillar. These change what the chapter *is*; line/clarity polish cannot fix them.
- **A minor (prose-only) `WARN` does not halt** — cadence, tics, and sentence clarity route to the authorized repair stage instead.

## Pipeline Steps

1. **Step 1: Scaffolding & Preflight (`FICTION` / `NONFICTION` / `HYBRID`)**
   - **Fiction (and narrative hybrid chapters):**
     - Verifies existence of `Wiki/Outline/Book-N/Chapter_NN_Scene.md` (two-digit, zero-padded) or generates it from book outline beats using `fiction-scenes` (enforcing active `relationship_checkpoints` and micro-friction per scene).
     - Verifies existence of `Wiki/Psych/Book-N/Chapter_NN_Psych.md` or generates it using `fiction-psych` so `what_they_wont_say` and `show_dont_tell_gaps` are mapped before drafting.
     - When the scene plan includes substantial conversation, runs the `fiction-dialogue` preflight so speaker objectives, unequal knowledge, and anti-interview rules are locked.
   - **Non-Fiction (and expository/argument hybrid chapters):**
     - Verifies existence of the chapter's `## Chapter NN` section in `Wiki/Outline/Book-N/plan.md` (or generates/refreshes it using `nonfiction-chapter-plan`), locking rhetorical mode, central claim, evidence blocks, transitions, and explicit `evidence_needed` items.
     - Checks source and citation readiness in `Wiki/Research/` (`sources.yaml` + `claims-matrix.md`) using `nonfiction-research` so primary sources are inspected before drafting.
   - Halts on major beat/plan/evidence gaps (see Halt conditions); minor gaps are noted and carried forward.

2. **Step 2: Pre-Draft Packet & Drafting**
   - Register a new authorized target with `project_state.py --root ROOT --book Book-N register-chapters --spec SPEC.json` using the plan's ID, reading order, and destination. The draft packet resolves the canonical path and report stem. Use the scene-specific POV entry for fiction drafting.
   - Compiles `_Edits/Book-N/packets/Chapter-NNN_DraftPacket.json` via `project_state.py --root ROOT --book Book-N draft-packet --chapter N` (bundling POV-specific voice prompts or style authority, active relationship checkpoints, psych subtext constraints, confirmed knowledge state, active scoped `editorial-memory` decisions, and the rolling 3-chapter cooling list).
   - **Fiction:** invokes `fiction-writechapter` with the compiled draft packet, scene brief, voice prompt(s) (`fiction-voiceprompt`), and preceding chapter context.
   - **Non-Fiction:** invokes `nonfiction-writechapter` with the compiled draft packet, `Wiki/Outline/Book-N/plan.md` chapter section, `Wiki/Research/` source excerpts, and preceding chapter transition context.
   - **Hybrid:** invokes the skill matching the chapter's mode (or drafts narrative vs. expository sections under their respective authority files).
   - Outputs draft to `Chapters/Book-N/Chapter-NNN.md`.

3. **Step 3: Promise, Knowledge & Evidence Harvest**
   - **Fiction:** runs `fiction-promises` on the drafted chapter so every setup and payoff is recorded in `Wiki/Story/Book-N/promises.yaml` *before* the gate runs, and runs `fiction-knowledge` harvest (`knowledge-state --action record`) to record character belief/knowledge acquisitions and reader exposures in `Wiki/Story/knowledge-events.json`.
   - **Non-Fiction & Hybrid:** run `project_state.py --root ROOT --book Book-N workflow` for the resolved required checks (`HYBRID` resolves per chapter via `chapter.mode: narrative | expository | blended` rather than applying both sets blindly). Runs `promise-tracker` on the drafted chapter to register promised explanations, counterarguments, and thesis payoffs in `Wiki/Story/Book-N/promises.yaml`, and builds/validates the chapter assertion evidence record `_Edits/Book-N/evidence/Chapter-NNN.json` using `nonfiction-research` and [evidence.py](../nonfiction-research/scripts/evidence.py) (`--root ROOT --record _Edits/Book-N/evidence/Chapter-NNN.json`, plus `--reanchor` after edits). Hybrid narrative chapters also run `fiction-knowledge` harvest.
- **Batch CLI wrappers:** Prefer single-shot `project_state.py chapter-preflight` (Step 2) and `project_state.py chapter-finalize` (Step 3/4) plus `--events` / `--dispositions` batch flags and `project_state.py reanchor --chapter N` after polish edits rather than dozens of individual CLI invocations.

4. **Step 4: Readiness Gate Check & Act Checkpoint**
   - Run the reviews specified by `workflow`. Use the manifest-resolved report stem under `_Edits/Book-N/` and capture the policy inputs with the report.
   - `Gate` invokes `gate-check` for canon, promise, knowledge, and prose checks. Run chapter-format and the [book continuity review](../book-status/references/continuity-review.md), including [evidence that a scene depends on](../book-status/references/evidence-chain.md). Record continuity claims before `review-begin` so self-invalidation never occurs.
   - `FactCheck` invokes `nonfiction-factcheck` against the inspected sources and `evidence.py`. When both checks are required, run it before `ClarityEdit`, which invokes `nonfiction-clarity-edit`.
   - Use the project's documented producer for a custom check. Mark it pending if the producer or current evidence is missing.
   - Refresh evidence from the exact final chapter after any authorized changes. Halts on `FAIL` or on canon/continuity/knowledge/factual/ledger `WARN`, reporting blockers with actionable fixes.
   - After every **4 chapters** or at an **Act boundary**, trigger a lightweight **4-Chapter / Act Developmental Checkpoint** (`fiction-dev-editor` + `rhythm-map` + `drift-check` + `cast --gap 4 --through SELECTOR`) and refresh the board with `project_state.py --root ROOT --book Book-N kanban` before moving into the next block.

5. **Step 5: Profile-specific editorial work**
   - For `draft_verified`, stop after reconciliation and the current gate(s). Do not silently add an edit pass or describe the result as fully line-edited.
   - For `full_editorial_candidate`:
     - Run `fiction-dev-editor` (fiction/hybrid) or `nonfiction-dev-editor` (non-fiction) over the complete chapter. In review-only mode, return proposed findings and stop without edits or an achieved-candidate claim. With existing revision authorization, apply only in-scope repairs using `fiction-revise` (or flag structural re-plans back to `fiction-scenes`/`nonfiction-chapter-plan`), recording an explicit supported no-change disposition if none are warranted. Save an immutable developmental checkpoint and its source/report hashes before sentence editing.
     - Run `fiction-full-editor` (fiction) or `nonfiction-clarity-edit` (non-fiction) as a distinct paragraph/scene- or section-aware pass against the checkpoint revision. Merge anchored findings centrally; apply only authorized target edits via `fiction-revise`, preserving conflicts and out-of-scope findings. A report without applied repairs or a justified no-change disposition does not complete this stage.
     - Read the entire resulting chapter continuously with fresh evidence; if an immediate predecessor exists, reread the ending/transition of that chapter and the current chapter's opening as one seam. Reconcile affected promise, knowledge, relationship, and factual-evidence state through committed ledger generations. Then run all required current final checks (`gate-check`, `continuity`, and/or `nonfiction-factcheck` + `nonfiction-clarity-edit`) against the exact resulting chapter and generation. Any subsequent change invalidates affected checks.
   - For `independent_editorial_gate`, perform `sequential-read` first in a verified fresh context with only reader-facing text and a spoiler-free brief. Seal reactions and the actual permitted-input manifest before exposing production notes. If isolation cannot be demonstrated, record `PENDING / ISOLATION_UNAVAILABLE`; do not claim this stage ran. Then execute the informed stages required by the selected operation. Original reactions remain attached to the original revision.
   - Never substitute `kill-chapter` or a focused AIism/clarity pass for the declared developmental plus paragraph-level stages of the full profile. A clean report is not an applied edit, and a completed pipeline is not author or publication approval.

## Resumable execution and final evidence

Use [project_state.py](../book-status/scripts/project_state.py) (`step-start` / `step-complete`, or `pipeline --action record --spec` for custom envelopes) with schema-versioned pipeline journal records in [state-contract.md](../book-status/references/state-contract.md). Record running and completed step evidence, including before/after lineage for in-place transformations and immutable checkpoint outputs. Reuse only completed stages whose historical outputs and untouched dependencies still match; a later authorized transformation does not erase a valid checkpoint. Inspect interrupted edits before retrying. Harvest promises idempotently (match existing IDs/source anchors, never re-seed) and run `fiction-knowledge` / `nonfiction-research` evidence harvest before gating. Reconcile an interrupted harvest against current prose and ledger before continuing. Every prose change invalidates affected final checks: obtain current final evidence after changed prose, including crutch-only changes. A source hash mismatch is a need to reconcile, not permission to repeat destructive work.
