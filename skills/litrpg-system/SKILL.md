---
name: litrpg-system
description: "Design, balance, and document LitRPG and progression fantasy mechanics — system rules, attribute formulas, level-up curves, class trees, skill costs, encounter scaling, and character sheets. Use when user says 'design litrpg system', 'create game mechanics', 'balance litrpg', 'build class tree', 'litrpg system', 'power curve', 'system bible', or after choosing LitRPG in fiction-genre."
metadata:
  author: Fiction Toolkit
  version: "1.1.0"
  category: fiction-writing
---

# LitRPG System Designer

Designs, balances, and establishes the game-like mechanics and mathematical rules for a LitRPG or Progression Fantasy series. Populates the canonical `Wiki/World/Systems/` directory, initializes character stat sheets under `Wiki/Characters/`, and seeds the machine-readable progression ledger so all downstream drafting and gating maintain airtight numeric continuity.

## Core Contract

A great LitRPG maintains strict mechanical consistency:
1. **No Free Lunch:** Every ability has a resource cost, cooldown, or limitation; every advantage has a counter; power is earned through struggle and optimization rather than authorial fiat.
2. **Deterministic Math:** Attribute formulas, XP thresholds, level scaling, and stat point rewards are clearly defined in canon so reader audits and automated scripts confirm the numbers add up.
3. **Anti-Stat-Dump UI:** System notifications use standardized Markdown callouts (`> [!SYSTEM]`) with delta-first notation, reserving full character sheets for major arc milestones.

---

## Step 1: Load Project Context

Search the project's `Wiki/` folder for existing canon:
- `Wiki/Style/genre.md`: confirm LitRPG subgenre (VRMMO, System Apocalypse, Isekai/Portal, Cultivation/Progression).
- `Wiki/Story/synopsis.md`: identify protagonists, primary threats, world premise, and tone.
- `Wiki/Characters/`: inspect existing character profiles.

If `Wiki/World/Systems/` does not exist, create it.

---

## Step 2: Gather System Parameters

Ask the user or derive from the synopsis:
1. **System Origin & Personality:** Is the system an ancient cosmic law, an antagonistic dungeon AI, a cold numerical overlay, or a playful companion?
2. **Attribute Framework:** Classic 6-stat (STR, AGI, CON, INT, WIS, CHA/LCK), streamlined 3-stat (Body, Mind, Soul), or custom?
3. **Progression Model:** Quadratic scaling (Base * Level^2), tiered breakthroughs (Iron -> Bronze -> Silver), or exponential?
4. **Free Stat Points:** Default 5 points per level, or custom?

---

## Step 3: Read Design References

Read these domain references before generating system documents:
- [references/system-design-principles.md](references/system-design-principles.md) — Core balance, dopamine cadence, and "no free lunch" rules.
- [references/stat-box-guide.md](references/stat-box-guide.md) — UI syntax, notification formatting, and audiobook-safe conventions.
- [references/progression-curves.md](references/progression-curves.md) — Level formulas, stat caps, and derived pool math.
- [references/encounter-and-dungeon-guide.md](references/encounter-and-dungeon-guide.md) — Threat grading (F to S), dungeon layers, and boss phase mechanics.

---

## Step 4: Generate System Canon Files

Write three core system files into `Wiki/World/Systems/`:

### 1. `Wiki/World/Systems/system-rules.md`
Scaffold from [assets/system-rules-template.md](assets/system-rules-template.md):
- System nature and narrator voice.
- Attributes, derived pool formulas (HP, MP, SP), and regen rates.
- XP leveling curve and tier thresholds.
- Universal system constraints and anti-deus-ex-machina rules.
- Currency and item rarity spectrum.

### 2. `Wiki/World/Systems/classes-skills.md`
- Class evolution trees (Tier 0 Novice -> Tier 1 Base -> Tier 2 Advanced -> Tier 3 Master).
- Skill acquisition taxonomy (tomes, practice, achievements).
- Complete skill list for known classes with exact costs, cooldowns, and scaling coefficients.

### 3. `Wiki/World/Systems/encounters-loot.md`
- Monster tier grading (F-Rank through S-Rank).
- Dungeon floor hierarchy, environmental hazards, and boss phase templates.
- Loot drop mechanics and crafting material grading.

---

## Step 5: Initialize Character Sheets & Progression Ledger

For each protagonist:
1. Create a companion character sheet at `Wiki/Characters/<Character_Name>_sheet.md` using [assets/character-sheet-template.md](assets/character-sheet-template.md) matching starting Level 1 (or story entry level) stats.
2. Initialize or update `Wiki/World/Systems/ledger.yaml` using [assets/ledger-template.yaml](assets/ledger-template.yaml) with starting attributes, timed skill unlocks, and starting chapter state. Include structured XP thresholds and pool formulas and use the auditable transition fields from the ledger template.

---

## Step 6: Present and Confirm

Present a clean summary to the user:
- The core attributes and derived pool formulas.
- Level-up pacing and reward cadence.
- Class paths available to the protagonist.
- Initial character sheet and starting stats.

Prompt the user: *"Are these system formulas and class trees aligned with your vision, or should we adjust any attributes, costs, or scaling rates?"*

When approved:
- Note that `litrpg-audit` and `gate-check` will now mechanically enforce these rules on every drafted chapter.
- Next step: proceed with `fiction-outline` or `fiction-scenes`.
