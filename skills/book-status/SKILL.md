---
name: book-status
description: "Inspect manuscript health, chapter progress, gate check results, word counts, open Chekhov promises, and stylistic drift metrics across books and chapters. Use when user asks 'book status', 'manuscript dashboard', 'how far along is the book', 'what needs attention', or 'show project status'."
metadata:
  author: Storycraft Skills
  version: "1.1.0"
  category: cross-cutting
---

# Book Status Dashboard

Provides an executive summary of manuscript health, drafting completeness, gate checks, promise debts, and stylistic health across the entire book or series.

For the per-chapter workflow view — where each chapter sits between scene plan, draft, gate, and done — run `kanban-board`, which derives `Wiki/Story/Book-N/kanban.md` from the same on-disk state this skill reads.

## Dashboard Metrics

1. **Chapter Ledger & Word Counts:**
   - Word count per chapter against target range.
   - Total book word count and pacing breakdown by act.
2. **Quality Gate Status:**
   - Status of `_Edits/Book-N/Chapter-NNN_Gate.md` for each chapter: `PASS`, `WARN`, `FAIL`, or `UNCHECKED`.
3. **Promise Ledger (`promises.yaml`):**
   - Active setups, due chapters, overdue promises, and deferred series threads.
4. **Editorial & Review Reports:**
   - Persona review coverage: `reader-persona-review` drafts and its `_synthesis.md` consensus live under `_Edits/Book-N/reviews/`; `review-panel` files under `Wiki/Review/`.
   - Unapplied revision items: any `Chapter-NNN_<Type>.md` report in `_Edits/Book-N/` newer than the chapter's last edit.
5. **Drift & Cadence Health:**
   - Summarize `_Edits/Book-N/drift-report.md` and `_Edits/Book-N/burstiness-report.md` when present. If they are absent, report "no drift report on file — run `drift-check`" rather than inventing findings.

---

## Procedure

1. **Scan `Chapters/Book-N/`:**
   - Count word totals and verify sequential numbering.
2. **Scan `_Edits/Book-N/`:**
   - Aggregate gate results, editor passes, and persona review tallies.
3. **Scan the promise ledger (`Wiki/Story/Book-N/promises.yaml`):**
   - Tally setup/payoff balance with the ledger's own script: `python3 .agents/skills/fiction-promises/scripts/promises.py --book Book-N` for fiction projects; `promise-tracker`'s copy of the same-named script for non-fiction and hybrid projects. Both accept `--chapter chNN` to evaluate as of a chapter.
4. **Render Markdown Dashboard:**
   - Output structured table with immediate blockers and recommended next actions.
