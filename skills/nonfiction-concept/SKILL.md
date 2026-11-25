---
name: nonfiction-concept
description: "Define the book's central argument/thesis, target reader transformation, and 'big idea'. Use when user says 'define concept', 'what is this book about', 'central thesis', 'big idea', or when starting a non-fiction book."
metadata:
  author: Nonfiction Toolkit
  version: "1.2.0"
  category: nonfiction-writing
  output-format: markdown
---

# Nonfiction Concept Definer

**Output:** `Wiki/Concept/thesis.md` in the project's `Wiki/` folder. All inputs are read from `Wiki/` Markdown files; all output is written as Markdown. All work stays in the project's Markdown files.

## Step 1: Locate the Project and Load Context

The project may live in a subfolder of the working directory, so search for the upstream files:

- `**/_Intake/series-brief.md`, `**/_Intake/nonfiction-brief.md`, `**/_Intake/Book-*/premise.md`, and `**/_Intake/Book-*/raw-notes/*.md`: Read first when present to pre-populate the core question, book mode (trade narrative, memoir, practical guide, academic, or hybrid), comps, and voice boundaries instead of asking cold in a vacuum.
- `**/Wiki/Concept/audience.md`: Recommended, not required — if it exists, read it for target reader profile, knowledge level, objections, prerequisites. If missing, proceed; the concept can derive the reader from intake/conversation, and `nonfiction-audience` refines it afterward.
- `**/Wiki/Concept/structure.md`: Optional. If it exists, read it for chosen architecture and rhetorical mode.

Treat the folder containing `Wiki/` as the project root. Read the frontmatter and `##` sections of each file that exists.

## Step 2: Load Reference Files

Read these craft knowledge files before generating:

- [references/argument-construction.md](references/argument-construction.md): how to build a central thesis that holds across a full book; what makes an argument deployable vs. abstract
- [references/transformation-mapping.md](references/transformation-mapping.md): how to define the reader's before/after state, what makes a transformation concrete and measurable
- [references/big-idea-frameworks.md](references/big-idea-frameworks.md): frameworks for identifying the "big idea" (one-sentence hook, unique mechanism, contrarian insight); how to differentiate from competing books

Extract: what makes a thesis load-bearing, what makes a transformation concrete and promise-able, how to find the unique angle in a crowded market.

## Step 3: Gather User Input

Ask the user for one piece of information using the host's normal question mechanism:

**Question:** "What is the one thing you want your reader to believe, understand, or be able to do after finishing this book? A sentence, a claim, a transformation — whatever you have. Or say 'derive from audience' and I'll build one from your reader's pain points and aspirations."

This question is intentionally open-ended. The concept skill pulls the core argument out of the writer.

## Step 4: Generate the Concept Engine

You may generate directly or, when the host supports one, use an isolated worker with the context gathered above to keep the main conversation clean; either way, apply the rules below. If the user provided a concept seed, build outward from their words and do not override their intent. If "derive from audience", build from the reader's stated problems and desired outcomes.

Cover every field in [references/json-schema.json](references/json-schema.json) as frontmatter or a section (checklist: thesis, reader_transformation, big_idea, unique_angle, core_promise, evidence_architecture). Adapt each field to the book's actual tradition (argumentative/practical vs trade narrative/memoir/essay):

**thesis**: For argumentative or practical books, a declarative central argument the book proves. For narrative nonfiction, investigative journalism, or memoir, frame this as the central controlling question, narrative inquiry, or throughline rather than forcing a synthetic B2B claim.

**reader_transformation**: The specific before/after shift. Define:
- `from_state`: Where the reader starts (assumptions, questions, gap, or context)
- `to_state`: Where the reader ends (new clarity, capability, witness, or perspective)
- `measure`: How the shift shows up — a concrete practice indicator for instructional books, OR a concrete interpretive/witness shift for memoir/narrative nonfiction (do not force pseudo-metrics onto literary narrative).

**big_idea**: The one-sentence positioning hook that distinguishes this book. Use `"[Core insight/story] + [Why it matters]"` for narrative/memoir or `"[Unique mechanism] + [Reader outcome]"` for practical/argument books.

**unique_angle**: What makes this book stand apart from neighboring titles (fresh archival access, lived witness, synthesis, framing, or field evidence).

**core_promise**: What the reader gets by reading to the end, matched to the book's register (no synthetic `"By the end of this book you will [metric]"` hype on memoirs or histories).

**evidence_architecture**: The types of proof this argument will use (primary research, case studies, frameworks, data, personal narrative, expert interviews, historical analysis, counter-arguments addressed). List 3-6 types with one sentence each on why that evidence serves this thesis.

## Step 5: Save and Confirm

Write the result to `Wiki/Concept/thesis.md` under the project root found in Step 1. Create the `Wiki/Concept/` folder if it does not exist. `Wiki/Concept/thesis.md` is the single source of truth for concept; downstream skills (audience, structure, chapter-plan) read it from that exact path.

File shape:

```markdown
---
thesis: "The central argument as a single declarative sentence. Quote it; it may contain colons."
big_idea: "The one-sentence marketplace hook."
core_promise: "By the end of this book you will [specific outcome]."
---

## Reader Transformation

### From State
[Where the reader starts — knowledge, belief, capability, pain. 2-3 sentences.]

### To State
[Where the reader ends — new knowledge, shifted belief, new capability, relief. 2-3 sentences.]

### Measure
[Concrete indicator of transformation. Not a feeling. One sentence.]

## Unique Angle

[One paragraph: the contrarian insight, the missing step others skip, the synthesis nobody has made, the evidence nobody has gathered.]

## Evidence Architecture

### [Evidence Type 1]
[Why this evidence serves this thesis. One sentence.]

### [Evidence Type 2]
...

### [Evidence Type N]
...
```

Frontmatter must be plain, conservative YAML: scalar values only here, strings quoted when they contain colons. `##` sections for each major component so every field stays grep-able.

Then present the concept to the user in readable form (do not paste the raw file) and ask: "What should I change?"

If changes are needed, edit `Wiki/Concept/thesis.md` in place and re-present until approved.

When approved: if `Wiki/Concept/audience.md` does not exist yet, say `"Next: use nonfiction-audience to profile your reader."`; if `audience.md` already exists, say `"Next: use nonfiction-style to lock voice and citation rules, then nonfiction-structure."`
