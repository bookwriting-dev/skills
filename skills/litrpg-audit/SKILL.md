---
name: litrpg-audit
description: "Deterministic numeric and progression continuity audit for LitRPG chapters — checks stat math, level curves, skill prerequisites, resource expenditure, inventory continuity, and status box accuracy against the ledger. Use when user says 'audit stats', 'litrpg audit', 'check stat math', 'verify progression', 'stat continuity', 'audit chapter numbers', or as part of gate-check."
metadata:
  author: Fiction Toolkit
  version: "1.1.0"
  bundled-dependencies: book-status
  category: fiction-editing
---

# LitRPG Progression Auditor

A mechanical, deterministic continuity checker for LitRPG chapters. Parses drafted chapter prose, extracts status boxes, stat gains, skill uses, and XP awards, and validates them against `Wiki/World/Systems/ledger.yaml` and `Wiki/World/Systems/system-rules.md`.

Never relies on hallucinated mental arithmetic. Runs a standalone Python script to ensure that character progression is mathematically sound and that reader audits will find zero calculation errors.

## Arguments

The request argument: one chapter reference (e.g., "1", "Chapter-001", "Chapter-001.md").

---

## Step 1: Locate Chapter and System Ledger

1. Parse the request argument into a target file path (e.g., `Chapters/Book-1/Chapter-001.md`).
2. Search for the project's progression ledger at:
   - `Wiki/World/Systems/ledger.yaml`
   - or `Wiki/Story/Book-N/ledger.yaml`
3. Search for the system rules file at `Wiki/World/Systems/system-rules.md`.

---

## Step 2: Run the Progression Audit Script

Execute [scripts/stat_audit.py](scripts/stat_audit.py) using the host's available Python interpreter:

```bash
python3 .agents/skills/litrpg-audit/scripts/stat_audit.py Chapters/Book-N/Chapter-NNN.md --json
```

Capture the JSON output.

---

## Step 3: Evaluate Audit Findings

Read [references/audit-rules.md](references/audit-rules.md) to categorize findings:

1. **Violations (Hard Fails):**
   - Unearned attribute points (allocated > earned).
   - Use of locked/unlearned skills in combat.
   - Contradictions in derived pools (HP/MP calculations not matching formulas).
2. **Warnings:**
   - Stat-dump paralysis (>25 line status boxes).
   - Unregistered skills or unexplained resource recovery.
3. **Notices:**
   - Level milestones detected; XP delta ready for ledger commit.

---

## Step 4: Save Report

1. Check for the chapter's `_Edits/Book-N/` directory. Create it if missing.
2. Save report as `_Edits/Book-N/Chapter-NNN_StatAudit.md`:

```markdown
# LitRPG Progression Audit: Chapter NNN (Book N)
**Status:** [PASS / WARN / FAIL]  **System Blocks:** [Count]  **Ledger:** [Loaded / None]

## Summary
- **Violations:** [Count]
- **Warnings:** [Count]
- **Level-Ups Detected:** [Details]
- **Skills Unlocked:** [Details]

## Findings
[Detailed bullet points with exact line numbers and quotes]

## Next Steps
- If PASS: Progression cleared; update ledger with state out.
- If FAIL: Adjust allocated numbers or prose in Chapter-NNN.md before final approval.
```

---

## Step 5: Update the Ledger (On Clean Runs)

If the audit passes and the chapter contains approved level-ups, stat allocations, or newly learned skills:
- Update `Wiki/World/Systems/ledger.yaml` under `chapters.Chapter-NNN` with the ending `state_out`.
- Synchronize `Wiki/Characters/<Name>_sheet.md` if an attribute milestone was reached.

Report the outcome to the user.

## Current evidence and author decisions

For a saved report, follow [state-contract.md](../book-status/references/state-contract.md) using [project_state.py](../book-status/scripts/project_state.py): capture inputs BEFORE review, then record report metadata only if those inputs still match. Include every consumed chapter, plan, canon/style reference, relevant ledger, applicable editorial decision file (including its absence), and this skill's rules. Use stable finding IDs with exact quotes and blocking/nonblocking classification. No sidecar is required for a conversational verdict.

Consult applicable active editorial-memory decisions before proposing style repairs. Include the applicable scoped decision block verbatim in each focused worker brief; coordinator awareness alone is insufficient. Preserve deliberate choices within their stated scope; correctness checks remain binding. Do not generalize a local rejection. For in-place editing, record each applied finding's source quote and before/after hashes in the disposition ledger; review the resulting chapter with fresh evidence. A pre-edit PASS cannot establish post-edit readiness. Diagnostic-only skills still never edit source prose. Blind reader passes receive only reader-facing text; preference/canon checks happen in a separate coordinator pass.
