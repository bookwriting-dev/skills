---
name: kill-simile
description: Hunt explain-it similes and meta-comparison crutches ("the way", "a way", "the kind", "a kind", "as if", "like") across a chapter and reword or cut them so the reader infers instead of being told (parallel focused workers, edits in place). Use when user says "kill-simile", "kill similes", or "cut the explain-it comparisons".
metadata:
  author: Fiction Toolkit
  version: "1.2.0"
  bundled-dependencies: book-status, kill-chapter
  category: fiction-editing
---

# Kill the explain-it simile — make the reader infer, don't compare them to death

A recurring model weakness is the **comparison crutch**: prose that reaches for a simile or
a "the way / the kind of" construction to explain a feeling or image the concrete detail
already carries. The comparison tells the reader how to feel instead of letting the image do
the work. This skill finds them in the named files and rewords or cuts them in place.

The request arguments = the chapter file(s): a path, a file pattern, or several paths. Resolve it to a
concrete file list first.

## Single-source rule-set (What to fix vs. keep)

Read [simile.md](../kill-chapter/references/simile.md) before triaging or launching workers. That file is the single source of truth for FIX/KEEP criteria, examples, and triage patterns shared with `kill-chapter`; pass its contents verbatim to every focused worker so single-pass and full-chapter sweeps never drift.

## Procedure

1. **Resolve The request arguments to files.**
2. **Triage:** search for `like|as if|the way|a way|the kind|a kind` and
   skim. If spread across many files, split into up to 6 roughly equal groups and use one
   focused worker per group in parallel when the host supports workers; otherwise process the groups sequentially.
3. **Each worker gets:** its exact file list; the FIX/KEEP rules verbatim; instruction to
   read each file in 20-line chunks so it judges every hit in full context; the global style
   rules (no em dashes except to interrupt dialogue; complete grounded sentences; no
   metaphorical math/analytical language). It makes the minimal in-place edit (prefer cutting
   the comparison to rewriting the whole sentence) and reports a per-file verdict list: each
   hit tagged (KEPT-fresh / KEPT-voice / KEPT-literal / CUT / REWORDED) with before→after for
   changes.
4. **Verify when all workers return.** Worker edits make your in-context file state stale;
   reread before any follow-up edit. Report the consolidated change list and the before/after
   simile count.
5. Offer to commit or leave staged.

## Notes

- Restraint is the goal: the chapter should end up with a small number of strong, earned
  comparisons, not zero. Don't mechanically strip every "like."

## Current evidence and author decisions

For a saved report, follow [state-contract.md](../book-status/references/state-contract.md) using [project_state.py](../book-status/scripts/project_state.py): capture inputs BEFORE review, then record report metadata only if those inputs still match. Include every consumed chapter, plan, canon/style reference, relevant ledger, applicable editorial decision file (including its absence), and this skill's rules. Use stable finding IDs with exact quotes and blocking/nonblocking classification. No sidecar is required for a conversational verdict.

Consult applicable active editorial-memory decisions before proposing style repairs. Include the applicable scoped decision block verbatim in each focused worker brief; coordinator awareness alone is insufficient. Preserve deliberate choices within their stated scope; correctness checks remain binding. Do not generalize a local rejection. For in-place editing, record each applied finding's source quote and before/after hashes in the disposition ledger; review the resulting chapter with fresh evidence. A pre-edit PASS cannot establish post-edit readiness. Diagnostic-only skills still never edit source prose. Blind reader passes receive only reader-facing text; preference/canon checks happen in a separate coordinator pass.
