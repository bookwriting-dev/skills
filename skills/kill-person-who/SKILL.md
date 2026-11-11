---
name: kill-person-who
description: Hunt the construction "the [exact/elaborate/specific/particular/steady] [noun] of a [person] who [clause]" across a chapter and rewrite it into concrete action/dialogue/detail instead of a labeled abstraction (deletion-first rewrite, parallel focused workers, edits in place). This is a default go-to move for character interiority/subtext that reads as a mechanical tic on a binge read. Use when user says "kill-person-who", "kill the person-who construction", "kill the 'of a man/woman who' tic", or flags repeated "the [quality] of a [person] who [does X]" phrasing.
metadata:
  author: Fiction Toolkit
  version: "1.2.0"
  bundled-dependencies: book-status, kill-chapter
  category: fiction-editing
---

# Kill "the [quality] of a [person] who [clause]" — stop labeling subtext, show it

The tic: instead of dramatizing a character's attitude through action, dialogue, or a
concrete physical detail, the prose names an abstract quality, attaches it to a generic
type-cast of the person ("a man who," "a woman who," "men who"), and closes with a
defining relative clause that does the interpretive work for the reader.

The request arguments = the chapter file(s): a path, a file pattern, or several paths. Resolve it to a
concrete file list before doing anything.

## Single-source rule-set (Pattern & What to keep vs. fix)

Read [person-who.md](../kill-chapter/references/person-who.md) before triaging or launching workers. That file is the single source of truth for the detection template, qualifiers/nouns, FIX/KEEP criteria, and examples shared with `kill-chapter`; pass its contents verbatim to every focused worker so single-pass and full-chapter sweeps never drift. Vary the concrete replacement per instance (gesture, dialogue, or outright deletion) so multiple fixes in one chapter do not create a new tic.

## Procedure

1. **Resolve the request arguments to files.** Search each with the pattern above; keep only files
   with hits.
2. **Triage:** if hits are sparse (1-3 total), fix inline. If spread across multiple
   files/scenes, split into up to 6 roughly equal groups and use one focused
   worker per group in parallel when the host supports workers; otherwise process the groups sequentially.
3. **Each worker gets:** its exact file list; the pattern description, KEEP/FIX rules,
   and confirmed examples verbatim; instruction to read each file in full scene-length
   chunks (not narrow windows — needs surrounding context to invent a concrete beat); the
   global style rules (no em dashes except to interrupt dialogue; complete grounded
   sentences; no metaphorical math/analytical language; POV-appropriate voice). It makes
   the minimal in-place edit per hit and reports a per-file verdict list: each hit tagged
   (KEPT-isolated / REWRITTEN) with before→after.
4. **Verify when all workers return:** search again for the pattern across the same files — should
   be at most one surviving isolated instance per file. Worker edits make your in-context
   file state stale; reread before any follow-up edit. Report the consolidated
   before/after list and total hit count.
5. Offer to commit or leave staged.

## Current evidence and author decisions

For a saved report, follow [state-contract.md](../book-status/references/state-contract.md) using [project_state.py](../book-status/scripts/project_state.py): capture inputs BEFORE review, then record report metadata only if those inputs still match. Include every consumed chapter, plan, canon/style reference, relevant ledger, applicable editorial decision file (including its absence), and this skill's rules. Use stable finding IDs with exact quotes and blocking/nonblocking classification. No sidecar is required for a conversational verdict.

Consult applicable active editorial-memory decisions before proposing style repairs. Include the applicable scoped decision block verbatim in each focused worker brief; coordinator awareness alone is insufficient. Preserve deliberate choices within their stated scope; correctness checks remain binding. Do not generalize a local rejection. For in-place editing, record each applied finding's source quote and before/after hashes in the disposition ledger; review the resulting chapter with fresh evidence. A pre-edit PASS cannot establish post-edit readiness. Diagnostic-only skills still never edit source prose. Blind reader passes receive only reader-facing text; preference/canon checks happen in a separate coordinator pass.
