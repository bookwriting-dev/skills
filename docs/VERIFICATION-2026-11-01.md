# Verification record — 2026-11-01

Library revision 2026.11.01. Implementation and tests are local working-tree changes; no existing manuscript project was upgraded.

## Executed checks

- `make check`: 78 skills, zero lint errors/warnings, current inventory; 24 Python files and three shell scripts syntax-checked; two ledger contracts pass.
- Existing behavioral eval: 11/11 pass.
- New state/workflow integration regressions: 19/19 pass. Includes source-vs-timestamp freshness, directory additions, report mutation, review input race, root containment, schema rejection, lock conflict, scoped preference supersession, correctness-waiver rejection, false beliefs/flashbacks, reader-order exposure, duplicate knowledge IDs, isolated packet content, interrupted pipeline state, campaign cycles/checks/recovery conflicts, moved project root, disposition resolution, safe upgrades, source-safe exports, internal-note stripping, system block preservation, duplicate chapter rejection, and honest unscored editorial results.
- Scaffold smoke: 29/29 pass on the local macOS environment. CI remains configured for macOS and Ubuntu; remote CI has not run in this session.
- `make export-eval`: actual beta Markdown/DOCX, submission DOCX, and publication Markdown/EPUB/PDF outputs generated successfully using installed Pandoc and Typst. Source hashes remain identical. DOCX/EPUB ZIP structures and PDF header verified. The synthetic fixture gates in this conversion test are explicitly test-only, not editorial endorsements.
- Candidate and HEAD baseline packet generation: 24 packets each, including recursively bundled rule sources and source hashes. Literary outputs/author scores are not fabricated.
- PDF preview: first rendered page inspected at 1,100 pixels; headings, TOC, Unicode punctuation, paragraphs, and footer were legible. Native DOCX preview through Quick Look failed with sandbox initialization errors; no DOCX/EPUB visual-layout approval is claimed.

## Sequential reader pilot

Three fresh isolated agents read one packet each in strict order. The first saw Chapter 1 only; the next packets contained the current chapter and the previous sealed reaction. No future text, canon, knowledge ledger, or outline was supplied. Agent references: /root/blind_chapter_1, /root/blind_chapter_2, /root/blind_chapter_3. Coordinator-condensed carried memory is explicitly marked truncated. The final run reports sealed with three checkpoints.

The first reader predicted an address/landlord connection and identified unclear pronouns and an unstated address comparison. The second retained the receipt thread, suspected the upstairs glance mattered, and reported growing frustration with repeated withholding. The final reader revised the interpretation when Jo's involvement was revealed, felt relief at an answer, and still could not reconstruct the payments or the evidence establishing the photograph as a warning. Earlier predictions were preserved instead of being rewritten to match the reveal.

These are simulated observations on a short synthetic fixture. They demonstrate the workflow; they are not real beta-reader research or evidence of commercial appeal. Full pilot records and sample export artifacts are disposable files under /private/tmp/storycraft-export-verification/.

## Pending human/expanded validation

The 24 preservation labels need author review; category tolerances and repeated matched baseline/candidate scoring remain pending. Add author-selected full chapter examples and a held-out set before claiming measured prose improvement. A longer creative revision campaign should exercise structural tasks across real chapter-length material. DOCX/EPUB rendered-layout approval remains pending. These limits are also recorded in the implementation plan and editorial evaluation guide.
