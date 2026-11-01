---
name: series-continuity
description: "Audit character status, resolved vs lingering secrets, timeline chronology, and spent promises across multiple books in a series to prevent cross-book plot holes. Use when user says 'series continuity check', 'check across books', 'audit series consistency', 'multi-book consistency', or 'series continuity audit'."
metadata:
  author: Storycraft Skills
  version: "1.1.0"
  bundled-dependencies: book-status
  category: fiction-editing
---

# Series Continuity Auditor

Audits multi-book consistency across drafted and released volumes in a series. Verifies that character physical states, emotional trajectories, world changes, and spent plot points remain coherent from Book 1 to Book N.

## Dimensions Audited

1. **Character State Persistence:**
   - Physical scars, chronic conditions, age progression, family/relationship status.
   - Professional titles, jurisdictions, and legal constraints.
2. **Spent Mysteries & Secret Protection:**
   - Verifies that secrets solved in Book N are not re-treated as unknown in Book N+1.
   - Ensures information asymmetry between characters remains realistic.
3. **World Chronology & Seasons:**
   - Weather, seasons, calendar elapsed time across book gaps.
4. **Series Promise & Thread Ledger:**
   - Cross-checks `Wiki/Story/series-arc.md` and deferred promises in `promises.yaml`.

## Procedure

1. Read `Wiki/Story/series-arc.md` and `Wiki/Characters/`.
2. Inspect latest chapters of Book N-1 and opening chapters of Book N.
3. Output continuity report into `_Edits/Book-N/Series_Continuity_Report.md`.

## Current evidence and author decisions

For a saved report, follow [state-contract.md](../book-status/references/state-contract.md) using [project_state.py](../book-status/scripts/project_state.py): capture inputs BEFORE review, then record report metadata only if those inputs still match. Include every consumed chapter, plan, canon/style reference, relevant ledger, applicable editorial decision file (including its absence), and this skill's rules. Use stable finding IDs with exact quotes and blocking/nonblocking classification. No sidecar is required for a conversational verdict.

Consult applicable active editorial-memory decisions before proposing style repairs. Include the applicable scoped decision block verbatim in each focused worker brief; coordinator awareness alone is insufficient. Preserve deliberate choices within their stated scope; correctness checks remain binding. Do not generalize a local rejection. For in-place editing, record each applied finding's source quote and before/after hashes in the disposition ledger; review the resulting chapter with fresh evidence. A pre-edit PASS cannot establish post-edit readiness. Diagnostic-only skills still never edit source prose. Blind reader passes receive only reader-facing text; preference/canon checks happen in a separate coordinator pass.
