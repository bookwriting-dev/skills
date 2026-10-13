# LitRPG Progression Curves & Mathematical Formulas

Maintaining numeric continuity requires a clear mathematical backbone. When an author or agent knows the exact formula, level thresholds, stat point rewards, and XP curves are completely reproducible and audit-safe.

## 1. Experience Point (XP) Curves

Choose one of three standard progression models based on series length and story pacing:

### Model A: Quadratic Scaling (Standard / Medium Series)
Ideal for standard 3–5 book trilogies with 50–60 levels.
- **Formula:** `XP_required(Level) = Base * Level^2` (e.g., Base = 100)
- **Progression Table:**
  - Level 1 -> 2: 100 XP
  - Level 2 -> 3: 400 XP
  - Level 3 -> 4: 900 XP
  - Level 4 -> 5: 1,600 XP
  - Level 9 -> 10: 8,100 XP
  - Level 19 -> 20: 36,100 XP

### Model B: Tiered Flat-Stepped (Cultivation / Floor-Based)
XP resets each tier, but within each tier progress is roughly linear, punctuated by a breakthrough bottleneck.
- **Tiers:** Iron (1–10), Bronze (11–20), Silver (21–30), Gold (31–40).
- Leveling within a tier requires standard monster cores (e.g., 5 Iron cores per level).
- Breakthrough (e.g. 10 -> 11) requires a special catalyst, boss core, or enlightenment trial.

### Model C: Exponential Scaling (High-Fantasy / Apocalypse)
Early levels fly by; later levels require massive planetary or dungeon-scale feats.
- **Formula:** `XP_required(Level) = Base * (Multiplier)^(Level - 1)` (e.g., Base = 100, Multiplier = 1.3)

---

## 2. Stat Point Allocation and Pool Formulas

### Standard Allocation Per Level
- **Free Attribute Points:** Typically **5 points** per level.
- **Class-Fixed Attribute Points:** Optional 1–3 automatic points distributed according to class archetype (e.g., +2 STR, +1 CON for Warrior).
- **Skill Points:** 1 point every level or every 2 levels.

### Derived Pool Formulas
Keep the math simple and easy to verify:

| Derived Pool | Formula | Notes |
|---|---|---|
| **Health Points (HP)** | `(Constitution * 10) + (Level * 5) + Base(50)` | Flat and predictable. |
| **Mana Points (MP)** | `(Intelligence * 10) + (Wisdom * 5) + Base(50)` | Wisdom can add to pool or regen. |
| **Stamina (SP)** | `(Endurance * 8) + (Strength * 4) + Base(50)` | Powers physical skills and sprinting. |
| **Health Regen** | `(Constitution * 0.1) / minute` (out of combat) | In-combat regen is 0 without skills/potions. |
| **Mana Regen** | `(Wisdom * 0.2) / 10 seconds` | Natural replenishment during pauses. |

---

## 3. Stat Soft Caps and Diminishing Returns

To prevent numbers from breaking the narrative after Level 30:

- **Soft Cap 1 (Human Peak - 25 points):**
  - Up to 25: 1 point gives 100% full value (e.g., 1 STR = 10 lbs carrying capacity increase).
- **Soft Cap 2 (Superhuman - 50 points):**
  - 26 to 50: 1 point gives 75% efficiency unless supported by a Tier 2 Class or Body Refinement technique.
- **Hard / Breakthrough Barrier (100 points):**
  - Requires ascending past mortal limits; stat cannot exceed 99 until a breakthrough quest is cleared.

---

## 4. Skill Damage and Healing Formulas

When documenting active skills, give explicit scaling coefficients:

```
Damage = Base_Value + (Primary_Stat * Scaling_Factor)
```

**Examples:**
- *Firebolt (Rank 1):* `25 + (INT * 0.5)` fire damage. Cost: 12 MP. Cooldown: 2s.
- *Heavy Cleave (Rank 1):* `40 + (STR * 0.8)` physical damage. Cost: 20 SP. Cooldown: 5s.
- *Lesser Heal (Rank 1):* `35 + (WIS * 0.6)` restoration. Cost: 25 MP. Cooldown: 8s.

Having exact numbers prevents the "author suddenly forgot how powerful Firebolt was" syndrome.
