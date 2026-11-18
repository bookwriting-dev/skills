---
name: book-reverse-engineer
description: "Reverse-engineer an existing finished or undisciplined draft manuscript into Storycraft canon (Wiki/), scene outlines, Chekhov promises, voice profile, and defect findings. Use when user says 'reverse engineer', 'retrofit book', 'import manuscript', 'bring existing book into storycraft', 'analyze existing draft', 'rebuild undisciplined book', or 'audit raw manuscript'."
metadata:
  author: Fiction Toolkit
  version: "1.1.0"
  category: cross-cutting
  output-format: markdown
---

# Book Reverse-Engineer

Retrofit an existing, undisciplined, or externally drafted manuscript into the full Storycraft discipline without rewriting it from scratch.

This skill operates in two distinct phases separated by an explicit human review checkpoint:
1. **Analyze (Read-Only):** Reads the prose, extracts the implied story world, character roster, timeline, Chekhov promises, and voice DNA into a comprehensive analysis report (`_Edits/Book-N/reverse-analysis.md`). Flags all contradictions and dropped threads.
2. **Import (Scaffold & Populate):** Converts the reviewed report into authoritative `Wiki/` canon, retrofitted scene beat files in `Wiki/Outline/Book-N/`, a seeded `promises.yaml`, and a machine-readable defect ledger in `_Edits/Book-N/findings.yaml`.

From there, the manuscript enters the ordinary Storycraft editing loop (`fiction-dev-editor` → `fiction-revise` → `gate-check`) for surgical repairs.

---

## Step 1: Locate and Ingest the Manuscript

Locate the target manuscript:
- Look first in `_Intake/Book-N/raw-manuscript/` (staged by `new-book.sh --import`).
- If not found there, ask the user for the file path (a single `.md` / `.txt` file, or a directory of chapter files).
- Default to `Book-1` unless the user specifies another volume.

Run `scripts/manuscriptkit.py` to inspect units and word counts:

```bash
python3 .agents/skills/book-reverse-engineer/scripts/manuscriptkit.py <source-path>
```

Preview the chapter split and destination without writing prose. The preview includes front matter, the original line ranges, and any proposed replacements.

```bash
python3 .agents/skills/book-reverse-engineer/scripts/manuscriptkit.py <source-path> --export-chapters Chapters/Book-N --preview
```

---

## Step 2: Generate the Analysis Report (Read-Only)

Read the source and use the previewed chapter ranges (or the split chapter files in `_Intake/Book-N/raw-manuscript/`) and write `_Edits/Book-N/reverse-analysis.md` following [references/reverse-schema.md](references/reverse-schema.md).

Cover every section thoroughly:

1. **Character Roster:**
   - Catalog every character who speaks or acts.
   - Record traits, role, age, physical markers, and relationships.
   - Tag items as `CONFIRMED` (with chapter citations), `CANON GAP` (missing essential details), `LOW CONFIDENCE` (inferred guesses), or `CANON CONFLICT` (contradictions in the text).
2. **Setting & World Rules:**
   - Establish geography, factions, systems (magic, tech, legal, economic), and historical backstory.
   - Note any rule established in early chapters that is violated later.
3. **Timeline & Chronology:**
   - Map chronological story time vs. told order.
   - Catch timeline breaks, impossible travel times, or calendar inconsistencies.
4. **Retrofitted Chapter Beats:**
   - For every chapter, extract POV, scene goal, opposing conflict, turn/outcome, and 3–5 bulleted beats.
5. **Chekhov Ledger & Open Threads:**
   - Catalog every loaded promise, weapon, clue, or secret.
   - Mark status: `paid`, `unpaid`, or `abandoned`.
6. **Voice & Style Profile:**
   - Mechanical: POV, primary tense, dialogue-to-prose ratio, sentence burstiness.
   - List explicit `VOICE BREAK` items (accidental POV hops, tense slippage).
   - Capture 5–8 verbatim anchor passages that showcase the author's voice at its strongest.
7. **Discrepancy Punch List (`## Open Questions / Discrepancy Punch List`):**
   - Collect every flagged bullet from the report (`CANON CONFLICT`, `DROPPED THREAD`, `CANON GAP`, `VOICE BREAK`, `LOW CONFIDENCE`) into a single actionable list at the bottom.

Save the report to `_Edits/Book-N/reverse-analysis.md`.

---

## Step 3: Human Review Checkpoint (Mandatory Pause)

Stop and present the findings to the user:
- Summarize total word count, chapter count, and detected character roster.
- Highlight the major `CANON CONFLICT` and `DROPPED THREAD` items.
- Ask the user to review `_Edits/Book-N/reverse-analysis.md` and make their canonical choices (e.g., *"Is Marcus 30 or 40?"* or *"Should the silver key subplot be cut or paid off?"*).

**Do NOT proceed to Step 4 until the user approves or edits the analysis report.**

---

## Step 4: Import into Storycraft Spine

Use the approved preview and run the same command without `--preview`. The importer keeps `FrontMatter.md` beside the chapters and records the imported hashes. A rerun preserves author edits. For a reported conflict, show the diff and keep the edited file with `--keep FILE` or pass the author's approved `--replace FILE:CURRENT_SHA256:INCOMING_SHA256`. Use `missing` in place of a missing current hash. If an import was interrupted, inspect the staged operation and use `--export-chapters DIR --recover` to resume it.

After the approved prose import completes, populate the project's permanent file structure.

1. **Populate `Wiki/Characters/`:**
   - Write one file per significant character (`Wiki/Characters/<Name>.md`) based on the reviewed roster.
2. **Populate `Wiki/World/`:**
   - Create place files in `Wiki/World/Places/` and faction files in `Wiki/World/Factions/`.
   - If LitRPG/progression elements are present, populate `Wiki/World/Systems/`.
3. **Populate `Wiki/Style/`:**
   - Create `Wiki/Style/genre.md`, `Wiki/Style/audience.md`, and `Wiki/Style/style.md` using the extracted profile.
4. **Populate `Wiki/Story/`:**
   - Write `Wiki/Story/synopsis.md` and `Wiki/Story/theme.md`.
   - Seed `Wiki/Story/Book-N/promises.yaml` with the cataloged Chekhov promises.
5. **Populate `Wiki/Outline/Book-N/`:**
   - Write `Wiki/Outline/Book-N/outline.md` summarizing the overall act structure.
   - Write `Wiki/Outline/Book-N/Chapter_NN_Scene.md` for each chapter using the retrofitted beats.
6. **Generate Defect Ledger (`_Edits/Book-N/findings.yaml`):**
   Run `scripts/findings.py` on the reviewed analysis report:
   ```bash
   python3 .agents/skills/book-reverse-engineer/scripts/findings.py _Edits/Book-N/reverse-analysis.md -o _Edits/Book-N/findings.yaml
   ```

---

## Step 5: Transition to the Rebuild Loop

Report completion to the user and outline the repair path:
1. **Structural issues:** Run `fiction-dev-editor` on chapters flagged with structural defects or dropped beats.
2. **Surgical chapter repairs:** Run `fiction-revise` to fix continuity conflicts, voice breaks, and factual errors chapter by chapter against `Wiki/` canon.
3. **Verification & Gates:** Run `fiction-reviewchapter` or `gate-check` on revised chapters to ensure they are greenlit against the newly established canon.
