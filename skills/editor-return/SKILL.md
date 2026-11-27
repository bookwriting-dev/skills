---
name: editor-return
description: "Review a Word manuscript an editor returned with tracked changes: list every change and untracked edit, preview Markdown diffs, record the author's accept or reject decisions, and apply accepted changes to chapters. Use for 'what did my editor change', 'accept my editor's punctuation fixes', or 'apply the tracked changes'. For beta readers' comments and notes use beta-feedback."
metadata:
  author: Storycraft Skills
  version: "1.0.0"
  bundled-dependencies: beta-feedback, book-status, compile-manuscript
  category: cross-cutting
---

# Editor Return

Take an editor's tracked changes from a returned DOCX into the Markdown chapters. The author decides what is accepted. Only the apply step writes chapters.

## Before sending the manuscript

Export with `compile-manuscript` using the `beta` profile and DOCX format, and send that `manuscript-combined.docx`. Ask the editor to keep track changes on. The import compares the returned file with the archived copy, so keep the export folder.

## Tools

Prefer the `storycraft_editor_return`, `storycraft_editor_decide` and `storycraft_editor_apply` tools. Each takes `root`, `book` and `docx`, plus `export` if the file lost its export bookmark. Lists are paged: follow `next_offset` until it is empty before summarizing or asking for approval.

Without those tools, run [editor_return.py](scripts/editor_return.py) with Python 3 and `--root ROOT --book Book-N --docx FILE`, adding the options below.

| Step | Tool call | Script options |
|---|---|---|
| List changes | `storycraft_editor_return` | none |
| Untracked edits, comments | `view: untracked` or `view: comments` | in the same output |
| Preview | `view: preview` | `--preview [--change ID]` |
| Preview what apply would write | `view: preview`, `accepted: true` | `--preview --accepted` |
| Decide | `storycraft_editor_decide` with `status` | `--mark STATUS` |
| Apply | `storycraft_editor_apply` with `token` | `--apply TOKEN` |

## 1. Report

The first import saves `_Edits/Book-N/editor-returns/<export-id>/<file-hash>.json`; reading the same file again returns that saved report with its decisions. Report:

- Changes by chapter, with before, after and author. `supported` marks a plain text change within one body paragraph; `reason` says why another one is manual.
- Untracked edits: paragraphs that differ from the archived copy without a revision mark. Show both versions. Formatting changed with tracking off is not detected.
- Comments with their anchored passages. To use them in a revision campaign, import the same file with `beta-feedback`.

## 2. Preview

Show the diffs and say which chapters changed since the export. List every `manual` entry with its reason: unsupported revisions, markup the edit would touch or cross, paragraphs that were rewritten or cannot be told apart, and edits whose Markdown would not read as the editor intended. Inserted punctuation follows the chapter's quote, dash and ellipsis style.

## 3. Decide

Changes start as `pending`. Record only decisions the author makes.

- By ID (`changes`, or `--change`). Edits to pieces of one word are decided together, and the output lists every affected change.
- By filter: `chapter`, `author` or `punctuation_only`. The first call only shows the matches and a `confirm` token. Show every match to the author, then repeat the call with that token.

Manual changes cannot be accepted. The author makes them by hand and may mark them rejected.

## 4. Apply

1. Preview with `accepted`. Show every diff and every `manual` entry. A chapter is written with all of its accepted changes or none, so a held chapter needs the author to reject or reset the change that cannot be placed.
2. When the author asks to write, apply with the returned `apply_token`. If chapters or decisions changed since that preview, the token is refused; preview again.
3. Report `written`, `held` and `failed`. Each written chapter has a `backup` of its earlier text.

Do not describe a change as applied unless its status is `applied`.

## Next step

For each written chapter, run `storycraft_sync_edits` with the backup path as `baseline` to find stale reviews and broken quotes.
