---
name: fiction-full-editor
description: Default comprehensive fiction editing pass combining AIism detection, prose craft mechanics, and line editing into a single scan. Preferred over individual single-layer scanners (line-editor, prose-editor, aiism-editor). Uses paragraph- and scene-aware contextual packets. Use when user says "full edit", "edit chapter", "line edit", "check prose", "polish writing", or asks for general sentence-level editing.
metadata:
  author: Fiction Toolkit
  version: "1.5.0"
  bundled-dependencies: book-status, fiction-aiism-editor, fiction-prose-editor, fiction-line-editor
  category: fiction-editing
---

# Full Editor

Runs every micro-level check in a single pass. Each focused worker scans complete paragraph/scene-aware target passages against the complete criteria set: AIisms + prose craft + line editing. Fixed line counts are not passage boundaries.

## Arguments

The request argument is a chapter reference (e.g., "5", "Chapter-5", "Chapter-5.md").

## Step 1: Find Paths, Capture Input Evidence & Load Author Decisions

1. Parse the request argument to determine the chapter.
2. Search the project files for the chapter (e.g., `**/Chapter-5*`). If not found, ask.
3. Search for the project's review guide (`**/review_guide.md`), style guide (`**/style_guide.md`), and scoped `editorial-memory` records (`Wiki/Style/editorial-decisions.json`). Use whichever exist, and load applicable active editorial decisions before proposing style repairs (preserving deliberate choices within their stated scope while keeping correctness checks binding; never generalize a local rejection).
4. Resolve chapter identity/path through the project resolver when present. Read the complete chapter and identify paragraph, scene, verse, quotation, and literal-block boundaries. If both legacy style-guide names exist and conflict, preserve both and report the authority conflict rather than choosing silently.
5. For a saved report, follow [state-contract.md](../book-status/references/state-contract.md) using [project_state.py](../book-status/scripts/project_state.py) (`prepare`): capture inputs BEFORE review, including every consumed chapter, plan, canon/style reference, relevant ledger, active editorial decision file (including its absence), and this skill's rules. (No sidecar is required for a conversational verdict; diagnostic passes still never edit source prose.)

## Step 2: Read All Criteria

Read ALL three reference files and combine their contents:
- [AIism criteria](../fiction-aiism-editor/references/aiism-criteria.md)
- [prose criteria](../fiction-prose-editor/references/prose-criteria.md)
- [line-edit criteria](../fiction-line-editor/references/agent-instructions.md)

Combine them into a single criteria block for the worker prompts.

## Step 3: Launch Focused Workers

Use the shared [passages.py](../book-status/scripts/passages.py) extractor to partition by paragraph and scene/section boundaries under the available context budget. Give each passage a stable ID and mark the editable target separately from before/after context. Include the complete neighboring paragraph when a local definition, referent, irony cue, or voice signal crosses the target boundary. Preserve verse and intentional lineation. If a single paragraph exceeds budget, split only at sentence boundaries, retain one parent passage ID, record offsets/mappings, and ensure every sentence is covered exactly once.

Launch all chunks in parallel when the host supports workers; otherwise process the chunks sequentially. Keep the work in the foreground so all findings can be compiled in this run.

**Worker prompt for each chunk:**

> You are performing a comprehensive fiction edit. Inspect the complete supplied context, but propose changes only inside the explicitly marked target passage(s).
>
> 1. Read the review guide at: {review_guide_path} (if it exists)
> 2. Read the style guide at: {style_guide_path} (if it exists)
> 3. Read the source revision {subject_sha256}. Target passage IDs and exact zero-based half-open Unicode code-point offsets: {target_passages}. Context before/after is read-only: {context_passages}.
> 4. Apply this scoped author-decision block, including intentional KEEP examples: {applicable_editorial_decisions}. Do not generalize it beyond scope.
>
> 5. Check every line against ALL of the following criteria:
>
> {paste the combined contents of all three criteria files}
>
> 6. Return each finding with the exact quote, offsets into the exact delivered chapter string, target passage ID, category, reason, and smallest proposed replacement. Do not edit context-only text. Return NOTHING if no issues found:
>
> ```
> **Anchor:** `{start}:{end}` `exact quoted text` (passage `{passage_id}`)
> Category: [use the most specific category name from the criteria]
> Problem: [why it's a problem]
> Fix: [specific replacement]
> ```
>
> Be thorough but avoid false positives. If a construction works for character voice, skip it.

## Step 4: Compile Report

Collect all worker results. Deduplicate any issues flagged by overlapping criteria:
- **Deduplication by line:** If the same line is flagged across multiple criteria (e.g., both an AIism and a prose craft issue), merge into a single finding under the primary category and keep the single best, most actionable fix. Never output contradictory rewrites for the same line.
- Group into these top-level sections:

```
## Full Edit: [Chapter Title]

[2-3 sentence assessment — total count, severity, dominant pattern]

---

## AIism Issues
### Forbidden Words/Phrases
### AI Construction Patterns
### Forbidden Personification
### Vague Descriptors / Paradiastole

## Prose Craft Issues
### Narrative Fragments
### Choppy Constructions / S-V-O Chains
### Simile Overuse / Rule of Threes
### Show vs Tell / Info Dumps
### Emotion-Body Formulas

## Line Edit Issues
### Cliches and Tired Phrasing
### Repetition
### Awkward Constructions
### POV Violations
### Voice Violations
### Paired Adjectives

## Style Guide Violations
[any project-specific rule violations]

---

**Total issues: {count}**
**By severity:** {high/medium/low breakdown if clear}
```

Skip empty categories and sections.

## Step 5: Save, Snapshot Evidence & Report

1. Look for the chapter's `_Edits/Book-N/` folder (the same `Book-N` level as the chapter's `Chapters/Book-N/` location). If none exists, create it.
2. Save as `Chapter-NNN_FullEdit.md` (three-digit number matching the chapter), using stable finding IDs with exact quotes and blocking/nonblocking classification.
3. Run `project_state.py --root ROOT snapshot` to record `_Edits/Book-N/Chapter-NNN_FullEdit.meta.json` only if the captured inputs from Step 1 still match per [state-contract.md](../book-status/references/state-contract.md).
4. Perform a complete integration read of the chapter after merging/deduplicating findings; do not infer chapter readiness or publication approval from a diagnostic report. Tell the user the report location, issue count, leading categories, and any unresolved limitations.
5. Offer to apply approved items with `fiction-revise` (which records applied source quotes and before/after hashes in the disposition ledger; any subsequent prose edit invalidates prior gate evidence).
