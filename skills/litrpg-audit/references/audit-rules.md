# LitRPG Numeric Audit & Continuity Rules

Deterministic rules enforced by `stat_audit.py` and `litrpg-audit`.

## 1. Audit Dimensions & Severity Rubric

### Hard Violations (Blocks Gate Approval)
1. **Stat Point Inflation:**
   - Allocating more attribute points than the level gain warrants (e.g. gaining 1 level but allocating +8 points when the rule is 5).
2. **Ghost Skill Usage:**
   - Casting an active spell or skill that has never been unlocked or learned in canon.
3. **Derived Pool Contradiction:**
   - A printed status box displaying HP or MP that does not match the canonical formulas based on the character's current attributes.
4. **Dead Character Action:**
   - A character whose health reached 0 or who suffered fatal trauma acting without resurrection mechanics.

### Warnings (Requires Revision or Approval)
1. **Stat-Dump Paralysis:**
   - Status screens exceeding 25 lines in standard chapter prose, creating reading fatigue.
2. **Resource Overdraft:**
   - Casting high-cost spells consecutively without mentioning mana potions, ambient mana absorption, or rest periods.
3. **Item Vanishing / Duplication:**
   - Equipped weapons or unique loot vanishing from chapter inventory without an in-text trade, break, or drop.
4. **XP Threshold Mismatch:**
   - Triggering a level up on an encounter that yielded far fewer XP than required by the level curve.

### Notices (Informational Tracking)
1. **Unregistered Skill Invocation:**
   - Using a skill name that is not yet formally indexed in `ledger.yaml` (suggests ledger update needed).
2. **Level Progression Milestones:**
   - Records current level and detected XP gains for state-keeper synchronization.

---

## 2. Remediation Routing

- If **Hard Violation:** Re-calculate stat allocation or revise combat sequence before re-running `gate-check`.
- If **Stat-Dump Paralysis:** Convert full character sheet into a condensed delta status box using `references/stat-box-guide.md`.
- If **Missing from Ledger:** Run `state-keeper` or update `Wiki/World/Systems/ledger.yaml` to register newly acquired skills and state transitions.
