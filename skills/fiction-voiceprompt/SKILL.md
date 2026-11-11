---
name: fiction-voiceprompt
description: "Generate or refresh a compact protagonist voice_prompt.md from character, style, theme, audience, genre, and synopsis files. Use when user says voice prompt, protagonist voice, refresh voice, or robotic prose prevention."
metadata:
  author: Fiction Toolkit
  version: "2.2.0"
  bundled-dependencies: book-status
  category: fiction-writing
  output-format: markdown
---

# Voice Prompt Generator

Create a compact `Wiki/Style/voice_prompt.md` (and per-POV `Wiki/Style/voice_prompt_<Character_Name>.md` files for dual/multi-POV books) that a chapter-writing agent can obey directly. This is not a full style guide. It is the fast-access POV and voice firewall for each viewpoint character.

## Step 1: Identify Project Files

Find these paths in the working directory; the project may live in a subfolder:

Required:
- `**/Wiki/Story/synopsis.md`
- `**/Wiki/Style/style_guide.md` or legacy `**/Wiki/Style/Style Guide.md`
- `**/Wiki/Characters/**/*.md`

Optional but strongly preferred:
- `**/Wiki/Story/theme.md`
- `**/Wiki/Style/audience.md`
- `**/Wiki/Style/genre.md`
- `**/Wiki/Style/review_guide.md` or legacy `**/Wiki/Style/Review Guide.md`
- existing `**/Wiki/Style/voice_prompt*.md` or root `**/voice_prompt.md`

If multiple projects exist, ask which one. Inspect `pov_mode` and `pov_1` / `pov_2` in `Wiki/Style/style_guide.md` (or infer from `Wiki/Story/synopsis.md`) to determine whether the book is single-POV or dual/multi-POV.

## Step 2: Read Inputs

Read:
1. Synopsis
2. Style guide
3. Every POV character file in full, plus any key non-POV deuteragonist/antagonist files needed for relationship voice
4. Theme, audience, genre, and review guide if present
5. Existing voice prompt(s) if present, to preserve useful project-specific rules

## Step 3: Build the Voice Prompt(s)

- **Single-POV project:** Compose `Wiki/Style/voice_prompt.md` for the sole POV protagonist using the structure below.
- **Dual or multi-POV project:** Compose one `Wiki/Style/voice_prompt_<Character_Name>.md` per POV character (replacing spaces with underscores, matching `Wiki/Characters/<Character_Name>.md`), AND write `Wiki/Style/voice_prompt.md` as the **Multi-POV Voice Index & Contrast Firewall** linking each per-POV file and explicitly defining how the POVs contrast in sentence rhythm, emotional translation, perception filters, and metaphor domains so POV 1 never bleeds into POV 2.

Compose each POV character's voice prompt using this structure:

```markdown
# Voice Prompt: [Protagonist Name] Close-[POV] Rewrite

## Core POV Rule
[POV, tense, distance, and whose perception controls the prose.]

## Who [Protagonist] Is
[Age, background, pressure, contradictions, what they want, what they hide.]

## Interior Voice
[How their thoughts sound under calm, pressure, fear, desire, shame, anger, grief.]

## What They Notice
[Concrete perception filters from background, job, class, culture, body, trauma, desire, genre.]

## Emotional Translation Rules
[How to turn emotion into body, action, object, silence, and direct thought.]

## Motif Limits
[Allowed motifs, where they belong, where they become overuse, and what to vary them with.]

## Language Firewall
[Specific words, abstractions, registers, and sentence patterns that would make this protagonist sound robotic, analytical, therapist-like, outline-like, generic, or unlike themselves.]

## Relationship Voice
[How narration changes around key characters without violating POV.]

## Direct Thought Examples
[10-20 short thought lines the protagonist might actually think.]

## Before / After Examples
[5-10 micro-rewrites converting flat, robotic, abstract, or authorial prose into the protagonist's voice.]

## Final Standard
[A short pass/fail test for whether a paragraph belongs to this protagonist.]
```

## Step 4: Hard Requirements

The voice prompt must:
- Be specific enough that a chapter writer can draft from it without reading the full style guide.
- Preserve the protagonist's lived background without turning it into stereotype or exposition.
- Include a negative voice definition: what the prose must never sound like.
- Include motif boundaries so one strong motif does not become the syntax for every emotional beat.
- Include before/after examples with concrete replacements.
- Prefer body, object, action, silence, and blunt thought over abstract explanation.

Avoid:
- Generic advice that could apply to any protagonist.
- Status labels like "bestselling" or "literary" without actionable rules.
- Therapy language unless the protagonist would genuinely think that way.
- Analytical/engineering language unless the protagonist's actual voice supports it.
- Craft-outline terms in the generated prompt examples.

## Step 5: Save and Report

Write the full voice prompt Markdown to `Wiki/Style/voice_prompt.md` in the project (create the `Wiki/Style/` folder if it is missing). For dual or multi-POV books, also write `Wiki/Style/voice_prompt_<Character_Name>.md` for each POV protagonist and keep `Wiki/Style/voice_prompt.md` as the cross-POV contrast and routing index. If a legacy voice prompt exists under another name or at the project root, still write the canonical path(s); downstream skills (`fiction-writechapter`, `project_state.py draft-packet`) read the canonical paths. Overwrite on refresh; the files are safe to regenerate.

Return only:

`Voice Prompt written to Wiki/Style/voice_prompt.md (and per-POV voice_prompt_<Name>.md files if multi-POV).`

## Editorial decisions and current continuity

Read only applicable active reusable editorial-memory entries and local passage decisions from Wiki/Style/editorial-decisions.json when present. Preserve their scope, resolve conflicts against current user/book instructions, and keep preference records during regeneration. Examples illustrate voice; do not copy them into unrelated prose. For fiction, consult current confirmed knowledge events from Wiki/Story/Book-N/knowledge.json as of this scene. Story chronology and reader reveal order differ in flashbacks. Missing coverage is unknown. After drafting, harvest evidence with fiction-knowledge; never silently establish a new canon fact from an unsupported belief.
