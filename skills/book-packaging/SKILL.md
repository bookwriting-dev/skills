---
name: book-packaging
description: "Generate professional publishing and marketing packaging kits including back-cover blurb copy, query letters, loglines, Amazon retail metadata, and artist cover design briefs. Use when user says 'write book blurb', 'query letter', 'generate cover brief', 'create book metadata', or 'package book for publication'. Also use for narrator pronunciation sheets and audiobook pronunciations."
metadata:
  author: Storycraft Skills
  version: "1.3.0"
  bundled-dependencies: book-status
  category: cross-cutting
---

# Book Packaging & Marketing Kit

Translates a finished or near-finished manuscript and its Storycraft canon into market-facing publishing assets: high-converting blurbs, traditional publishing query letters, retail metadata and keywords, and cover design briefs for illustrators/designers.

For a pronunciation sheet alone, go directly to **Audiobook pronunciation sheet** and deliver only that requested sheet.

## Step 1: Load Project Context

Search the project and read whatever canonical planning files exist for the target book (`Book-N`):

- **Fiction:** `Wiki/Style/genre.md`, `Wiki/Style/audience.md`, `Wiki/Story/theme.md`, `Wiki/Story/synopsis.md`, `Wiki/Story/Book-N/synopsis.md`, and primary POV/protagonist files in `Wiki/Characters/`.
- **Non-fiction:** `Wiki/Concept/thesis.md`, `Wiki/Concept/audience.md`, `Wiki/Concept/structure.md`, and `Wiki/Outline/Book-N/plan.md`.
- **Advisory inception notes:** `_Intake/series-brief.md` and `_Intake/Book-N/premise.md` (for comp titles, pitch angles, or author bio notes not yet in `Wiki/`).

If `Wiki/Style/` or `Wiki/Concept/` lacks genre/audience/synopsis context, tell the user what is missing (suggesting `fiction-genre` / `fiction-audience` / `fiction-synopsis` or `nonfiction-concept` / `nonfiction-audience`) and ask only for the missing pitch elements (genre, target reader, core hook, comp titles, author bio) before continuing. Do not invent canon names, plot turns, or comp details unsupported by the project.

## Step 2: Verify Manuscript & Delivery State

1. Inspect `Chapters/Book-N/` to compute actual total word count (rounded to the nearest thousand for query letters) and confirm which chapters exist on disk.
2. Check for `compile-manuscript` outputs and `Chapters/Book-N/export/<profile>/export-manifest.json` for the target `beta`, `submission`, or `publication` profile.
3. Confirm that blurb promises, stakes, and word counts reflect the authoritative current manuscript rather than an outdated outline. If packaging is generated from an unchecked export preview or before final `gate-check` / `nonfiction-factcheck` passes, disclose that explicitly in the generated header (`Delivery Basis: PRE-EXPORT DRAFT` or `UNCHECKED PREVIEW`). Conversion alone does not prove release readiness.

## Step 3: Generate the 4 Packaging Assets

Produce all four sections tailored to the book's genre/category and target audience boundaries (`audience.md`):

1. **Back-Cover Blurb Copy:**
   - Hook line, protagonist/reader dilemma, escalating stakes, and a forward-pulling payoff question (never spoil late-book twists).
   - 3 length variants: **Micro** (~50 words for ads/taglines), **Standard** (150–200 words for back cover and retail product pages), **Expanded** (with positioning and comp-title hooks).
2. **Traditional Query Letter:**
   - Salutation and personalization placeholder (`[Agent Name]`), one-sentence logline, metadata block (title, series position, genre/category, exact rounded word count, audience), ~250-word pitch paragraphs, 2–3 comparable titles (published within the last 3–5 years when supplied or marked `[VERIFY COMP DATE]` if proposed), and brief bio placeholder.
3. **Retail Metadata & Keywords:**
   - 7 Amazon / retail long-tail search keyword phrases matching reader search intent (no trademarked author names or misleading claims).
   - BISAC / retail category recommendations appropriate to the book's genre and age group.
   - Taglines and series subtitle options.
4. **Cover Design Brief:**
   - Visual genre expectations and color/mood palette aligned with `genre.md` and `audience.md`.
   - Focal imagery (grounded in canonical setting/character objects from `Wiki/`), background cues, and typography style guidance.
   - Explicit avoidance list (visual cliches or elements that mismatch tone or age category).

## Step 4: Save to Canonical Layout

Save the packaging kit to the canonical per-book path:
`Wiki/Story/Book-N/packaging.md`

Include a concise header recording the book, target export profile (or draft basis), verified word count, and link to `export-manifest.json` when present.

## Step 5: Present & Hand Off

Present the Micro and Standard blurb variants, logline, and verified word count to the user alongside the saved path (`Wiki/Story/Book-N/packaging.md`). Offer next steps:
- Refine blurb tone, comps, or cover brief details.
- Run `social-media-marketing` (which consumes `Wiki/Story/Book-N/packaging.md` directly) to build launch and ongoing social campaigns.
- Run `compile-manuscript` if a verified `submission` or `publication` export package has not yet been generated.

## Audiobook pronunciation sheet

On request, run [editorial_tools.py](../book-status/scripts/editorial_tools.py) with `--root . --book Book-N pronunciation`. Present a narrator sheet ordered by first use, with the name, place or invented term, first chapter and quotation, and the author-approved pronunciation with stressed syllables in capitals. List pending readings as questions for the author. Match the series glossary and spellings in the manuscript before adding terms. Check each narrative unit for uncatalogued names, places and coined words. Include these with repeated --term arguments. The helper verifies each term against the actual text and locates its first use. Save each author's supplied reading with `pronunciation --approve "TERM" --reading "STRESSED reading"` and regenerate the sheet. Approvals live in the project's shared Wiki/Style/pronunciations.json and carry into later books when the same term and profile appear.
