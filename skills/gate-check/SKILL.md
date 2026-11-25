---
name: gate-check
description: "Run comprehensive chapter gate checks combining mechanical linting, canon integrity assertions, Chekhov setup validation, and prose quality checklists to determine chapter production readiness. Use when user says 'gate check', 'is chapter ready', 'run chapter gate', 'validate chapter', or 'check chapter continuity'. The lighter checklist gate over the same pillars as fiction-reviewchapter's full review — this is the one chapter-pipeline runs."
metadata:
  author: Storycraft Skills
  version: "1.10.0"
  bundled-dependencies: book-status, litrpg-audit
  category: fiction-editing
---

# Gate Check

The definitive readiness and continuity validator for a drafted chapter. Evaluates chapter prose against canon facts, scene commitments, voice constraints, Chekhov setups, mechanical prose rules, and (for LitRPG/Progression books) mathematical progression continuity before declaring a chapter cleared for subsequent editing or final compilation.

## Gate Checklist Dimensions

Every gate run systematically evaluates up to 7 pillars:

1. **Canon Integrity (Hard Gate):**
   - Characters: names, physical states, active injuries, and active chapter-sliced `relationship_checkpoints` (`chapter_start <= N <= chapter_end`) match `Wiki/Characters/`.
   - World & Setting: locations, sensory anchors, physical distances match `Wiki/World/`.
   - Timeline: chronological continuity with preceding chapters and series timeline.
2. **Scene Contract, Micro-Friction & Beat Fulfillment:**
   - Evaluates drafted prose against `Wiki/Outline/Book-N/Chapter_NN_Scene.md` or scene plan.
   - All mandatory narrative beats, emotional shifts, and turning points must be present, dramatized (no back-half summary compression), and earned through at least one micro-friction resistance beat (failed tactic, deflection, or raised cost) rather than instant concession.
3. **Chekhov & Promise Maintenance:**
   - Any clues, objects, or dramatic setups introduced in this chapter must be registered in `promises.yaml` via `fiction-promises`.
   - Any setups resolved here must be correctly retired.
4. **Voice, POV, Subtext & Dialogue Integrity:**
   - Adherence to designated POV (Third Limited, First, etc.) and POV-matched `voice_prompt_<POV>.md` / `voice_prompt.md` with zero POV slips or head-hopping.
   - Subtext compliance against `Wiki/Psych/Book-N/Chapter_NN_Psych.md` when present: characters must not speak aloud or narrate as flat summary any thought listed under **What they won't say**. For **Show-Don't-Tell Gaps**, assess whether the chosen channel—action, perception, thought, speech, memory, omission, object, or purposeful emotional naming—fits the voice and moment. Bodily cues are optional; do not fail a chapter for choosing another earned channel.
   - Dialogue architecture (`fiction-dialogue`): dialogue reflects speaker register and unequal knowledge. Carry any scene-plan conversation form and pressure-source exception into the gate. Consecutive direct answers are not a failure by count alone; inspect whether the exchange changes knowledge, risk, permission, status, commitment, or available action. A declared form does not excuse a truly inert exchange, and arbitrary inserted evasion is not a repair.
5. **Mechanical, Cooling List & Machine Cadence Lint:**
   - Apply [diction and clock time](../book-status/references/diction-and-time.md) and run its scan on the chapter. A confirmed diction or time-format slip earns a prose WARN with the quote and correction. Exclude justified uses from the warning count. Include the shared rules and scanner in saved gate inputs.
   - Tricolon (rule-of-three) saturation rate.
   - "Not X but Y" negation density.
   - Em-dash clusters (>10 in a scene).
   - Paragraph-closing aphorisms.
   - Stock sensory repetitions (dust, paper must, brass warmth, creaking wood) and trailing 3-chapter `cooling_list` violations (reused somatic hotspots, repeated 3-grams/similes, or repeated chapter opener/closer formulas from `project_state.py draft-packet`).
6. **Closing Beat & Transition:**
   - Chapter ending leaves a distinct forward momentum or deliberate unresolved hook (avoiding homogeneous quiet-tea reflective resolutions on 100% of chapters).
7. **LitRPG & Numeric Continuity (Conditional Gate):**
   - When the project defines a system (`Wiki/World/Systems/`) or is classified as LitRPG / Progression Fantasy:
   - Run `python3 .agents/skills/litrpg-audit/scripts/stat_audit.py Chapters/Book-N/Chapter-NNN.md`.
   - Inspect `rule_results` for points, level thresholds, skills, pools, resources, inventory, incapacitation and display length. Record source-linked violations as FAIL and unresolved progression coverage as WARN on the continuity pillar. Read the [audit rules](../litrpg-audit/references/audit-rules.md) when the ledger cannot resolve one of the checks.

---

## Procedure

1. **Step 1: Capture Input Evidence & Load Author Decisions**
   - For a saved gate report, follow [state-contract.md](../book-status/references/state-contract.md) using [project_state.py](../book-status/scripts/project_state.py) (`review-begin --chapter N --type Gate`, or `prepare --spec` for custom paths): capture inputs BEFORE review, including the target chapter, preceding chapter, scene plan, psych pass, canon/style references, relevant ledgers, active `editorial-memory` decision file (including its absence), and this skill's rules. (No sidecar is required for a conversational verdict; diagnostic gate runs never edit source prose.)
   - Consult applicable active `editorial-memory` decisions before proposing style repairs, preserving deliberate choices within their stated scope while keeping correctness checks binding. Include scoped decisions verbatim in any worker briefs; never generalize a local rejection.

2. **Step 2: Run Format, Continuity & Evidence-Chain Checks**
   - Follow [book continuity review](../book-status/references/continuity-review.md): run `project_state.py --root ROOT --book Book-N chapter-format --chapter SELECTOR` and treat its findings as mechanical failures. Verify each marked POV against the actual prose.
   - Capture the source hash, review the complete unannotated chapter, and record sourced continuity claims (`continuity --action record`) before running `continuity --action audit --chapter SELECTOR`. Cite competing passages for confirmed contradictions and record unresolved ordering, time anchors, and count scope as editorial notes.
   - For scenes that depend on earlier events, technical conditions, or inferences, check consequential assertions against their sources using [evidence that a scene depends on](../book-status/references/evidence-chain.md), including cited manuscript or retained research sources in the gate's input snapshot. Report stale or missing support as a gate blocker when the plot depends on it.

3. **Step 3: Audit Knowledge & Story Pillars**
   - Audit character actions and dialogue against sourced knowledge acquisitions in story time (`knowledge-state --observer CHARACTER --story-order N`), and reader exposure separately in reading order (`--observer reader --reader-order N`). Report premature knowledge with exact action and acquisition quotes; preserve supported deductions and intentional false beliefs. Missing or stale knowledge-ledger coverage is `UNKNOWN`, and knowledge `WARN` blocks pipeline completion until reconciled.
   - Evaluate all 7 Gate Checklist Dimensions above (including `promises.yaml` and `litrpg-audit` when applicable).

4. **Step 4: Save Report, Snapshot Metadata & Route**
   - Save `_Edits/Book-N/Chapter-NNN_Gate.md` with stable finding IDs, exact quotes, and blocking/nonblocking classification.
   - Record `_Edits/Book-N/Chapter-NNN_Gate.meta.json` via `project_state.py review-finish --prepared ... --verdict ...` (or `snapshot`) only if the inputs captured in Step 1 still match.
   - After any authorized prose repair, recheck formatting, refresh continuity/knowledge evidence from the resulting prose, and re-run the gate — a pre-edit `PASS` never establishes post-edit readiness.

For manifest-managed chapters use the `chapter_path` and `report_stem` returned by `project_state.py --root ROOT --book Book-N chapter-format --chapter SELECTOR`. Keep the normal report suffix and its companion metadata under `_Edits/Book-N/`. Numbered chapters retain their usual names.

## Output Contract

Gate check produces a timestamped run report saved to:
`_Edits/Book-N/Chapter-NNN_Gate.md`

```markdown
# Chapter Gate Report: Chapter NNN (Book N)
**Timestamp:** YYYY-MM-DD HH:MM  **Status:** [PASS / WARN / FAIL]  **Run:** #1

## Summary
- **Canon Violations:** 0
- **Unfulfilled Scene Beats:** 0
- **Chekhov Debt (Unregistered setups):** 0
- **Progression & Stat Inconsistencies:** 0  *(LitRPG only)*
- **Cadence & Lint Warnings:** [N]

## Detailed Assessment

### 1. Canon & Timeline: [PASS / FAIL]
- [Details with line citations]

### 2. Scene Contract: [PASS / FAIL]
- [Target beats matched to chapter paragraphs]

### 3. Setup & Promise Register: [PASS / ACTION REQUIRED]
- Setups introduced: [List]
- Promises paid: [List]

### 4. POV & Dialogue Integrity: [PASS / WARN]
- [POV slips or dialogue notes]

### 5. Cadence & Lint Flags: [PASS / WARN]
- [Flagged sentences with exact quotes and line numbers]

### 6. LitRPG Progression Audit: [PASS / WARN / FAIL / N/A]
- [Stat math, skill checks, and status box findings from stat_audit.py]

## Action Verdict & Routing
- If **PASS**: Cleared for chapter progression or `fiction-full-editor`.
- If **FAIL (Structural / Canon / Progression)**: Route back to scene plan or `litrpg-audit` to fix mathematical contradictions.
- If **WARN (Prose / Cadence)**: Route directly to `fiction-revise` or `kill-chapter`.
```
