# Storycraft Skills Library — Audit Report

**Date:** 2026-10-10
**Scope:** `skills/` (47 skills), `templates/AGENTS.md`, `templates/CLAUDE.md`, `new-book.sh`, `sync-check.sh`, `CHANGELOG.md`, `sync-manifest.txt`
**Method:** Full read of all 47 `SKILL.md` files (5,455 lines), reference/criteria files, templates, and scripts; frontmatter extraction via `grep`; line counts via `wc -l`; cross-check of `workflow-position` / `requires` / `next-skill` chains against `AGENTS.md` ordering; verification of `kill-chapter` pass coverage against `references/` contents.
**Status:** Findings and recommendations only. No library files were modified for this report.

---

## 1. Executive summary

The library is in good shape at the strategic level: the fork is clean, the CHANGELOG rationale is strong, and the three newest skills (`fiction-divergence`, `fiction-promises`, `fiction-series-outline`, plus `fiction-review-panel` / `drift-check`) correctly target idea-level and book-level weaknesses rather than more surface linting.

The problems are all at the **routing and overlap layer**. The library has grown by accretion — each harvest pass bolted a step onto `fiction-reviewchapter` and added a new scan skill — and no pass has ever narrowed a description or removed an entry point. The result:

| # | Finding | Severity |
|---|---------|----------|
| F1 | Editing stack: 4 near-identical 40-line scanners + 6 single-issue scans = 10 entry points for "check my prose" | **High** |
| F2 | Kill family inconsistent: `kill-chapter` runs 4 of 7 passes; `kill-crutch` already generalizes `kill-soft`/`kill-flat` | **High** |
| F3 | Review stack has no routing rule (`dev-editor` **or** `reviewchapter`) | **High** |
| F4 | `fiction-reviewchapter` becoming a god-skill (218-line orchestrator, 10 criteria, 8 steps) | **Medium-High** |
| F5 | No owned revise loop (every skill reports; none owns applying fixes) | **Medium** |
| F6 | Metadata + workflow-chain contradictions (4 skills lack version block; position chain contradicts AGENTS.md) | **Low effort, do first** |
| F7 | Name/place generator trigger overlap across 4 skills | **Low-Medium** |

Recommended order: **F6 → F2 → F1 → F3/F4 → F5 → F7.** F6+F2 are mechanical and safe. F1 needs one content decision (Option A vs B below). F3–F5 are structural and should be designed together.

---

## 2. Inventory baseline (verified)

- **47 skills** in `skills/`. Total `SKILL.md` body: 5,455 lines.
- Largest orchestrators: `fiction-reviewchapter` (218 lines SKILL.md, 655 lines with references), `fiction-world` (189 / 572), `fiction-psych` (187 / 283), `fiction-style` (180 / 2,201 — large `assets/` + `references/`), `fiction-outline` (175 / 839), `fiction-scenes` (146 / 980), `fiction-genre` (106 / 5,507 — large data assets).
- Criteria references for the editing scanners are small and overlapping: `agent-instructions.md` (80 lines), `prose-criteria.md` (77 lines), `aiism-criteria.md` (142 lines).
- `kill-chapter/references/` contains exactly 4 rule-sets: `crutch.md`, `flat.md`, `simile.md`, `soft.md`.
- Git head at audit time: `a606b30 feat: persona-panel harvest`. `sync-manifest.txt` tracks 22 owned files.

---

## 3. Findings with evidence

### F1 — Editing-stack overlap (High)

Four skills share the same 5-step scaffold (find paths → read criteria → fan out 40-line workers → compile by category → save to `_Edits/`):

- `skills/fiction-line-editor/SKILL.md:16` — "Comprehensive sentence-level editing using focused workers… Each worker reads 40 lines."
- `skills/fiction-prose-editor/SKILL.md:17` — "Prose craft mechanics scan using focused workers… Each worker reads 40 lines."
- `skills/fiction-aiism-editor/SKILL.md:16` — "Targeted scan for AI fingerprints using focused workers… Each worker reads 40 lines."
- `skills/fiction-full-editor/SKILL.md:16` — "Runs every micro-level check in a single pass. Each focused worker scans its 40-line chunk against the complete criteria set: AIisms + prose craft + line editing."

`fiction-full-editor/SKILL.md:30-36` confirms it is the union of the other three (reads all three criteria files and combines them). Meanwhile `fiction-line-editor/SKILL.md:3-7` claims AIisms, fragments, POV, voice, show-vs-tell, and repetition — i.e. its advertised scope already covers large parts of the prose-editor and aiism-editor scopes.

Six further single-issue scan skills use the same chunk-scan/report shape: `burstiness-check`, `pangram`, `drift-check`, `levelup`, `fragment-hunter`, `nominalization-hunt`.

**Impact:** The agent router (and the human user) must choose among ~10 entry points for "check my prose." Overlapping descriptions guarantee inconsistent invocation and duplicate findings across passes (the same line flagged as an AIism, a prose-mechanics issue, and a line-edit issue with three different fixes). `templates/AGENTS.md:95-97` lists them as flat lists with no selection rule, which codifies the ambiguity.

### F2 — Kill-family inconsistency (High)

- `skills/kill-crutch/SKILL.md` is already the generalized pass ("Hunt **any** crutch/filler word… the generalized version of `kill-soft` and `kill-flat`"). `kill-soft` and `kill-flat` nevertheless remain as standalone skills with near-identical scaffolding.
- `skills/kill-chapter/SKILL.md:32-35` runs exactly four passes in sequence: simile, crutch, soft, flat. The three newer kill skills — `kill-the-whole`, `kill-person-who`, `kill-opinion-personification` — are not in the sequence and have no corresponding files in `kill-chapter/references/`.
- Net effect: the skill advertised as "run every crutch pass over a chapter" (`kill-chapter/SKILL.md:10-15`) does not run every crutch pass.

**Impact:** Users who run the orchestrator silently miss three tic families; users who run individual kills duplicate the soft/flat work already covered by the crutch pass. Tuning a keep/fix rule requires knowing which of up to three locations owns it.

### F3 — Review-stack routing ambiguity (High)

- `skills/fiction-dev-editor/SKILL.md:18`: "It does not authorize line editing."
- `skills/fiction-reviewchapter/SKILL.md:205`: "This is an EDITING PASS. For each issue found: Issue / Fix / Example."
- `templates/AGENTS.md:81`: "Story-level problems go to `fiction-dev-editor` **or** `fiction-reviewchapter`."
- `skills/fiction-dialogue/SKILL.md` owns conversation-architecture gates; `fiction-reviewchapter` criterion 4 (Character Authenticity) evaluates overlapping dialogue/voice ground with no precedence rule.
- `skills/coldread/SKILL.md` is read-only by design, but nothing in AGENTS.md states it must run before (not after) rule-loaded review, which is the condition its isolation value depends on.

**Impact:** The same chapter can be routed to two skills with opposite scopes. Findings come back at different altitudes (structural vs. sentence) with no merge rule, and structural findings risk being "fixed" as line edits.

### F4 — `fiction-reviewchapter` scope creep (Medium-High)

Verified shape: 218-line `SKILL.md`, 10 numbered criteria (Step 4), plus Step 5 (canon-assertion audit), Step 6 (Chekhov-ledger audit), Step 7 (page-verification), Step 8 (output). Three reference files. The single worker prompt assembles: chapter + previous chapter + review guide + style guide + character files + world files + outline + scene plan + promise ledger + genre file + synopsis + three criteria documents.

Each of the last three harvest passes (trilogy-lessons, confidently-wrong, persona-panel) correctly identified a real failure mode and then installed it as another inline step in this one worker. The trajectory is linear growth of one prompt.

**Impact:** Prompt bloat in a single judging worker degrades the judgment the gate exists to provide; Step 7 (verify-every-claim) exists precisely because unverified findings have already occurred. Failure mode: plausible, well-formatted reviews with false premises that cost a triage pass each (the skill's own Step 7 text says this).

### F5 — Missing revise loop (Medium)

All review/edit scanners end with "ask if they want fixes applied" (`line-editor:115`, `prose-editor:111`, `aiism-editor:104`, `full-editor:114`, `reviewchapter:65`). Only `fiction-dev-editor` (edit-in-place mode for beats/outline) and `kill-*` (in-place token edits) own the application step. There is no skill that takes `_Edits/Chapter-N_Review.md` + chapter + user-selected item numbers and returns an edited chapter with a change ledger and re-gate checklist.

**Impact:** Fixes are manual copy-paste from report to chapter today. Selective application ("apply items 3, 7, 12") and verification ("confirm each fix on the page, list what was skipped and why") are unowned, so they happen inconsistently or not at all.

### F6 — Metadata and workflow-chain contradictions (Low effort)

Verified by frontmatter extraction across all 47 `SKILL.md` files:

- Missing `metadata:` block (no version/author/category): `coldread`, `fiction-dialogue`, `nominalization-hunt`, `pangram` (4/47). `burstiness-check` carries version 1.3.0 but not the standard block shape.
- Version quoting mixed: `"1.0.0"` (quoted) vs `1.2.0` (unquoted) across skills.
- Chain contradictions vs `templates/AGENTS.md:51-67` ordering:
  - `fiction-scenes` declares `next-skill: fiction-psych`, but AGENTS.md orders psych (step 10) → scenes (step 11).
  - `fiction-series-outline` declares `requires: fiction-synopsis` **and** `next-skill: fiction-synopsis` (circular); AGENTS.md runs series-outline (step 5) between synopsis (4) and characters (6).
  - `fiction-writechapter` declares `workflow-position: 12`; `fiction-reviewchapter` declares 8; `fiction-promises` 8.5; `fiction-review-panel` 9 — the numbers do not match AGENTS.md steps 13/14/15 and collide with each other.
  - `fiction-psych`, `fiction-dialogue`, `fiction-dev-editor`, all four world-deepening skills, and all kill/edit scanners carry no `workflow-position` at all — so the chain is neither complete nor authoritative, yet it exists where it can contradict.

**Impact:** Low user-facing impact today, but the chain is a latent defect source for any future tooling that reads it, and the AGENTS-vs-frontmatter contradiction is exactly the class of "two sources of truth" the library otherwise avoids (cf. Wiki-wins rule, `AGENTS.md:47`).

### F7 — Name/place generator trigger overlap (Low-Medium)

Four skills with colliding trigger phrases: `name-generator` (people), `town-generator` (settlement names), `fantasy-settlement` (full settlement profile; triggers include "generate a town", "town profile", "what's in this city"), `fiction-places` (scene-bearing sites; explicitly "not full towns," `fiction-places/SKILL.md:8`). `templates/AGENTS.md:77` names only the first two ("use `name-generator` or `town-generator`. Do not freehand names") and is silent on when the other two apply.

**Impact:** Router must disambiguate four overlapping descriptions; consistent naming discipline (the AGENTS.md:77 rule) is only partially enforced by the index.

---

## 4. Recommendations

### R0 — Single source of truth + routing decision tree (do first; ~30 min; no behavior change)

1. Declare `templates/AGENTS.md` the sole workflow authority. Either complete the frontmatter `workflow-position` chain to match it exactly, or (recommended) delete `workflow-position` / `requires` / `next-skill` from frontmatter and keep the order in exactly one place. This eliminates finding F6 as a class.
2. Add missing `metadata:` blocks to the 4 skills; normalize version quoting.
3. Rewrite `AGENTS.md` Editing (§"Editing") and Skill index as a **decision tree**, not a list. Proposed routing:
   - Story structure / causality / "does this chapter move?" → `fiction-dev-editor`.
   - Chapter gate (default review) → `fiction-reviewchapter`.
   - Dialogue-only failure (samey, interview-like, expository) → `fiction-dialogue`, architecture gates before diction.
   - Blind POV/voice test → `coldread`, read-only, before rule-loaded review.
   - Sentence-level (default) → `fiction-full-editor`; the layer-specific scanners only when the user names the layer.
   - Recurring crutches (default) → `kill-chapter`; single-kill only when the user names the word.
   - Back-half flatness / pet words / formula openers → `drift-check`.
   - Reader reaction → `fiction-review-panel`.
4. Record in CHANGELOG; bump template version note per repo convention.

### R1 — Kill consolidation (mechanical; safe)

1. Copy the `the-whole` / `person-who` / `opinion-personification` rule-sets into `kill-chapter/references/` so the orchestrator runs 7 passes. Bump `kill-chapter` 1.0.0 → 2.0.0.
2. Resolve the generic-vs-specific duplication one way: either (a) `kill-crutch WORD` owns all single-word filler passes and `kill-soft` / `kill-flat` are removed from the AGENTS index (files retained for compat, descriptions pointer to `kill-crutch`), or (b) the orchestrator drops its generic crutch pass in favor of the specific ones. Option (a) is recommended — one word-list owner.
3. Extend the existing consecutive-not-parallel guard (`kill-chapter:20-25`) to the new passes unchanged.

### R2 — Editing-stack triage (needs one content decision)

- **Option A (recommended):** `fiction-full-editor` becomes the default sentence-level skill; `line` / `prose` / `aiism` become documented `--layer` modes, with their descriptions rewritten to route ("use `fiction-full-editor` unless you need only this layer"). No criteria rewrite required — `full-editor` already unions the three files. Demote `pangram` / `burstiness-check` descriptions to "diagnostic, not a gate" and route gradient questions to `drift-check`.
- **Option B (cheaper):** Keep all four scanners but narrow their advertised scopes so they no longer overlap (line = voice/cliché/repetition; prose = mechanics; aiism = tells), fixing `line-editor`'s current over-claim. Preserves router burden; fixes duplicate-findings cost only partially.
- Either option should add a dedup rule to the compile step (full-editor already has one at `fiction-full-editor:68`; promote it to the shared shape).

### R3 — Review slim-down + revise loop (structural; design together)

1. Extract `fiction-reviewchapter` Steps 5–6 (canon assertions, ledger audit) from inline worker prose into **delegated checks the orchestrator invokes** — the worker calls the promises/canon logic rather than re-deriving the ledger spec inside its prompt. Removes ~40 lines from the worker prompt with no coverage loss.
2. Add a small new `fiction-revise` skill: input = chapter + one `_Edits/*_Review.md` + user-selected item numbers; output = edited chapter + change ledger (applied / skipped / why) + re-gate checklist. This gives finding F5 an owner and stops `reviewchapter` Step 3.4 ("edit only approved changes") from being an unowned afterthought.
3. Codify precedence: beats/outline diagnosis → dev-editor; prose-chapter gate → reviewchapter; exchange-level architecture → dialogue; coldread never edits. Four bullets in AGENTS.md.

### R4 — Generator disambiguation (small)

Rewrite the four descriptions with mutually exclusive triggers (people-names vs settlement-names vs full-settlement-profile vs scene-bearing-site) and extend the `AGENTS.md:77` naming rule to name all four. No file moves needed.

---

## 5. Suggested roadmap

| Phase | Content | Risk |
|-------|---------|------|
| Phase 0 | R0 (metadata, chain, AGENTS decision tree) | None — text-only, no behavior change |
| Phase 1 | R1 (kill consolidation) | Low — mechanical, rule-set copies + index edits |
| Phase 2 | R2 (editing triage, Option A or B) | Medium — description rewrites change routing; needs owner decision |
| Phase 3 | R3 (review slim-down + `fiction-revise`) | Medium — touches the gate prompt; gate before/after comparison advised |
| Phase 4 | R4 (generator triggers) | Low |

Phase 0+1 can ship as one release under the repo's existing convention (CHANGELOG entry + frontmatter version bumps). Phases 2–3 should each be their own release with before/after gate output on a sample chapter.

---

## 6. Appendix — verification notes

- Frontmatter extraction: `grep -H "version:" skills/*/SKILL.md` plus per-file `head -12` inspection. Missing-block list (F6) verified against file heads, not inferred from descriptions.
- `kill-chapter` coverage (F2): `ls skills/kill-chapter/references/` → `crutch.md flat.md simile.md soft.md`; `ls skills/ | grep kill` → 7 kill skills + orchestrator. The 3-skill gap is a file-listing fact, not an interpretation.
- Reviewchapter size (F4): `wc -l` → 218-line SKILL.md; 655 lines with references. Step/section citations above are to the file's own headings (Steps 1–8, criteria 1–10).
- Workflow-chain table (F6): `fiction-scenes → next-skill: fiction-psych` vs AGENTS steps 10–11; `fiction-series-outline → requires/next: fiction-synopsis` vs AGENTS step 5; `fiction-writechapter position 12` vs AGENTS step 13. All three verified by direct read.
- No upstream comparison was run for this audit (`sync-check.sh` not invoked); all findings are intra-library and independent of upstream drift.

---

*Prepared as a read-only audit. No library, template, or script files were changed in producing this report.*
