---
name: sequential-read
description: "Simulate a reader experiencing chapters in order with isolated contexts, sealed predictions, and no future text or private canon. Use when the user says sequential blind read, read the book in order, test reveal timing, or track reader expectations."
metadata:
  author: Storycraft Skills
  version: "1.0.0"
  category: cross-cutting
  bundled-dependencies: book-status
---

# Sequential Blind Reading

## Establish reader and run

Resolve book, ordered authoritative chapter paths, spoiler-free target-reader brief, and allowed packaging. Default to one neutral target reader; add perspectives only when requested. Use [run.json](assets/run.json) and [reaction.json](assets/reaction.json). The runtime is [project_state.py](../book-status/scripts/project_state.py); read [state-contract.md](../book-status/references/state-contract.md).

Run `project_state.py --root ROOT --book Book-N reading --run RUN --action init --spec RUN.json`. The run directory is immutable history: choose a new run ID for a rerun. This is simulated feedback, not actual reader research or market evidence.

## Produce one packet

Run `reading --run RUN --action packet`. Only the current chapter, spoiler-free reader brief, and previous sealed reaction enter the packet. Inspect the brief for plot leakage. Do not pass future chapters, canon, knowledge ledgers, outlines, editorial diagnoses, earlier private conversations, or a persona built from spoiler-bearing story outcomes.

## Read in an isolated context

Use one fresh isolated worker for each chapter, in strict chapter order. Give that worker only the packet plus the following task: read as the designated target reader; return remembered facts, predictions, questions, emotional_response, continue_reading with reason, confusion with exact quotes, relationship_changes, and isolation_evidence identifying the actual allowed input transcript. Record memory truncation explicitly. The coordinator must inspect the worker input transcript; an isolation claim alone is insufficient.

Never perform a purported blind pass inline in a context already exposed to future material. If isolation is unavailable, prepare packets and mark the run pending execution. Do not fabricate reactions to complete the workflow.

## Seal before advancing

Validate reaction quotes against the chapter. Use `reading --run RUN --action seal --spec REACTION.json` before producing the next packet. Reactions are capped at 16,000 JSON characters; summarize explicitly before sealing rather than silently dropping memory. Never rewrite an old prediction in light of later chapters. Later reactions may update expectations while preserving their earlier history.

If chapter K changes, fork a new run. Reuse only verified checkpoints before K, with provenance, and regenerate all later packets/reactions. The helper refuses continuation when an earlier source no longer matches. Copying old reactions for changed chapters is invalid.

## Synthesize after the run

Only after the run is sealed may a separate analysis pass compare predictions with reveals, promises, and knowledge ledgers. Save synthesis.md in the run directory. Distinguish obvious-too-early revelations, confusing acquisition, forgotten setup, sustained curiosity, and emotional response with chapter evidence. Compression-related memory loss is a method limitation. Avoid star-rating predictions or fabricated beta-reader consensus. Return the run path, scope, isolation evidence, limitations, and the few strongest findings. Offer a targeted revision or a fresh read of the revised scope.
