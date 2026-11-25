---
name: kill-crutch
description: Hunt any crutch/filler word (including "soft", "flat", "just", "little", "really", "almost") across a chapter and remove bad uses while keeping literal and in-voice ones (deletion-first, parallel workers, edits in place). Use when user says "kill-crutch WORD", "kill-soft", "kill-flat", "kill the word X", or "strip filler word X".
metadata:
  author: Fiction Toolkit
  version: "1.3.1"
  bundled-dependencies: book-status, kill-chapter
  category: fiction-editing
---

# Kill a crutch word — strip the filler, keep the real ones

The first token of the request arguments is the **target word** (e.g. `soft`, `flat`, `just`, `little`, `really`,
`quite`, `almost`, `slightly`, `a bit`, `seemed`, `somehow`, `simply`). Anything after it is the **scope**: a chapter file path, a
file pattern, or several paths. This generalized pass also covers `soft` and `flat` (`kill-crutch soft` / `kill-crutch flat`).

## Single-source rule-set (Deletion-first & What to keep vs. fix)

Read [crutch.md](../kill-chapter/references/crutch.md) (and [soft.md](../kill-chapter/references/soft.md) or [flat.md](../kill-chapter/references/flat.md) when targeting `soft` or `flat`) before triaging or launching workers. Those files are the single source of truth for the default filler vocabulary, deletion-first rules, KEEP/FIX criteria, and examples shared with `kill-chapter`; pass their contents verbatim (alongside any word-specific KEEP split for the requested token) to every focused worker so single-pass and full-chapter sweeps never drift. State your proposed keep/fix split for the requested word in one line, then proceed.

## Procedure

1. **Parse the request arguments:** first token = WORD; remainder = scope. Resolve scope to files,
   then use the host's available text search to keep only files that contain the word.
2. **Triage:** search for whole-word matches across the files and skim. If rare, fix inline. If spread
   across many files, split into up to 6 roughly equal groups and use one focused worker
   per group in parallel when the host supports workers; otherwise process the groups sequentially.
3. **Each worker gets:** its exact file list; the WORD; the KEEP/FIX and deletion-first
   rules verbatim; instruction to read each file in 20-line chunks so it sees every hit in
   full context; the resolved `style-policy` (`Wiki/Style/style_guide.md` / `review_guide.md` register preset and punctuation rules) and active scoped `editorial-memory` decisions (`Wiki/Style/editorial-decisions.json`) verbatim. It makes the minimal
   in-place edit, touching ONLY the target word, and reports a per-file verdict list: each
   hit tagged (KEPT-literal / KEPT-voice / DELETED / REWRITTEN) with before→after for changes.
4. **Verify when all workers return** and consolidate. Search again for rewrite residue (workers
   that expanded instead of deleting) and convert those to plain deletions. Worker edits
   make your in-context file state stale; reread before any follow-up edit. Report the
   consolidated change list and before/after count from the host's available text search.
5. Offer to commit or leave staged.

## Notes

- Never blanket-ban the bare word; it usually has legit literal uses. Target only the
  hedging/padding collocations.

## Current evidence and author decisions

For a saved report, follow [state-contract.md](../book-status/references/state-contract.md) using [project_state.py](../book-status/scripts/project_state.py): capture inputs BEFORE review, then record report metadata only if those inputs still match. Include every consumed chapter, plan, canon/style reference, relevant ledger, applicable editorial decision file (including its absence), and this skill's rules. Use stable finding IDs with exact quotes and blocking/nonblocking classification. No sidecar is required for a conversational verdict.

Consult applicable active editorial-memory decisions before proposing style repairs. Include the applicable scoped decision block verbatim in each focused worker brief; coordinator awareness alone is insufficient. Preserve deliberate choices within their stated scope; correctness checks remain binding. Do not generalize a local rejection. For in-place editing, record each applied finding's source quote and before/after hashes in the disposition ledger; review the resulting chapter with fresh evidence. A pre-edit PASS cannot establish post-edit readiness. Diagnostic-only skills still never edit source prose. Blind reader passes receive only reader-facing text; preference/canon checks happen in a separate coordinator pass.
