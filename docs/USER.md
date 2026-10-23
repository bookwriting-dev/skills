# User Guide

What this skill library does for you when you sit down to write a book with an agent,
and which skill to reach for at each moment. For how the library itself is built and
maintained, see [DEVELOPER.md](DEVELOPER.md).

## The mental model

There are two kinds of repository, and keeping them apart is the whole game:

- **This library repo** (`storycraft-skills`) — the source of truth for the skills.
  You rarely touch it while writing.
- **A series project repo** — one per series, created by `new-book.sh`. It holds a
  *pinned copy* of the skills at `.agents/skills/`, your canon, and your prose. Each
  project has its own git history; updating a project's library means copying `skills/`
  over again and committing.

Inside a project, everything has a defined job:

| Place | Job |
|---|---|
| `_Intake/` | **Staging & Inception.** Creative brief (`series-brief.md`), per-book premise (`Book-N/premise.md`), raw voice memos/brain dumps, and imported manuscripts (`raw-manuscript/`). Advisory to planning skills; never binding canon. |
| `Wiki/` | **Canon.** Characters, world, style, outlines, promises, review findings. Wiki wins over any draft — if a chapter and the Wiki disagree, the Wiki is right until you explicitly change canon. |
| `Chapters/Book-N/` | The prose. `Chapter-001.md`, three-digit numbering, title + POV name(s) inside the file. |
| `_Edits/Book-N/` | Review and edit reports (`Chapter-NNN_Review.md`, `_FactCheck.md`, `_ClarityEdit.md`…), defect ledgers (`findings.yaml`), matched to chapters by number. |

A series is shared canon (Wiki root: characters, world, style, series synopsis,
`series-arc.md`, review panel) plus per-book slots (`Book-N/` subfolders for synopsis,
outline, psych, promises, chapters, edits). Skills never invent a proper noun that
isn't in the Wiki — they stop and ask instead.

## Starting a series

```bash
./new-book.sh my-series "My Series Title"          # → ~/Projects/Books/my-series (fiction)
./new-book.sh my-thesis "My Thesis" --type nonfiction   # or --type hybrid
./new-book.sh my-book "My Book" --import /path/to/draft.md   # import existing manuscript
```

You get the folder skeleton, the `_Intake/` creative brief staging area, the pinned skill
library, rendered `AGENTS.md` + `CLAUDE.md`, and an initial commit.

There are two distinct entry points:

- **Path A: Greenfield (Starting from a new idea):**
  Review or fill out `_Intake/series-brief.md`. Then open the project with your agent and say
  **"start the book"** — the planning skills (`fiction-genre` first) ingest your intake notes
  automatically to seed `Wiki/` canon without grilling you cold.
- **Path B: Brownfield (Reverse-engineering an existing manuscript):**
  If you provided `--import`, your manuscript is staged in `_Intake/Book-1/raw-manuscript/`.
  Say **"reverse engineer the book"** — `book-reverse-engineer` will analyze the text, extract
  characters, rules, timeline, promises, and voice into `_Edits/Book-1/reverse-analysis.md`,
  flag contradictions, lock `Wiki/` canon upon your review, and seed `_Edits/Book-1/findings.yaml`
  for surgical repairs.

`--type` sets the project-type line in the rendered `AGENTS.md` and, for `nonfiction`
and `hybrid`, creates `Wiki/Concept/` and `Wiki/Research/` alongside the shared Wiki
slots.

## The fiction workflow

**Plan the book (once, in order):** genre → audience → theme → synopsis → series
outline → characters → world (+ places/factions/polities/religions as needed) →
outline → divergence pass → psych → scene plans → style + voice prompt. Each step
writes a Wiki file; the next skill reads them.

**Write loop (per chapter):**

1. `fiction-writechapter` drafts `Chapters/Book-N/Chapter-NNN.md` from the scene plan,
   voice rules, and Wiki canon.
2. `fiction-reviewchapter` is the chapter gate — canon assertions, the Chekhov ledger,
   character consistency, prose rules — and files `_Edits/Book-N/Chapter-NNN_Review.md`.
3. `fiction-revise` applies the review items *you approve* to the chapter in place,
   with a change ledger. (Structural findings — missing beats, wrong POV — go back to
   the scene plan and a re-draft instead.)
4. `kill-chapter` or `fiction-full-editor` when you ask for a cleanup/polish pass.

**Book-level QA:** run `review-panel` per act and before calling the book done
(persona reads with verified quotes); `drift-check` at part boundaries (it's the only
skill that can see the back half getting flatter while every chapter gate stays green);
`fiction-promises` before closing (overdue/due/undated setups).

### LitRPG and Progression Fantasy series

If your series has game mechanics, stat systems, or cultivation/progression tiers:

1. **System Design:** Run `litrpg-system` right after `fiction-genre` and `fiction-world`. It populates `Wiki/World/Systems/` (`system-rules.md`, `classes-skills.md`, `encounters-loot.md`), seeds protagonist character sheets in `Wiki/Characters/<Name>_sheet.md`, and initializes the progression ledger (`Wiki/World/Systems/ledger.yaml`).
2. **Notification Standards:** Format system notifications and blue boxes using Markdown callouts (`> [!SYSTEM]`, `> [!ALERT]`, `> [!SKILL]`) following `stat-box-guide.md`. The burstiness diagnostic (`burstiness-check`) and prose linters automatically recognize and ignore these blocks so stat sheets never false-flag as choppy prose or repetition hotspots.
3. **Deterministic Progression Audits:** Run `litrpg-audit` (or `gate-check`) on every chapter. It mechanically calculates whether stat point allocations match level gains, verifies that invoked skills have been unlocked in canon, checks resource limits, and catches stat-dump paralysis.

## The non-fiction workflow

As the library stands today, the end-to-end chain is nine skills deep, plus the
cross-genre tools that also run on non-fiction (`promise-tracker`, `review-panel`,
`drift-check`):

**concept** (`Wiki/Concept/thesis.md`) → **audience** (`audience.md`, five reader
archetypes) → **structure** (`structure.md`: problem-solution / chronological /
conceptual / hybrid) → **research** (`Wiki/Research/`: citation vault + claims matrix)
→ **chapter plan** (`Wiki/Outline/Book-N/plan.md`: each chapter's claim, evidence,
transition, takeaway) → **writechapter** (`Chapters/Book-N/`) → **dev-editor**
(argument architecture and cognitive load) → **factcheck**
(`_Edits/…_FactCheck.md`) → **clarity-edit** (`_Edits/…_ClarityEdit.md`).

`promise-tracker` keeps the unified promise/claim ledger, and `review-panel` and
`drift-check` run on non-fiction too (non-fiction persona seats; claim-density and
evidence-ratio drift metrics).

One non-fiction layer is intentionally not built yet: a non-fiction revise skill. The
workflow routes around it — structural problems go back to `nonfiction-chapter-plan`
and a re-draft, and approved report fixes apply through `fiction-revise`, which is
report-driven and book-agnostic. (DEVELOPER.md's reconciliation record lists it, should
you want to build it.)

## Which editing skill? (the decision tree)

Ask "what's wrong?" and read the row:

| Symptom | Fiction | Non-fiction |
|---|---|---|
| "Does this chapter move / prove?" — structure, causality | `fiction-dev-editor` | `nonfiction-dev-editor` |
| Default chapter review (the gate) | `fiction-reviewchapter` (full review of a finished draft); `gate-check` = lighter checklist, the one `chapter-pipeline` runs | `nonfiction-factcheck` + `nonfiction-clarity-edit` |
| LitRPG stat math / progression contradictions | `litrpg-audit` (also in `gate-check`) | — |
| One claim sounds machine-written | `coldread` (blind, read-only) | `coldread` |
| Dialogue samey / interview-like | `fiction-dialogue` | — |
| Loose ends, unpaid setups | `fiction-promises` | `promise-tracker` (also owns **hybrid** projects — it carries both kind vocabularies) |
| General sentence-level polish | `fiction-full-editor` | `nonfiction-clarity-edit` |
| Apply approved fixes from a report | `fiction-revise` | `fiction-revise` (report-driven, book-agnostic) |
| Recurring crutches, whole-chapter sweep | `kill-chapter` (7 passes) | `nominalization-hunt`, `kill-passive`, `kill-hedge`, `kill-acronym`; `kill-crutch WORD` (book-agnostic) for one filler token |
| Back half feels flatter than the front | `drift-check` | `drift-check` |
| "What would a reader think?" | `review-panel` (act/book QA) or `reader-persona-review` (quick chapter pulse) | `review-panel` non-fiction seats or `reader-persona-review` |

Rule of thumb: **editing passes run only when you ask.** Review is part of the loop;
revision is your call. And a structural problem is never an editing job — fix the plan,
re-draft the chapter.

## Skill catalog

All 74 skills, grouped by role. "Say" gives a trigger phrase the agent will recognize.
(A machine-generated, always-current version of this list — name, version, category,
summary — lives in [SKILL-INVENTORY.md](SKILL-INVENTORY.md); `make check` keeps this
hand-written catalog's versions honest against it.)

### Fiction — plan the promise

| Skill | What it does |
|---|---|
| `fiction-story-sparks` 1.2.0 | Compact story prompts from character + location + object/creature + event + twist + ending. Only on explicit request — never auto-starts your book. |
| `fiction-genre` 3.2.2 | Genre, subgenre, flavor, tone, tropes → `Wiki/Style/genre.md`. Say "pick a genre" / "start a new book". |
| `fiction-audience` 4.0.0 | Target reader age group, content boundaries, structural norms → `Wiki/Style/audience.md`. |
| `fiction-theme` 3.1.0 | The thematic engine: central question, tone, motifs → `Wiki/Story/theme.md`. |
| `fiction-synopsis` 5.2.3 | Turns a braindump into the book synopsis: premise, central question, reader promise, answer, act structure → `Wiki/Story/synopsis.md`. |
| `fiction-series-outline` 1.0.0 | Series-level plan: per-book dramatic-question stack, inter-book promise map, character arc spans, escalation, handoffs → `Wiki/Story/series-arc.md`. Run at series inception; refresh before each later book. |

### Fiction — build the people

| Skill | What it does |
|---|---|
| `fiction-characters` 3.1.1 | One profile per character in `Wiki/Characters/` — personality and dialogue style written as *instructions*, not descriptions. |
| `fiction-psych` 2.1.0 | Per-chapter psychological interior pass (what each character believes/fears/wants underneath the scene's external beats) → `Wiki/Psych/Book-N/`. |
| `fiction-dialogue` 1.0.0 | Draft, diagnose, or revise dialogue when speaker fidelity, unequal knowledge, or subtext matters. |
| `fiction-voiceprompt` 2.0.0 | Compact protagonist `voice_prompt.md` distilled from the character/style/theme/synopsis files. |

### Fiction — build the world

| Skill | What it does |
|---|---|
| `fiction-world` 5.1.1 | The setting build: locations, organizations, systems, events. |
| `fiction-places` 1.0.0 | Scene-bearing sites and landmarks (ruins, rooms, tactical locations) — not full towns. |
| `fiction-factions` 1.0.0 | Factions, institutions, guilds, crews, cults, corporations, rival networks. |
| `fiction-polities` 1.0.0 | Kingdoms, empires, federations, city-states and their territorial divisions. |
| `fiction-religions` 1.0.0 | Religions, philosophies, ancestor traditions, civic faiths, machine creeds. |
| `litrpg-system` 1.0.0 | System rules, attribute formulas, progression curves, class trees, and character sheets for LitRPG/Progression → `Wiki/World/Systems/`. |

### Fiction — shape the book

| Skill | What it does |
|---|---|
| `fiction-outline` 5.3.1 | Chapter-by-chapter outline with `what_must_happen` directives; every conflict binds to an earlier setup and leaves a consequence → `Wiki/Outline/Book-N/outline.md`. |
| `fiction-divergence` 1.0.0 | Anti-convergence pass over the outline: per beat, a default, an inversion, and a cost-shift candidate; keeps the least-expected-but-earned; per-act surprise ledger. |
| `fiction-scenes` 4.0.1 | Chapter beats and scene plans — turning the outline into writable action (`Chapter_NN_Scene.md`). |
| `fiction-style` 7.1.0 | `style_guide.md` + `review_guide.md` — the project's prose law. |
| `fiction-writechapter` 4.1.1 | Draft or continue a chapter from scene plan + voice + canon; maintains the active-context log. |

### Fiction — review the story

| Skill | What it does |
|---|---|
| `fiction-reviewchapter` 2.7.1 | The chapter gate: canon assertions, Chekhov ledger audit (incl. the book mis-quoting itself), character consistency, prose rules → `_Edits/…_Review.md`. |
| `litrpg-audit` 1.0.0 | Deterministic numeric audit: checks stat point math, level curves, skill prerequisites, and status boxes against `ledger.yaml`. |
| `fiction-dev-editor` 2.0.0 | Story-level diagnosis: plot movement, scene purpose, motivation, pacing, setup/payoff. |
| `coldread` 1.0.1 | Blind, read-only test of one chapter or section (fiction or non-fiction): does it deliver the claimed voice, viewpoint, register? Run it *before* rule-loaded review. |
| `fiction-promises` 1.2.0 | The Chekhov ledger: harvest setups, record payoffs, report overdue/due/undated → `Wiki/Story/Book-N/promises.yaml`. Fiction's owner; non-fiction/hybrid use `promise-tracker`. |
| `review-panel` 1.1.3 | Persona review panel for fiction and non-fiction (built per series in `Wiki/Review/`): each persona is a stake + a way of being wrong about THIS book; every quoted line is grep-verified before filing. |
| `drift-check` 1.3.0 | Book-level drift audit — pet words, formula openers/closers, construction density, specifics thinning; non-fiction claim/evidence metrics too. Diagnostic only; never edits. |

### Fiction — edit the prose

| Skill | What it does |
|---|---|
| `fiction-full-editor` 1.2.0 | **Default** sentence-level pass: AI-isms + prose mechanics + line edits in one scan. |
| `fiction-revise` 1.1.0 | Applies the report items you approve to the chapter in place — exact-quote verification, minimal perturbation, change ledger. |
| `fiction-line-editor` 5.2.0 | Line craft/voice layer only (clichés, repetition, POV violations) when isolating that layer. |
| `fiction-prose-editor` 1.3.0 | Prose mechanics only (fragments, choppy S-V-O chains, simile density, rule-of-threes, show-vs-tell). |
| `fiction-aiism-editor` 1.4.1 | AI fingerprints only (forbidden words, machine constructions, self-announcing narration; with LitRPG system exceptions). |
| `levelup` 1.2.0 | Filter-word scan ("she saw / he felt") — reader-distance fixes. |
| `fragment-hunter` 1.2.0 | Mechanically extracts 1–3-word sentences, rebuilds them into performable prose (audiobook prep). |
| `nominalization-hunt` 1.1.0 | Finds abstract self-explanation ("the realization of…"), restores action and observation. |

### Fiction — remove the tells (kill passes)

| Skill | What it does |
|---|---|
| `kill-chapter` 2.0.0 | **Default sweep**: runs all seven passes consecutively, in place, with a combined report. |
| `kill-simile` 1.0.0 | Explain-it similes ("the way…"). |
| `kill-person-who` 1.0.0 | Subtext-by-label ("the [quality] of a [person] who [clause]"). |
| `kill-opinion-personification` 1.0.0 | Non-sentient things "having opinions". |
| `kill-the-whole` 1.0.0 | Hollow "the whole of X" intensifiers. |
| `kill-crutch` 1.0.0 | Generalized filler-word pass — `kill-crutch WORD` hunts any word. |
| `kill-soft` 1.0.0 / `kill-flat` 1.0.0 | The mood-adjectives "soft" and "flat" (also covered by `kill-crutch`). |

### Non-fiction

| Skill | What it does |
|---|---|
| `nonfiction-concept` 1.1.0 | Central argument/thesis, reader transformation, big idea → `Wiki/Concept/thesis.md`. |
| `nonfiction-audience` 1.1.0 | Reader knowledge, objections, prerequisites across five archetypes → `Wiki/Concept/audience.md`. |
| `nonfiction-structure` 1.1.0 | Argument architecture (problem-solution / chronological / conceptual / hybrid) → `Wiki/Concept/structure.md`. |
| `nonfiction-research` 1.0.0 | Manages citation vaults, claims matrices, and primary evidence in `Wiki/Research/`. |
| `nonfiction-chapter-plan` 1.1.0 | Per chapter: claim, evidence, transition, reader takeaway — one `## Chapter NN` section per chapter in `Wiki/Outline/Book-N/plan.md` (the default home; per-chapter files only if the project already uses them). |
| `nonfiction-writechapter` 1.0.1 | Drafts from the plan: explanatory clarity, signposting, concrete examples, varied evidence. |
| `nonfiction-dev-editor` 1.0.0 | Developmental review: thesis scaffolding, argument architecture, cognitive load, conceptual progression. |
| `nonfiction-factcheck` 1.2.0 | Verifies every claim, quote, statistic, date, proper noun; flags unsupported assertions → `_Edits/…_FactCheck.md`. |
| `nonfiction-clarity-edit` 1.1.1 | **Default** clarity pass: jargon density, abstraction ladder, cognitive load, signposting → `_Edits/…_ClarityEdit.md`. |

### Cross-cutting (fiction and non-fiction)

| Skill | What it does |
|---|---|
| `book-reverse-engineer` 1.0.0 | **Retrofit & rebuild**: analyzes existing unguided manuscript, reconstructs Wiki canon, scene outlines, Chekhov promises, voice DNA, and defect findings in `_Edits/…/findings.yaml`. |
| `chapter-pipeline` 1.1.0 | Unified end-to-end runner: scene planning → draft → promise harvest → gate validation → *applied* polish. |
| `gate-check` 1.1.1 | Comprehensive chapter readiness & continuity gate (canon, Chekhov debt, cadence lint, and LitRPG progression audit). |
| `book-status` 1.1.0 | Manuscript dashboard: word counts, gate status, open promises, review tallies. |
| `kanban-board` 1.0.0 | Per-book production board (`Wiki/Story/Book-N/kanban.md`): one card per chapter in Backlog → Ready → Drafting → Review → Done, derived mechanically from the outline, scene plans, drafts, and gate reports, with next-move routing. Regenerated view, never the source of truth. |
| `canon-guard` 1.0.0 | Safeguards canon from drift; impact scan before deliberate world/character edits. |
| `series-continuity` 1.0.0 | Audits multi-book consistency: character states, resolved secrets, timeline elapsed. |
| `reader-persona-review` 1.0.1 | Qualitative reader feedback across diverse archetypes and panel presets with synthesis. |
| `compile-manuscript` 1.0.0 | Stitches chapter drafts into continuous manuscript with front/back matter and clean exports. |
| `book-packaging` 1.0.0 | Generates marketing kits: back-cover blurbs, query letters, retail keywords, cover art briefs. |
| `social-media-marketing` 1.0.0 | Facebook, Instagram, and TikTok campaigns: launch plans, ongoing content calendars, scripts, captions; optional paid-ads plan → `Wiki/Marketing/`. |
| `promise-tracker` 1.1.0 | Unified promise/claim ledger — Chekhov setups (fiction) or thesis threads and unresolved tensions (non-fiction) → `Wiki/Story/Book-N/promises.yaml`. Owns non-fiction **and hybrid** projects. |
| `kill-hedge` 1.0.0 | Removes hedges and qualifiers that weaken claims. |
| `kill-passive` 1.0.0 | Converts passive to active for clarity and authority. |
| `kill-acronym` 1.0.1 | Flags unexplained initialisms/acronyms on first use. |

### Diagnostics (never edit — they measure and route)

| Skill | What it does |
|---|---|
| `drift-check` 1.3.0 | The gradient across the whole book (see Review). |
| `burstiness-check` 1.5.0 | Sentence/paragraph variance, repeated openings, dialogue ratio vs. the book's own baseline — excludes system callout blocks from prose variance. |
| `pangram` 2.0.0 | Statistical patterns associated with AI-detection risk (predictability, lexical diversity, uniform construction). |

### Utilities

| Skill | What it does |
|---|---|
| `name-generator` 1.2.0 | Character names from 24 culture corpora. Collision-checks against existing fiction/games/brands before a name enters canon. |
| `town-generator` 1.1.0 | Settlement names (lexical, 11 corpora + epithets). |
| `fantasy-settlement` 1.0.1 | Full settlement dossier: population, economy, districts, security. |

### Meta

| Skill | What it does |
|---|---|
| `skill-builder` 2.0.0 | Designs and validates a new skill for the library, provider-neutral. |

## Recipes

Phrases that map to skills (the agent routes on them):

- "Reverse-engineer existing draft" → `book-reverse-engineer` → `_Edits/Book-N/reverse-analysis.md` + `findings.yaml`
- "Review chapter 5" → `fiction-reviewchapter` (or `gate-check`) → `_Edits/Book-N/Chapter-005_Review.md`
- "Run chapter pipeline on chapter 3" → `chapter-pipeline`
- "Show book status / dashboard" → `book-status`
- "Show the board / what's in progress" → `kanban-board`
- "Safely update character fact" → `canon-guard`
- "Audit series continuity" → `series-continuity`
- "Run reader persona review on chapter 2" → `reader-persona-review`
- "Compile manuscript for export" → `compile-manuscript`
- "Write back-cover blurb and query letter" → `book-packaging`
- "Plan my launch on TikTok / Instagram / Facebook" / "write a TikTok script" → `social-media-marketing`
- "Organize research sources" → `nonfiction-research`
- "Review non-fiction argument flow" → `nonfiction-dev-editor`
- "Apply fixes 1, 3, and 5" → `fiction-revise`
- "Clean this chapter" / "run the kill passes" → `kill-chapter`
- "Full edit on chapter 7" → `fiction-full-editor`
- "Check loose ends" / "what have I forgotten to pay off" → `fiction-promises`
- "Why does the back half feel flatter?" → `drift-check`
- "What would a romance reader think of the act break?" → `review-panel` (act-level QA; `reader-persona-review` for a quick single-chapter pulse)
- "Does chapter 12 actually sound like a teenager?" → `coldread`
- "Kill the word 'just'" → `kill-crutch just`
- "Name a harbor town" → `town-generator`; "name the antagonist" → `name-generator`
- "Verify the claims in chapter 3" → `nonfiction-factcheck`

## House rules worth knowing

1. **Wiki wins.** A draft that contradicts canon is wrong until you change canon.
2. **No invented proper nouns.** If a skill needs a name the Wiki doesn't have, it
   stops and asks; character/town names route through the generators with a
   collision check.
3. **Editing passes are opt-in.** Review gates run as part of the workflow; kill
   passes and full edits only when you ask.
4. **Structural problems are re-drafts, not edits.** Missing beats or a canon breach
   baked through a chapter go back to the scene plan.
5. **Diagnostics never edit.** `drift-check`, `burstiness-check`, `pangram` report;
   routing to an editing skill is the fix.
6. **Verified quotes.** Panel findings grep-verify every line they attribute to your
   book — personas hallucinate, and the library knows it.
7. **Your project owns its library.** Updating skills in this repo doesn't change
   existing projects. When you want a project to take an update, run
   `tools/update-project.sh <project-dir>` to see what changed, then add `--apply` to
   copy the library in and rewrite the project's `.agents/skills/.storycraft-source`
   pin — commit it in the project repo. (The long way still works: copy `skills/` over
   `.agents/skills/` and commit.)
