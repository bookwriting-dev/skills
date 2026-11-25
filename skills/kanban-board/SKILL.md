---
name: kanban-board
description: "Render a per-book Kanban board at Wiki/Story/Book-N/kanban.md (Backlog, Ready, Drafting, Review, Done) mechanically from outlines, scene plans, drafts, and gate reports. Read-only diagnostic except for the board file; works for fiction and non-fiction. Use for 'kanban', 'show the board', 'what is in progress', or 'where am I in this book'."
metadata:
  author: Storycraft Skills
  version: "1.4.0"
  bundled-dependencies: book-status
  category: cross-cutting
---

# Book Kanban Board

A book is produced one chapter at a time through a fixed sequence — outline
beat, scene plan, draft, review/gate, revise — but nothing in a project shows
that sequence at a glance. `book-status` reports metrics (word counts, gate
tallies, promise debt); this skill renders the *workflow position*: one card
per chapter, five columns, derived from what exists on disk.

## Contract

- **Read-only diagnostic except for the board file.** Deriving the board never
  touches chapters, scene plans, canon, or reports. The only file this skill
  writes is `Wiki/Story/Book-N/kanban.md` (regenerated in full on every run).
- **The board is never the source of truth.** It is a view of the files, and it
  is rebuilt from the files every time it is shown — if a stale board and the
  files ever disagree, regenerate rather than hand-edit.
- **No judgment.** Column placement is mechanical (see the mapping below). If
  the evidence is ambiguous, the card stays in the earlier column with a `?`
  note; the board never upgrades a chapter on a guess.

## Columns

A chapter appears in exactly one column — the furthest its on-disk evidence
reaches.

| Column | A chapter is here when |
|---|---|
| **Backlog** | It has an entry in `Wiki/Outline/Book-N/outline.md` but no scene plan yet. |
| **Ready** | Its scene plan exists (`Wiki/Outline/Book-N/Chapter_NN_Scene.md`), no draft yet. |
| **Drafting** | A draft exists (`Chapters/Book-N/Chapter-NNN.md`), no gate/review report yet. |
| **Review** | A gate or review report exists (`_Edits/Book-N/Chapter-NNN_Gate.md` or `Chapter-NNN_Review.md`) and the gate verdict is not `PASS`. |
| **Done** | Its configured gate evidence is CURRENT PASS, with no unresolved blocking findings or campaign tasks. |

Chapters that exist only as drafts or reports but have no outline entry still
get a card (in Drafting or later) — the outline is an input, not a gate, for
placement; flag the missing outline entry on the card.

## Card contents

One line per chapter: number, title (from the scene plan or the draft's title
line), POV name(s), word count, gate verdict, and flags. Example:

> `004 — The Tar Auction — POV: Ren — 3,410 words — gate: PASS`

Flags: `no-scene-plan`, `no-outline-entry`, `unapplied-review-findings` (unresolved stable findings in the disposition ledger; legacy resolution UNKNOWN),
`?` for ambiguous state.

## Procedure

1. **Generate deterministically first:** Call `storycraft_kanban` when MCP tools are connected, or run the zero-LLM script renderer via [project_state.py](../book-status/scripts/project_state.py) (`--root ROOT --book Book-N kanban`) or [kanban.py](../book-status/scripts/kanban.py), which builds `Wiki/Story/Book-N/kanban.md` directly from `dashboard()`, `outline.md` / `plan.md`, `Chapter_NN_Scene.md`, chapter files, and `promises.yaml`.
2. **Scope & fallback rules:** Default to the book the session is working in (`Book-1` when ambiguous); honor an explicit book ("show the book 2 board"). If neither outline nor chapters exist for the book, say so and stop. The script checks the same sources listed below (`dashboard`, outline/plan, scene plan, drafts, Gate/FactCheck/ClarityEdit reports, and `promises.yaml`):
   - use `project_state.py --root ROOT --book Book-N dashboard` from [book-status](../book-status/scripts/project_state.py) for chapter IDs, expected and missing chapters, required reviews, and current readiness;
   - outline entry in `Wiki/Outline/Book-N/outline.md`;
   - scene plan `Wiki/Outline/Book-N/Chapter_NN_Scene.md`;
   - draft `Chapters/Book-N/Chapter-NNN.md` plus its word count;
   - reports `_Edits/Book-N/Chapter-NNN_Gate.md` and
     `_Edits/Book-N/Chapter-NNN_Review.md` (verdict: the gate report's stated
     `PASS` / `WARN` / `FAIL`);
   - the book's promise ledger `Wiki/Story/Book-N/promises.yaml` (overdue
     count for the header, if present).
3. **Place cards** by the column table. Use the dashboard's `ready` verdict, current campaign state, and effective required reviews for Done.
4. **Render the board** (template below) with a one-line header: book, refresh
   date, per-column counts, overdue-promise count.
5. **Write** `Wiki/Story/Book-N/kanban.md` (create the folder if needed) and
   print the board in the reply.
6. **Suggest the next move** — one line per actionable card, routing only:
   - Backlog, no scene plan → `fiction-scenes`
   - Ready → `fiction-writechapter` (or `chapter-pipeline` to run the whole leg)
   - Drafting, no report → `fiction-reviewchapter` / `gate-check`
   - Review with `WARN`/`FAIL` findings → apply approved fixes with
     `fiction-revise`, then re-run the gate
   - overdue promises in the header → `fiction-promises`

## Non-fiction

Same board, same columns; the evidence sources change only:

- Backlog source is `Wiki/Outline/Book-N/plan.md` (the chapter plan);
- Review/Done evidence is `_Edits/Book-N/Chapter-NNN_FactCheck.md` and
  `_Edits/Book-N/Chapter-NNN_ClarityEdit.md` — a chapter is Done only when current required fact-check/clarity evidence passes and blocking findings are resolved;
- next-move routing uses the non-fiction skills (`nonfiction-chapter-plan`,
  `nonfiction-writechapter`, `nonfiction-factcheck`,
  `nonfiction-clarity-edit`, `promise-tracker`).

## Board template

```markdown
# <Series title> — Book <N> board

Refreshed <date> — Backlog <b> · Ready <r> · Drafting <d> · Review <v> ·
Done <done> · Overdue promises <p>

## Backlog

- <NNN> — <title or "untitled"> <flags>

## Ready

...

## Drafting

...

## Review

...

## Done

...
```

Empty columns are shown with a `- (empty)` line, not omitted — the five-column
shape is the point of the board.

## Freshness overrides column placement

Use [project_state.py](../book-status/scripts/project_state.py) and [state-contract.md](../book-status/references/state-contract.md). Fiction Done requires a CURRENT PASS plus no unresolved blocking findings/campaign tasks. STALE or UNKNOWN PASS remains Review with its reason. Non-fiction Done requires CURRENT configured fact-check and clarity evidence and all blocking findings resolved, not merely the existence of a clarity report. Hybrid projects explicitly configure required checks. Use finding dispositions, never mtime, to determine applied/rejected work. The board remains a generated view and never modifies sources.
