---
name: fiction-knowledge
description: "Track who knows, suspects, or falsely believes each fact and when readers encounter it. Use when the user says track secrets, who knows what, audit reveals, knowledge continuity, or check premature knowledge."
metadata:
  author: Storycraft Skills
  version: "1.0.0"
  category: fiction-editing
  bundled-dependencies: book-status
---

# Knowledge and Belief Continuity

## Resolve scope and sources

Identify book, chapter/scene range, and story chronology from the assigned manuscript and established canon. Use [project_state.py](../book-status/scripts/project_state.py) and [state-contract.md](../book-status/references/state-contract.md). Use [event.json](assets/event.json) as the entry template. A missing ledger has unknown coverage, never a clean audit.

## Harvest sourced events

Read the chapter in scene order. Distinguish a fact's truth status from an observer's belief. A statement can be false, disputed, unresolved, or deliberately unreliable. Record what a character witnessed, was told, inferred with support, suspected, disbelieved, or forgot. Reader exposure is separate from character knowledge. Do not infer that silence establishes ignorance.

Assign stable fact_id and event id. Record observer, epistemic state, exact source quote and source_sha256, confidence/reason, and confirmed status. Positions are integer arrays [chapter, scene, beat]. story_position follows in-world chronology; reader_position follows manuscript order. Flashbacks can therefore occur earlier in story_position and later in reader_position. Keep proposed uncertain events confirmed false until checked. If revising an event, create a new sourced event with supersedes; preserve the old entry as evidence history. Link promise IDs only when there is an actual setup/payoff obligation.

Run `project_state.py --root ROOT --book Book-N knowledge --action record --spec EVENT.json`. The helper verifies the exact source and rejects duplicate IDs. Use `knowledge --action audit` to identify stale evidence, and `knowledge --action as-of --observer NAME --position 8.2.3` to inspect current confirmed state. Reader as-of queries use reading order; other observers use story order.

## Audit use against acquisition

Compare a character's action/dialogue with supported acquisition events at that point in story time. Report premature use with the action quote and the later acquisition quote. Allow a supported deduction even if nobody explicitly announces the fact. Preserve intentional false beliefs, deception, reader-only knowledge, and unreliable narration. Explain partial coverage and any inference needing confirmation. A numeric position comparison assists bookkeeping; it does not establish that an utterance semantically uses a secret.

## Save and hand off

For durable audits, save Chapter-NNN_Knowledge.md and current metadata using the state contract, with stable finding IDs and exact quotes. Feed confirmed changes into drafting context, dialogue checks, gate-check, canon impact scans, and series continuity. Never send the ledger to a blind reader. Return new/superseded events, stale sources, and actionable contradictions. Offer re-harvest of changed chapters or review of a specific reveal.
