---
name: chapter-pipeline
description: "Run the complete end-to-end chapter production lifecycle from scene briefing to draft generation, promise-ledger harvest, gate verification, and applied line polish in a unified automated execution. Use when the user asks to 'run chapter pipeline', 'do chapter start to finish', 'draft outline and gate chapter', or 'execute full pipeline on chapter N'."
metadata:
  author: Storycraft Skills
  version: "1.3.0"
  bundled-dependencies: book-status
  category: fiction-writing
---

# Chapter Pipeline Orchestrator

Automates the multi-skill sequence required to produce a publication-ready chapter in a single command, enforcing checkpoints and halting only on genuine blockers.

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
5. **Applied Polish & Review:**
   - On `PASS` or prose-only `WARN`, runs ONE polish route to completion:
     - `kill-chapter` — edits the draft in place, deletion-first; no further step needed, or
     - `fiction-aiism-editor` → report at `_Edits/Book-N/Chapter-NNN_AIisms.md` → `fiction-revise` to apply the approved items. The report alone is not polish; this route is not done until `fiction-revise` has run.
   - Re-runs `gate-check` after any polish edit so the final gate metadata matches the post-polish chapter bytes, and reports the final verdict.

## Resumable execution and final evidence

Use [project_state.py](../book-status/scripts/project_state.py) with the pipeline journal in [state-contract.md](../book-status/references/state-contract.md). Record running and completed step evidence. Reuse only completed steps whose inputs AND outputs match; inspect interrupted edits before retrying. Harvest promises idempotently (match existing IDs/source anchors, never re-seed) and run fiction-knowledge harvest before gating. Reconcile an interrupted harvest against current prose and ledger before continuing. Every polish change invalidates the pre-polish gate: always obtain a current final gate after changed prose, including crutch-only changes. A source hash mismatch is a need to reconcile, not permission to repeat destructive work.
