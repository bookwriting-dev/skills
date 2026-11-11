---
name: gate-check
description: "Run comprehensive chapter gate checks combining mechanical linting, canon integrity assertions, Chekhov setup validation, and prose quality checklists to determine chapter production readiness. Use when user says 'gate check', 'is chapter ready', 'run chapter gate', 'validate chapter', or 'check chapter continuity'. The lighter checklist gate over the same pillars as fiction-reviewchapter's full review — this is the one chapter-pipeline runs."
metadata:
  author: Storycraft Skills
  version: "1.3.0"
  bundled-dependencies: book-status
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
   - Subtext compliance against `Wiki/Psych/Book-N/Chapter_NN_Psych.md` when present: characters must not speak out loud or narrate as flat summary any thought listed under **What they won't say**, and moments in **Show-Don't-Tell Gaps** must be rendered through body, object, or silence.
   - Dialogue architecture (`fiction-dialogue`): dialogue reflects speaker register and unequal knowledge; 3+ consecutive clean question-answer pairs without deflection or action are flagged as an interview-pattern `WARN`.
5. **Mechanical, Cooling List & Machine Cadence Lint:**
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
   - Verifies stat arithmetic (points earned vs allocated), level curve milestones, skill unlock prerequisites, derived pool calculations (HP/MP), and status box format.

---

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

## Current evidence and author decisions

For a saved report, follow [state-contract.md](../book-status/references/state-contract.md) using [project_state.py](../book-status/scripts/project_state.py): capture inputs BEFORE review, then record report metadata only if those inputs still match. Include every consumed chapter, plan, canon/style reference, relevant ledger, applicable editorial decision file (including its absence), and this skill's rules. Use stable finding IDs with exact quotes and blocking/nonblocking classification. No sidecar is required for a conversational verdict.

Consult applicable active editorial-memory decisions before proposing style repairs. Include the applicable scoped decision block verbatim in each focused worker brief; coordinator awareness alone is insufficient. Preserve deliberate choices within their stated scope; correctness checks remain binding. Do not generalize a local rejection. For in-place editing, record each applied finding's source quote and before/after hashes in the disposition ledger; review the resulting chapter with fresh evidence. A pre-edit PASS cannot establish post-edit readiness. Diagnostic-only skills still never edit source prose. Blind reader passes receive only reader-facing text; preference/canon checks happen in a separate coordinator pass.

## Knowledge gate

Audit actions/dialogue against sourced knowledge acquisitions in story time, and reader exposure separately in reading order. Report premature knowledge with exact action/acquisition quotes. A supported deduction or intentional false belief is not a contradiction. Missing/stale ledger coverage is explicitly UNKNOWN and cannot clear the knowledge pillar. Knowledge WARN blocks pipeline completion until reconciled.
