# Book continuity review

Use the installed `project_state.py --root ROOT --book Book-N` commands below. The reviewer supplies claims from the actual prose. The runtime validates the source citations and compares those claims across chapters.

For calendar dates and windows, technical attributes, package inventories, and source-backed assertions, use [evidence that a scene depends on](evidence-chain.md).

## Record a chapter's evidence

1. Run `continuity --action source --chapter SELECTOR` before reviewing the authoritative chapter. Keep the returned `source_sha256` and `record_sha256` (including null for a new record).
2. Read the whole chapter for consequential identifiers, object state, clocks and durations, and counts. Check the book Wiki and earlier occurrences when assigning a key or interpreting a callback. Search the manuscript beyond adjacent chapters if an earlier occurrence is unindexed. Reuse stable keys across chapters for the same thing or event. Capture actual facts and actual claims about them. Keep intentional false beliefs, lies, dreams and hypotheticals out of the objective record unless the prose asserts the fact independently. For each claim, include `kind`, a one-based `line`, and a nonempty exact `quote` from that line.
3. Write a temporary JSON spec with `schema_version: 1`, both hashes from step 1, and the complete `claims` list. An empty list means the reviewer read this exact chapter and found no applicable claims. Use `continuity --action record --chapter SELECTOR --spec SPEC.json`. This replaces that chapter's previous evidence under a lock. On a concurrent change, compare the chapter and current claims before retrying. After prose edits, re-read and update the claims against the new source.
4. Run `chapter-format --chapter SELECTOR` and `continuity --action audit --chapter SELECTOR`. Omit the selector for a whole-book check. A chapter audit compares its claims with evidence through that chapter in reading order. Within that set, object states follow in-world story position. Whole-book reconciliation also sees later chapters, including later disclosures of earlier events.

| Kind | Additional fields |
|---|---|
| `identifier` | `key` identifies the entity, and `value` is the designation used on the page. Set `canonical: true` for an established designation and add optional `aliases` only with clear source support. Compare repeated designations against the canonical value or first sourced use. A second entity gets its own key. |
| `state` | `key` identifies an object and property, such as the condition of a particular seal. Use `value` and `operation` (`set` for a shown or explicitly established change, `assert` for a description of existing state). Set `position` to three ordered integers in **story time** and distinguish beats within a scene. A flashback may return to a smaller position than earlier text. Give different seals their own keys when the text establishes distinct objects. |
| `clock` | `clock` names the common time axis, `key` names the event, and integer `value` gives minutes from the same origin. Include day offsets across midnight. Leave unplaced events unresolved. |
| `duration` | `clock`, `start`, and `end` identify the time axis and two event keys. `value` is the stated elapsed time in minutes. Optional `tolerance` is a nonnegative number of minutes justified by approximate wording. Distinguish separate reference events before comparing their elapsed times. |
| `count` | `key` names the common collection, `snapshot` names the inventory state or count occasion, `scope` identifies the set readers can infer, and integer `value` gives the count. Use null for `scope` when the relation to the other counts is unclear to the reader. Give changed inventories new snapshot keys when the prose establishes the change. |

For a saved gate, use each audit's `inputs` to prepare the review snapshot along with the helper files and book rules used. Rerun the audits against the prepared inputs before recording the verdict. In the report, retain each finding's ID, source quotes and line numbers. Confirm that claims really describe the same entity, state, interval or set before grounding an edit on a conflict. Confirmed contradictions fail the gate. Unresolved anchors, uncertain ordering, and unclear count scope are review notes with their own source evidence. Missing or stale chapter records are explicit coverage gaps.

## Draft and release

Put a compact `Continuity keys: KEY, KEY` line in the scene plan when a previously established detail matters. The draft packet includes current earlier claims for those keys and an index of other known keys. Use `continuity --action context --chapter SELECTOR --key KEY` for another lookup. The data is production context and stays out of blind reader packets.

New fiction scaffolds activate book-wide reconciliation. On an existing book, recording the first chapter activates it. A project manifest can also set `continuity_required: true` on a book to require coverage even before a record exists. Backfill the rest of the canonical chapters before release. The exporter reruns the check over its exact manifest-resolved sources. Beta preflight reports coverage gaps and findings. Submission and publication require current coverage for an active book and block on confirmed conflicts. Review notes appear in every export profile.

## Chapter formatting

The heading uses the project's manifest display label, followed by an optional title after a spaced dash or colon. Conventional numbered layouts resolve to labels such as `Chapter 9`. Declare the label in the manifest for custom headings, including a book that deliberately displays padded numbers. The optional book-level `chapter_format` object accepts:

- `pov_style` as `plain` (`POV: Tess`), `bold_label` (`**POV:** Tess`), `bold` (`**POV: Tess**`), or `comment` (`<!-- POV: Tess -->`). Without a declared style, use the first recognized chapter or scene POV tag in reading order. A chapter range without tags defaults to the bold-label form.
- `require_pov: true` for books requiring a tag at the chapter head and each explicit scene break. By default tags are optional and checked when present. The reviewer verifies the character named in each marker against the actual opening POV and scene transitions.
- `scene_break` for a custom source scene marker. The standard `* * *` remains recognized.

The checker inspects chapter heads and scene seams. It reports file, line, and the expected convention. Submission and publication preflight block on these findings. Beta and explicitly unchecked previews carry warnings. Recognized POV comments are treated as private chapter metadata in export.
