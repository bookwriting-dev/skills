---
name: chapter-pipeline
description: "Run a declared chapter production profile from scene briefing through drafting, evidence reconciliation, review, and any authorized repair. Use when the user asks to 'run chapter pipeline', 'do chapter start to finish', 'draft outline and gate chapter', or 'execute full pipeline on chapter N'."
metadata:
  author: Storycraft Skills
  version: "1.5.0"
  bundled-dependencies: book-status
  category: fiction-writing
---

# Chapter Pipeline Orchestrator

Coordinates a declared chapter workflow and reports exactly which stages ran. A completed pipeline is not author approval or publication approval. Default to `draft_verified`; use a more extensive profile only when requested or explicitly configured.

## Completion profiles and operation mode

- **`draft_verified`**: current draft, applicable plan/canon checks, reconciled relevant ledgers, and a current gate. Do not describe this as a developmental repair, full line edit, independent read, or publication-ready chapter.
- **`full_editorial_candidate`**: complete draft read; developmental diagnosis; authorized developmental repairs; immutable developmental checkpoint; distinct paragraph/scene-aware line edit; continuous reread of the resulting full chapter; immediate predecessor/current seam reread when a predecessor exists; ledger reconciliation; and current final checks. A report without an applied repair does not satisfy a repair stage. An explicit justified no-change disposition is required when a stage finds nothing to change.
- **`independent_editorial_gate`**: first provide only approved reader-facing text and spoiler-free brief to a fresh isolated reader context; preserve the actual permitted-input manifest and seal first reactions before exposing production notes. Then run the informed assessment and required full-profile stages. If the host cannot verify isolation, mark that stage `PENDING` with `ISOLATION_UNAVAILABLE`; do not simulate an independent result. Review-only mode returns proposals without claiming applied repairs.

Distinguish **review-only** from **authorized produce/revise**. A review-only request may record findings and proposed repairs but never edits prose. Existing explicit revision authorization permits in-scope repairs without repeated approval; it does not authorize canon changes or neighboring-file writes. Record profile, operation identity, subjects, revision hashes, stage role, and outputs in the pipeline journal. Historical checkpoints remain historical evidence; final checks must cover the exact final prose and ledger generation.

## Halt conditions

The pipeline halts before the polish step when:

- **A major beat gap exists** — an outline `what_must_happen` directive for this chapter has no corresponding scene in the plan, as reported by `fiction-scenes`. Scenes missing from the plan entirely are also major.
- **The gate returns `FAIL`**, or a `WARN` on a canon, continuity, knowledge, or promise-ledger pillar. These change what the chapter *is*; polish cannot fix them.
- **A minor (prose-only) `WARN` does not halt** — cadence, tics, and repetition route to the polish step instead.

## Pipeline Steps

1. **Scene, Psych & Dialogue Scaffolding:**
   - Verifies existence of `Wiki/Outline/Book-N/Chapter_NN_Scene.md` (two-digit, zero-padded) or generates it from book outline beats using `fiction-scenes` (enforcing active `relationship_checkpoints` and micro-friction per scene).
   - Verifies existence of `Wiki/Psych/Book-N/Chapter_NN_Psych.md` or generates it using `fiction-psych` so `what_they_wont_say` and `show_dont_tell_gaps` are mapped before drafting.
   - When the scene plan includes substantial conversation, runs the `fiction-dialogue` preflight so speaker objectives, unequal knowledge, and anti-interview rules are locked.
   - Halts on major beat gaps (see above); minor gaps are noted and carried forward.
2. **Pre-Draft Packet & Drafting:**
   - Compiles `_Edits/Book-N/packets/Chapter-NNN_DraftPacket.json` via `project_state.py --root ROOT --book Book-N draft-packet --chapter N` (bundling POV-specific voice prompts, active relationship checkpoints, psych subtext constraints, confirmed knowledge state, and the rolling 3-chapter cooling list).
   - Invokes `fiction-writechapter` with the compiled draft packet, scene brief, voice prompt(s) (`fiction-voiceprompt`), and preceding chapter context.
   - Outputs draft to `Chapters/Book-N/Chapter-NNN.md`.
3. **Promise & Knowledge Harvest:**
   - Runs `fiction-promises` on the drafted chapter so every setup it introduces and every payoff it lands is recorded in `Wiki/Story/Book-N/promises.yaml` *before* the gate runs — the gate requires it.
   - Runs `fiction-knowledge` harvest so character belief/knowledge acquisitions and reader exposures in the drafted chapter are recorded in `Wiki/Story/Book-N/knowledge.json`.
4. **Readiness Gate Check:**
   - Runs `gate-check` against canon, Chekhov ledger, knowledge continuity, subtext/dialogue architecture, cooling list, and prose linting.
   - Outputs `_Edits/Book-N/Chapter-NNN_Gate.md`.
   - Halts on `FAIL` or on canon/continuity/knowledge/ledger `WARN`, reporting blockers with actionable fixes.
5. **Profile-specific editorial work:**
   - For `draft_verified`, stop after reconciliation and the current gate. Do not silently add an edit pass or describe the result as fully line-edited.
   - For `full_editorial_candidate`, run `fiction-dev-editor` over the complete chapter. In review-only mode, return proposed findings and stop without edits or an achieved-candidate claim. With existing revision authorization, apply only in-scope developmental repairs using `fiction-revise`; record an explicit supported no-change disposition if none are warranted. Save an immutable developmental checkpoint and its source/report hashes before line editing.
   - Run `fiction-full-editor` as a distinct paragraph/scene-aware line pass against the checkpoint revision. Merge anchored findings centrally; apply only authorized target edits, preserving conflicts and out-of-scope findings. A report without applied repairs or a justified no-change disposition does not complete this stage.
   - Read the entire resulting chapter continuously with fresh evidence; if an immediate predecessor exists, reread the ending/transition of that chapter and the current chapter's opening as one seam. Reconcile affected promise, knowledge, and relationship state through committed ledger generations. Then run all required current final checks against the exact resulting chapter and generation. Any subsequent change invalidates affected checks.
   - For `independent_editorial_gate`, perform `sequential-read` first in a verified fresh context with only reader-facing text and a spoiler-free brief. Seal reactions and the actual permitted-input manifest before exposing production notes. If isolation cannot be demonstrated, record `PENDING / ISOLATION_UNAVAILABLE`; do not claim this stage ran. Then execute the informed stages required by the selected operation. Original reactions remain attached to the original revision.
   - Never substitute `kill-chapter` or a focused AIism pass for the declared developmental plus paragraph-level stages of the full profile. A clean report is not an applied edit, and a completed pipeline is not author or publication approval.

## Resumable execution and final evidence

Use [project_state.py](../book-status/scripts/project_state.py) with schema-versioned pipeline journal records in [state-contract.md](../book-status/references/state-contract.md). Record running and completed step evidence, including before/after lineage for in-place transformations and immutable checkpoint outputs. Reuse only completed stages whose historical outputs and untouched dependencies still match; a later authorized transformation does not erase a valid checkpoint. Inspect interrupted edits before retrying. Harvest promises idempotently (match existing IDs/source anchors, never re-seed) and run fiction-knowledge harvest before gating. Reconcile an interrupted harvest against current prose and ledger before continuing. Every prose change invalidates affected final checks: obtain current final evidence after changed prose, including crutch-only changes. A source hash mismatch is a need to reconcile, not permission to repeat destructive work.
