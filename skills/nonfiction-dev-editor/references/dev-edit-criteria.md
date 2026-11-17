## Non-Fiction Developmental Editing Criteria

Developmental editing operates at the argument and chapter-architecture level. It answers: *"Does this chapter prove, illuminate, or transform what the book promised?"* It does **not** rewrite individual sentences — sentence-level clarity belongs to `nonfiction-clarity-edit`, and claim verification belongs to `nonfiction-factcheck`.

---

### 1. Thesis & Claim Spine
- **Chapter claim:** Every chapter needs one identifiable core takeaway anchored to `Wiki/Concept/thesis.md` and `Wiki/Outline/Book-N/plan.md`.
- **Falsifiability & stakes:** What belief, habit, or mental model of the reader changes by the end of the chapter? If nothing changes, the chapter is background summary.
- **Section dependency:** Each section must perform a distinct job (establish problem, introduce mechanism, supply evidence, address strongest objection, or derive practical implication). Sections that merely rephrase the chapter thesis in new vocabulary should be merged or cut.
- **Rhetorical mode fit:** Respect the chapter's declared rhetorical mode (`Wiki/Concept/structure.md` / `plan.md`) — narrative-driven, investigative, historical, tutorial, or argument-first — rather than forcing an argument-first template onto every chapter.

### 2. Evidence-to-Assertion Proportion
- **Claim proportionality:** Match evidence strength to claim scope. Universal or causal claims ("always", "causes", "proves") require comparative or causal backing; single anecdotes support illustration or hypothesis generation only.
- **Primary source grounding:** High-stakes empirical assertions must trace back to `Wiki/Research/claims-matrix.md` and `Wiki/Research/sources.yaml` (or flag an explicit `evidence_needed` gap for `nonfiction-research`).
- **Counterargument & limitation handling:** Strong non-fiction confronts the best competing explanation or boundary condition rather than dismissing strawmen. Unacknowledged limitations create brittle credibility.
- **Evidence without interpretation (and vice versa):** Data dumps without an explicit takeaway stall momentum; abstract commentary stacked 3+ paragraphs without empirical or concrete anchors floats untethered.

### 3. Abstraction Ladder & Grounding Rhythm
- Readers climb from lived specifics to unifying concepts one rung at a time.
- Check chapter-scale oscillation between high-level principles (top rungs) and named cases, numbers, mechanisms, or observable artifacts (bottom rungs).
- When multiple consecutive sections remain purely theoretical or purely anecdotal, mark a structural imbalance and identify where a concrete case or synthesis bridge must move in `plan.md`.
- See [abstraction-criteria.md](../../nonfiction-clarity-edit/references/abstraction-criteria.md) for sentence- and paragraph-level ladder diagnostics.

### 4. Cognitive Load & Concept Sequencing
- **Prerequisite discipline:** Verify against `Wiki/Concept/audience.md` that every technical framework, distinction, or historical dependency is introduced *before* downstream sections rely on it.
- **Concept budget per chapter:** A chapter introducing more than 2–3 major competing frameworks without consolidation risks reader drop-off. Recommend splitting, deferring secondary concepts, or adding a structural synthesis milestone.
- **Pacing across sections:** Alternating dense conceptual synthesis with narrative case studies or concrete walkthroughs prevents fatigue across long chapters.
- See [cognitive-load-criteria.md](../../nonfiction-clarity-edit/references/cognitive-load-criteria.md) for sentence- and paragraph-level load thresholds.

### 5. Architecture, Signposting & Chapter Handoffs
- **Promise alignment:** Compare the chapter's opening promise/question against what the closing section actually resolves. Any unresolved thread intended for a later chapter must be tracked via `promise-tracker` (`promises.yaml`).
- **Inter-chapter handoff:** Check how this chapter inherits from Chapter `N-1` (no redundant re-introduction of settled premises) and sets up Chapter `N+1` (clean conceptual bridge, not an arbitrary cliffhanger or abrupt stop).
- **Roadmap integrity:** If the chapter opens with a multi-part structural promise, confirm the section sequence delivers every part in the promised order.
- See [signposting-criteria.md](../../nonfiction-clarity-edit/references/signposting-criteria.md) for paragraph-level transition checks.

### 6. Background-Noise & Cut Test
Classify every major section or extended digression as one of:
- **Driver:** Directly advances the chapter's central claim, mechanism, or reader transformation.
- **Evidence Support:** Supplies primary backing, comparison, or objection testing required by a Driver.
- **Grounding Example:** Provides the concrete anchor needed to make an abstract Driver intelligible.
- **Tangential Excursion:** Interesting material that does not shift the chapter's central question — move to another chapter, appendix, or cut.
- **Redundant Restatement:** Repeats an argument, example, or definition already settled earlier in this chapter or an adjacent chapter.

### What a Good Non-Fiction Dev Edit Report Looks Like
- **Structural, not line-level:** Recommend "merge Sections 2 and 4," "move the 1998 case study ahead of the taxonomy," or "split the counterargument into its own bridge section" — never line edits.
- **Balanced:** Name the strongest sections and moves to preserve before recommending cuts.
- **Evidence-grounded:** Cite section headings, exact short quotes, and explicit `plan.md` / `thesis.md` obligations.
