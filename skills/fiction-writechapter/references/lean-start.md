# Lean / Act-1 Sprint Track

Use this track when a writer wants to start drafting quickly (discovery writing, novellas, or testing an idea on the page) instead of running the full 13-step planning sequence upfront.

## When to activate

- The writer asks for a "lean start", "fast start", "Act-1 sprint", or wants to promote `_Intake/Book-1/opening-scene.md` directly into Chapters 1–3 without building the entire series world bible first.
- Do NOT use when a full `Wiki/` bible and `outline.md` already exist; follow the standard `fiction-writechapter` workflow there.

## Minimum Viable Canon (4 files)

Seed only what Chapters 1–3 need, drawing from `_Intake/series-brief.md`, `_Intake/Book-1/premise.md`, and any promoted opening-scene trial:

1. **Protagonist card (`Wiki/Characters/<Name>.md`):** core drive, active flaw/tension, voice notes, and any immediate relationship checkpoints for Chapters 1–3.
2. **Minimal style & voice (`Wiki/Style/style_guide.md` + `Wiki/Style/voice_prompt.md`):** POV, tense, diction defaults ([diction and clock time](../../book-status/references/diction-and-time.md)), and 3–5 positive/negative voice rules.
3. **Rolling 3-chapter outline (`Wiki/Outline/Book-1/outline.md`):** concrete `what_must_happen` directives for Chapters 1–3 plus a provisional Act-1 question.
4. **Immediate scene plan (`Wiki/Outline/Book-1/Chapter_01_Scene.md` … `Chapter_03_Scene.md`):** causal beats, micro-friction, and ending turn for the chapter being drafted.

## Sprint Loop (Chapters 1–3)

1. Register Chapters 1–3 via `project_state.py --root ROOT --book Book-1 register-chapters`.
2. Draft Chapter N via `fiction-writechapter` using `draft-packet`.
3. At each chapter's gate (`gate-check`), **promote** any provisional proper nouns, rules, or setups introduced on the page into `Wiki/Characters/`, `Wiki/World/`, and `Wiki/Story/Book-1/promises.yaml` (never leave new proper nouns uncatalogued).
4. Refresh the rolling 3-chapter horizon (`outline.md` + next scene plan) as discoveries emerge.
5. After Chapter 3 (end of Act 1), transition into the full Storycraft pipeline (`fiction-outline`, `fiction-divergence`, `fiction-psych`, and `rhythm-map` / `review-panel`) before drafting Act 2.
