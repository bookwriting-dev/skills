---
name: fiction-revise
description: Apply approved edits from a review or edit report (_Edits/Chapter-NNN_*.md) directly to a chapter manuscript file with minimal, verified in-place edits and a change ledger. Use when user says "apply edits", "apply review fixes", "revise chapter", "apply fixes 1, 3, 5", or after running fiction-reviewchapter, fiction-full-editor, or another editing pass.
metadata:
  author: Fiction Toolkit
  version: "1.3.0"
  bundled-dependencies: book-status
  category: fiction-editing
---

# Fiction Revise — Apply Approved Edits

Applies approved review findings and edit recommendations directly to a chapter manuscript file.
Enforces strict in-place edits, verifies exact quoted text before touching files, skips stale
or conflicting items, records durable dispositions, and produces a complete change ledger.

## Arguments

The request accepts:
1. **Chapter reference** (e.g. `5`, `Chapter-005`, `Chapters/Book-1/Chapter-005.md`)
2. **Report reference** (optional; defaults to the most recent report in `_Edits/Book-N/` for that chapter)
3. **Selection filter** (e.g. `all`, `items 1, 3, 5-8`, `all AIisms`, or interactive confirmation)

## Step 1: Locate Chapter, Report, and Freshness

1. Resolve the chapter file (prefer canonical `Chapters/Book-N/Chapter-NNN.md`).
2. Locate the source edit report:
   - Check `_Edits/Book-N/` (or adjacent `_Edits/` folder).
   - Match the `Chapter-NNN_<Type>.md` pattern — every report writer in the library follows it (`Review`, `Gate`, `FullEdit`, `LineEdit`, `AIisms`, `LevelUp`, `FragmentHunt`, `FactCheck`, `ClarityEdit`).
   - If multiple reports exist and the user didn't specify one, ask or default to the newest.
3. Inspect report freshness via [project_state.py](../book-status/scripts/project_state.py) (`check --meta`) per [state-contract.md](../book-status/references/state-contract.md) before selection. A `STALE` report can supply a still-exact local quote only after inspecting its current context; never treat its old gate verdict as current.
4. Read both the chapter and the report into context.

## Step 2: Parse and Select Edits

Extract all structured recommendations from the report:
- Stable finding ID / item identifier
- Target line reference or anchor
- Quoted original snippet
- Proposed fix / replacement text
- Category / issue type

If the user gave specific item numbers (e.g. "apply 1, 4, 7-10"), select only those items.
If the user said "apply all", select all local line-edit items.
If the user did not specify, list the available items grouped by category and ask which to apply.

## Step 3: Pre-flight Verification & The Scrap-vs-Patch Guard

Before making any edit, check each selected item against two safety rules:

1. **The Scrap-vs-Patch Guard:**
   - If a finding is **structural** (e.g. missing required beat, wrong POV character, whole-scene causal failure), do NOT apply it line-by-line. Flag it as `SKIPPED: STRUCTURAL` — per project rules, structural problems require fixing the scene plan and re-drafting with `fiction-writechapter`.
2. **Quote Match Verification:**
   - Locate the exact quoted text in the current chapter manuscript.
   - If the exact quote cannot be found (e.g. earlier edits shifted text or changed phrasing), do NOT guess. Mark the item as `SKIPPED: STALE_QUOTE`.

## Step 4: Apply Edits & Record Dispositions (Minimal Perturbation)

Apply the validated items to the chapter file in place:
- Make the **minimal necessary change**: touch ONLY the targeted words or phrase specified in the fix.
- Do not rewrite unflagged adjacent sentences.
- Do not insert unsolicited adjectives, flourishes, or mood descriptors.
- Obey project style rules (e.g. no em dashes except dialogue interruptions; grounded physical sentences).
- If multiple approved edits target the same line or overlapping text, apply the primary fix and mark the subordinate edit as `MERGED`.
- Record each `applied`, `rejected`, or `deferred` finding in `_Edits/Book-N/decisions.jsonl` using `project_state.py --root ROOT --book Book-N disposition --spec SPEC.json`, capturing the report hash, stable finding ID, source quote, and before/after hashes. Record the author's reason verbatim when supplied. Keep a local rejection local unless the user explicitly asks `editorial-memory` to remember a reusable preference.

## Step 5: Report Change Ledger

Output a concise, structured ledger:

```markdown
## Revision Ledger: Chapter [NNN]

**Applied ({count}):**
- **Item [N] (Line {line}):**
  - *Before:* "..."
  - *After:* "..."

**Skipped ({count}):**
- **Item [N]:** [Reason: user excluded | STALE_QUOTE | STRUCTURAL (needs re-draft)]

**Next Step:**
Chapter manuscript updated. Every source change invalidates old gate evidence — re-run `fiction-reviewchapter` (or `gate-check` / `nonfiction-factcheck` + `nonfiction-clarity-edit`) for fresh current verification before declaring the chapter Done.
```

Offer to leave staged or commit per project convention. Do not commit unless requested.
