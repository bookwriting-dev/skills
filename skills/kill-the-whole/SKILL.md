---
name: kill-the-whole
description: Hunt the intensifier phrase "the whole of [me/him/it/attention]" across a chapter and cut the hollow padding while keeping literal quantitative uses and in-voice dialogue idioms (deletion-first, parallel focused workers, edits in place). "the whole of X" is a frequently overused filler intensifier, especially during high-arousal/high-stress beats. Use when user says "kill-the-whole", "kill the whole", or "strip the whole-of crutch".
metadata:
  author: Fiction Toolkit
  version: "1.2.0"
  bundled-dependencies: book-status, kill-chapter
  category: fiction-editing
---

# Kill "the whole of X" — strip the hollow intensifier, keep the real ones

"the whole" is correct when it names the actual entirety of a concrete, countable, or
nameable thing (a crew, a room, a night, a plan) and is filler almost everywhere it's
stretched over a pronoun or a rising sensation to inflate a beat without adding a concrete
image.

The request arguments = the chapter file(s): a path, a file pattern, or several paths. Resolve it to a
concrete file list before doing anything (skip files that don't contain "the whole").

## Single-source rule-set (What to keep vs. fix)

Read [the-whole.md](../kill-chapter/references/the-whole.md) before triaging or launching workers. That file is the single source of truth for deletion-first rules, KEEP/FIX criteria, examples, and triage patterns shared with `kill-chapter`; pass its contents verbatim to every focused worker so single-pass and full-chapter sweeps never drift.

## Procedure

1. **Resolve the request arguments to files.** Then use the host's available text search to keep only files that
   contain the phrase.
2. **Triage:** search for "the whole" and skim. If rare, fix inline. If spread
   across many files, split into up to 6 roughly equal groups and use one focused worker
   per group in parallel when the host supports workers; otherwise process the groups sequentially.
3. **Each worker gets:** its exact file list; the KEEP/FIX and deletion-first rules
   verbatim; instruction to read each file in 20-line chunks so it sees every hit in full
   context; the global style rules (no em dashes except to interrupt dialogue; complete
   grounded sentences; no metaphorical math/analytical language). It makes the minimal
   in-place edit, touching only the target phrase, and reports a per-file verdict list: each
   hit tagged (KEPT-literal / KEPT-voice / DELETED / REWRITTEN) with before→after for
   changes.
4. **Verify when all workers return:** search again for `"the whole of (me|him|her|it|my|his|her)"` →
   should be near-empty (some clean literal survivors are fine). Worker edits make your
   in-context file state stale; reread before any follow-up edit. Report the consolidated
   change list and before/after count from the host's available text search.
5. Offer to commit or leave staged.

## Current evidence and author decisions

For a saved report, follow [state-contract.md](../book-status/references/state-contract.md) using [project_state.py](../book-status/scripts/project_state.py): capture inputs BEFORE review, then record report metadata only if those inputs still match. Include every consumed chapter, plan, canon/style reference, relevant ledger, applicable editorial decision file (including its absence), and this skill's rules. Use stable finding IDs with exact quotes and blocking/nonblocking classification. No sidecar is required for a conversational verdict.

Consult applicable active editorial-memory decisions before proposing style repairs. Include the applicable scoped decision block verbatim in each focused worker brief; coordinator awareness alone is insufficient. Preserve deliberate choices within their stated scope; correctness checks remain binding. Do not generalize a local rejection. For in-place editing, record each applied finding's source quote and before/after hashes in the disposition ledger; review the resulting chapter with fresh evidence. A pre-edit PASS cannot establish post-edit readiness. Diagnostic-only skills still never edit source prose. Blind reader passes receive only reader-facing text; preference/canon checks happen in a separate coordinator pass.
