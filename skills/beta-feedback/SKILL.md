---
name: beta-feedback
description: "Build reader-specific changed-scene reread packets and import comments returned by real beta readers from a Storycraft beta DOCX or pasted notes. Use when a writer asks to import beta-reader comments, review returned Word comments, group beta feedback, or turn selected beta feedback into revision tasks."
metadata:
  author: Storycraft Skills
  version: "1.2.0"
  bundled-dependencies: book-status, compile-manuscript, revision-campaign
  category: cross-cutting
---

# Beta Feedback

Match real reader feedback to the archived beta edition they saw. Keep reader comments verbatim and carry their origin and exact quoted passage into any selected revision task.

## Resolve the edition

Use the book, returned DOCX, or notes named by the writer. Open the frozen reader edition and use its original anchors for returned notes. Find the beta export ID in its export manifest, including previous editions retained by [compile-manuscript](../compile-manuscript/SKILL.md). If several editions could match pasted notes, use the writer's stated edition or ask which they saw. For DOCX, use the embedded export bookmark or a supplied edition. A mismatched bookmark is a conflict.

## Import and report

Run [beta_feedback.py](scripts/beta_feedback.py) with Python 3 and the arguments --root ROOT --book Book-N --export ID. For returned Word comments add --docx FILE. A bookmarked DOCX supplies its own ID if --export is omitted. For pasted notes copy the original quoted text and comment into a JSON file with schema_version 1, reader, and a notes array. Each note has comment and may have quote, chapter, and an explicit anchor. Put this input file in a temporary directory and pass --notes FILE. To list saved notes, use the edition ID alone.

The helper updates the book's feedback record and groups anchored comments by passage. Summarize recurring reactions with the source chapter and feedback IDs. Preserve individual disagreements. Report general observations and unresolved or ambiguous locations with their reader's words. Ask for a chapter, longer quote, or returned copy only when it would resolve an ambiguous anchor.

## Hand off selected feedback

Use --campaign RUN --select FEEDBACK_ID, repeating --select for each item the writer selected. The helper checks the anchor against the current manuscript and creates pending chapter tasks for [revision-campaign](../revision-campaign/SKILL.md). Report the task IDs and any passage requiring reconciliation. Apply edits only when the writer authorizes the revision itself.

## Returning beta readers

For each recipient, run the helper with --export EARLIER_ID --reread-to REVISED_ID --reader "Name". Both IDs identify frozen full-book beta exports. Share the resulting reread.docx or reread.epub. Keep the passage map and manifest with the coordinator. The packet includes every new or revised scene, explains moves or removals, and quotes that recipient's earlier comments verbatim. Uncertain scene matches and unlocated notes retain their labels. For a returned Word packet use --docx FILE. For pasted EPUB comments use --export PACKET_ID --notes FILE. The importer saves the reaction against the archived revised manuscript edition, including when drafting has continued.
