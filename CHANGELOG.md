# Changelog

Our changes to the library, newest first. Skill versions live in each SKILL.md's frontmatter and bump with every change; entries here record the why.

## 2026-10-10 — Fork declaration + first owned release

**Ownership.** This library is now ours, not a tracked-deltas copy of upstream. Two pre-fork passes (below) were recorded as deltas against the upstream ZIP; from here on, changes are ordinary development recorded in this file.

Rationale for the fork and the additions: research consensus 2024–2026 is that LLM fiction's core weakness is not surface style (which the kill-* / aiism / burstiness family already fights) but **idea-level and structural sameness** — novelty, surprise, and diversity shortfalls, and convergence on repetitive structural templates. The additions below target that layer, plus two house-keeping gaps: no setup/payoff bookkeeping, and no series-level planning.

### Added

- **`fiction-divergence` 1.0.0** — anti-convergence pass over an outline or beat plan. Generates three candidates per planned beat (default, inversion, cost-shift), selects least-expected-but-earned, checks the outline's skeleton against the genre's default template, and maintains a per-act surprise ledger. Directly targets the homogenization/convergence findings.
- **`fiction-promises` 1.0.0** — the Chekhov ledger, ported from our book-scaffold plugin and adapted to the Wiki layout. Every setup the text makes (object with weight, unanswered question, mentioned skill, threat, debt) tracked in `Wiki/Story/Book-N/promises.yaml` with a required `payoff_by_ch`; buckets overdue / due / undated. Includes a standalone `scripts/promises.py` (no plugin dependencies).
- **`fiction-series-outline` 1.0.0** — series-level planning: per-book dramatic-question stack, inter-book promise map (where `deferred_to_series` setups land), character arc spans across books, escalation plan, handoff inventory. The library was strictly single-book before.
- **`sync-check.sh`** — downloads the upstream ZIP, diffs it against `skills/`, and classifies each difference as ours (expected, per CHANGELOG) or upstream drift to review.
- **`templates/AGENTS.md`** — new skills registered in the start-of-book workflow, the per-chapter loop, and the skill index; `Wiki/Story/series-arc.md` and the per-book `promises.yaml` added to the canon layout.

### Changed

- **`fiction-outline` 5.1.0 → 5.2.0** — setup-and-consequence binding: every chapter's central conflict must bind to an earlier setup (or the premise situation) and leave a consequence a later chapter can use. Conflict from nowhere, or resolution into nothing, is a merge/cut candidate. Grounded in the narrative-planning literature (conflict injection, binding/consequence operations).
- **`fiction-reviewchapter` 2.3.0 → 2.4.0** — new Step 6: audit the Chekhov ledger. Harvests new promises from the chapter as a reader would, records on-the-page payoffs (both `paid_in_ch` and `paid_how`, or neither), and reports overdue/due/undated promises in the review.

## 2026-10-10 — Second confidently-wrong harvest pass (pre-fork)

Rationale: 13-chapter cross-walk of *Confidently Wrong* against this library. Full ledger in the mermaid project's memory (`skill-updates-2026-10-10`) and ZCode memory (`confidently-wrong-audit`).

- `fiction-reviewchapter` 2.3.0: canon-assertion audit step — unsupported specifics against the Wiki are findings.
- `fiction-story-sparks` 1.2.0: forced domain-collision lever for generic premises.
- `fiction-style` 7.0.1 + `fiction-aiism-editor` 1.1.0: marketing-register buzzword additions to `critical-donts.md` / `aiism-criteria.md`.
- `fiction-prose-editor` 1.1.0: cadence-flatline flag — 3+ consecutive same-length sentences in `prose-criteria.md`.
- `templates/AGENTS.md`: scrap-vs-patch rule in Editing.

## 2026-10-10 — First trilogy-lessons pass (pre-fork)

- `fiction-writechapter` 4.1.0: count/date + verbatim-dup completion checks, per-section POV markers, worker-brief rule-binding clause, two-sided word-floor rule.
- `fiction-reviewchapter` 2.2.0: book-layout world paths, tolerant genre-contract extraction, page-verification step.
- `fiction-world` 5.1.0: defers to the book's world layout.
- `name-generator` 1.1.0: canonization collision check.
