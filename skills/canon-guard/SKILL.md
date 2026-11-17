---
name: canon-guard
description: "Safeguard locked canon files during writing, execute impact analysis scans across drafted chapters before intentional canon updates, and safely reconcile world, character, or timeline revisions. Use when user says 'update canon', 'change world rule', 'canon conflict', 'character change impact', or 'modify canon safely'."
metadata:
  author: Storycraft Skills
  version: "1.2.0"
  bundled-dependencies: book-status
  category: cross-cutting
---

# Canon Guard & Update Manager

Protects core narrative truth from accidental drift during drafting, and manages deliberate, controlled updates to locked reference files (`Wiki/Characters/`, `Wiki/World/`, `Wiki/Style/`, or `Wiki/Story/series-arc.md`).

## Core Rules

1. **Canon is Read-Only by Default:**
   - Skills writing drafts (`fiction-writechapter`, `fiction-revise`) cannot silently mutate canon files when prose encounters an apparent mismatch.
2. **Impact Scan Before Edit:**
   - Before modifying a canon rule, character trait, or timeline anchor, run an impact scan across all existing chapters (`Chapters/Book-N/`), ledgers, and knowledge state to identify references that will become obsolete or contradictory.
3. **Explicit Confirmation & Re-Gating:**
   - Present the affected lines, obtain user confirmation within the authorized scope, apply the canon update, and trigger downstream invalidation and re-gating via `project_state.py` and `revision-campaign`.

## Procedure

### Step 1: Define Canon Change & Lock Target
- Identify the authoritative target file (e.g., `Wiki/Characters/cross.md`, `Wiki/World/magic.md`, or `Wiki/Story/series-arc.md`).
- Specify the old canon fact vs. the proposed new canon fact and confirm the authorized edit scope.

### Step 2: Run Semantic, Continuity & Knowledge Impact Scan
- Scan drafted chapters across all books (`Chapters/Book-N/`) and scene plans (`Wiki/Outline/Book-N/`) for both explicit occurrences and semantic consequences of the old fact, trait, or location.
- Consult `fiction-knowledge` (`project_state.py --root ROOT knowledge-state`) and `Wiki/Story/relationship-events.json` for supported acquisitions, suspicions, false beliefs, and reader-only exposure at each affected scene. Verify cited source hashes; missing coverage cannot establish ignorance, and intentional deception or unreliable narration must be preserved.
- Run `project_state.py --root ROOT --book Book-N continuity --action audit` and check `Wiki/Story/Book-N/promises.yaml` for linked identifiers, story clocks, object states, and setups.
- Categorize impacts:
  - **Direct Contradictions:** Explicit statements in prose, plans, or ledgers that directly violate the new rule.
  - **Implicit Tension:** Subtext, character assumptions, or downstream payoffs that need adjustment.

### Step 3: Present Impact Matrix & Confirm Scope
- Render a structured table of chapter numbers, exact line quotes, ledger/knowledge entries, and required prose or plan edits.
- Obtain user confirmation (existing explicit user authorization applies within its stated scope; confirm before expanding scope).

### Step 4: Apply Canon Update & Launch Revision Campaign / Invalidation
- Write the approved change to the target `Wiki/` file with an audit note in `Wiki/Story/active-context.md`. Because `project_state.py` hashes consumed canon directories and files in every `.meta.json` sidecar, modifying the target `Wiki/` file automatically marks affected chapter gate and review sidecars `STALE` on the next `project_state.py check` or `dashboard` run.
- For multi-chapter prose, plan, or ledger repairs, initialize or update a `revision-campaign` task graph (`project_state.py --root ROOT --book Book-N campaign`) so affected chapters, ledgers, and re-gates stay tracked until current verification succeeds. Never remove impacted reminders until fresh gate checks pass on the exact updated prose.
