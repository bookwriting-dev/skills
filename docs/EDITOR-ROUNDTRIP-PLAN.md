# Editor round trip for tracked changes

Status: Phases 1 to 4 implemented 2026-11-27 (uncommitted). Phase 0, testing a file from the editor's software, is open. Written 2026-11-27.

## Goal

Send an editor a Word manuscript, get it back with tracked changes and comments, review each change, and apply the accepted ones to the Markdown chapters without losing markup or overwriting newer work.

## What exists

| Piece | Where | Reuse |
|---|---|---|
| Frozen edition with export ID, source hashes, chapter bookmarks and paragraph bookmarks | `skills/compile-manuscript/scripts/beta_exchange.py` | As is |
| Word comment import and anchoring | `skills/beta-feedback/scripts/beta_feedback.py` (`word_notes`, `location`) | Reuse, with the fix below |
| Source passages with exact offsets | `skills/book-status/scripts/passages.py` | Locate paragraphs in current chapters |
| Stale review and broken quote report after manual edits | `skills/book-status/scripts/sync_edits.py` | Run after apply |

## Findings that shape the design

Tested on 2026-11-27 with Pandoc 3.14 and a small hand-built DOCX.

- `--track-changes=all` reports insertions, deletions and a paragraph merge.
- A move comes through as an unrelated deletion and insertion.
- A tracked formatting change (italic added) disappears from the report: no mode marks it.

So the importer reads `word/document.xml` directly. Pandoc stays on the export side.

Reproduced and fixed in Phase 1: a comment whose selection included a tracked change came back `UNRESOLVED`. Comments now anchor against the original (reject-all) text.

## Design

Build this inside Storycraft as one script, one skill (`editor-return`) and MCP tools in `mcp/storycraft_mcp.py`. A separate server would duplicate the edition, anchoring and staleness code.

Three steps, each its own command:

1. **Import** (writes only the ledger). Check the export ID. For each bookmarked paragraph, build the original text (insertions removed, deletions kept) and the revised text (the reverse). Save each change with an ID, author, date, chapter, before, after and status to `_Edits/Book-N/editor-returns/<export-id>/<docx-sha256>.json`.
2. **Decide.** The author accepts or rejects by change ID, or by an explicit filter such as "punctuation only in Chapter 3". Show the filter's matches before recording them. Changes default to pending.
3. **Apply.** Preview a Markdown diff by default; write only with `--apply`.

### Safety rules

- The original text of a paragraph must equal the same paragraph in the archived DOCX, which also covers unbookmarked blocks and footnotes and works when bookmarks are lost. A mismatch means an untracked edit: report it with both versions and never apply it automatically.
- Compare the whole document, including paragraphs with no revision marks, so edits made with tracking off are listed.
- Every revision element is either handled or listed as manual. An unknown one is never skipped silently.
- A change applies only if its source paragraph is unchanged in the current chapter, or matches exactly once.
- Changes to pieces of the same word are accepted or rejected as a group. (Narrowed from "one sentence", which would have tied independent fixes together.)
- `--apply` takes a token from the preview of accepted changes, so it writes only what was shown.
- Apply is all or nothing per chapter, checks the file hash again before writing, and keeps a copy of the previous text.
- After writing, extract the reader text again and confirm it equals the expected result. Restore the copy if it does not.

### The hard part: Word text to Markdown

Word shows curly quotes and dashes where the source may have `"` and `--`, and the source holds `*emphasis*`, links and private comments that Word never sees. Align the rendered paragraph with its source span character by character, change only the edited characters, and keep the rest byte for byte. If an edit crosses a markup boundary or the alignment is ambiguous, list it as manual. Write inserted text in the chapter's existing quote and dash style.

## Scope of the first version

| Change | First version |
|---|---|
| Text inserted, deleted or replaced inside a paragraph | Apply |
| Comments | Import and anchor |
| Paragraph split, merge, insertion or removal | List as manual |
| Moves, formatting changes, tables, footnotes, headers | List as manual |

## Phases

Each phase starts with a failing test in `tools/test-editor-return.py`, added to `make check`. The code is in the `editor-return` skill (`editor_return.py`, `editor_preview.py`, `editor_apply.py`); `revisions.py` stays in `beta-feedback`, which shares it.

| Phase | Deliverable | Done when |
|---|---|---|
| 0 | One real returned file from your editor's software | We know whether bookmarks and revision marks survive it |
| 1 | Read-only import and report; comment anchoring fix | Every change in the fixtures is listed; untracked edits are caught |
| 2 | Alignment and diff preview | Fixtures with smart quotes, dashes, emphasis and repeated paragraphs map correctly or are listed as manual |
| 3 | Decisions and apply | Accepting nothing leaves files identical; accepting all supported changes matches the expected text; a stale chapter is refused |
| 4 | Skill, MCP tools, docs, plugin builds | `make check`, `make check-plugin` and `make check-claude-plugin` pass |

Phase 1 is useful on its own: it gives a complete change list even if apply is never built.

## Open questions

1. What does your editor use: Word, Google Docs, Pages or LibreOffice? Bookmark survival outside the generator is untested for all of them. If bookmarks are lost, matching on archived paragraph text is the fallback, and it needs its own tests.
2. Should the editor receive the existing `beta` export, or an `editor` profile? The plan assumes `beta`, which already freezes what is needed.
