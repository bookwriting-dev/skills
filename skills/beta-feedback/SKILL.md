---
name: beta-feedback
description: "Import real beta readers' Word comments and pasted notes, including book-wide reactions, chapter ranges and strengths. Use for reader-specific changed-scene rereads, beta feedback summaries, and author-selected diagnoses or passage repairs."
metadata:
  author: Storycraft Skills
  version: "1.5.0"
  bundled-dependencies: book-status, compile-manuscript, fiction-dev-editor, revision-campaign
  category: cross-cutting
---

# Beta Feedback

Match each real reader's feedback to the archived beta edition they saw. Keep their words, edition and stated scope together. A reader can describe losing interest across an act without supplying a line number.

## Resolve the edition

Use the book, returned DOCX, or notes named by the writer. Open the frozen reader edition and use its original anchors for returned notes. Find the beta export ID in its export manifest, including previous editions retained by [compile-manuscript](../compile-manuscript/SKILL.md). If several editions could match pasted notes, use the writer's stated edition or ask which they saw. For DOCX, use the embedded export bookmark or a supplied edition. A mismatched bookmark is a conflict.

## Import and report

Run [beta_feedback.py](scripts/beta_feedback.py) with Python 3 and the arguments `--root ROOT --book Book-N --export ID`. For returned Word comments add `--docx FILE`. A bookmarked DOCX supplies its own ID if `--export` is omitted. For pasted notes, copy the original comment and any quoted text into a temporary JSON file and pass `--notes FILE`. Use the edition ID alone to list saved notes.

```json
{
  "schema_version": 1,
  "reader": "Nora",
  "notes": [
    {"comment": "I forgot why the sisters still needed each other."},
    {"chapter_range": ["Chapter 8", "Chapter 14"], "comment": "I kept waiting for Nell to make a different choice."},
    {"chapter": "Chapter 20", "kind": "strength", "comment": "I loved that they washed the dishes together."},
    {"chapter": "Chapter 8", "quote": "Clara locked the door.", "comment": "Which door is this?"}
  ]
}
```

An unquoted observation may cover the book, one chapter, or a contiguous range. Use chapter IDs, display labels, filenames without extensions, or project-relative chapter paths from the archived edition. The [scope resolver](scripts/feedback_scope.py) uses that edition's reading order. An explicit `"scope": "book"` or `chapter_range` can accompany a supporting `quote` or `anchor`. A quote must resolve uniquely or match its bookmark. Keep unresolved evidence visible and ask for clarification when it would help locate it.

Report recurring reactions and disagreements using the verbatim comments, reader names and feedback IDs. The CLI returns `groups` for passages and `scope_groups` for broader observations. Readers who comment on the same section may have different reactions there. Identify the successful passages or effects readers want to keep.

## Hand off selected feedback

Use `--campaign RUN` and repeat the relevant selection flag for each comment the writer chose.

- `--select FEEDBACK_ID` creates a pending, read-only [developmental diagnosis](../fiction-dev-editor/SKILL.md) for a book, chapter, or range observation. Read those chapters in order, cite the scene that sets up the expectation and the later choice or payoff, and check whether the current edition still produces that effect. Return the possible repair and the passages worth keeping. For a verified passage observation, selection plans a local repair and rechecks the quotation if the chapter has changed.
- `--diagnose FEEDBACK_ID` lets the writer select a margin comment for broader investigation. The investigation uses the note's stated scope or the whole book for a passage-only comment. Add `--chapter-range FIRST LAST` to give these diagnoses a specific range. The original margin anchor and reader's words stay attached.
- `--preserve FEEDBACK_ID` carries the comment into the campaign as a strength. Selecting a note already marked `"kind": "strength"` does the same. Quote what worked and protect that effect when considering a repair.

Report the planned [revision-campaign](../revision-campaign/SKILL.md) tasks and preservation constraints. Overlapping passage repairs follow the structural diagnosis. Selection authorizes planning. Author approval of a diagnosis allows reading and reporting. Apply a proposed manuscript change when the writer authorizes that revision.

## Returning beta readers

For each recipient, run the helper with `--export EARLIER_ID --reread-to REVISED_ID --reader "Name"`. [reread.py](scripts/reread.py) compares the two frozen full-book beta exports. Share the resulting reread.docx or reread.epub. Keep the passage map and manifest with the coordinator. The packet includes every new or revised scene, explains moves or removals, and quotes that recipient's earlier comments and strengths with their passage or broader scope. When an excerpt links to an omitted passage, the packet identifies its location in the full beta. Uncertain scene matches and unlocated notes retain their labels. For a returned Word packet use `--docx FILE`. For pasted EPUB comments use `--export PACKET_ID --notes FILE`. The importer saves the reaction against the archived revised manuscript edition with the packet ID. Describe the input as changed-scene excerpts when reporting what that reader reread.
