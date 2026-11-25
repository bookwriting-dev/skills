---
name: nominalization-hunt
description: Find nominalized self-explanation in chapters (fiction or non-fiction) and propose concrete rewrites that restore observation, bodily response, and action or blunt thought. Use when the user says "nominalization hunt" or asks to find abstract self-explanation.
metadata:
  author: Fiction Toolkit
  version: "1.3.0"
  bundled-dependencies: book-status
  category: fiction-editing
---

# Nominalization Hunt

Read the chapter supplied by the user in chunks of 40 lines. Flag every instance of nominalized self-explanation, then propose a concrete rewrite for each.

## The Pattern

This is NOT about word choice. It is a structural flaw where the prose turns an observation or feeling into a noun phrase, then comments on that noun phrase instead of staying in the scene.

The four sub-patterns to catch:

**1. Observation-being-quality-was-meaning**
`The [observation] being [quality] was [meaning].`
> "Being ready for it was a kind of old he did not have a name for."
> "The voice being level was a bad sign."

**2. Negation nominalized**
`The not-[action] / not-[feeling] did [consequence].`
> "The not-knowing sat in his chest."
> "The not-looking changed nothing."

**3. X was the answer / The answer was**
The scene has already shown the answer. The narration then explains what the answer means.
> "The argument was complete."
> "The other thing was permission."
> "The answer was the same."

**4. AI-style logical chain**
`X was Y, and he did not like Y, and not liking Y changed nothing.`
The prose chains abstractions into a recursive loop instead of landing in the body.
> "The wanting had gone into his chest and sat there, and he had buried it before he knew he was burying it. He had buried the wanting fast, before he knew he was burying it."

## Related tells (flag but lower severity)

- `"the X of it"` used to name a quality rather than render it: "the neatness of it," "the shape of it," "the fact of it"
- `"something in him was [state]"` — abstract resident object doing the feeling
- `"a [noun] he could not [verb]"` — nominalization followed by authorial comment: "a generosity to himself he could not quite stand"
- `"[gerund] was a [noun]"` — action turned into aphorism: "Wanting was a handle people grabbed you by"
- Repeated avoidance phrase used more than once: "He did not look at that part" — one use is technique, three is a tic

## The fix rule

Every rewrite must restore concrete scene grounding: **Observation → concrete channel (action, perception, blunt thought, speech, omission, or earned physical response).**

Never explain what the observation means, and never name the feeling as an abstract noun and then handle it. Vary the channel rather than defaulting every beat to somatic clichés (`jaw`, `breath`, `throat`, `chest` — overusing those trips `cooling_list` in `draft-packet`).

Consult `Wiki/Style/editorial-decisions.json` (if present) and pass applicable scoped author decisions into any chunk worker brief so intentional phrasing is preserved.

| Instead of | Use |
|---|---|
| "The wanting sat in his chest" | "His hand went into his pocket and closed around the spare key." |
| "The argument was complete" | "He had run the numbers three ways and reached the same shortage." |
| "The neatness of it" | "He stacked the ledgers edge to edge until the spines lined up." |
| "Something in him was already done" | "He checked the bolt twice and left the coat on the peg." |

## Output format

For each flag:

1. Line number
2. Exact quoted sentence(s)
3. Which sub-pattern it is
4. Proposed rewrite

End with a severity table: High / Medium / Low for each flag.

Report in conversation; this scan does not save a file. If the user wants rewrites applied, route the approved items through `fiction-revise` (or apply them directly with per-item confirmation, verifying each quote before editing).

## Current evidence and author decisions

For a saved report, follow [state-contract.md](../book-status/references/state-contract.md) using [project_state.py](../book-status/scripts/project_state.py): capture inputs BEFORE review, then record report metadata only if those inputs still match. Include every consumed chapter, plan, canon/style reference, relevant ledger, applicable editorial decision file (including its absence), and this skill's rules. Use stable finding IDs with exact quotes and blocking/nonblocking classification. No sidecar is required for a conversational verdict.

Consult applicable active editorial-memory decisions before proposing style repairs. Include the applicable scoped decision block verbatim in each focused worker brief; coordinator awareness alone is insufficient. Preserve deliberate choices within their stated scope; correctness checks remain binding. Do not generalize a local rejection. For in-place editing, record each applied finding's source quote and before/after hashes in the disposition ledger; review the resulting chapter with fresh evidence. A pre-edit PASS cannot establish post-edit readiness. Diagnostic-only skills still never edit source prose. Blind reader passes receive only reader-facing text; preference/canon checks happen in a separate coordinator pass.
