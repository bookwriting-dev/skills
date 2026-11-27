---
name: book-status
description: "Inspect manuscript health, chapter progress, gate results, word counts, open promises, and stylistic drift. Use for 'book status', 'manuscript dashboard', 'how far along is the book', 'what needs attention', 'show project status', personal read-through bookmarks, passages changed since an author's read, or a targeted manuscript scan for dated wording and spelled-out clock times."
metadata:
  author: Storycraft Skills
  version: "1.20.0"
  bundled-dependencies: nonfiction-research
  category: cross-cutting
---

# Book Status Dashboard

Provides an executive summary of manuscript health, drafting completeness, gate checks, promise debts, and stylistic health across the entire book or series.

For the per-chapter workflow view — where each chapter sits between scene plan, draft, gate, and done — run `project_state.py --root ROOT --book Book-N kanban` (backed by [kanban.py](scripts/kanban.py)) or `kanban-board`, which derives `Wiki/Story/Book-N/kanban.md` deterministically from the same on-disk state this skill reads. When the host exposes `storycraft_*` MCP tools (`storycraft_dashboard`, `storycraft_draft_packet`, `storycraft_kanban`, `storycraft_rhythm_map`, `storycraft_sync_edits`, `storycraft_review_begin`, `storycraft_review_finish`, `storycraft_record_disposition`, `storycraft_reanchor`, `storycraft_chapter_preflight`, `storycraft_chapter_finalize`, `storycraft_promises`, `storycraft_compile`), prefer them before falling back to shell calls to [project_state.py](scripts/project_state.py). Otherwise use `project_state.py chapter-preflight`, `project_state.py chapter-finalize`, `reanchor --chapter N`, `--events`, and `--dispositions` batch modes to run preflight, ledger updates, re-anchoring after prose edits, and finalization in minimal round-trips.

For a request limited to diction or clock notation, resolve the requested manuscript paths and run [prose_style.py](scripts/prose_style.py) as described in [diction and clock time](references/diction-and-time.md). Return the confirmed passages and suggested edits within that scope.

## Dashboard Metrics

1. **Chapter Ledger & Word Counts:**
   - Word count per chapter against target range.
   - Total book word count and pacing breakdown by act.
2. **Quality Gate Status:**
   - Status of `_Edits/Book-N/Chapter-NNN_Gate.md` for each chapter: `PASS`, `WARN`, `FAIL`, or `UNCHECKED`, paired independently with freshness (`CURRENT`, `STALE`, or `UNKNOWN`).
3. **Promise Ledger (`promises.yaml`):**
   - Active setups, due chapters, overdue promises, and deferred series threads. The preflight packet uses [draft_promises.py](scripts/draft_promises.py) to surface obligations and verified setup passages.
4. **Editorial & Review Reports:**
   - Persona review coverage: `reader-persona-review` drafts and its `_synthesis.md` consensus live under `_Edits/Book-N/reviews/`; `review-panel` files under `Wiki/Review/`.
   - Unapplied revision items: unresolved stable finding IDs in saved reports, using the disposition ledger; legacy resolution is `UNKNOWN`.
5. **Drift & Cadence Health:**
   - Summarize `_Edits/Book-N/drift-report.md` and `_Edits/Book-N/burstiness-report.md` when present. If they are absent, report "no drift report on file — run `drift-check`" rather than inventing findings.

---

## Procedure

1. **Step 1: Resolve Project & Validate State Runtime**
   - Resolve project identities and canonical chapter/style paths through [project_manifest.py](scripts/project_manifest.py); preview legacy-layout adoption with `python3 .agents/skills/book-status/scripts/project_state.py --root ROOT manifest --action preview` and apply (`--action apply`) only when explicitly requested.
   - Run `python3 .agents/skills/book-status/scripts/project_state.py --root ROOT --book Book-N validate` and `dashboard` to gather machine-verified freshness, unresolved blocking finding IDs, and migration state under [references/state-contract.md](references/state-contract.md) and [assets/report-meta.schema.json](assets/report-meta.schema.json).
   - Read the dashboard's `required_checks`, each chapter's readiness, and `missing_chapters`. Use the resolved chapter paths for word totals.

2. **Step 2: Inspect Chapter Format & Continuity Coverage**
   - For fiction projects, run `project_state.py --root ROOT --book Book-N chapter-format` and `project_state.py --root ROOT --book Book-N continuity --action audit` using [chapter_format.py](scripts/chapter_format.py) and [continuity.py](scripts/continuity.py).
   - Report coverage gaps, confirmed conflicts, and review notes from [book continuity review](references/continuity-review.md) alongside any supporting [evidence-chain.md](references/evidence-chain.md) findings. (Shared helpers [passages.py](scripts/passages.py) and [reader_text.py](scripts/reader_text.py) remain part of the `book-status` runtime for downstream editors and blind readers.)

3. **Step 3: Query Committed Ledgers (Promises, Knowledge, Relationships)**
   - Inspect multi-ledger transaction state with `python3 .agents/skills/book-status/scripts/ledger_transaction.py --root ROOT --status` backed by [ledger_store.py](scripts/ledger_store.py); uncommitted generations remain visible for safe retry rather than being overwritten.
   - Tally setup/payoff balance in `Wiki/Story/Book-N/promises.yaml` using `.agents/skills/fiction-promises/scripts/promises.py --book Book-N` for fiction projects, or `promise-tracker`'s copy for non-fiction and hybrid projects (both accept `--chapter chNN`).
   - Query `Wiki/Story/knowledge-events.json` with `knowledge-state --observer CHARACTER --story-order N` (and `--observer reader --reader-order N`), and query `Wiki/Story/relationship-events.json` with `relationship-state --observer Mara --scope Jo --story-order N` when story chronology is known.

4. **Step 4: Aggregate Editorial, Persona & Diagnostic Reports**
   - Inspect `_Edits/Book-N/` gate reports, editor reports, and `.meta.json` sidecars. Ignore file mtimes when determining applied edits; read report-hash/finding-ID dispositions and flag legacy reports without metadata as `UNKNOWN`.
   - Summarize `_Edits/Book-N/reviews/` (`_synthesis.md`), `Wiki/Review/`, `_Edits/Book-N/drift-report.md`, and `_Edits/Book-N/burstiness-report.md` (or state honestly if missing).

5. **Step 5: Check Active Campaigns, Reading Checkpoints & Migrations**
   - Surface active `revision-campaign` blockers, invalidated `sequential-read` checkpoints, stale knowledge evidence, and pending schema migrations from the runtime dashboard output. Never infer that every task marked complete still has current checks.

6. **Step 6: Render Executive Dashboard**
   - Output a structured Markdown dashboard showing verdict (`PASS`/`WARN`/`FAIL`) separately from freshness (`CURRENT`/`STALE`/`UNKNOWN`) with reasons, immediate blockers, and the first concrete blocked next action.


## Personal read-through

Use the project state CLI with the book selector followed by `author-read --action start` to freeze the current reader edition. An optional `--edition ID` selects an archived beta. On an explicit author update, run `author-read --action mark --chapter 5` for a completed chapter, or add `--quote "last line read"` for partial progress. A unique quote can identify the chapter itself. For an ambiguous quote use a longer excerpt or chapter selector. Report `--action resume` or `--action changes` against current prose or the named edition. Only credit chapters the author actually reports reading. Surface the dashboard’s personally read total separately from review readiness. [Edition comparison](scripts/editions.py)

## Book-level editorial evidence

[editorial_tools.py](scripts/editorial_tools.py) prepares cast and long-absence evidence, a hypothetical scene cut with earlier and later passages, a chapter-only nonfiction reader packet, or a narrator sheet. Use [rhythm_map.py](scripts/rhythm_map.py) (`project_state.py --root ROOT --book Book-N rhythm-map --markdown`) for a whole-book pacing, POV share, promise density, and character-absence matrix. Use [sync_edits.py](scripts/sync_edits.py) (`project_state.py --root ROOT --book Book-N sync-edits --chapter N`) after an author hand-edits a chapter to surface changed paragraphs, broken continuity/knowledge quotes, stale reports, and advisory preference candidates. Use the corresponding editorial or packaging skill to interpret these findings. The importer and export checker read package spines and navigation through [epub_publication.py](scripts/epub_publication.py). These book-level checks run on request or at an act or whole-book milestone. They do not enter the list of required chapter reviews.
