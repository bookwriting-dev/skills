# LitRPG & Progression Fantasy System Design Principles

A great LitRPG is not just a fantasy story with numbers slapped on; it is a story where mechanical constraints generate authentic dramatic tension. Readers read LitRPG for the "I built this" satisfaction—watching an underdog understand, optimize, and exploit a complex system through sweat and strategy.

## 1. The Core Contract: "No Free Lunch"

The fastest way to kill tension in a LitRPG is **unearned power** or **convenient system handwaves**.

### The Three Laws of System Tension
1. **Every Power Has a Cost:**
   - Mana, stamina, or life force drain.
   - Opportunity cost (investing in Strength means sacrificing Agility or Magic).
   - Cooldowns, casting vulnerability, or dangerous debuffs/side-effects.
2. **Every Advantage Has a Counter:**
   - No invincible build. High defense is weak to armor-piercing or status effects; glass cannons get crushed if caught.
   - Monsters and rivals also have system abilities and counters.
3. **The System Never Cheats for the Protagonist:**
   - If the protagonist discovers a loophole or synergy, it must follow from the previously established rules of the system.
   - System notifications must remain objective arbiters, not cheerleaders (unless the system AI itself is an established diegetic character with explicit bias, like in *Dungeon Crawler Carl*).

---

## 2. Pacing the Progression: The Dopamine Curve

Progression readers expect a regular cadence of rewards, but rewards must scale properly to maintain value.

| Level / Tier Span | Scope of Challenge | Reward Cadence | Impact of Milestone |
|---|---|---|---|
| **Early Game (Lvl 1–10)** | Basic survival, rats/goblins, discovering system UI | Frequent (every 1–2 chapters) | Immediate, tangible survival improvement (e.g., +10 HP saves their life). |
| **Mid Game (Lvl 11–30)** | Specialized combat, dungeon delving, party roles | Moderate (every 3–5 chapters) | Synergy unlocked; abilities combo together; class specialization. |
| **High Tier (Lvl 31–50+)** | Regional threats, faction warfare, boss encounters | Slower (major arc climaxes) | Qualitative breakthrough; domain expansion, conceptual abilities. |

### The "Dopamine Stagger" Pattern
- **Chapter N:** High-stakes encounter, severe resource drain, cliffhanger.
- **Chapter N+1:** The victory, loot drop, notification ding, stat allocation debate.
- **Chapter N+2:** Field-testing the new skill or upgraded weapon on an unexpected wrinkle.

---

## 3. Stat Architecture & Mathematical Sanity

Choose an attribute framework that fits the story's complexity level:

### Common Attribute Frameworks
- **Classic 6-Stat:**
  - `Strength (STR)`: Physical power, carrying capacity, blunt damage.
  - `Agility / Dexterity (AGI/DEX)`: Movement speed, reflex, precision, crit rate.
  - `Constitution / Endurance (CON/END)`: Health pool, physical armor, stamina, disease resistance.
  - `Intelligence (INT)`: Mana pool, spell complexity, magical damage, mental processing speed.
  - `Wisdom / Willpower (WIS/WIL)`: Mana regeneration, perception, mental resistance, magical defense.
  - `Charisma / Luck (CHA/LCK)`: System favor, critical rolls, NPC reaction, rare drop multiplier.
- **Tri-Stat (Streamlined):**
  - `Body / Might` (Physical actions, durability)
  - `Mind / Focus` (Magic, perception, tactical speed)
  - `Soul / Spirit` (Aura, resistance, divine/system connection)

### Mathematical Sanity Rules
- **Flat vs. Percentage Scaling:** Flat additions (`+5 Strength`) feel huge at Level 1 but become meaningless at Level 50 unless stats scale or soft-cap.
- **Diminishing Returns:** Ensure stat investment has sensible diminishing returns so a character cannot become infinitely untouchable without specialized skills.
- **Derived Pools:** Document explicit formulas:
  - `HP = CON * 10 + Level * 5`
  - `MP = INT * 10 + WIS * 5`
  - `Stamina = (STR + CON) * 5`
  - `Mana Regen = WIS * 0.2 / sec`

---

## 4. Class Trees and Skill Acquisition

### Class Evolution Paths
- **Tier 0:** Classless / Novice / Wanderer (Levels 1–10). Basic survival skills.
- **Tier 1:** Base Class (e.g., Warrior, Rogue, Mage, Healer) (Level 10). First major identity choice.
- **Tier 2:** Specialized / Hybrid Class (e.g., Shadow-Blade, Rune-Knight, Battle-Medic) (Level 25).
- **Tier 3:** Prestige / Conceptual Class (Level 50). Unique to character achievements and rare legacy.

### Skill Categories
- **Passives:** Always active. Keep their numbers modest (`+10% Poison Resistance`, `Enhanced Spatial Awareness`).
- **Actives:** Explicit resource cost and cooldown. Must have concrete physical or visual manifestations.
- **Mastery / Skill Levels:** Skills gain proficiency through deliberate practice or extreme use under pressure (Ranks 1–10 or F to S).

---

## 5. Avoiding Common Pitfalls

1. **The Stat Dump Fatigue:**
   - NEVER drop a full 40-line character sheet into prose mid-combat or more than once every 10–15 chapters.
   - Use **delta notifications** (`Strength: 14 -> 16 (+2)`) or **focused summaries** for regular updates.
2. **The Spreadsheet Protagonist:**
   - Numbers exist to reflect personality and struggle, not replace them. An optimization choice should reveal who the character is (e.g., hoarding defensive points out of trauma).
3. **Forgotten Inventory / Abilities:**
   - If an item or skill was gained in Chapter 4, the reader expects it to either be used when relevant in Chapter 14 or explicitly accounted for (broken, sold, traded, or out-leveled).
4. **Inflation Power Creep:**
   - If numbers jump from 100 to 1,000,000 within ten chapters, combat becomes abstract and boring. Ground the impact in physical realities (e.g., the punch that used to crack wood now shatters stone).
