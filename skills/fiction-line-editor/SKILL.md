---
name: fiction-line-editor
description: Focused sentence-level line editing for fiction prose (voice, cliches, repetition, POV violations, awkward constructions). Use fiction-full-editor for general sentence editing; use this skill only when isolating the line-craft and voice layer without running full craft/AIism checks. Uses focused workers for 40-line chunk scanning.
metadata:
  author: Fiction Toolkit
  version: "5.7.0"
  bundled-dependencies: book-status
  category: fiction-editing
---

# Line Editor

Focused sentence-level line editing using focused workers when supported. Each worker reads 40 lines and checks against voice and line-craft criteria. For general sentence editing that also catches AI-tells and prose mechanics, use `fiction-full-editor`.

## Arguments

The request argument is a chapter reference (e.g., "5", "Chapter-5", "Chapter-5.md", "Chapters/Chapter-5.md").

## Step 1: Find Paths, Capture Input Evidence & Load Author Decisions

1. Parse the request argument to determine the chapter. Accept number, filename, or path.
2. Search the project files for the chapter (e.g., `**/Chapter-5*`). If not found, ask.
3. Search for the project's review guide (`**/review_guide.md`), style guide (`**/style_guide.md`), and scoped `editorial-memory` records (`Wiki/Style/editorial-decisions.json`). Load applicable active editorial decisions before proposing repairs (preserving deliberate choices within their stated scope while keeping correctness checks binding).
4. Get the chapter's line count using the host's available file or line-count operation.
5. For a saved report, capture input evidence BEFORE review using [project_state.py](../book-status/scripts/project_state.py) (`prepare`) per [state-contract.md](../book-status/references/state-contract.md), including the chapter, style/review references, active editorial decision file (including its absence), and this skill's rules. (No sidecar is required for a conversational verdict; diagnostic passes never edit source prose.)
6. Match each target to its scene narrator using manuscript markers and the plan. Read the narrator’s private voice prompt and any shared contrast index. Send each worker the author-selected passage and intended effect for its scene; mark the handoff if its lines cross viewpoints. Capture both voice sources in saved evidence. `review-begin --type LineEdit` tracks the chapter’s voice files; add `--extra-path PATH` for an original anchor or additional voice source opened during review.

## Step 2: Read Criteria

Read [references/agent-instructions.md](references/agent-instructions.md).

Store its contents — you will inject them into each worker prompt alongside the applicable scoped editorial decisions.

Run the [diction and clock-time scan](../book-status/references/diction-and-time.md) once. Give each worker the applicable convention and candidates in its assigned lines.

Resolve punctuation through `project_state.py --root ROOT --book Book-N style-policy` and include its guide inputs and scoped author decisions. Apply the book’s dash rule to each passage.

## Step 3: Launch Focused Workers

Calculate 40-line chunks: lines 1-40, 41-80, 81-120, etc.

For EACH chunk, use one isolated worker with the task description `Line edit lines {start}-{end}`.

Launch all chunks in parallel when the host supports workers; otherwise process the chunks sequentially. Keep the work in the foreground so all findings can be compiled in this run.

**Worker prompt for each chunk:**

> You are a line editor scanning fiction prose. Check ONLY lines {start} through {end}.
>
> 1. Read the review/style guide at: {guide_path} — note project-specific rules, forbidden words, POV requirements, character voice patterns. If the file is not found, use general fiction craft principles.
> 2. Read the chapter using offset={start - 1} and limit=40: {chapter_path}
> 3. Apply this scoped author-decision block, including intentional KEEP examples: {applicable_editorial_decisions}. Do not generalize local decisions beyond their stated scope.
>    Read {scene_voice_anchor_and_contrast}. Identify the specific effect of a proposed voice edit and whether it preserves the narrator’s characteristic attention, rhythm and judgment.
> 4. Check every line against ALL of the following criteria:
>
> {paste the full contents of agent-instructions.md here}
>
> 5. Return your findings in this EXACT format with stable finding IDs (`LE-NNN`), exact quotes, and blocking/nonblocking classification. Return NOTHING if no issues found in your chunk:
>
> ```
> **Line {N}:** `exact quoted text`
> Category: [Cliches and Tired Phrasing | Repetition | Awkward Constructions | POV Violations | Voice Violations | Paired Adjectives for Mood | Style Guide Violations]
> Problem: [why it's a problem]
> Fix: [specific replacement text]
> ```

## Step 4: Compile Report

Collect all worker results. Group issues by category. Sort by line number within each category. Compile into this format:

```
## Line Edit: [Chapter Title]

[1-2 sentence overall assessment — issue count, severity, patterns]

---

### Cliches and Tired Phrasing
[issues sorted by line number]

### Repetition
[issues]

### Awkward Constructions
[issues]

### POV Violations
[issues]

### Voice Violations
[issues]

### Paired Adjectives for Mood
[issues]

### Style Guide Violations
[issues]

---

**Total issues: {count}**
```

Skip any category with zero findings.

## Step 5: Save, Snapshot Evidence & Report

1. Look for the chapter's `_Edits/Book-N/` folder (the same `Book-N` level as the chapter's `Chapters/Book-N/` location). If none exists, create it.
2. Save report as `Chapter-NNN_LineEdit.md` (three-digit number matching the chapter), preserving stable finding IDs and exact quotes.
3. Run `project_state.py --root ROOT snapshot` to record `_Edits/Book-N/Chapter-NNN_LineEdit.meta.json` only if the captured inputs from Step 1 still match.
4. Tell the user: location, issue count, top 3 most common categories.
5. Offer to apply approved items with `fiction-revise` (which logs dispositions and requires fresh post-edit review evidence before completion).
