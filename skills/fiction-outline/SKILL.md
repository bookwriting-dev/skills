---
name: fiction-outline
description: "Generate the chapter-by-chapter outline at Wiki/Outline/Book-N/outline.md with what_must_happen directives. Use when user says 'create outline', 'outline my story', 'structure the plot', or after running fiction-synopsis."
metadata:
  author: Fiction Toolkit
  version: "5.7.0"
  bundled-dependencies: book-status
  category: fiction-writing
  output-format: markdown
---

# Outline Generator

**Output:** `Wiki/Outline/Book-N/outline.md`, one chapter entry per chapter, each carrying a `what_must_happen` directive. `N` is the book being planned (Book-1 for a first book; ask when the project holds several).

This skill runs its generation in an isolated worker when the host supports one, to keep the main conversation context clean. The coordinator locates the input files and passes their paths; it does not read them itself. If isolated workers are unavailable, follow the same generation instructions directly.

## Step 1: Locate Inputs

All inputs are Markdown files in the project's `Wiki/` and `_Intake/` folders. The project may live in a subfolder, so search for them:

- `**/Wiki/Story/Book-N/synopsis.md` (when outlining a specific book in a series) or `**/Wiki/Story/synopsis.md` (series / standalone synopsis): required. Contains the premise, dramatic and thematic questions, reader promise, story answer, chosen form and movements, trope payoff plan, protagonists and setting. Prefer the target book's `Wiki/Story/Book-N/synopsis.md` if one exists; for `Book-2+`, if `Wiki/Story/Book-N/synopsis.md` is missing, prompt the user to generate it with `fiction-synopsis` (which reads `Wiki/Story/series-arc.md`) or confirm fallback to the root synopsis.
- `**/Wiki/Story/series-arc.md`: optional (recommended for series projects). Carries the inter-book promise map, per-book dramatic question stack, and handoff inventory.
- `**/_Intake/series-brief.md`, `**/_Intake/Book-N/premise.md`, and `**/_Intake/Book-N/raw-notes/*.md`: optional (advisory). Specific chapter ideas, set-pieces, or beat notes from the author's intake brief (`Wiki/` canon wins on any conflict).
- `**/Wiki/Style/genre.md`: selected tropes and their genre-level commitments. Required when the project was built through `fiction-genre`; if missing, flag that trope coverage cannot be verified.
- `**/Wiki/Characters/*.md`: one file per character: names, roles, personality, dialogue_style, and `relationship_checkpoints`.
- `**/Wiki/World/**/*.md` (current layout) and the legacy per-type folders (`**/Wiki/Locations/*.md`, `**/Wiki/Organizations/*.md`, `**/Wiki/Systems/*.md`, `**/Wiki/Events/*.md`): location names and organization constraints (prevents/forces/enables).
- `**/Wiki/Story/theme.md`: thematic question (legacy central_question), tone, motifs.

**Do NOT read these files in the coordinator.** Just collect their paths. The project root is the folder containing `Wiki/`.

If neither `Wiki/Story/Book-N/synopsis.md` nor `Wiki/Story/synopsis.md` exists (or the found synopsis is empty): tell the user to run `fiction-synopsis` first and stop.

## Step 2: Launch the Outline Worker

When the host supports isolated workers, start one with the description `Generate outline for [title]` and give it everything from the **"## Worker Instructions"** section below, replacing the placeholders:
- `{{SYNOPSIS_PATH}}` → the synopsis file path
- `{{GENRE_PATH}}` → the genre file path, or "none"
- `{{CHARACTER_PATHS}}` → the character file paths, or "none"
- `{{WORLD_PATHS}}` → the location/organization/system/event file paths, or "none"
- `{{SERIES_AND_INTAKE_PATHS}}` → relevant series handoff, premise, and intake paths, or "none"
- `{{THEME_PATH}}` → the theme file path, or "none"
- `{{PROJECT_ROOT}}` → the folder containing `Wiki/`

If isolated workers are unavailable, or if you are already the dedicated worker for this task, follow the same instructions directly.

---

## Worker Instructions

Generate the chapter-by-chapter outline for this project and save it to `{{PROJECT_ROOT}}/Wiki/Outline/Book-N/outline.md`, where `Book-N` is the book folder this outline belongs to (create the folder if missing).

**Project root:** `{{PROJECT_ROOT}}`
**Synopsis:** read `{{SYNOPSIS_PATH}}` fully.
**Genre:** read `{{GENRE_PATH}}` fully (skip if "none" and report that trope coverage cannot be verified).
**Characters:** read every file in `{{CHARACTER_PATHS}}` (skip if "none").
**World:** read every file in `{{WORLD_PATHS}}` (skip if "none").
**Theme:** read `{{THEME_PATH}}` (skip if "none").
**Series handoff and author intake:** read `{{SERIES_AND_INTAKE_PATHS}}` when present.

Cover every field in [references/json-schema.json](references/json-schema.json) as frontmatter or a labeled section in the output file; that schema is the field checklist, nothing more.

Before generating, read these craft knowledge files:
- [references/structure-templates.md](references/structure-templates.md): act distribution patterns, where chapter breaks naturally fall, how to pace revelations across the arc
- [references/anti-flat-rules.md](references/anti-flat-rules.md): what makes a chapter directive feel like instructions vs. a plot summary; how to ensure what_must_happen tells the writer what to show, not what to report
- [references/detailed-prompts.md](references/detailed-prompts.md): how to write chapter directives that are specific enough to generate a scene from, without locking down prose-level decisions
- [references/negative-arc.md](references/negative-arc.md): how to build chapter entries that track character cost, not just plot advancement

Extract: the quality standard for what_must_happen entries before finalizing.

### Contract gate

Identify the premise, dramatic question, reader promise, story answer, and agreed trope treatments. Read older `central_question` in context. If it asks a concrete plot question, retain it as `dramatic_question`; if it asks about values, keep it as `thematic_question` and derive the plot question from the existing premise and outcome. If an older synopsis has three named acts, they already define its form. A change of field names alone requires no rewrite or new gate. Compare the payoff plan with every trope in `genre.md`. If an essential contract field still has no evidence or a selected trope has no planned treatment, stop and report that the synopsis must be refreshed with `fiction-synopsis`. Do not silently infer the missing contract inside the outline and do not generate an outline that drops it.

### Rules

**title**: From the synopsis.

**Book contract**: Carry `premise`, `dramatic_question`, `thematic_question`, `reader_promise`, `story_answer` and `structure_form` from the synopsis, preserving the author’s wording and any deliberately open interpretation. When an older book has no thematic question, use `theme.md` if available, otherwise leave it unspecified.

**note**: Write one sentence explaining how POV is assigned across chapters (e.g., "Chapters are story events, not POV units; POV is assigned per scene as the story requires" or "Chapters alternate: odd = heroine, even = hero"). Add any other global convention the writer needs before opening individual entries.

**chapters and movement**: Map each chapter to the named movement or strand in the chosen structure. Use existing declared reading order for parts, letters or interludes. A braid may revisit a strand in nonconsecutive chapters. Choose breaks from the intended reader experience. For a new numbered outline, number chapters from 1.

**title**: A concrete, evocative title that names the chapter's central event or image without spoiling the turn. Not a beat label like "The Inciting Incident"; a title like "The Shadow on the Sun".

**what_must_happen**: This is the load-bearing field. Write it as a directive to the writer, not a description. Use the imperative: "Write Nico at the card table..." "Open at Le Cercle..." "Show the gap between her internal experience and her external presentation..." Include: who is present, what happens, what the reader must see and feel, specific images or exchanges that are non-negotiable, and how the chapter ends. The concrete action must execute the chapter's premise movement, dramatic question, promise delivery, and any listed trope obligations; do not leave those jobs only in metadata. Draw from the chosen movement for narrative intent. Draw from the character files' dialogue styles and internal monologue descriptions for voice guidance. Draw from the location files' sensory descriptions for atmosphere. 3-6 sentences. No passive summary.

**premise_movement**: One sentence naming how this chapter changes the unstable situation, the protagonist’s options, the reader’s understanding, or the cost of pursuing the premise. A chapter that does none of these is a merge or cut candidate.

**Setup & consequence binding**: Each chapter’s central action, observation, or payoff should draw on something earlier in the outline — an established situation, a promise made, a resource granted, a wound left, a constraint imposed — or, in the opening chapters, to the premise situation itself. A chapter can complete a promised outcome, or leave a consequence a later chapter can spend: a changed relationship, a new constraint, a debt, knowledge gained or exposed. Name the binding inside `what_must_happen` ("this spends the trust Mara earned in ch 4"), not just in metadata. If a chapter neither develops nor pays an earlier event, identify what the reader loses if it is cut.

**question_pressure**: Name what the reader can now fear, infer, hope for, or rule out about the dramatic question. Give the thematic question space to retain competing answers.

**promise_delivery**: One sentence naming the part of the reader experience or satisfaction this chapter actually delivers. Do not repeat the global promise without identifying an on-page event.

**Middle and subplot_threads**: Trace the protagonist’s first workable solution into a complication caused by that solution. For each important secondary line, show what its owner wants, the move they make for their own reasons, where it changes the lead’s options, and the later cost. Put the action in the chapter directive. “The sister’s family thread advances” cannot explain why the hearing occurs. “Her sister petitions to seal their mother’s archive; at the hearing the lead must publicly identify the letter she meant to keep private” can. In a contemplative or episodic middle, follow the accumulating change in perception or relationship across the juxtaposed scenes.

**cadence_role**: Choose `pressure_turn`, `aftermath_valley`, `payoff_catharsis`, or `tonal_counterpoint` as appropriate. Inspect repeated intensity for stalled movement. A sustained run may create grief, dread or comic accumulation through changing details.

**trope_obligations**: Zero or more entries using the exact snake_case identifiers from the genre file and synopsis payoff plan. Format each as `trope_id: setup | development | payoff | texture | subversion - concrete chapter action`. A chapter need not carry every trope, but every selected trope must receive the complete treatment its role requires across the outline.

**ends_with**: 1-2 sentences on the exact state of play at close. What each relevant character knows, has, and wants. Include unresolved matters where relevant. A complete farewell, quiet payoff, or closed final image can finish the chapter. If using a cliffhanger or sharp reversal hook, note how Chapter `N+1` will cash it cleanly (no false cliffhangers instantly waved away on line 1 of the next chapter).

### Partial / Mid-Book Re-Outline (`--from-chapter K`)

When re-outlining after discovery drafting (`lean-start.md`), structural pivots, or Act-1 sprints:
- Freeze drafted chapters `1..K-1` verbatim as canonical history: do not alter their summaries or invent retroactively contradicting setups inside frozen entries.
- Inventory open promises (`Wiki/Story/Book-N/promises.yaml`), changed relationship states, and reader/POV knowledge gaps from `1..K-1`, then re-plot chapters `K..end` to absorb all live threads and pay them off coherently.

### Distribution
Use the synopsis’s movement names, order and transition points. In a three-act book with a midpoint, locate that turn where the material supports it. Five acts keep five movements; interleaved accounts retain their alternating order. Do not impose a percentage split, mandatory reversal, or extra climax.

### Save

Write the outline to `{{PROJECT_ROOT}}/Wiki/Outline/Book-N/outline.md` (create the `Wiki/Outline/Book-N/` folder if missing). Format:

- YAML frontmatter carrying the scalar fields. Plain, conservative YAML: block lists only (one `- item` per line), never inline `[a, b]` lists; quote strings containing colons.

```
---
title: "Working Title"
note: "One sentence on POV assignment and any global convention."
chapter_count: 24
premise: "The concrete unstable situation from the synopsis."
dramatic_question: "The concrete outcome the reader follows?"
thematic_question: "The interpretive question the events explore?"
structure_form: "Structure named in the synopsis"
reader_promise: "The spoiler-light experience and satisfaction owed."
story_answer: "The spoiler-containing answer demonstrated by the ending."
---
```

- Body: one `## Chapter NN: Title` section per chapter (zero-padded two-digit number), with one bold field label per line so every field stays grep-able:

```
## Chapter 01: The Shadow on the Sun

- **chapter_number:** 1
- **title:** The Shadow on the Sun
- **movement:** [name from the synopsis]
- **what_must_happen:** [directive prose]
- **premise_movement:** [how the unstable situation or cost changes]
- **question_pressure:** [how action and choice pressure the dramatic question]
- **promise_delivery:** [the concrete reader experience delivered here]
- **cadence_role:** pressure_turn | aftermath_valley | payoff_catharsis | tonal_counterpoint
- **subplot_threads:** [optional secondary threads braided here]
- **trope_obligations:** enemies_to_lovers: setup - [concrete action]; forced_proximity: development - [concrete action]
- **ends_with:** [state of play at close]
```

Before saving, run a coverage pass across the complete outline:

- The opening chapters dramatize the premise and pose the dramatic question rather than merely repeating them in frontmatter.
- Each chapter contributes something the reader would lose by its removal, including changed understanding or an earned emotional landing.
- Each chapter draws on the premise or an earlier setup. A chapter can pass a consequence forward, change the reader’s understanding, or finish a promised experience. In the final chapter, identify the payoff it delivers. No additional downstream event is owed.
- The actual transitions in the chosen form do their intended work. The middle develops consequences of choices, or accumulates meaning where the form promises that effect.
- The ending delivers the promised outcome or experience. Identify what changes for the reader and what interpretation the author deliberately leaves open.
- Every trope in `genre.md` appears under its exact identifier in the outline. Genre-contract and structural tropes receive setup, development, and payoff; supporting texture recurs with variation; deliberate subversions establish the expected pattern and replace it with equal satisfaction.
- Trope obligations are embodied in `what_must_happen`, not merely listed in metadata.

If the premise, promise, dramatic question, story answer, or trope payoff plan conflict, stop and report the mismatch instead of forcing contradictory material into chapters. The synopsis is the place to repair that contract.

Return: "Outline written to Wiki/Outline/Book-N/outline.md" and a one-line summary of chapter count and how chapters map to the chosen form.

### Relationship turns (add checkpoints where a bond changes)

Relationship states live as chapter-anchored checkpoints; `fiction-characters` seeded the chapter-1 state in each character's `Wiki/Characters/<Name>.md` file. The outline is where you know a bond *turns*: enemies to allies, friends to lovers, a betrayal. For each such turn, record a checkpoint at the chapter where it lands, keeping the incoming relationship intact until the scene earns its change.

Checkpoints live in the character files, not in `outline.md`. For each turn, append a new dated entry to the `## relationship_checkpoints` section of BOTH characters' `Wiki/Characters/<Name>.md` files, under the existing `### <Other Character Name>` heading `fiction-characters` seeded:

```markdown
### <Other Character Name>
- **book:** [selected book ID or display label]
- **link_type:** romantic
- **chapter_start:** [chapter the turn lands]
- **turn_scene:** [number of the scene that earns the change, or unresolved until scene planning]
- **chapter_end:** (open)
- **notes:** one-line state from here on
```

When adding the new checkpoint, keep the prior span through the turn chapter. The character enters the named scene in that prior state; subsequent scenes can use the changed state. A turn already established before the chapter opens uses `turn_scene: opening`. Confirm scene timing during scene planning. Only add a checkpoint when the bond actually shifts; a stable relationship keeps its earlier checkpoint until something changes.

---

## Step 3: Register Expected Chapters and Confirm

Use [project_state.py](../book-status/scripts/project_state.py) with `--root ROOT --book Book-N register-chapters --spec SPEC.json` to record the intended chapters of an authorized book plan. For a numbered plan the spec is `{"schema_version":1,"chapters":[{"number":1},{"number":2}]}` with the actual planned numbers. For custom ordering use the top-level `"chapter_order":"declared"` and supply `id`, `display_label`, `path`, and `reading_order` for each custom chapter or interlude. Reuse existing IDs and destinations. Register only the target for a focused planning request. Surface any conflict with existing authority before handoff.


Show the worker's summary and ask: "What should I change?"

If changes are needed, use the same isolated-worker mechanism when available with the revision instructions plus the existing `Wiki/Outline/Book-N/outline.md` path, and have it rewrite the file.

When approved, confirm the file was saved and suggest: "Next: use `fiction-divergence` for the beat-the-defaults pass, then `fiction-scenes` to expand each chapter into scene plans at `Wiki/Outline/Book-N/Chapter_[NN]_Scene.md`."
