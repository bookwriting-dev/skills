---
name: nonfiction-research
description: "Organize, index, and audit factual research, evidence matrices, literature notes, and primary citations in Wiki/Research/ to ground non-fiction chapters. Use when user says 'organize research', 'add source', 'audit citations', 'manage research notes', or 'evidence matrix'."
metadata:
  author: Storycraft Skills
  version: "1.3.0"
  category: nonfiction-writing
---

# Non-Fiction Research & Source Manager

Establishes and maintains the empirical research foundation in `Wiki/Research/`. Indexes primary sources, academic literature, case studies, and interview transcripts to provide direct citation backing for arguments in non-fiction manuscripts.

## Research Structure

Manages files inside `Wiki/Research/`:
- `sources.yaml`: Structured registry of books, papers, articles, and interviews with IDs (`SRC-001`, etc.).
- `claims-matrix.md`: Maps core thesis claims to concrete evidence and citation IDs.
- `case-studies/`: Deep-dive contextual examples indexed by chapter.

## Procedure

1. **Intake & Extraction:**
   - Extracts key claims, methodology, sample size, and direct quotes from raw notes.
2. **Citation Registration:**
   - Assigns unique `SRC-NNN` ID and tags by topic and chapter relevance.
3. **Claims Matrix Mapping:**
   - Ensures no high-stakes claim in `Wiki/Concept/structure.md` is left without at least one primary source.
## Assertion evidence readiness

Maintain inspected source and passage records, then build an assertion inventory for each chapter. Use [scripts/evidence.py](scripts/evidence.py) to validate a chapter evidence record, resolve shared `Wiki/Research/sources.yaml` entries by `source_id`, and derive factual readiness:

```text
python3 .agents/skills/nonfiction-research/scripts/evidence.py --root PROJECT --record _Edits/Book-N/evidence/Chapter-NNN.json
python3 .agents/skills/nonfiction-research/scripts/evidence.py --root PROJECT --record _Edits/Book-N/evidence/Chapter-NNN.json --reanchor
```

The record is a versioned `chapter_evidence` JSON object containing `subject_path` and exact `subject_sha256`, source records (which automatically inherit matching metadata from `Wiki/Research/sources.yaml` when referenced by `source_id`), one assertion per distinct claim, one verification result per assertion, and a chapter-level `inventory_coverage` review. Source records include type, title, locator, explicit access/inspection/rights states, version or date context, limitations, and inspected passage IDs with exact quotes or precise locators. Anchors use zero-based half-open Unicode code-point offsets into the exact UTF-8 decoded chapter string. Run `--reanchor` after prose edits to recompute offsets for surviving exact quotes without manually counting UTF-8 indices; do not pass `--confirm-coverage` unless you inspected every edit and verified no new claims entered.

An inspected source requires an identifiable revision and retained passages or precise locators. A verified claim must cite known passages from inspected sources; unknown or uninspected sources cannot be cited as support. `not_empirical` is valid for properly classified `definition`, `normative_judgment`, `hypothetical_illustration`, `firsthand_account` (memoir/eyewitness recollection), and `domain_baseline` (undisputed reference terminology/facts) assertions. Missing results, stale anchors, unsupported claims, missing source limitations, and incomplete coverage remain blockers. The validator checks record consistency; it cannot prove that a source is true or that a semantic inventory is complete. Human research review and its limitations must be recorded honestly.

The validator reports source input hashes and verified assertion anchors for downstream gates. When an inspected source has a retained UTF-8 Markdown or text snapshot, check every quoted passage against that snapshot.
