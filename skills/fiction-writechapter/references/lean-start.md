# Lean / Act-1 Sprint Track

Use this track when a writer wants to start drafting quickly (discovery writing, novellas, or testing an idea on the page) instead of running the full upfront planning sequence.

## When to activate

- The writer asks for a "lean start", "fast start", "Act-1 sprint", or wants to promote `_Intake/Book-1/opening-scene.md` directly into Act 1 (`Chapters 1–K`) without building the entire series world bible first.
- Do NOT use when a full `Wiki/` bible and `outline.md` already exist; follow the standard `fiction-writechapter` workflow there.

## Minimum Viable Canon (4 files)

Seed only what Act 1 (`Chapters 1–K`, default `K = 3` or any natural Act-1 end) needs, drawing from `_Intake/series-brief.md`, `_Intake/Book-1/premise.md`, and any promoted opening-scene trial:

1. **Protagonist card (`Wiki/Characters/<Name>.md`):** core drive, active flaw/tension, voice notes, and any immediate relationship checkpoints for Chapters 1–K.
2. **Minimal style & voice (`Wiki/Style/style_guide.md` + `Wiki/Style/voice_prompt.md`):** `register_preset`, POV, tense, clock/diction defaults ([diction and clock time](../../book-status/references/diction-and-time.md)), and 3–5 positive/negative voice rules.
3. **Rolling opening outline (`Wiki/Outline/Book-1/outline.md`):** concrete `what_must_happen` directives for Chapters 1–K plus a provisional Act-1 question.
4. **Immediate scene plan (`Wiki/Outline/Book-1/Chapter_01_Scene.md` … `Chapter_0K_Scene.md`):** causal beats, `cadence_role`, and ending turn for the chapter being drafted.

## Sprint Loop & Provisional-Noun Protocol (Chapters 1–K)

To avoid the discovery-drafting Catch-22 (needing a finalized Wiki before discovering character/place names on the page):

1. Register Chapters 1–K via `project_state.py --root ROOT --book Book-1 register-chapters`.
2. **Provisional-Noun Discovery Allowance:** While inside a lean sprint, `fiction-writechapter` MAY introduce new situational proper nouns (walk-on characters, tavern names, local streets) **only if** it appends them to `_Edits/Book-1/lean-nouns.md` (`name`, `kind`, `chapter_introduced`, `provisional_fact`) so nothing is orphaned or unrecorded. Core protagonist/antagonist/system canon still lives in `Wiki/`.
3. Draft Chapter N via `fiction-writechapter` using `draft-packet`.
4. At each chapter's gate (`gate-check`), **promote** kept provisional entries from `_Edits/Book-1/lean-nouns.md` into `Wiki/Characters/`, `Wiki/World/`, and `Wiki/Story/Book-1/promises.yaml` (or prune cut ones), clearing the buffer before gating Chapter `N` `PASS`.
5. Refresh the rolling horizon (`outline.md` + next scene plan) as discoveries emerge.

## Post-Sprint Synthesis Bridge (Act 1 -> Act 2)

When the opening sprint concludes (whenever the writer is ready to architect Act 2, regardless of chapter number K):

1. Synthesize `Wiki/Style/genre.md` (`fiction-genre`), `Wiki/Story/theme.md` (`fiction-theme`), and `Wiki/Story/synopsis.md` (`fiction-synopsis`) from the drafted Act-1 prose and remaining intake notes.
2. Run `fiction-outline` in **partial re-outline mode (`--from-chapter K+1`)**, freezing drafted Chapters `1–K` as settled canon and plotting Chapters `K+1..end` to cash all active promises cleanly.
3. Run `fiction-divergence` (`surprise-ledger.md`), `fiction-psych` on remaining chapters, a whole-block macro check (`project_state.py --root ROOT --book Book-1 rhythm-map --markdown`, `drift-check`, and `fiction-dev-editor`), and optional `review-panel` on Act 1 before drafting Act 2.
