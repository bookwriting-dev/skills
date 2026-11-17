---
name: series-continuity
description: "Audit character status, resolved vs lingering secrets, timeline chronology, and spent promises across multiple books in a series to prevent cross-book plot holes. Use when user says 'series continuity check', 'check across books', 'audit series consistency', 'multi-book consistency', or 'series continuity audit'."
metadata:
  author: Storycraft Skills
  version: "1.2.0"
  bundled-dependencies: book-status
  category: fiction-editing
---

# Series Continuity Auditor

Audits multi-book consistency across drafted and released volumes in a series (`Book-1` through `Book-N`). Verifies that character physical states, knowledge and secrets, relationships, world rules, chronology, and deferred promises remain coherent across volume boundaries. Diagnostic-only: never edits manuscript prose directly.

## Dimensions Audited

1. **Character State Persistence:**
   - Physical scars, injuries, chronic conditions, age progression, equipment/items, and survival/status.
   - Relationship states, alliances, titles, jurisdictions, and legal/political constraints.
2. **Spent Mysteries & Information Asymmetry:**
   - Secrets revealed in earlier volumes are not treated as unknown in later volumes by characters who learned them, nor leaked prematurely by characters who did not.
   - Unreliable narration and intentional deception remain distinct from contradictions.
3. **World Chronology & Rule Persistence:**
   - Elapsed calendar time, seasons, travel durations, and book-to-book gaps reconcile across volumes.
   - World-level canon changes (`Wiki/World/`) or irreversible events from earlier endings hold in later openings.
4. **Series Promise & Thread Ledger:**
   - Cross-checks `Wiki/Story/series-arc.md`, each volume's `Wiki/Story/Book-K/synopsis.md`, and `deferred_to_series` entries in every `Wiki/Story/Book-K/promises.yaml`.

## Procedure

### Step 1: Capture Input Evidence & Load Series Canon
1. Discover all book folders present under `Chapters/Book-*` and `Wiki/Story/Book-*` (`Book-1` through `Book-N`).
2. Read shared canon and series planning:
   - `Wiki/Story/series-arc.md`
   - `Wiki/Characters/` (including `relationship_checkpoints` across books)
   - `Wiki/World/`
   - `Wiki/Story/Book-*/synopsis.md`
   - Active `editorial-memory` decisions (`Wiki/Style/editorial-decisions.json`), preserving deliberate stylistic choices within scope while keeping canon, knowledge, and numeric correctness binding.
3. For a saved report, follow [state-contract.md](../book-status/references/state-contract.md) using [project_state.py](../book-status/scripts/project_state.py) (`prepare`): capture inputs BEFORE auditing, including all inspected book directories/chapters, series arc, character/world references, ledgers, active editorial decision file (including its absence), and this skill's rules. (No sidecar is required for a conversational check.)

### Step 2: Run Deterministic Ledger & Continuity Queries Across Volumes
1. For each volume `Book-1..Book-N`, run:
   - `python3 .agents/skills/book-status/scripts/project_state.py --root ROOT --book Book-K continuity --action audit`
   - `python3 .agents/skills/fiction-promises/scripts/promises.py --book Book-K` (or `promise-tracker` for hybrid projects) to collect all `deferred_to_series`, `OVERDUE`, and `PAID` threads.
2. Query series-wide knowledge and relationship histories at key boundary story-order positions using `project_state.py --root ROOT knowledge-state` and `relationship-state`, checking `Wiki/Story/knowledge-events.json` and `Wiki/Story/relationship-events.json`. Note partial or missing ledger coverage honestly as `UNKNOWN` rather than assuming consistency.

### Step 3: Audit the 4 Multi-Book Continuity Dimensions
Inspect the drafted prose across all volumes — paying special attention to the closing chapters of every Book `K`, the opening chapters of Book `K+1`, and any chapters flagged by Step 2 or referencing shared series events:
1. Trace each major character's physical, positional, and relationship continuity from Book `1` through Book `N`.
2. Verify every mystery or secret solved in Book `1..K` against its handling in Book `K+1..N`.
3. Reconcile elapsed calendar dates, seasons, and story clocks across volume boundaries.
4. Verify that every `deferred_to_series` promise and `series-arc.md` handoff obligation is honored, advanced, or explicitly still open without vanishing silently.

### Step 4: Compile Report & Finalize Metadata
1. Save `_Edits/Book-N/Series_Continuity_Report.md` (creating `_Edits/Book-N/` if absent) with:
   - Overall cross-book verdict (`PASS` / `WARN` / `FAIL`) and ledger coverage disclosure (`CURRENT` / `PARTIAL` / `UNKNOWN`).
   - Volume-by-volume handoff summary (`Book 1 → Book 2 … → Book N`).
   - Findings ranked by severity with stable IDs (`SC-001`, etc.), `blocking` / `nonblocking` classification, exact quoted passages from both volumes/canon files, and affected ledger IDs.
   - Deferred series promises & handoff status table.
2. Finalize `_Edits/Book-N/Series_Continuity_Report.meta.json` via `project_state.py --root ROOT snapshot` only if Step 1 inputs still match.

### Step 5: Route Repairs
- Multi-book or multi-chapter prose/plan repairs route to `revision-campaign` to execute dependent edits and re-gating safely.
- Intentional changes to shared world/character truth route through `canon-guard` before touching `Wiki/`.
- Never edit manuscript prose directly from this diagnostic pass.
