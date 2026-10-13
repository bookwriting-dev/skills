# LitRPG Notification Box & UI Style Guide

In LitRPG, the "blue box" or system interface is an integral storytelling element. How notifications are rendered affects reading rhythm, visual pacing, and audiobook narration compatibility.

## 1. Syntax Standard: Markdown Callout Blocks

To maintain visual clarity, seamless tool integration (e.g. ignoring system boxes during prose linters and sentence burstiness checks), and consistent e-reader rendering, use **Markdown Blockquotes with standardized header tags**.

### Standard Box Format
```markdown
> [!SYSTEM]
> **Level Up!**
> You have reached **Level 7**.
> Unassigned Attribute Points: **+5**
> Free Skill Points: **+1**
```

### Alternative Callout Types
- `> [!SYSTEM]` — General game announcements, level-ups, quest updates.
- `> [!ALERT]` / `> [!WARNING]` — Threat warnings, environmental hazards, critical health alerts.
- `> [!SKILL]` — Skill acquisition, evolution, or mastery upgrades.
- `> [!LOOT]` — Item drops, chest rewards, equipment tooltips.
- `> [!COMBAT]` — Combat damage calculations, status effects applied/resisted.

---

## 2. Notification Types & Templates

### A. Level Up Notification
Keep it punchy. Highlight the milestone, the new stat pool, and any rewards.

```markdown
> [!SYSTEM]
> **Level Up!**
> **Current Level:** 12 -> 13
> **Health:** 240/240 | **Mana:** 160/160
> **Stat Points Earned:** 5
> **New Perk Available:** Class Trait at Level 15 (2 levels remaining).
```

### B. Skill Unlock / Evolution
Give the skill name, rank/tier, resource cost, cooldown, and an exact functional description.

```markdown
> [!SKILL]
> **Skill Acquired: Mana Dart (Rank 1 / Novice)**
> **Cost:** 15 MP | **Cast Time:** 1.2s | **Cooldown:** None
> Compresses raw arcane energy into a piercing projectile. Deals `(10 + INT * 0.8)` magical damage. Range: 25 meters.
```

### C. Item / Loot Tooltip
Include name, rarity, type, durability/requirements, and specific stat buffs.

```markdown
> [!LOOT]
> **Item:** Viper-Fang Dagger
> **Rarity:** Uncommon | **Type:** One-Handed Piercing
> **Attack Power:** 18–22
> **Durability:** 60/60
> **Equip Requirement:** Dexterity 16
> **Special Effect:** *Envenomed* — 15% chance on strike to inflict Mild Poison (3 nature damage/sec for 6s).
```

### D. Condensed Character Sheet (The In-Prose State Check)
Never paste a 50-line sheet unless it marks the end of a major book arc. For regular check-ins, use the **Condensed Status**:

```markdown
> [!SYSTEM]
> **Status: Zachary Cross**
> **Class:** Shadow Weaver (Tier 1) | **Level:** 14
> **HP:** 310/310 | **MP:** 220/220 | **Stamina:** 180/180
> **Attributes:** STR: 14 | AGI: 22 (+2) | CON: 18 | INT: 20 | WIS: 16 | CHA: 10
> **Unassigned Points:** 0
> **Active Buffs:** None
```

---

## 3. Formatting Rules for Prose & Audiobook Performance

1. **Paragraph Spacing Around System Boxes:**
   - Always leave a blank line before and after a system blockquote.
   - Do not bury system boxes inside ordinary narrative sentences.
2. **Audiobook / Screen-Reader Safety:**
   - Keep stat tables tabular and clean.
   - Avoid excessive ASCII borders like `+-------------------+` that audio narrators are forced to stumble through or spell out.
   - Bold numerical changes (`**+2**`) so human readers scan them instantly.
3. **The "Delta First" Rule:**
   - When a stat changes, show the delta: `Constitution: 14 -> 16 (+2)`.
   - Never force the reader to do mental subtraction against a sheet printed five chapters ago to see what changed.
4. **Frequency & Pacing Constraints:**
   - **Maximum Frequency:** No more than 2–3 notification boxes per chapter.
   - **Climax Constraint:** Do NOT interrupt a fast-paced combat climax with a full stat dump. A one-line alert (`> [!ALERT] Mana critical: 8/220`) is fine; a full inventory audit kills momentum.
