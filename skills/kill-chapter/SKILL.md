---
name: kill-chapter
description: One-pass cleanup orchestrator running seven deletion-first kill passes consecutively in place (similes, person-who, opinion personification, "the whole of X", filler words, "soft", "flat") with parallel workers. Book-agnostic. Use when user says "kill-chapter", "clean this chapter", "run the kill passes", or "strip the crutches".
metadata:
  author: Fiction Toolkit
  version: "2.3.2"
  bundled-dependencies: book-status
  category: fiction-editing
---

# Kill-chapter — run every crutch pass over a chapter, one at a time

Language models can insert the same prose crutches into every book regardless of setting:
explain-it similes, the person-who subtext shortcut, opinion personification, hollow "the
whole of X" intensifiers, hedging filler words, and the mood-adjectives "soft" and "flat".
This skill runs each kill pass **consecutively** over the same file(s), then reports a combined
change list.

The request arguments identify the chapter file(s): a path, a file pattern, or several paths (e.g.
`Chapters/Chapter_15_*.md`). Resolve it to a concrete file list once, up front.

## Why consecutive, not parallel

Each pass already fans out its own parallel workers that **edit files in place**. Running
two passes at once would put two agents on the same file simultaneously and they would
clobber each other's edits. So the passes run strictly one after another: pass N fully
completes and verifies before pass N+1 begins.

## The passes, in order

Run these in sequence. Each has its single-source rule-set in `references/` (shared with the seven standalone `kill-*` skills); read it and hand it to that pass's workers verbatim:

1. **simile** — `references/simile.md` (structural rewrites first, while the prose is untouched)
2. **person-who** — `references/person-who.md` (labeling subtext via "the [quality] of a [person] who [clause]")
3. **opinion-personification** — `references/opinion-personification.md` (non-sentient things "having opinions")
4. **the-whole** — `references/the-whole.md` (hollow intensifier "the whole of [me/him/attention]")
5. **crutch** — `references/crutch.md` (sweep the common filler set: `just`, `little`, `really`, `quite`, `almost`, `slightly`, `a bit`, `seemed`, `somehow`, `simply`)
6. **soft** — `references/soft.md`
7. **flat** — `references/flat.md`

Resolve the book’s simile limits, fragment and dash rules with `project_state.py --root ROOT --book Book-N style-policy`. Count chapter-wide patterns once before dispatch. Pass the resolved policy and scoped author decisions to each worker. Use chapter-level limits as prompts to inspect individual passages.

## Per-pass procedure (identical each time)

1. From the resolved file list, use the host's available text search to identify files containing the pass's target token(s); skip files that
   don't contain it.
2. Triage: search for the token across those files and skim. If rare, fix inline. If spread across
   many files, split the file list into up to 6 roughly equal groups and use one focused
   worker per group in parallel when the host supports workers; otherwise process the groups sequentially.
3. Each worker gets: its exact file list; the pass's rule-set verbatim; the deletion-first
   rule; instruction to read each file in full context (20-line chunks, or a full sentence
   per hit) before judging, and the current book’s style rules and approved KEEP examples. It makes
   the minimal in-place edit, touching ONLY the target token and nothing else on the line,
   and returns a per-file verdict list (each hit tagged KEEP-reason / DELETED / REWORDED,
   with before→after for changes).
4. When all workers for this pass return, run the pass's verification search. Worker edits make
   any in-context file state stale: reread before any follow-up edit. Record the change
   count, then move to the next pass.

## After all seven passes

- Print a consolidated summary: per-pass change counts and the notable before→after edits.
- Sanity-check that the passes only touched their target tokens/constructions (a worker that "helpfully"
  fixed an adjacent word it wasn't asked to is out of scope — revert those).
- Offer to commit or leave staged. Do not commit unless asked.

## Notes

- The seven `references/*.md` are the single source of each pass's keep/fix rules; edit those
  to tune behavior, not this file.
- Book-agnostic by design: no character names, settings, or per-book canon. If a specific
  book needs extra KEEP exceptions, note them at invocation and pass them to the workers.

## Current evidence and author decisions

For a saved report, follow [state-contract.md](../book-status/references/state-contract.md) using [project_state.py](../book-status/scripts/project_state.py): capture inputs BEFORE review, then record report metadata only if those inputs still match. Include every consumed chapter, plan, canon/style reference, relevant ledger, applicable editorial decision file (including its absence), and this skill's rules. Use stable finding IDs with exact quotes and blocking/nonblocking classification. No sidecar is required for a conversational verdict.

Consult applicable active editorial-memory decisions before proposing style repairs. Include the applicable scoped decision block verbatim in each focused worker brief; coordinator awareness alone is insufficient. Preserve deliberate choices within their stated scope; correctness checks remain binding. Do not generalize a local rejection. For in-place editing, record each applied finding's source quote and before/after hashes in the disposition ledger; review the resulting chapter with fresh evidence. A pre-edit PASS cannot establish post-edit readiness. Diagnostic-only skills still never edit source prose. Blind reader passes receive only reader-facing text; preference/canon checks happen in a separate coordinator pass.
