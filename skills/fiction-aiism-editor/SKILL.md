---
name: fiction-aiism-editor
description: Targeted scan specifically for AI-generated fingerprints, forbidden words, and machine-sounding constructions in fiction prose. Use fiction-full-editor for general sentence editing; use this skill only when isolating the AI-tell layer. Uses focused workers for 40-line chunk scanning.
metadata:
  author: Fiction Toolkit
  version: "1.6.0"
  bundled-dependencies: book-status
  category: fiction-editing
---

# AIism Editor

Targeted scan for AI fingerprints using focused workers when supported. Each worker reads 40 lines and checks only for AI-tells. Fast and focused. For general sentence editing that also checks voice, POV, and craft mechanics, use `fiction-full-editor`.

## Arguments

The request argument is a chapter reference (e.g., "5", "Chapter-5", "Chapter-5.md").

## Step 1: Find Paths, Capture Input Evidence & Load Author Decisions

1. Parse the request argument to determine the chapter.
2. Search the project files for the chapter (e.g., `**/Chapter-5*`). If not found, ask.
3. Search for the project's review guide (`**/review_guide.md`), style guide (`**/style_guide.md`), and scoped `editorial-memory` records (`Wiki/Style/editorial-decisions.json`). Load applicable active editorial decisions before proposing repairs (preserving deliberate choices within their stated scope while keeping correctness checks binding).
4. Get the chapter's line count using the host's available file or line-count operation.
5. For a saved report, capture input evidence BEFORE review using [project_state.py](../book-status/scripts/project_state.py) (`prepare`) per [state-contract.md](../book-status/references/state-contract.md), including the chapter, style/review references, active editorial decision file (including its absence), and this skill's rules. (No sidecar is required for a conversational verdict; diagnostic passes never edit source prose.)

## Step 2: Read Criteria

Read [references/aiism-criteria.md](references/aiism-criteria.md).

Store its contents — you will inject them into each worker prompt alongside the applicable scoped editorial decisions.

## Step 3: Launch Focused Workers

Calculate 40-line chunks. For EACH chunk, use one isolated worker with the task description `AIism scan lines {start}-{end}`.

Launch all chunks in parallel when the host supports workers; otherwise process the chunks sequentially. Keep the work in the foreground so all findings can be compiled in this run.

**Worker prompt for each chunk:**

> You are scanning fiction prose for AI-generated patterns. Check ONLY lines {start} through {end}.
>
> 1. Read the review/style guide at: {guide_path} — note any project-specific forbidden words/phrases. If not found, use the criteria below only.
> 2. Read the chapter using offset={start - 1} and limit=40: {chapter_path}
> 3. Apply this scoped author-decision block, including intentional KEEP examples: {applicable_editorial_decisions}. Do not generalize local decisions beyond their stated scope.
> 4. Check every line against these criteria:
>
> {paste the full contents of aiism-criteria.md here}
>
> 5. Return your findings in this EXACT format with stable finding IDs (`AI-NNN`), exact quotes, and blocking/nonblocking classification. Return NOTHING if no issues found:
>
> ```
> **Line {N}:** `exact quoted text`
> Category: [Forbidden Words | Forbidden Phrases | Paradiastole Patterns | Over-Qualified Adverbs | Vague Abstract Descriptors | Forbidden Personification | AI Construction Patterns | Self-Announcing Narration | Noun-Swapped Dies | Math / Analytical Language]
> Problem: [why it's an AI tell]
> Fix: [specific replacement]
> ```

## Step 4: Compile Report

Collect all worker results. Group by category, sort by line number. Format:

```
## AIism Edit: [Chapter Title]

[1-2 sentence assessment — count, severity]

---

### Forbidden Words
[issues]

### Forbidden Phrases
[issues]

### AI Construction Patterns
[issues]

### Forbidden Personification
[issues]

### Vague Abstract Descriptors
[issues]

### Paradiastole Patterns
[issues]

### Over-Qualified Adverbs
[issues]

### Self-Announcing Narration
[issues]

### Noun-Swapped Dies
[issues]

### Math / Analytical Language
[issues]

---

**Total issues: {count}**
```

Skip empty categories.

## Step 5: Save, Snapshot Evidence & Report

1. Look for the chapter's `_Edits/Book-N/` folder (the same `Book-N` level as the chapter's `Chapters/Book-N/` location). If none exists, create it.
2. Save as `Chapter-NNN_AIisms.md` (three-digit number matching the chapter), preserving stable finding IDs and exact quotes.
3. Run `project_state.py --root ROOT snapshot` to record `_Edits/Book-N/Chapter-NNN_AIisms.meta.json` only if the captured inputs from Step 1 still match.
4. Tell the user: location, issue count, worst category.
5. Offer to apply approved items with `fiction-revise` (which logs dispositions and requires fresh post-edit review evidence before completion).
