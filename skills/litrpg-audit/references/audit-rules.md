# LitRPG progression evidence and verdicts

The audit reads the committed progression ledger, or a legacy standalone YAML ledger. Each chapter can provide a default character, entering and ending state, and an ordered event list. Multiple characters can use separate state records under participants and name the actor on each event.

For entering state, use level, xp, unspent_stats, attributes, resources, inventory, and incapacitated as applicable. The chapter-specific values establish the starting point. A present-day sheet may supply the starting point when state_chapter matches the audited chapter. Skill entries use name, unlocked_chapter, optional requires_level or requires, and optional cost_type and cost.

The audit reads named prose casts and recognized system displays. A display can carry an Actor or Character label, followed by skill, level, stat, or pool lines. Use typed events for other transitions, including allocate, level_up, xp_gain, unlock, use_skill, status, spend, recover, gain_item, lose_item, incapacitate, revive, and act. Include line and exact quote when reconciling a transition with manuscript prose. Earlier events authorize later actions. For an unlock in the current chapter, record when the actor acquired it.

Set cumulative XP thresholds for the level being reached in xp_thresholds. Quadratic ledgers use xp_base times the square of the previous level and exponential ledgers also need xp_growth. Define derived pools as coefficient maps in pool_formulas. For example, HP can use base 50, CON 10, and level 5. A status event supplies pools as a map of printed maximums.

## Apply findings

- **FAIL** covers unearned stats, missing skill prerequisites, proven premature use, mismatched derived pools, or acting while incapacitated.
- **WARN** covers unsupported level advances, negative resources or inventories, and displays longer than 25 lines.
- **UNVERIFIED** identifies an applicable check that needs more evidence, such as the acting character or entering mana. Preserve it as an unresolved warning in the gate.
- **NOT_APPLICABLE** means the supplied chapter evidence contains no event for that rule. Inspect prose not represented by structured events when its progression affects continuity.

Use the exact text and ledger entries in the report. Reconcile incomplete or ambiguous transitions before updating approved canon or character sheets.
