---
name: kill-opinion-personification
description: Hunt the "opinion" personification tic (pain, wounds, and inanimate objects "having opinions" or "saying their piece") across a chapter range and cut or vary the repeats while keeping one or two founding uses (deletion-first, parallel focused workers, edits in place). Use when user says "kill-opinion-personification", "kill the opinion tic", "kill 'had opinions'", or flags repeated "X had an opinion about Y" / "sent up its opinion" phrasing.
metadata:
  author: Fiction Toolkit
  version: "1.2.0"
  bundled-dependencies: book-status, kill-chapter
  category: fiction-editing
---

# Kill the "opinion" personification tic — keep the first, vary or cut the rest

The tic: pain, wounds, body parts, and inanimate objects (pilings, walls, ribs) are given
"opinions" as a stand-in for sensory/physical description — a cute deflection move that
substitutes a labeled abstraction ("it had an opinion about X") for the actual physical
detail. This is a voice choice in small doses that becomes a predictable crutch when repeated.

The request arguments = the chapter file(s) or range: a path, a file pattern, or several paths.

## Single-source rule-set (Pattern & What to keep vs. fix)

Read [opinion-personification.md](../kill-chapter/references/opinion-personification.md) before triaging or launching workers. That file is the single source of truth for the detection pattern, founding-use KEEP budget, physical-detail FIX rules, and examples shared with `kill-chapter`; pass its contents verbatim to every focused worker so single-pass and full-chapter sweeps never drift.

## Procedure

1. **Resolve the request arguments to files**, in chapter order. Search each for the pattern above;
   confirm each hit by eye (subject must be non-sentient/a body part/pain, not an actual
   character's opinion).
2. **Establish the chronological order of hits** across the range first — this determines
   which one or two survive.
3. **Triage:** if the total confirmed hit count is small, fix inline. If spread across
   multiple files, use one focused worker per file (or small file group)
   in parallel when the host supports workers; otherwise process them sequentially. Pass each worker the full ordered hit list
   across the whole range so it knows which instances are pre-designated KEEP vs FIX —
   don't let per-file workers independently decide what's "the founding use."
4. **Each worker gets:** its exact file(s); the full ordered hit list with KEEP/FIX
   assignments already decided; the direction rules above; the global style rules (no em
   dashes except to interrupt dialogue; complete grounded sentences; no metaphorical
   math/analytical language; POV-appropriate voice). It makes the minimal in-place edit per
   FIX hit, leaves KEEP hits untouched, and reports a per-file verdict list (KEPT-founding
   / KEPT-echo / REWRITTEN) with before→after for changes.
5. **Verify when all workers return:** search again for the pattern across the full range — should
   show at most two surviving "opinion"-personification hits total, correctly the ones
   pre-designated KEEP. Worker edits make your in-context file state stale; reread
   before any follow-up edit. Report the consolidated before/after list.
6. Offer to commit or leave staged.

## Current evidence and author decisions

For a saved report, follow [state-contract.md](../book-status/references/state-contract.md) using [project_state.py](../book-status/scripts/project_state.py): capture inputs BEFORE review, then record report metadata only if those inputs still match. Include every consumed chapter, plan, canon/style reference, relevant ledger, applicable editorial decision file (including its absence), and this skill's rules. Use stable finding IDs with exact quotes and blocking/nonblocking classification. No sidecar is required for a conversational verdict.

Consult applicable active editorial-memory decisions before proposing style repairs. Include the applicable scoped decision block verbatim in each focused worker brief; coordinator awareness alone is insufficient. Preserve deliberate choices within their stated scope; correctness checks remain binding. Do not generalize a local rejection. For in-place editing, record each applied finding's source quote and before/after hashes in the disposition ledger; review the resulting chapter with fresh evidence. A pre-edit PASS cannot establish post-edit readiness. Diagnostic-only skills still never edit source prose. Blind reader passes receive only reader-facing text; preference/canon checks happen in a separate coordinator pass.
