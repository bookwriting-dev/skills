---
name: fragment-hunter
description: "Targeted fragment audit for fiction prose. Extracts 1-3 word narrative sentences and dispatches workers to judge which verbless fragments need rebuilding into performable prose while preserving intentional short sentences and scoped author decisions. Use when user says 'fragment-hunter' with a chapter, or asks to fix choppy prose or prep for audiobook narration."
metadata:
  author: Fiction Toolkit
  version: "1.4.0"
  bundled-dependencies: book-status
  category: fiction-editing
---

# Fragment Hunter

Audits 1–3 word narrative sentences to separate **unperformable verbless fragments** (which starve audiobook narrators and chop up rhythm) from **complete short sentences** (`"She didn't move."`, `"The line died."`) and **intentional voice choices** permitted by the book's style policy and editorial memory.

Respect the book's resolved `style-policy` fragment rule (`project_state.py --root ROOT --book Book-N style-policy`) and active scoped decisions in `Wiki/Style/editorial-decisions.json`. Never rewrite an intentional short sentence just to inflate a fix count.

## Arguments

The request argument — Chapter reference (e.g., "258", "Chapter-258", "Chapter-258.md", "Chapters/Chapter-258.md")

---

## Step 1: Find the Chapter

1. Parse the request argument. Accept number, filename, or path.
2. Search the project files for the file (e.g., `**/Chapter-258*`). If not found, ask the user.
3. Get the line count using the host's available file or line-count operation.

---

## Step 2: Load Character Voice, Style Policy & Author Decisions

1. Identify the POV character(s) for this chapter and read their `Wiki/Style/voice_prompt_<POV>.md` (or `voice_prompt.md`) and `Wiki/Characters/<Name>.md`.
2. Run `project_state.py --root ROOT --book Book-N style-policy` to resolve the book's fragment rule and register preset.
3. Load applicable active scoped decisions from `Wiki/Style/editorial-decisions.json` (if present). Pass both the resolved fragment rule and applicable editorial decisions verbatim into every worker prompt.

The POV character's voice governs every rewrite. When expanding a genuine fragment, the replacement must sound like that character's mind and this book's register.

---

## Step 3: Read Criteria

Read [references/fragment-criteria.md](references/fragment-criteria.md).

Store its full contents. You will inject this into every worker prompt.

---

## Step 4: Mechanical Extraction (Pass 1)

Chapters are written in normal paragraph form. Multiple sentences live on the same line. A naive per-line word count will miss fragments buried inside paragraphs. You need to split by sentence boundaries first, then count words per sentence.

Run this Python script with the host's available Python interpreter to extract every candidate fragment with its source line number:

```python
python3 -c "
import re, sys

with open(sys.argv[1]) as f:
    lines = f.readlines()

for line_num, raw_line in enumerate(lines, 1):
    line = raw_line.strip()
    # Skip blank lines, headings, callouts, images, horizontal rules
    if not line or line.startswith('#') or line.startswith('>') or line.startswith('![') or line == '---':
        continue
    # Split line into sentences at . ! ? (preserve the delimiter)
    # Handles: end of sentence followed by space or end of line
    sentences = re.split(r'(?<=[.!?])\s+', line)
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        # Skip dialogue: starts with a quote mark
        if sent.startswith('"') or sent.startswith('\u201c'):
            continue
        # Skip sentences that are PART of dialogue (inside quotes context)
        # Crude check: if the line itself starts with a quote, skip all its sentences
        if line.startswith('"') or line.startswith('\u201c'):
            continue
        # Count words
        words = sent.split()
        wc = len(words)
        if 1 <= wc <= 3:
            print(f'LINE {line_num} [{wc} words]: {sent}')
" "[chapter_path]"
```

**Why Python over awk:** Sentence splitting on `.!?` boundaries needs regex lookahead. Python handles this cleanly. The script splits each paragraph line into individual sentences, skips dialogue and markdown syntax, then flags any sentence with 1-3 words.

**This is a deliberately rough candidate extractor.** It will overfire. That is by design. Pass 2 exists to judge. Known sources of false positives:

- **Abbreviations:** "Mr. Smith" splits into "Mr." (1-word hit) and "Smith..." Pass 2 catches this.
- **Decimals:** "Level 3.5 was..." may split mid-number. Pass 2 catches this.
- **Ellipses:** "And then..." produces trailing junk. The `if not sent` check catches empties, but partial splits still leak through.
- **Closing quotes/parentheses:** "He said 'fine.' The door..." splits after the period inside quotes. May flag the tail.
- **Initials:** "J. R. Tolkien" splits into letter fragments.

**Dialogue detection is also crude.** The script skips lines that start with a quote mark, but prose often mixes narration and dialogue on the same line:
- Dialogue tags after quotes ("she said.") will be caught if they are 1-3 words.
- Internal thought in italics (`*Not good.*`) looks like narration to the script.
- Free indirect style ("Of course it was. Because Zoe.") is narration and SHOULD be caught.

None of this is fatal. The mechanical pass is a net. It catches everything short. Pass 2 is the brain. It decides what actually dies.

If the hit list is empty, tell the user the chapter is clean and stop.

---

## Step 5: Context Batching

Take the candidate list from Step 4. Group the hits into batches of ~8-12 candidates each, keeping candidates that are close together (within 20 lines) in the same batch. This ensures workers see clusters of fragments together and can merge them intelligently.

For each batch, note the line range needed: from 5 lines before the first candidate to 5 lines after the last candidate in that batch.

---

## Step 6: Launch Focused Workers (Pass 2)

For EACH batch, use one isolated worker with the task description `Fragment judge batch {n}`. Launch all batches in parallel when the host supports workers; otherwise process them sequentially.

**Worker prompt template:**

> You are evaluating candidate short narrative sentences in fiction prose. A mechanical scan extracted 1–3 word sentences. Your job is to judge each one accurately: is it an unperformable verbless fragment that weakens rhythm, or a grammatically complete short sentence / intentional voice beat that earns its place?
>
> **POV Character & Voice:** {POV character name and voice summary from Step 2}. All replacements must match this voice.
> **Resolved Fragment Rule:** {style_policy.punctuation.fragments or default}.
> **Scoped Author Decisions (do not generalize beyond scope):** {applicable_editorial_decisions}.
>
> **Candidates to evaluate:**
> {paste the candidate lines for this batch, with line numbers}
>
> **Instructions:**
> 1. Read the chapter file at {chapter_path}, offset={first_line - 6}, limit={range + 10} to get full context around all candidates.
> 2. For each candidate, apply these criteria:
>
> {paste full contents of fragment-criteria.md here}
>
> 3. For each candidate, return ONE of these verdicts:
>
> **FIX** (genuine verbless fragment that hurts rhythm or performability):
> ```
> **Line {N}:** `exact quoted fragment`
> Verdict: FIX
> Word count: [1 | 2 | 3]
> Context: [the 1-2 sentences before and after]
> Problem: [one sentence: why this fragment weakens clarity or cadence]
> Fix: [the rewritten passage with the fragment merged or expanded in the POV character's voice]
> ```
>
> **KEEP** (grammatically complete short sentence, intentional voice beat, or protected by style policy / editorial memory):
> ```
> **Line {N}:** `exact quoted fragment`
> Verdict: KEEP
> Reason: [complete sentence, imperative, dialogue, scoped author decision ID, or deliberate voice beat]
> ```
>
> **FALSE POSITIVE** (the mechanical splitter misfired; not a standalone sentence):
> ```
> **Line {N}:** `exact quoted fragment`
> Verdict: FALSE POSITIVE
> Reason: [abbreviation split, decimal split, dialogue tag, mid-quote fragment, etc.]
> ```
>
> Be fair and voice-protective. A grammatically complete 2–3 word sentence (`"She didn't move."`, `"The door shut."`) is **KEEP** unless part of an unintended staccato pileup. Respect scoped author decisions and the book's register preset.

---

## Step 7: Compile Report

Collect all worker results and sort findings by line number.

**Output format:**

```
## Fragment Hunter: [Chapter Filename]

**Fixes proposed: {count}** | **Kept: {count}** | **False positives: {count}**

[2-3 sentence summary: fragment density, worst clusters, overall cadence assessment]

---

### Proposed Fixes

**Line {N}:** `exact fragment`
Words: {n} | Problem: [brief reason]
Context: [surrounding sentences]
Fix: [rewritten passage]

[repeat for each FIX, sorted by line number]

---

### Kept (Intentional / Complete)

**Line {N}:** `exact text` — [short reason or editorial-memory decision ID]

[repeat, sorted by line number]

---

### False Positives (Splitter Noise)

**Line {N}:** `exact text` — [abbreviation split / decimal / dialogue tag / etc.]

[repeat, sorted by line number]
```

Skip any section with zero entries.

---

## Step 8: Save and Report

1. Look for the chapter's `_Edits/Book-N/` folder (the same `Book-N` level as the chapter's `Chapters/Book-N/` location). If none exists, create it.
2. Save report as `Chapter-NNN_FragmentHunt.md` in that folder (three-digit number matching the chapter — the same `Chapter-NNN_<Type>.md` convention every other `_Edits` report uses, so `fiction-revise` finds it by pattern).
3. Tell the user: save location, proposed fix count, kept count, and worst clusters.
4. Offer to apply approved FIX rewrites via `fiction-revise` (which records dispositions and preserves exact quotes). KEPT and FALSE POSITIVE entries remain untouched.

---

## Step 9: Apply Approved Fixes (only if user accepts)

Prefer routing approved items through `fiction-revise`. If applying directly, walk through each approved FIX in line-number order:

1. Read the current line from the chapter file to confirm the exact quote is still present.
2. Apply only the approved replacement text.
3. Record dispositions in `_Edits/Book-N/decisions.jsonl` via `project_state.py record-disposition`.

**Do NOT touch any KEEP or FALSE POSITIVE.** If a line has shifted and the quote no longer matches, skip it and report the mismatch.

## Current evidence and author decisions

For a saved report, follow [state-contract.md](../book-status/references/state-contract.md) using [project_state.py](../book-status/scripts/project_state.py): capture inputs BEFORE review, then record report metadata only if those inputs still match. Include every consumed chapter, plan, canon/style reference, relevant ledger, applicable editorial decision file (including its absence), and this skill's rules. Use stable finding IDs with exact quotes and blocking/nonblocking classification. No sidecar is required for a conversational verdict.

Consult applicable active editorial-memory decisions before proposing style repairs. Include the applicable scoped decision block verbatim in each focused worker brief; coordinator awareness alone is insufficient. Preserve deliberate choices within their stated scope; correctness checks remain binding. Do not generalize a local rejection. For in-place editing, record each applied finding's source quote and before/after hashes in the disposition ledger; review the resulting chapter with fresh evidence. A pre-edit PASS cannot establish post-edit readiness. Diagnostic-only skills still never edit source prose. Blind reader passes receive only reader-facing text; preference/canon checks happen in a separate coordinator pass.
