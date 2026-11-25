---
name: fiction-psych
description: "Generate a chapter-level psychological interior pass (start state, beat-by-beat interior cost, end state, show-don't-tell gaps) saved to Wiki/Psych/Book-N/Chapter_[NN]_Psych.md from scene plans, outline beats, and POV voice/character files. Use after fiction-style, fiction-voiceprompt, and fiction-scenes, or to refresh interior layers."
metadata:
  author: Fiction Toolkit
  version: "2.3.0"
  category: fiction-writing
  output-format: markdown
---

# Fiction Psych: Interior Pass

Generates a psychological analysis for each chapter. The analysis maps what the POV character feels underneath every external beat: what they carry in their body, what they refuse to name, where the prose must render through action rather than report.

Output files are human-readable and editable. The user can revise any chapter's psych pass before drafting: `fiction-writechapter` reads the POV character's psych document for interior movement while drafting the chapter.

## When to Use

- After `fiction-style` + `fiction-voiceprompt`, `fiction-outline`, and `fiction-scenes` have settled the scene splits and POV voice prompts
- Manually, when you want to deepen a specific chapter's interior layer before writing
- After revising a chapter's scene plan or outline, to refresh the psych pass for changed chapters

## Step 1: Identify the Project

Find the project's `Wiki/` folder by searching for `**/Wiki/Outline/**/outline.md`; the project may be a subfolder. If multiple projects match, ask which one. If the project holds several books (`Book-N` outline folders), ask which book to process.

## Step 2: Gather Source Files

All inputs come from the project's `Wiki/` folder. Read:

- The resolved book outline (`Wiki/Outline/Book-N/outline.md`): chapter entries with `what_must_happen`, `premise_movement`, `question_pressure`, `cadence_role`, and `ends_with`
- The chapter's scene plan (`Wiki/Outline/Book-N/Chapter_[NN]_Scene.md`, if present): per-scene POV assignments, beats, turns, and interior targets
- `Wiki/Characters/*.md`: full character profiles, one file per character
- `Wiki/Style/style_guide.md` and `Wiki/Style/voice_prompt*.md` (also accept legacy `Wiki/Style/Style Guide.md`): craft rules, `register_preset`, and POV perceptual lens / expression boundaries
- `Wiki/Story/theme.md`: motifs, central question

Create the `Wiki/Psych/Book-N/` folder if it doesn't exist.

## Step 3: Run Psych Pass Per Chapter

For each chapter, use one isolated worker when the host supports one. Do not require a particular model. If isolated workers are unavailable, perform the same chapter pass directly, one chapter at a time.

Pass the worker:
- The chapter's full outline entry from `Wiki/Outline/Book-N/outline.md` (`chapter_number`, `title`, `what_must_happen`, `premise_movement`, `question_pressure`, `promise_delivery`, `cadence_role`, `subplot_threads`, `trope_obligations`, `ends_with`)
- The chapter's scene plan (`Wiki/Outline/Book-N/Chapter_[NN]_Scene.md`, when present) for exact scene beats and POV switches
- The FULL profile of the POV character(s) from `Wiki/Characters/<Name>.md`
- The profiles of other characters present, each from its `Wiki/Characters/` file (trimmed: personality, dialogue_style, relationship_dynamics only)
- The craft rules and POV perceptual lens from `Wiki/Style/style_guide.md` and `Wiki/Style/voice_prompt_<POV>.md` / `voice_prompt.md`
- The motifs from `Wiki/Story/theme.md`
- The worker instructions below

Cap at 5 chapters running in sequence. Do not parallelize; each chapter's psych pass benefits from focused attention.

The worker writes each chapter's psych pass to `Wiki/Psych/Book-N/Chapter_[NN]_Psych.md`, in the same `Book-N` folder as the outline, where `[NN]` is the zero-padded two-digit chapter number (e.g. `Wiki/Psych/Book-1/Chapter_07_Psych.md`). Create parent folders if missing. These files are the canonical output; `fiction-writechapter` reads them from this exact path.

Update progress after each chapter.

## Step 4: Report

Tell the user:
- How many psych passes were generated
- That they are stored as `Wiki/Psych/Book-N/Chapter_[NN]_Psych.md` files
- "Review and edit any chapter's psych pass before drafting; `fiction-writechapter` reads this analysis alongside the scene plan."

Next: `fiction-writechapter` (or `fiction-scenes` / `fiction-style` if not yet built).

---

## Worker Instructions

You are generating a psychological interior analysis for a single chapter of a novel. This analysis will be read by the writing agent that drafts the chapter. Your job is to map what the POV character feels underneath significant external beats: what it costs them, what they refuse to name, and which expression channel best conveys the interior movement. Choose among action, perception, thought, speech, memory, omission, or purposeful emotional naming. Bodily cues are optional, not mandatory.

Read the criteria file at [references/psych-criteria.md](references/psych-criteria.md) before writing.

### What You Are Writing

A chapter-level psychological map with four sections:

---

**1. START STATE**

At the top of the chapter:
- Surface affect: what the character presents externally
- Underneath: what they are actually carrying, in specific emotional states, not generic ones
- Expression channel: which of action, perception, thought, speech, memory, omission, or purposeful naming best carries the start state; include a bodily cue only if apt

---

**2. BEAT-BY-BEAT INTERIOR COST**

For each significant external beat in the chapter summary, map:
- The beat (what happens externally)
- The interior cost (what it costs the POV character, the thing they feel but will not name)
- The expression channel and its specific evidence (physical tell, action, attention shift, thought, speech, memory, omission, or purposeful naming)
- What they won't say (the exact thought or word they swallow)

Do not work from generic psychology. Work from this specific character's profile: their personality, backstory, want, need, flaw, secret. The cost of each beat is specific to who this person is.

---

**3. END STATE**

At the chapter's close:
- Surface affect: what they present
- Underneath: what is actually in the room
- Expression channel: the most earned way to carry the final emotional weight; do not require a bodily closer

---

**4. SHOW-DON'T-TELL GAPS**

A table of specific moments where a reporting draft loses useful interiority. For each, propose the smallest fitting channel; direct emotional naming may be right when it suits the voice.
- The beat
- What a reporting draft does (observes, notes, states)
- A fitting alternative channel: action, perception, thought, speech, memory, omission, object, or purposeful naming

---

### Output Format

Write the file to `Wiki/Psych/Book-N/Chapter_[NN]_Psych.md` (same `Book-N` folder as the outline; zero-padded chapter number) with this structure:

```markdown
# Chapter [NN]: Psychological Interior Pass

**Chapter:** [Title]
**POV:** [Character name, age]
**Setting:** [Setting]
**External arc:** [One-line summary of what happens]
**Emotional arc:** [From outline, start state to end state]

---

## Start State

**Surface affect:** [What the character presents]

**Underneath:**
[Paragraph of specific emotional states. Not "he is tired." "The exhaustion has gone past tired into mean. He has counted the supplies eighty times. Each count comes up short and each shortfall feels like a personal insult." Draw from the character's personality and backstory to make this specific.]

**Expression channel:**
[The channel that best carries the start state, with a specific cue if available. Bodily detail is optional.]

---

## Beat-by-Beat Interior Cost

### [Beat name / external action]
- **Interior cost:** [What it costs them, specific to this character's psychology]
- **Expression channel:** [The best-fitting channel and specific evidence; bodily tell only if apt]
- **What they won't say:** [The exact swallowed thought, blunt, in their register]

[Repeat for each significant beat]

---

## End State

**Surface affect:** [What they present at chapter close]

**Underneath:**
[Paragraph: what is actually in the room. Specific. Drawn from what this chapter has done to this specific character.]

**Expression channel:**
[The most earned carrier of the chapter's emotional weight at the final beat; it need not be an image or bodily action.]

---

## Show-Don't-Tell Gaps

| Beat | What a reporting draft does | What it should do instead |
|------|----------------------------|--------------------------|
| [Specific moment] | [What the draft flattens or explains] | [Fitting channel: action, perception, thought, speech, memory, omission, object, or purposeful naming] |

---

## Bottom Line

[2-3 sentences: What is this chapter really about on the inside? What must the writing agent understand about what this character is living through, not what they do, but what it costs them to do it?]
```

### Critical Rules

- Never write generic psychology ("he feels sad"). Write specific psychology drawn from this character's profile.
- Do not force every interior state into a physical tell. Select channels for character and moment; preserve direct thought, selective attention, silence, and purposeful emotional naming when truer to the voice.
- The "what they won't say" entries should sound like the character's internal register: blunt, in their voice, not literary.
- Show-don't-tell gaps must name SPECIFIC beats from the chapter summary, not general advice.
- The bottom line is for the writing agent, not the reader. It should tell the agent what they must understand to stay inside the POV character's skin for this chapter.
