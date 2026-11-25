---
name: nonfiction-clarity-edit
description: "Default comprehensive non-fiction clarity pass: jargon density, abstraction ladder, cognitive load, and signposting, plus sentence-level mechanics. The non-fiction equivalent of fiction-full-editor. Uses paragraph- and section-aware contextual packets. Use when user says 'clarity edit', 'make it clearer', 'check readability', 'edit chapter', 'polish writing', or asks for general sentence-level editing of non-fiction."
metadata:
  author: Nonfiction Toolkit
  version: "1.6.0"
  bundled-dependencies: book-status
  category: nonfiction-editing
  output-format: markdown
---

# Nonfiction Clarity Edit

Runs every sentence-level clarity check in a single pass. Each focused worker scans complete paragraph- and section-aware target passages against the complete criteria set: jargon density + abstraction ladder + cognitive load + signposting + sentence mechanics. Fixed line counts are not passage boundaries.

## Arguments

The request argument is a chapter reference (e.g., "5", "Chapter-5", "Chapter-5.md").

## Step 1: Find Paths and Measure

1. Parse the request argument to determine the chapter.
2. Search the project files for the chapter (e.g., `**/Chapter-5*`). If not found, ask.
3. Search for the project's style guide (`**/style_guide.md`), review guide (`**/review_guide.md`), and scoped `editorial-memory` records (`Wiki/Style/editorial-decisions.json`). Load applicable active editorial decisions before proposing repairs (preserving deliberate choices within their stated scope while keeping factual/correctness checks binding).
4. Search for the chapter's plan (its `## Chapter NN` section in `Wiki/Outline/Book-N/plan.md` — the default home — or a per-chapter `**/Chapter_[NN]_Plan.md` file, or the project's planning convention from `nonfiction-chapter-plan`). The plan states the chapter's claim, evidence blocks, and required transitions — a clarity edit must not cut an argument move it mistakes for clutter, and must not pass prose that buries the plan's claim.
5. Resolve chapter identity/path through the project resolver when present. Read the complete chapter and identify paragraph, section, quotation, and intentional-format boundaries. If style-guide authorities conflict, preserve both and report the conflict rather than choosing silently.

## Step 2: Read All Criteria

Read ALL four reference files and combine their contents:

- [jargon-criteria.md](references/jargon-criteria.md)
- [abstraction-criteria.md](references/abstraction-criteria.md)
- [cognitive-load-criteria.md](references/cognitive-load-criteria.md)
- [signposting-criteria.md](references/signposting-criteria.md)

Also read the drafting-side clarity rules for known-good patterns: [clarity-rules.md](../nonfiction-writechapter/references/clarity-rules.md). Where a drafting rule and a detection criterion overlap, the detection criterion governs what gets flagged; the drafting rule supplies the fix pattern.

Combine them into a single criteria block for the worker prompts.

Run the [diction and clock-time scan](../book-status/references/diction-and-time.md) once on the chapter. Include the applicable rule and each passage’s candidates in its worker brief. Preserve verbatim sources and technical quantities when reviewing the author’s prose.

## Step 3: Launch Focused Workers

Use the shared [passages.py](../book-status/scripts/passages.py) extractor to partition the complete chapter by paragraph and section boundaries under the available context budget. Give each passage a stable ID and mark editable targets separately from read-only context before and after. Include nearby definitions, evidence qualifiers, referents, and rhetorical-mode instructions when they inform the target. Preserve quotations and intentional formatting. If one paragraph exceeds budget, split only at sentence boundaries, retain the common parent passage ID and source offsets, and cover every sentence exactly once.

Launch all chunks in parallel when the host supports workers; otherwise process the chunks sequentially. Keep the work in the foreground so all findings can be compiled in this run.

**Worker prompt for each chunk:**

> You are performing a comprehensive non-fiction clarity edit. Inspect all supplied context, but propose changes only inside the explicitly marked target passage(s).
>
> 1. Read the style guide at: {style_guide_path} (if it exists)
> 2. Read the chapter plan at: {plan_path} (if it exists) — note the chapter's claim, evidence blocks, and required transitions so argument moves are not flagged as clutter
> 3. Apply this scoped author-decision block verbatim, including intentional KEEP examples (do not generalize beyond scope): {applicable_editorial_decisions}
> 4. Read source revision {subject_sha256}. Target passage IDs and exact zero-based half-open Unicode code-point offsets: {target_passages}. Context before/after is read-only: {context_passages}.
> 5. Check every target passage against ALL of the following criteria:
>
> {paste the combined contents of all four criteria files}
>
> 6. Return each finding with exact quote, offsets into the exact delivered chapter string, target passage ID, reason, and smallest proposed replacement. Preserve claim strength, attribution, quantities, uncertainty, and evidence boundaries. Do not edit context-only text. Return NOTHING if no issues found:
>
> ```
> **Anchor:** `{start}:{end}` `exact quoted text` (passage `{passage_id}`)
> Category: [Jargon Density | Abstraction Ladder | Cognitive Load | Signposting | Sentence Mechanics | Style Guide Violations]
> Problem: [why it obstructs the reader]
> Fix: [specific replacement]
> ```
>
> Be thorough but avoid false positives. Technical terms of art are jargon only when the chapter's audience would not know them (check the plan's audience assumptions). A signpost is required only at a real argument move.

## Step 4: Compile Report

Collect all worker results. Deduplicate issues flagged across overlapping criteria: merge into a single finding under the primary category and keep the single best, most actionable fix. Never output contradictory rewrites for the same line.

Group into these top-level sections:

```
## Clarity Edit: [Chapter Title]

[2-3 sentence assessment — total count, severity, dominant pattern]

---

## Jargon Density Issues
### Undefined Terms of Art
### Jargon Stacking
### Banned Words

## Abstraction Ladder Issues
### Floating Abstractions
### Missing Concrete Rungs
### Ladder Inversions

## Cognitive Load Issues
### Overloaded Sentences
### Nested Clause Pileups
### One-Idea Violations
### Paragraph Load

## Signposting Issues
### Missing Transitions
### Topic Announcements
### Author-Centered Framing
### Hidden Argument Moves

## Sentence Mechanics Issues
### Passive Stance
### Nominalizations
### Hedge Mismatches

## Style Guide Violations
[any project-specific rule violations]

---

**Total issues: {count}**
**By severity:** {high/medium/low breakdown if clear}
```

Skip empty categories and sections.

For manifest-managed chapters use the `chapter_path` and `report_stem` returned by `project_state.py --root ROOT --book Book-N chapter-format --chapter SELECTOR`. Keep the normal report suffix and its companion metadata under `_Edits/Book-N/`. Numbered chapters retain their usual names.

## Step 5: Save and Report

1. Look for the chapter's `_Edits/Book-N/` folder (the same `Book-N` level as the chapter's `Chapters/Book-N/` location). If none exists, create it.
2. Save as `Chapter-NNN_ClarityEdit.md` (three-digit number matching the chapter).
3. Tell the user: location, total issue count, top 3 categories, and whether it's publishable or needs another pass.
4. Offer to apply approved items with `fiction-revise` (report-driven and book-agnostic).

## Ordering rule

Run `nonfiction-factcheck` first when the chapter contains statistics, quotes, or citations. Clarity edits reword sentences; rewording a sentence around a false fact wastes the edit and can launder the error into smoother prose.

## Current evidence and author decisions

For a saved report, follow [state-contract.md](../book-status/references/state-contract.md) using [project_state.py](../book-status/scripts/project_state.py): capture inputs BEFORE review, then record report metadata only if those inputs still match. Include every consumed chapter, plan, canon/style reference, relevant ledger, applicable editorial decision file (including its absence), and this skill's rules. Use stable finding IDs with exact quotes and blocking/nonblocking classification. No sidecar is required for a conversational verdict.

Consult applicable active editorial-memory decisions before proposing style repairs. Include the applicable scoped decision block verbatim in each focused worker brief; coordinator awareness alone is insufficient. Preserve deliberate choices within their stated scope; correctness checks remain binding. Do not generalize a local rejection. For in-place editing, record each applied finding's source quote and before/after hashes in the disposition ledger; review the resulting chapter with fresh evidence. A pre-edit PASS cannot establish post-edit readiness. Diagnostic-only skills still never edit source prose. Blind reader passes receive only reader-facing text; preference/canon checks happen in a separate coordinator pass.
