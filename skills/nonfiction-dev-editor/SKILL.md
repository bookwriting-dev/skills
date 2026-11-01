---
name: nonfiction-dev-editor
description: "Diagnose argument architecture, thesis scaffolding, chapter-level conceptual progression, cognitive load, and evidence density in non-fiction drafts before prose edits. Use when user says 'nonfiction developmental edit', 'review argument flow', 'check thesis structure', 'audit conceptual progression', or 'nonfiction dev editor'."
metadata:
  author: Storycraft Skills
  version: "1.1.0"
  bundled-dependencies: book-status
  category: nonfiction-editing
---

# Non-Fiction Developmental Editor

Evaluates the structural coherence, persuasive progression, and intellectual pacing of non-fiction chapters. Identifies logical leaps, unsupported assumptions, front-loaded abstraction, and uneven evidence density.

## Diagnostic Dimensions

1. **Thesis Scaffolding:** Does each section logically build on the preceding section toward the chapter takeaway?
2. **Evidence-to-Assertion Ratio:** Are strong normative or empirical claims backed by immediate, proportionate examples or data?
3. **Abstraction Ladder Movement:** Does the text smoothly oscillate between high-level theory and concrete, real-world case studies?
4. **Cognitive Load & Reader Fatigue:** Are complex terms introduced with necessary grounding, or does conceptual density cause reader drop-off?
5. **Signposting & Chapter Handoffs:** Does the chapter set expectations early and deliver clean conceptual transitions to the next chapter?

## Output

Outputs developmental analysis report to:
`_Edits/Book-N/Chapter-NNN_DevEdit.md`.

## Current evidence and author decisions

For a saved report, follow [state-contract.md](../book-status/references/state-contract.md) using [project_state.py](../book-status/scripts/project_state.py): capture inputs BEFORE review, then record report metadata only if those inputs still match. Include every consumed chapter, plan, canon/style reference, relevant ledger, applicable editorial decision file (including its absence), and this skill's rules. Use stable finding IDs with exact quotes and blocking/nonblocking classification. No sidecar is required for a conversational verdict.

Consult applicable active editorial-memory decisions before proposing style repairs. Include the applicable scoped decision block verbatim in each focused worker brief; coordinator awareness alone is insufficient. Preserve deliberate choices within their stated scope; correctness checks remain binding. Do not generalize a local rejection. For in-place editing, record each applied finding's source quote and before/after hashes in the disposition ledger; review the resulting chapter with fresh evidence. A pre-edit PASS cannot establish post-edit readiness. Diagnostic-only skills still never edit source prose. Blind reader passes receive only reader-facing text; preference/canon checks happen in a separate coordinator pass.
