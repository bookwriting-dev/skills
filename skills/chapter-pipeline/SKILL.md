---
name: chapter-pipeline
description: "Run the complete end-to-end chapter production lifecycle from scene briefing to draft generation, promise-ledger harvest, gate verification, and applied line polish in a unified automated execution. Use when the user asks to 'run chapter pipeline', 'do chapter start to finish', 'draft outline and gate chapter', or 'execute full pipeline on chapter N'."
metadata:
  author: Storycraft Skills
  version: "1.1.0"
  category: fiction-writing
---

# Chapter Pipeline Orchestrator

Automates the multi-skill sequence required to produce a publication-ready chapter in a single command, enforcing checkpoints and halting only on genuine blockers.

## Halt conditions

The pipeline halts before the polish step when:

- **A major beat gap exists** — an outline `what_must_happen` directive for this chapter has no corresponding scene in the plan, as reported by `fiction-scenes`. Scenes missing from the plan entirely are also major.
- **The gate returns `FAIL`**, or a `WARN` on a canon, continuity, or promise-ledger pillar. These change what the chapter *is*; polish cannot fix them.
- **A minor (prose-only) `WARN` does not halt** — cadence, tics, and repetition route to the polish step instead.

## Pipeline Steps

1. **Scene Scaffolding & Verification:**
   - Verifies existence of `Wiki/Outline/Book-N/Chapter_NN_Scene.md` (two-digit, zero-padded) or generates it from book outline beats using `fiction-scenes`.
   - Halts on major beat gaps (see above); minor gaps are noted and carried forward.
2. **Drafting:**
   - Invokes `fiction-writechapter` with scene brief, voice prompt (`fiction-voiceprompt`), and preceding chapter context.
   - Outputs draft to `Chapters/Book-N/Chapter-NNN.md`.
3. **Promise-Ledger Harvest:**
   - Runs `fiction-promises` on the drafted chapter so every setup it introduces and every payoff it lands is recorded in `Wiki/Story/Book-N/promises.yaml` *before* the gate runs — the gate requires it.
4. **Readiness Gate Check:**
   - Runs `gate-check` against canon, Chekhov ledger, and prose linting.
   - Outputs `_Edits/Book-N/Chapter-NNN_Gate.md`.
   - Halts on `FAIL` or on canon/continuity/ledger `WARN`, reporting blockers with actionable fixes.
5. **Applied Polish & Review:**
   - On `PASS` or prose-only `WARN`, runs ONE polish route to completion:
     - `kill-chapter` — edits the draft in place, deletion-first; no further step needed, or
     - `fiction-aiism-editor` → report at `_Edits/Book-N/Chapter-NNN_AIisms.md` → `fiction-revise` to apply the approved items. The report alone is not polish; this route is not done until `fiction-revise` has run.
   - Re-runs `gate-check` if polish changed more than crutch tokens, and reports the final verdict.
