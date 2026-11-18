---
name: revision-campaign
description: "Coordinate a book or series revision through impact analysis, dependent tasks, verified edits, and resumable checkpoints. Use when the user says revise this across the book, make the betrayal earned, run a revision campaign, or resume the book revision."
metadata:
  author: Storycraft Skills
  version: "1.1.0"
  category: cross-cutting
  bundled-dependencies: book-status
---

# Revision Campaign

## Define observable outcome

Translate the authorized request into concrete changes and strengths to preserve. For a betrayal: earlier motive, trust-changing choices, fair evidence before the reveal, and consequences afterward. Resolve scope across chapters/books and record existing authorization. Use [campaign.json](assets/campaign.json), [checks.json](assets/checks.json), and [project_state.py](../book-status/scripts/project_state.py); read [state-contract.md](../book-status/references/state-contract.md).

## Map impact

Read all assigned manuscript units in order. Consult applicable canon, knowledge events, promises, reader findings, and editorial preferences. Combine text search with semantic reading: a changed motive affects scenes that never name it. Preserve specific successful passages. Classify work as plan repair, re-draft, local edit, canon update, ledger reconciliation, or verification. Inspect other active campaigns for overlapping files before execution.

## Build dependent tasks

Each task has a stable safe ID, explicit source files, depends_on IDs, acceptance conditions, edit scope, and authorization. Source files must be individual project-relative files. Reject cycles or missing dependencies. Record requested outcome and preservation constraints at campaign level. Initialize with `project_state.py --root ROOT --book Book-N campaign --run ID --action init --spec CAMPAIGN.json`. Initialization snapshots targeted files and records their content hashes. No source editing occurs during init.

A campaign initialized from `beta-feedback` preserves selected comments and their edition and source evidence. Treat selection for planning as a pending task. Start revision when the writer requests that work.

## Execute authorized work

Use `campaign --run ID --action start --task TASK`. If hashes changed outside recorded predecessor tasks, reconcile the author's changes before continuing. Structural work goes through fiction-dev-editor/fiction-scenes and fiction-writechapter. Local fixes use fiction-revise. Canon changes use canon-guard, honoring already authorized scope. Do not request approval again for changes the user's campaign instruction already covers; ask only for a blocking story choice or expanded scope.

Perform in-place tasks sequentially when they share files. Re-harvest affected knowledge and promises without duplicate IDs. Review/gate affected chapters and capture current PASS evidence. Complete a task with `campaign --run ID --action complete --task TASK --spec CHECKS.json`, naming its check metadata. Do not equate edited with verified.

## Resume or recover

Use `campaign --run ID --action status` and inspect each completed task's output hashes/check freshness before reuse. Interrupted running tasks require inspection and reconciliation; never apply their edits twice. Update status/board with affected chapters and blockers. Completion requires all task acceptance conditions, current configured checks, reconciled ledgers, and no unresolved blocking decisions.

Recovery uses `campaign --run ID --action recover --task TASK` only for an unchanged campaign-owned output with no active/completed dependent task. Otherwise present a conflict-aware recovery plan. Never use Git reset or discard later author edits. Return the campaign path, completed/blocked tasks, preserved strengths, and current verification. Offer the next ready task or final manuscript export.
