---
name: nonfiction-style
description: "Establish nonfiction prose voice, citation conventions, register preset (trade-narrative, memoir-literary, practical-guide, or academic-monograph), and banned phrasing at Wiki/Style/style_guide.md and review_guide.md. Use when starting nonfiction prose styling or adjusting narrative/academic tone."
metadata:
  author: Nonfiction Toolkit
  version: "1.0.0"
  bundled-dependencies: book-status
  category: nonfiction-writing
  output-format: markdown
---

# Nonfiction Style & Register

Establish the book's prose register, citation discipline, and banned-phrasing rules before chapter drafting (`nonfiction-writechapter`). Reads `_Intake/`, `Wiki/Concept/thesis.md`, `Wiki/Concept/audience.md`, and `Wiki/Concept/structure.md` so register choices align with the book's actual reader and rhetorical mode.

## Selectable Nonfiction Registers

Choose one primary `nonfiction_register` (plus optional per-section `mode` overrides in `HYBRID` or multi-mode books):

1. **`trade-narrative`** (investigative, history, journalism, serious general nonfiction):
   - Narrative attribution allowed and often preferred (`"Smith (2022) showed..."`, inline scene grounding, concrete opening scenes).
   - No forced `"To prove [sub-claim], we examine..."` section templates or royal `"we"`.
   - Active prose, calibrated epistemic certainty (`nonfiction-factcheck` alignment), endnotes or smooth prose attribution instead of APA parenthesis walls.
2. **`memoir-literary`** (memoir, personal essay, literary biography, witness narrative):
   - First-person voice (`I`), lived sensory scene-work, reflective interiority, and associative transitions allowed.
   - `firsthand_account` claims distinguished cleanly from archival/empirical claims in `evidence.py`.
   - Zero corporate/textbook framing (`takeaways`, `frameworks`, `"To prove..."`).
3. **`practical-guide`** (practitioner playbook, engineering/leadership manual, how-to):
   - Direct `you` or imperative guidance balanced with real case examples and concrete artifacts.
   - Prerequisite gating and scannable structural signposting without academic citation stiffness.
4. **`academic-monograph`** (scholarly treatise, peer-facing monograph, technical reference):
   - Formal third-person or editorial `"we"` as chosen, rigorous parenthetical/footnote citations, explicit hypothesis/evidence coupling (`clarity-rules.md` rules #9 and #15 active when selected).

## Procedure

1. Read `_Intake/series-brief.md` (or `_Intake/nonfiction-brief.md`), `Wiki/Concept/thesis.md`, `Wiki/Concept/audience.md`, and `Wiki/Concept/structure.md` if present.
2. Propose a matching `nonfiction_register` (`trade-narrative`, `memoir-literary`, `practical-guide`, or `academic-monograph`), point of view (`I` / editorial `we` / close third), citation convention, and [diction and clock time](../book-status/references/diction-and-time.md) preference (`clock_mode: words` vs `digits`). Ask the user once for adjustments if ambiguous.
3. Write `Wiki/Style/style_guide.md` and `Wiki/Style/review_guide.md`:
   - Frontmatter includes `nonfiction_register: <register>`, `citation_style: narrative | parenthetical | endnotes | footnotes`, and `clock_mode: words | digits`.
   - Separate universal clarity defects (vagueness, overclaiming beyond evidence, undefined terms of art for the audience) from register-specific mechanics.
4. Present a concise summary and next step: `Next: nonfiction-structure (if structure.md is missing), or nonfiction-research -> nonfiction-chapter-plan.`
