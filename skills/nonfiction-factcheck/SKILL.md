---
name: nonfiction-factcheck
description: "Verify every claim, quote, statistic, date, and proper noun in a non-fiction chapter against the book's research corpus and cited sources. Flag unsupported, contradicted, misattributed, and imprecise assertions. Use when user says 'fact check', 'verify', 'check citations', 'are the sources right', or after drafting a non-fiction chapter. Output goes to _Edits/Book-N/."
metadata:
  author: Nonfiction Toolkit
  version: "1.4.0"
  bundled-dependencies: book-status
  category: nonfiction-editing
  output-format: markdown
---

# Nonfiction Fact Check

Verify every factual assertion in the chapter against the book's research corpus and cited sources. An unsupported assertion is a finding, not texture: the reader's trust is the book's core asset, and one false number dents it everywhere else.

## Arguments

The request argument is a chapter reference (e.g., "5", "Chapter-5", "Chapter-5.md", "Chapters/Chapter-5.md").

## Step 1: Find Paths and Sources

1. Parse the request argument to determine the chapter. Accept number, filename, or path.
2. Search the project files for the chapter (e.g., `**/Chapter-5*`). If not found, ask.
3. Locate the research corpus — the authoritative evidence the chapter cites. Search in priority order for:
   - `**/Research/**/*.md` and `**/Research/**/*.yaml` (or the `**/Wiki/Research/**` variants): source notes, study summaries, interview records — and `sources.yaml`, the citation registry `nonfiction-research` writes; claims cite its source ids, so it is the first thing to load
   - `**/Wiki/Sources/**` or `**/sources.md` or `**/bibliography.md` (citation registry)
   - The chapter plan's `fact_status` table and citation fields (from `nonfiction-chapter-plan`)
   - Any file the chapter's citations name directly
4. Search for the project's style or review guide (`**/review_guide.md`, `**/style_guide.md`) for house citation rules.
5. Resolve the canonical chapter path/revision through the project resolver where available. Do not use line numbers as assertion identity.

If no research corpus exists at all, report that verification is impossible and recommend building one (`nonfiction-chapter-plan` records per-assertion fact status during planning). Never accept the draft's own statements as their own source.

## Step 2: Read Criteria

Read ALL reference files and combine their contents into a single verification block for the worker prompts:

- [verification-criteria.md](references/verification-criteria.md) — the master per-assertion checks
- [assertion-taxonomy.md](references/assertion-taxonomy.md) — what counts as an assertion and how each type is verified
- [common-failures.md](references/common-failures.md) — known failure patterns with examples and fixes
- [severity-rubric.md](references/severity-rubric.md) — status and severity classification

## Step 3: Extract Every Assertion

Sweep the chapter and build the assertion inventory before verifying anything. Every one of these is an assertion:

- **Statistics:** numbers, percentages, effect sizes, p-values, sample sizes, dates, durations
- **Quotes:** quoted material, block quotes, and near-verbatim paraphrases presented as someone's words
- **Claims:** causal, comparative, superlative, and definitional statements
- **Proper nouns:** names of people, institutions, studies, places, works
- **Attributions:** who said what, who found what, who holds which position

Assign each a stable assertion ID, claim type, and exact quote with zero-based half-open Unicode code-point offsets into the current delivered chapter string and its hash. Multiple claims on one sentence/line get distinct IDs. Include scope, population, units, attribution, certainty, and claim strength where applicable. Complete a semantic coverage sweep of the entire chapter and record the reviewer, method, exact revision, omissions, and limitations; schema-valid listed claims do not prove the inventory is complete.

## Step 4: Launch Focused Workers

Split the assertion inventory into balanced batches by assertion IDs, with target claims separated from read-only surrounding context. Give each worker the exact source revision and permitted source passages. Do not use fixed line chunks as context boundaries.

Launch all batches in parallel when the host supports workers; otherwise process sequentially. Keep the work in the foreground so all findings compile in this run.

**Worker prompt for each batch:**

> You are verifying non-fiction assertions. Assess ONLY the listed target assertion IDs; inspect surrounding context to preserve meaning.
>
> 1. Read the exact chapter revision {subject_sha256}; target IDs/quotes/offsets: {target_assertions}; context is read-only: {context}
> 2. For every empirical assertion, inspect its source record and exact passage in the research corpus: {source_paths}
> 3. Check every assertion against ALL of the following criteria:
>
> {paste the combined contents of all four reference files}
>
> 4. Return your findings in this EXACT format. Return NOTHING if all assertions verify:
>
> ```
> **Assertion:** `{assertion_id}` `{start}:{end}` `exact quoted text`
> Type: [factual | quotation_attribution | inference | definition | testimony | normative_judgment | hypothetical_illustration]
> Status: [verified | unsupported | contradicted | misattributed | imprecise | unverifiable | not_empirical | pending]
> Severity: [critical | high | medium | low]
> Source: [what the source actually says, with location]
> Fix: [corrected text, or the verification the author must supply]
> ```
>
> The draft itself, a previous chapter, general memory, and plausible-sounding knowledge are NOT evidence. Only the research corpus and cited sources count. If the corpus genuinely lacks the source, mark the assertion `unverifiable` — do not guess.

## Step 5: Compile Report

Collect all worker results. Deduplicate by line number (the same assertion flagged under multiple categories merges into one finding with the most specific status). Group into sections:

```
## Fact Check: [Chapter Title]

[2-3 sentence assessment — total assertions checked, failure count, dominant failure pattern]

---

## Critical Findings
[fabricated, contradicted, or misquoted material — must fix before anything else]

## Unsupported Assertions
[claims with no source in the corpus]

## Imprecise Assertions
[real but miscalibrated: wrong hedge, missing denominator, false precision]

## Misattributions and Quote Drift
[wrong name, wrong year, altered wording]

## Unverifiable
[assertions whose source the corpus does not contain — author must supply or cut]

## Verified Clean
[count of assertions that matched their sources exactly]

---

**Assertions checked: {total}**
**Findings: {count}**
**By severity:** {critical/high/medium/low breakdown}
```

Skip empty sections.

## Step 6: Save and Report

1. Look for the chapter's `_Edits/Book-N/` folder (the same `Book-N` level as the chapter's `Chapters/Book-N/` location). If none exists, create it.
2. Save as `Chapter-NNN_FactCheck.md` (three-digit number matching the chapter).
3. Run [evidence.py](../nonfiction-research/scripts/evidence.py) on the exact chapter evidence record. Report readiness and coverage separately from the semantic review; never infer publication approval from a fact-check result.
4. Offer to apply approved findings with `fiction-revise` (report-driven and book-agnostic; it verifies every quote and keeps a change ledger).

## Verification rules

- **The page governs.** Re-derive every number, date, and quotation from the current chapter text; do not trust a prior fact-check's rulings.
- **No silent repair.** Never change a number or quote in the chapter during the check. Report the discrepancy; the author decides.
- **Calibration is a finding.** A true claim stated with stronger language than its evidence supports (correlation rendered as causation) is flagged imprecise, not passed.
- **Context stripping counts.** A real quote severed from the meaning of its source is a misquote of substance.
- **Critical and High findings gate the next pass.** Run `nonfiction-clarity-edit` only after they are resolved — polishing prose around a false fact wastes the edit.

## Current evidence and author decisions

For a saved report, follow [state-contract.md](../book-status/references/state-contract.md) using [project_state.py](../book-status/scripts/project_state.py): capture inputs BEFORE review, then record report metadata only if those inputs still match. Include every consumed chapter, plan, canon/style reference, relevant ledger, applicable editorial decision file (including its absence), and this skill's rules. Use stable finding IDs with exact quotes and blocking/nonblocking classification. No sidecar is required for a conversational verdict.

Consult applicable active editorial-memory decisions before proposing style repairs. Include the applicable scoped decision block verbatim in each focused worker brief; coordinator awareness alone is insufficient. Preserve deliberate choices within their stated scope; correctness checks remain binding. Do not generalize a local rejection. For in-place editing, record each applied finding's source quote and before/after hashes in the disposition ledger; review the resulting chapter with fresh evidence. A pre-edit PASS cannot establish post-edit readiness. Diagnostic-only skills still never edit source prose. Blind reader passes receive only reader-facing text; preference/canon checks happen in a separate coordinator pass.
