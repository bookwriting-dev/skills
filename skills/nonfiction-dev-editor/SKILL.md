---
name: nonfiction-dev-editor
description: "Diagnose argument architecture, thesis scaffolding, chapter-level conceptual progression, cognitive load, and evidence density in non-fiction drafts before prose edits. Use when user says 'nonfiction developmental edit', 'review argument flow', 'check thesis structure', 'audit conceptual progression', or 'nonfiction dev editor'. Also use for fresh-reader walkthroughs of nonfiction exercises."
metadata:
  author: Storycraft Skills
  version: "1.4.0"
  bundled-dependencies: book-status, nonfiction-clarity-edit
  category: nonfiction-editing
---

# Non-Fiction Developmental Editor

Evaluates the structural coherence, persuasive progression, and intellectual pacing of non-fiction chapters or chapter ranges, and when explicitly authorized repairs `Wiki/Outline/Book-N/plan.md`. Matches the deliverable to the user's request instead of automatically generating a long report.

## Authority and Scope

Follow the user's current instruction first, then project `AGENTS.md`, `Wiki/Concept/`, `Wiki/Research/`, and existing workflow rules. Developmental work concerns thesis alignment, argument causality, evidence proportionality, prerequisite sequencing, cognitive load, and inter-chapter handoffs. It does not authorize sentence-level rewriting (`nonfiction-clarity-edit`), unverified fact claims (`nonfiction-factcheck`), or inventing sources.

## Choose a Mode

- **Quick verdict:** For targeted questions ("Does this chapter prove its claim?", "Is Section 3 a tangent?"). Answer directly in conversation; do not save a report file.
- **Focused diagnosis:** For one chapter when analysis is requested without a saved report. Surface the highest-impact structural findings and concrete restructuring moves.
- **Edit in place:** When explicitly asked to revise or restructure `Wiki/Outline/Book-N/plan.md` (not prose). Diagnose internally, update the chapter's `plan.md` section, verify alignment with `structure.md`, and summarize the structural changes.
- **Full developmental report:** When the user requests a saved dev edit/report over a chapter or range, or when `chapter-pipeline` (`full_editorial_candidate`) requires durable evidence at `_Edits/Book-N/Chapter-NNN_DevEdit.md`.

## Step 1: Load Context & Capture Input Evidence

1. Resolve the target chapter (`Chapters/Book-N/Chapter-NNN.md`) or chapter range through the project manifest/layout.
2. Read the core planning and research context proportional to the request:
   - `Wiki/Outline/Book-N/plan.md` (the chapter's claim, evidence blocks, rhetorical mode, transitions, and `evidence_needed` notes)
   - `Wiki/Concept/thesis.md`, `Wiki/Concept/audience.md`, and `Wiki/Concept/structure.md`
   - `Wiki/Research/claims-matrix.md` and `Wiki/Research/sources.yaml` (when empirical claims or citations appear)
   - Immediate predecessor/successor chapters or plan sections to check handoffs and redundancy
   - Applicable active `editorial-memory` decisions (`Wiki/Style/editorial-decisions.json`), preserving deliberate structural/voice choices within their stated scope while keeping factual and correctness checks binding.
3. For a saved report, follow [state-contract.md](../book-status/references/state-contract.md) using [project_state.py](../book-status/scripts/project_state.py) (`prepare`): capture inputs BEFORE analysis (target chapter(s), `plan.md`, `Wiki/Concept/` files, relevant `Wiki/Research/` files, active editorial decision file including its absence, and this skill's rules). (No sidecar is required for a conversational verdict; diagnostic modes never edit source prose.)

## Step 2: Run the Argument-Spine & Background-Noise Tests

Before auditing micro-pacing or clarity mechanics, test the chapter's structural backbone:

1. **Reader's starting state:** What belief, misconception, or practical problem does the target reader (`audience.md`) bring into this chapter?
2. **Core chapter claim:** Can the chapter's central assertion or takeaway be stated in one falsifiable or actionable sentence matching `plan.md`?
3. **Causal / logical turn:** What evidence, mechanism, or counterargument forces the reader to update that belief?
4. **Proof vs. assertion test:** Are load-bearing claims backed by primary evidence/cases rather than repeated assertions?
5. **Reader transformation:** What concrete capability, mental model, or open question (`promises.yaml`) is different at chapter end?
6. **Cut test:** What would the book's overall thesis (`thesis.md`) lose if this chapter vanished or merged into an adjacent chapter?

Classify every major section using the **Background-Noise Test** in [references/dev-edit-criteria.md](references/dev-edit-criteria.md) (`Driver`, `Evidence Support`, `Grounding Example`, `Tangential Excursion`, `Redundant Restatement`).

## Step 3: Evaluate the 5 Developmental Dimensions

Read [references/dev-edit-criteria.md](references/dev-edit-criteria.md) and cross-reference the chapter-scale structural layers against:
- [abstraction-criteria.md](../nonfiction-clarity-edit/references/abstraction-criteria.md) (concept-to-concrete oscillation across whole sections)
- [cognitive-load-criteria.md](../nonfiction-clarity-edit/references/cognitive-load-criteria.md) (concept budget, prerequisite order, and section fatigue)
- [signposting-criteria.md](../nonfiction-clarity-edit/references/signposting-criteria.md) (promised roadmap integrity and structural transitions)

Evaluate all five dimensions:
1. **Thesis Scaffolding & Mode Fit:** Each section builds logically toward the chapter takeaway without violating the planned rhetorical mode.
2. **Evidence-to-Assertion Proportion:** Empirical/normative claims match their backing; ungrounded gaps are flagged for `nonfiction-research`; counterarguments are steel-manned.
3. **Abstraction Ladder Movement:** Whole sections neither float in pure theory for pages nor dump raw anecdotes without synthesis.
4. **Cognitive Load & Prerequisite Sequencing:** Terms and frameworks appear only after necessary grounding for `audience.md`.
5. **Signposting & Inter-Chapter Handoffs:** Opening expectations match delivered structure, and ending bridges cleanly to Chapter `N+1`.

If running focused workers on a multi-chapter range, pass each worker its exact chapter/plan paths, [references/dev-edit-criteria.md](references/dev-edit-criteria.md) verbatim, and the applicable scoped `editorial-memory` block verbatim.

## Step 4: Save Report, Snapshot Metadata & Route

1. For full report mode, save `_Edits/Book-N/Chapter-NNN_DevEdit.md` (creating `_Edits/Book-N/` if absent) using only sections with actionable findings:
   - Verdict (`PASS` / `WARN` / `FAIL` for `.meta.json` compatibility) + `Structural Action` (`PASS` / `REVISE_PLAN` / `REORDER_SECTIONS`)
   - Argument Spine & Section Classification table (`Driver` / `Support` / `Example` / `Tangent` / `Redundant`)
   - Findings ranked by structural impact with stable finding IDs (`NFDEV-001`, etc.), exact section/quote evidence, and `blocking` / `nonblocking` classification
   - Prioritized structural repairs (`merge`, `split`, `reorder`, `cut`, `supply evidence`)
   - Strengths to preserve
2. Finalize `_Edits/Book-N/Chapter-NNN_DevEdit.meta.json` via `project_state.py --root ROOT review-finish` (or `snapshot`, using `PASS` / `WARN` / `FAIL`) only if the inputs captured in Step 1 still match.
3. Route repairs explicitly:
   - Structural defects (missing argument steps, broken sequencing, wrong rhetorical framing) go back to `nonfiction-chapter-plan` (`Wiki/Outline/Book-N/plan.md`) followed by a re-draft in `nonfiction-writechapter` — do **not** try to patch structural holes with line edits.
   - Missing primary citations or unverified data route to `nonfiction-research`.
   - Once structure and evidence are sound, route prose verification to `nonfiction-factcheck` followed by `nonfiction-clarity-edit`.

## Fresh-reader walkthrough

When the author asks whether a reader can follow a chapter, or a substantial exercise needs a practical check, prepare the reader chapter with [editorial_tools.py](../book-status/scripts/editorial_tools.py) with `--root . --book Book-N walkthrough --chapter SELECTOR`. Deliver only the returned chapter and this brief to a fresh isolated reader in a clean directory. Keep outlines, Wiki files, author notes, evaluators' expectations and other chapters outside that session. Copy the packet as data. Do not let the reader inspect the book checkout.

Ask the reader to follow the instructions in order using only what the chapter supplies. For an exercise that can be tried safely with disposable local materials or an in-memory simulation, actually attempt it. Record the input, actions taken and observed result. For an external, costly, sensitive or unavailable step, explain which step was reasoned through and which remains untested. On the first missing prerequisite or ambiguous decision, quote the exact step, say what information the reader had, what they needed and where they stopped. On success give the actual result and the passage that made it possible. The coordinator checks quoted evidence before suggesting the smallest clarification. If a fresh reader is unavailable, label the independent walkthrough pending.
