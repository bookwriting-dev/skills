---
name: fiction-prose-editor
description: Focused prose craft mechanics check for fiction (narrative fragments, choppy constructions, S-V-O chains, simile density, rule-of-threes, show-vs-tell). Use fiction-full-editor for general sentence editing; use this skill only when specifically isolating structural prose mechanics without voice or AIism checks. Uses focused workers for 40-line chunk scanning.
metadata:
  author: Fiction Toolkit
  version: "1.5.0"
  bundled-dependencies: book-status
  category: fiction-editing
---

# Prose Editor

Prose craft mechanics scan using focused workers when supported. Each worker reads 40 lines and checks for structural prose issues — not voice, not AI tells, just craft. For general sentence editing that also evaluates voice and AI-tells, use `fiction-full-editor`.

## Arguments

The request argument is a chapter reference (e.g., "5", "Chapter-5", "Chapter-5.md").

## Step 1: Find Paths, Capture Input Evidence & Load Author Decisions

1. Parse the request argument to determine the chapter.
2. Search the project files for the chapter (e.g., `**/Chapter-5*`). If not found, ask.
3. Search for the project's style guide (`**/style_guide.md`), review guide (`**/review_guide.md`), and scoped `editorial-memory` records (`Wiki/Style/editorial-decisions.json`). Load applicable active editorial decisions before proposing repairs (preserving deliberate choices within their stated scope while keeping correctness checks binding).
4. Get the chapter's line count using the host's available file or line-count operation.
5. For a saved report, capture input evidence BEFORE review using [project_state.py](../book-status/scripts/project_state.py) (`prepare`) per [state-contract.md](../book-status/references/state-contract.md), including the chapter, style/review references, active editorial decision file (including its absence), and this skill's rules. (No sidecar is required for a conversational verdict; diagnostic passes never edit source prose.)

## Step 2: Read Criteria

Read [references/prose-criteria.md](references/prose-criteria.md).

Store its contents — you will inject them into each worker prompt alongside the applicable scoped editorial decisions.

## Step 3: Launch Focused Workers

Calculate 40-line chunks. For EACH chunk, use one isolated worker with the task description `Prose scan lines {start}-{end}`.

Launch all chunks in parallel when the host supports workers; otherwise process the chunks sequentially. Keep the work in the foreground so all findings can be compiled in this run.

**Worker prompt for each chunk:**

> You are checking fiction prose craft mechanics. Check ONLY lines {start} through {end}.
>
> 1. Read the style guide at: {guide_path} — note POV rules, sentence structure preferences. If not found, use general fiction craft principles.
> 2. Read the chapter using offset={start - 1} and limit=40: {chapter_path}
> 3. Apply this scoped author-decision block, including intentional KEEP examples: {applicable_editorial_decisions}. Do not generalize local decisions beyond their stated scope.
> 4. Check every line against these criteria:
>
> {paste the full contents of prose-criteria.md here}
>
> 5. Return your findings in this EXACT format with stable finding IDs (`PE-NNN`), exact quotes, and blocking/nonblocking classification. Return NOTHING if no issues found:
>
> ```
> **Line {N}:** `exact quoted text`
> Category: [Narrative Fragments | Choppy Constructions | S-V-O Chains | Cadence Flatline | Simile Overuse | Rule of Threes | Gerund Chains | Escalation Patterns | Show vs Tell | Info Dumps]
> Problem: [what's wrong mechanically]
> Fix: [specific replacement]
> ```

## Step 4: Compile Report

Collect all worker results. Group by category, sort by line number. Format:

```
## Prose Edit: [Chapter Title]

[1-2 sentence assessment — count, severity, patterns]

---

### Narrative Fragments
[issues]

### Choppy Constructions
[issues]

### S-V-O Chains / Cadence Flatline
[issues]

### Simile Overuse / Rule of Threes
[issues]

### Gerund Chains / Escalation Patterns
[issues]

### Show vs Tell
[issues]

### Info Dumps
[issues]

---

**Total issues: {count}**
```

Skip empty categories.

## Step 5: Save, Snapshot Evidence & Report

1. Look for the chapter's `_Edits/Book-N/` folder (the same `Book-N` level as the chapter's `Chapters/Book-N/` location). If none exists, create it.
2. Save as `Chapter-NNN_Prose.md` (three-digit number matching the chapter), preserving stable finding IDs and exact quotes.
3. Run `project_state.py --root ROOT snapshot` to record `_Edits/Book-N/Chapter-NNN_Prose.meta.json` only if the captured inputs from Step 1 still match.
4. Tell the user: location, issue count, worst category.
5. Offer to apply approved items with `fiction-revise` (which logs dispositions and requires fresh post-edit review evidence before completion).
