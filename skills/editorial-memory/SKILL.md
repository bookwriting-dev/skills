---
name: editorial-memory
description: "Remember explicit author editing preferences with scoped decisions and supersession. Use when the user says remember this editorial choice, show my editing preferences, stop flagging this for this character, or retire that preference."
metadata:
  author: Storycraft Skills
  version: "1.1.0"
  category: cross-cutting
  bundled-dependencies: book-status
---

# Editorial Memory

## Resolve the requested decision

Read the user's instruction, the applicable book instructions, and the original report and chapter only as needed. An applied or rejected edit is a local disposition. It becomes a reusable preference only when the author explicitly says it should. Preserve the author's stated reason; do not invent one. If the scope is unspecified, retain the narrow passage scope and mark reusable false.

When the author edits a chapter by hand, `project_state.py --root ROOT --book Book-N sync-edits --chapter N` surfaces recurring edit deltas as *advisory candidates* only. Never record them silently — present them and persist only what the author explicitly confirms.

Use the bundled helper described in [state-contract.md](../book-status/references/state-contract.md). Its executable is [project_state.py](../book-status/scripts/project_state.py). A missing helper means incomplete installation; do not pretend to persist memory. The entry template is [decision.json](assets/decision.json).

## Record the evidence

Prepare a versioned JSON entry with a new stable ID, scope, rule_category, reason, status, reusable, and source evidence. Scope strings are series, Book-N, Book-N/Chapter-NNN, or Book-N/POV/Name; passage decisions also include source and quote. Copy the exact quote and source hash. Resolve conflicting records against current user direction and book instructions. A broad preference does not silently erase narrower exceptions. Name explicit supersedes IDs when the user authorizes replacing a decision.

Run Python 3 with the resolved helper path: `project_state.py --root ROOT memory --action record --spec ENTRY.json`. Use `memory --action list --scope SCOPE` to inspect active series/exact-scope records. For nested scopes, collect each ancestor explicitly and filter passage quotes against current text. Return unresolved conflicts to the author only when they block the requested edit. The script intentionally rejects reusable waivers in canon, fact, knowledge, and numeric categories.

## Apply in later work

Editors load only applicable active reusable entries plus local passage decisions. A rejection in one chapter does not exempt other chapters. Keep a deliberate fragment when its scoped decision applies, but continue flagging an unrelated confusing fragment. Cite the decision ID when it changes a KEEP/FIX judgment. Drafting may adopt the approved principle or cadence; never copy sample sentences into unrelated scenes.

To retire a preference, write a new non-reusable retired record with a new ID and supersedes pointing to the old record. Preserve history. Never rewrite editorial memory during style-guide regeneration or a library update.

## Report

Return the recorded ID, effective scope, whether it is reusable, and any superseded IDs. Offer to inspect its effect on the next editing pass. Never claim preferences were learned from silence or from elapsed time.
