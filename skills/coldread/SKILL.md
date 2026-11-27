---
name: coldread
description: Test a voice or viewpoint claim on one complete chapter or section, or ask an unprimed reader to characterize two anonymous narrator excerpts from one or two chapters. Use for cold reads, POV checks, and questions about telling narrators apart.
metadata:
  author: Fiction Toolkit
  version: "1.2.1"
  bundled-dependencies: book-status
  category: fiction-editing
---

# Cold Read

Test what the prose communicates without letting style guides, character sheets, neighboring chapters, earlier findings, or house rules prime the reader.

The value of this skill is isolation. If the reviewer receives the intended answer or a checklist of suspected problems, the result is no longer a cold read.

## Establish the test

1. Choose claim testing or unprimed recognition. For a claim test, resolve one exact manuscript file, a complete chapter or section, and one concise claim such as `first-person narrator, sardonic but frightened`.
2. For unprimed recognition, select either a single unit or two excerpts from the same or different chapters. Choose passages that give each narrator room to notice, interpret, and respond. Freeze each source version. Keep the intended voices and distinguishing features with the coordinator until the reviewer returns their observations.
3. Use the user's wording when they provide the claim. Otherwise, the coordinating agent may retrieve the minimum claim from the book's governing instructions or approved profile before creating the isolated review.
4. Do not pass the source of the claim, style rules, character history, prior verdicts, suspected lines, or desired outcome to the cold reader.

## Preserve genuine isolation

- Give one fresh, read-only reviewer the complete claim-test unit or the entire recognition packet. In a paired test, the same reader compares both excerpts.
- Do not prescribe a provider, model family, or named model. Use a reviewer capable of qualitative fiction judgment.
- Give the reviewer the exact snapshot. Include the concise claim only for claim testing.
- If the host cannot provide a genuinely isolated context, disclose that limitation and call the result an informed assessment, not a blind read.

Use this neutral assignment:

```text
Read only the supplied manuscript file or snapshot. Do not open other project files.

After reading the complete unit, assess one question: does the prose itself read as CLAIM?

Report what convinced you, what weakened the impression, and brief anchored examples. Judge the reading experience rather than compliance with an imagined style guide. Do not propose or apply edits.
```

Do not add examples of failure modes to the assignment. Do not tell the reviewer that another pass cleared or criticized the prose.

For **unprimed recognition**, ask the reader to describe who seems to be telling each passage, what they notice, misread, or leave unsaid, and which words led to that impression. For a pair, use neutral labels such as *Excerpt A* and *Excerpt B*. Ask where the voices differ or overlap and what remains uncertain. Keep the source filenames, author-selected anchors, narrator profiles, proposed identities and answer key with the coordinator.

Preserve each passage's prose, including names spoken or mentioned in the story. Mask identifying chapter titles, POV headings, and metadata in the reader copy. Record each excerpt's label, original file path, source hash or revision, exact passage boundaries, and any heading or metadata masked. Seal the reader's response before opening the key. Verify each quotation against its excerpt and compare the reader's characterizations with the author's intended distinctions. Report when names in the prose supplied the answer or an alternative interpretation also fits.

## Evaluate the returned read

Relay the review without silently removing inconvenient findings or defending prior edits. Distinguish:

- `CONVINCING`: the claimed viewpoint or voice is consistently legible from the page.
- `MIXED`: the intended reading is present but materially weakened, intermittent, or dependent on context the isolated reader did not have.
- `NOT CONVINCING`: the page substantially delivers a different viewpoint, narrator identity, age register, or voice.

Report:

1. Verdict and confidence.
2. What the prose successfully communicated.
3. Every material point that weakened the claim, with a line, paragraph, or distinctive-text anchor.
4. Any plain clarity problem the cold reader encountered because missing context could not be supplied automatically.
5. The exact snapshot reviewed, or both source snapshots, passage boundaries, label mapping and masking for a paired read. For recognition, report the reader's own description of each voice and how distinguishable they found them.

Treat an age-register judgment as a prose judgment, not a demographic stereotype. Ground it in attention, cognition, diction, assumed experience, emotional processing, and sentence behavior shown on the page.

## Boundaries

- The cold read is diagnostic and read-only. Do not edit the manuscript unless the user's request separately authorizes revision.
- A cold read does not replace canon, continuity, style, sensitivity, or technical editorial passes.
- Do not label prose incorrect merely because the reader lacked information intentionally withheld by the story. Report the experienced ambiguity and let the coordinating editor compare it with the intended reader promise.
- If a flagged line came from an earlier agent revision and that provenance is known, state it plainly without using authorship as a defense.
- The test is most useful on a complete, stable chapter or scene. If run earlier, identify the snapshot as provisional.

## Current evidence and isolation boundary

For a saved report, follow [state-contract.md](../book-status/references/state-contract.md) using [project_state.py](../book-status/scripts/project_state.py). Capture all source files being tested and any permitted packaging before reading. For excerpts from separate chapters, prepare both chapter paths as inputs and retain the exact masked packet with the private mapping. Finalize the report only if the source snapshots still match. Keep canon, outlines, editorial decisions, source mappings and voice profiles out of the reader's assignment.
