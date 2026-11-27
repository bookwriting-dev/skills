---
name: fiction-scenes
description: "Create or revise fiction chapter beats and scene plans. Use for chapter beats, scene breakdowns, scene files, or turning an outline into writable action; do not use for drafting prose or developmental diagnosis alone."
metadata:
  author: Fiction Toolkit
  version: "4.8.0"
  bundled-dependencies: book-status
  category: fiction-writing
  output-format: markdown
---

# Fiction Scenes

Turn chapter intent into a causal, writable scene plan. Preserve the user's requested scope: revising an existing beat sheet means editing that sheet, not creating a report or a second planning artifact.

## Authority and destination

Use this order of authority:

1. The user's current instructions.
2. The book's `AGENTS.md`, `CLAUDE.md`, and nested instructions.
3. The project's established source of truth and file conventions.
4. This skill's generic defaults.

Do not impose Wiki-only storage, integer numbering, or `Chapter_XX_Scene.md` when the project uses decimal or interlude chapters, or a different beats convention. An explicit output path wins. Otherwise, revise the existing assigned file. For a new file, follow neighboring chapter files; use `Wiki/Outline/Book-N/Chapter_[NN]_Scene.md` only when no project convention exists.

Do not create a diagnostic, receipt, character profile, location file, or organization article unless the user asks or book instructions require it. Record unresolved entity work inside the requested artifact only when it affects drafting.

## Choose the lightest useful mode

Infer the mode from the request; do not ask when it is clear.

- **Edit in place:** The user asks to adjust, regenerate, fix, or tighten an existing beat sheet. Read the current file, apply the requested changes throughout it, and verify stale material is gone.
- **Compact beats (default for one chapter):** Create a concise chapter spine and 1–3 scene entries. Include only what the writer needs to draft without guessing.
- **Full scene document:** Use when the user asks for detailed scene files, the downstream generator requires structured fields, or several writers/tools will consume the artifact. Read the full-mode references below.
- **Batch scenes:** Use for a chapter range. Preserve cross-chapter continuity and vary drivers and endings.

Do not silently escalate compact beats into a full scene dossier.

## Context

Read only context that can change the plan:

- assigned outline, proposal, existing beats, or chapter directive;
- the POV character and named participants, including the incoming state and the specific transition scene in this book’s `## relationship_checkpoints` in `Wiki/Characters/<Name>.md`;
- relevant current-canon locations, factions, systems, and active context;
- adjacent prose or beats needed for continuity;
- the project's style/voice source only when the beats include drafting guardrails or the user names it.

Use the project's required retrieval method first. If the book has a preferred index or semantic-search rule, follow it. Search narrowly after semantic retrieval for exact facts. Do not load every character or world file by default.

Separate **established**, **author-directed**, **proposed**, and **unknown** facts. Never convert a possibility into canon merely to fill a field. Avoid inventing names, ages, institutions, dates, or technical mechanics unless the scene cannot work without them; mark any necessary invention as proposed.

## Plot gate: do this before expanding scenes

Write the chapter's causal spine in one or two sentences and test it:

1. **Purpose:** Identify this chapter’s movement or strand and the intended reader experience. What does someone seek, observe, receive, or finally understand?
2. **Pressure:** What makes that difficult? Friction may be uncertainty, cost, incompatible duties, time, or incomplete knowledge; it need not be hostility.
3. **Cadence Role & Micro-Friction:** Assign each scene a `cadence_role` (`pressure_turn` [default], `aftermath_valley`, `payoff_catharsis`, or `tonal_counterpoint`).
   - For **`pressure_turn` (default):** What specific resistance, failed first tactic, deflection, or raised cost prevents the scene from resolving on the first push? (A direct answer can itself carry the price: sworn testimony exposes the speaker, or an admission gives someone authority to act.)
   - For **`aftermath_valley`**, **`payoff_catharsis`**, and **`tonal_counterpoint`** (earned integration, grief/sanctuary, joy/warmth, or comic respite immediately before or after a major turn): micro-friction is **optional** — do not manufacture fake bickering or arbitrary obstruction when the chapter's structural job is emotional dwell or tonal contrast. Still require genuine interior movement, consequence, or dramatic irony.
4. **Agency or viewpoint:** Whose choice drives events? For a witness, document or aftermath, what new relationship or interpretation does this viewpoint let the reader see?
5. **Change:** What is different by the end in action, feeling, relationship or the reader’s understanding? An earned farewell may complete a thread.
6. **Necessity:** What later choice, interpretation, contrast, or completed experience would the reader lose if this were cut?

If the spine cannot answer all six, repair the spine before adding worldbuilding. Look for an effect on a decision, relationship, or reader understanding. A final payoff can finish that work entirely within this chapter.

Prefer one primary driver and at most one supporting driver (or `subplot_threads` braid). Consult [driver-types.md](references/driver-types.md) when the driver is unclear or when planning a batch. Use [anti-flat-scenes.md](references/anti-flat-scenes.md) when a `pressure_turn` chapter risks becoming travel, processing, setup, or exposition without action.

## Build scenes around turns

Use 1–3 scenes according to real changes in location, time, power, or emotional register. One sustained scene is valid when it carries the full turn; do not split it merely to satisfy a count. Vary `cadence_role` across adjacent chapters so high-pressure sequences earn recovery valleys and climatic turns have emotional weight.

Each scene should establish:

- the POV character's immediate goal, `cadence_role`, any braided `subplot_threads`, and the active `relationship_checkpoints` state between participants at this chapter;
- for `pressure_turn` scenes: active pressure and a specific **micro-friction beat** or price at the turn itself, such as a truthful answer that exposes its speaker;
- when the reader holds confirmed knowledge the POV does not (`dramatic_irony` gap from `fiction-knowledge` / `DraftPacket.json`), note how the scene stages that asymmetry in action, dialogue subtext, or close calls without leaking unlearned secrets;
- when dialogue architecture materially shapes the scene, name the **conversation form** (for example interview, interrogation, briefing, examination, or purposeful cooperation) and its pressure source. State why direct answers or repeated confirmations serve the scene; do not use the label as a blanket exemption from checking actual stagnation;
- concrete actions and selective physical anchors;
- the turn: the line, discovery, refusal, choice, release, or act that changes the scene;
- the consequence carried into the next scene (if a bond shifts here, append a new dated checkpoint entry to `## relationship_checkpoints` in both characters' `Wiki/Characters/<Name>.md` files with this book’s ID and the numeric `turn_scene`; keep the prior span through this chapter and distinguish each person’s incoming stance from what changes on the page);
- the surface response and the truer interior movement;
- a specific ending beat: forward pull, earned quiet dwell, or closure. A final gesture can settle the question in full.

Worldbuilding belongs inside decisions and consequences. Keep lists selective. A single load-bearing object or transaction usually carries more story than an inventory.

Do not duplicate the same material across summary, emotional beat, writable beats, continuity notes, and recommendations. Add a field only when it gives the eventual drafter new information.

## Compact beats format

Adapt to the project's neighboring files. A useful default is:

```markdown
# Chapter [number]: [title]

## Chapter spine
- **Movement:** [named movement or strand from the outline, when specified]
- **Purpose or want:** ...
- **Pressure:** ...
- **Cadence role:** pressure_turn | aftermath_valley | payoff_catharsis | tonal_counterpoint
- **Subplot threads:** [active B-plot / thematic thread braided here, if any]
- **Decision or change in understanding:** ...
- **Consequence or payoff:** ...
- **Why this chapter cannot be cut:** ...

## Scene 1
- **POV:** [Single viewpoint name for this scene]
- **Cadence role:** pressure_turn
- **Goal:** ...
- **Action and turn:** [specific beat-by-beat action]
- **Dramatic irony leverage (when relevant):** [what reader knows that POV misses, staged for tension]
- **Interior movement:** [surface / underneath / where POV lands]
- **Consequence or hook:** ...
- **Conversation form / pressure source (when relevant):** ...
```

Name one POV per scene when a chapter changes viewpoint or the book has several narrators. A single viewpoint declared for the chapter may cover each scene that inherits it. When using the series knowledge ledger, record the established integer **Story order:** and **Reader order:** under the relevant scene so the draft packet reads knowledge and relationships at the right moment. If the series ledger uses a custom scene ID, include **Scene ID:** under its scene as well.

Add continuity or fact-status notes only where the drafter could otherwise contradict canon. Do not append a generic recommendations section after the plan is already usable.

When a scene depends on an established identifier, object state, clock, or scoped count, put the relevant keys on a single `Continuity keys: KEY, KEY` line in the plan for the draft packet. Look up the current keys with `project_state.py --root ROOT --book Book-N continuity --action context --chapter SELECTOR` or locate their establishing passages. See [book continuity review](../book-status/references/continuity-review.md).

Include the keys of decisive authorizations, evidence bundles, technical stages, and prior events when a scene depends on them. Identify what establishes the condition or supports the conclusion. See [evidence that a scene depends on](../book-status/references/evidence-chain.md).

## Full scene documents

Only in full mode, read:

- [json-schema.json](references/json-schema.json) as the structured field checklist;
- [continuity-tracking.md](references/continuity-tracking.md) for clocks, injuries, relationships, and carried threads;
- [chapter-hooks.md](references/chapter-hooks.md) when the ending lacks forward pull;
- [anti-flat-scenes.md](references/anti-flat-scenes.md) and [driver-types.md](references/driver-types.md) as needed.

Use [scene-template.md](assets/scene-template.md) or [output-template.json](assets/output-template.json) only when their format matches the project or downstream tool. Field-length examples are guidance, not quotas. A summary should be long enough to draft the scene and no longer. Emotional fields must add interior causality rather than paraphrase events.

For each structured scene, populate the fields required by the project's generator. Resolve proper nouns exactly when machine ingestion depends on them. If a valid provisional name cannot resolve, flag it; do not silently replace it or create unrelated canon.

Carry any declared conversation form and pressure-source rationale intact into dialogue preflight and downstream review/gates. A plan's declared form permits functional direct answers; it does not excuse an exchange that fails to change knowledge, risk, permission, status, commitment, or available action. Do not manufacture refusals or interruptions to satisfy a numeric resistance rule.

## Workers

Handle a single chapter or focused revision directly unless an isolated worker would clearly improve a large-context or multi-chapter task. Consider one worker for a substantial range or large continuity corpus; use one when book instructions require isolation. Do not delegate merely because the capability exists.

When using a worker, tell it the selected mode, exact target path, permitted side effects, authority order, and whether it may create reports. The coordinating agent must review the actual edited artifact before reporting completion.

## Revision verification

For edits, check every user-requested addition, removal, and reframing across the entire artifact, including continuity notes, hooks, guardrails, fact tables, and recommendations. Search exact banned terms, then read semantically for leftover concepts that use different words. Do not claim a concept is gone because one keyword no longer appears.

Before finishing, verify:

- the plot gate passes;
- background facts support the causal spine rather than compete with it;
- the chosen viewpoint contributes to the intended turn, consequence, or payoff;
- allies have independent agendas without forced hostility;
- no earlier chapter's decision or hook is merely repeated;
- proposed facts remain labeled;
- timeline and entity names follow project authority;
- the requested file, and only requested ancillary files, were changed;
- formatting checks pass when available.

Return a concise completion note with the file link and any true drafting blocker. Do not paste the artifact or produce a review report unless asked.

## Knowledge and campaign integration

Consult fiction-knowledge for supported acquisitions, suspicions, false beliefs, and reader-only exposure at the assigned scene. Verify cited source hashes; missing coverage cannot establish ignorance. Preserve intentional deception and unreliable narration. For multi-chapter changes, use revision-campaign to track affected plans, prose, ledgers, and current re-gating. Existing user authorization applies to its stated scope. Keep unresolved decisions and impacted chapters visible until current verification succeeds.
