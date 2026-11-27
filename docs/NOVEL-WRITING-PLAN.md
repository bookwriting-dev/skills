# Novel-writing improvements

## Implementation order

1. **Reproduce and repair four packet defects.** Exercise the ordinary draft/preflight path with a false rumor, a later-book relationship turn inside a chapter, repeated language, and a payoff due now. Cover incomplete knowledge, legacy records, committed ledgers, intentional repetitions, and stale setup quotes.
2. **Revise story planning.** Carry the dramatic and thematic questions separately. Honor the author's structure from synopsis through scene and review. Give novel-length premise batches a middle and give significant secondary characters independent actions that affect later choices.
3. **Connect prose and review.** Carry selected examples of each narrator's prose and the shared narrator contrasts into drafting and editing. Test anonymous voice recognition. Judge pressure, cooperation, recovery, and final closure according to the scene's intended effect.
4. **Support developmental beta feedback.** Preserve book- and chapter-range observations and strengths from a frozen edition. Let selected observations create developmental diagnosis work. Keep passage-level changes tied to verified text and author selections.
5. **Compare drafts blind.** Freeze the same brief, model, and word budget against two package revisions. Produce an opening, a consequential middle choice, and a payoff for each. Give readers anonymous samples and collect their own reasons and preferences.
6. **Verify and package.** Run focused regressions, the full package check, export checks, and distribution checks. Use synthetic material for the initial comparison. Keep the existing author-chapter editorial study independent.

## Completion criteria

The four reproduced failures each have a failing-before, passing-after regression. The package instructions, templates, and runtime agree at each handoff. Authors can run the comparison, read both versions blind, and record their judgment. Human judgments remain pending until someone actually reads and submits them.

## Verification record

- Added dedicated regression suites for [draft packets](../tools/test-novel-draft-packet.py), [payoff context](../tools/test-draft-promises.py), [beta feedback](../tools/test-novel-beta.py), and the [blind comparison](../tools/test-drafting-study.py). They run in `make check`.
- The [paired craft cases](../tools/eval-fixtures/novel-planning/cases.json) exercise selective story and editorial decisions. Their labels await human review.
- The [drafting study instructions](EDITORIAL-EVALS.md#blind-comparison-of-generated-fiction) cover preparation, live generation, blind distribution, and scoring. Software verification can finish before a human has submitted a ballot.
- On November 27, 2026, `make check`, `make export-eval`, `make check-plugin`, and `make check-claude-plugin` passed. The four dedicated suites ran 30 tests. The export checks verified the beta, submission, and publication formats.
- A second pass against the original findings caught conflicting rules in the dialogue and developmental references, an act checkpoint that omitted supporting characters’ decisions, and a cold-read path limited to one file. Drafting and review now follow the scene’s intended effect through those handoffs. Two anonymous excerpts can come from separate chapters.
- Two isolated model reviewers read the same funeral-kitchen ending with different preceding scenes. One kept the handoff of the chipped bowl as Nell’s first act of trust. The other recommended cutting it because the sisters had just exchanged and put away that same bowl. A separate unprimed model reader distinguished two narrators by their attention to repair and family relationships, cited four verifiable phrases, and described where the voices overlapped. These are synthetic checks. Reader preferences for the generated fiction await human ballots.
