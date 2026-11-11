---
name: kill-flat
description: Hunt the word "flat" across a chapter and cut the figurative mood-adjective uses while keeping the literal flatness ones (deletion-first, parallel focused workers, edits in place). Maintained as a dedicated pass; also covered by the generalized kill-crutch pass (kill-crutch flat). Use when user says "kill-flat", "kill flat", or "strip the flat crutch".
metadata:
  author: Fiction Toolkit
  version: "1.2.0"
  bundled-dependencies: book-status, kill-chapter
  category: fiction-editing
---

# Kill "flat" — cut the writerly adjective, keep the literal ones

"flat" is correct and load-bearing for **physical flatness** you could see or touch: a
calm sea, a flat surface, a body laid flat, a flat-bottomed hull, pinned-back animal ears.
It goes wrong when stretched over a **voice, manner, gaze, emotion, or abstract noun** as a
mood adjective ("a flat voice," "flat certainty," "flat dead quiet").

The request arguments = the chapter file(s): a path, a file pattern, or several paths. Resolve it to a
concrete file list first (skip files that don't contain "flat").

## Single-source rule-set (What to keep vs. fix)

Read [flat.md](../kill-chapter/references/flat.md) before triaging or launching workers. That file is the single source of truth for literal KEEP categories, figurative FIX categories, deletion-first rules, and verification patterns shared with `kill-chapter`; pass its contents verbatim to every focused worker so single-pass and full-chapter sweeps never drift.

## Procedure

1. **Resolve the request arguments to files;** use the host's available text search to keep only files containing "flat".
2. **Triage:** search for whole-word "flat" matches and skim. If rare, fix inline. If spread
   across many files, split into up to 6 roughly equal groups and use one focused worker
   per group in parallel when the host supports workers; otherwise process the groups sequentially.
3. **Each worker gets:** its exact file list; the KEEP/FIX and deletion-first rules
   verbatim; instruction to read a FULL sentence of context around every hit; the global
   style rules (no em dashes except to interrupt dialogue; complete grounded sentences; no
   metaphorical math/analytical language). It makes the minimal in-place edit, touching ONLY
   the token "flat" and nothing else on the line, and reports a per-file verdict list: each
   hit tagged (KEPT-literal / KEPT-idiom / KEPT-noun-the-flat / REMOVED / REWORDED) with
   before→after for changes.
4. **Verify when all workers return:** search again for
   `"flat (voice|certainty|truth|resolve|patience|interest|quiet|way)"` → should be empty.
   Worker edits make your in-context file state stale; reread before any follow-up edit.
   Report the consolidated change list and before/after count from the host's available text search.
5. Offer to commit or leave staged.

## Current evidence and author decisions

For a saved report, follow [state-contract.md](../book-status/references/state-contract.md) using [project_state.py](../book-status/scripts/project_state.py): capture inputs BEFORE review, then record report metadata only if those inputs still match. Include every consumed chapter, plan, canon/style reference, relevant ledger, applicable editorial decision file (including its absence), and this skill's rules. Use stable finding IDs with exact quotes and blocking/nonblocking classification. No sidecar is required for a conversational verdict.

Consult applicable active editorial-memory decisions before proposing style repairs. Include the applicable scoped decision block verbatim in each focused worker brief; coordinator awareness alone is insufficient. Preserve deliberate choices within their stated scope; correctness checks remain binding. Do not generalize a local rejection. For in-place editing, record each applied finding's source quote and before/after hashes in the disposition ledger; review the resulting chapter with fresh evidence. A pre-edit PASS cannot establish post-edit readiness. Diagnostic-only skills still never edit source prose. Blind reader passes receive only reader-facing text; preference/canon checks happen in a separate coordinator pass.
