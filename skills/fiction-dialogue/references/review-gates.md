# Dialogue Architecture Review Gates

Use these gates on the latest scene snapshot. Diagnose structure before rewriting lines.

## Gate 1: Character-source compliance

List the speakers and confirm that every current character sheet was read in full. For each major speaker, identify at least one recent canon exchange used for calibration.

Fail when a voice claim rests only on generic traits such as witty, kind, direct, intelligent, formal, or sarcastic.

Run a blind-speaker test on representative lines. Remove names and tags. If multiple speakers remain interchangeable, identify the shared cognition or sentence habit causing it. Do not solve the failure with catchphrases.

## Gate 2: Turn-taking and echo

Read a run of replies in context. What does the second speaker do with the first speaker’s words? An acknowledgment can accept blame, grant permission, offer comfort, or commit someone to act. Two people can achieve this through speech alone.

Flag an echo when the later line repeats information or sentiment and removing it preserves what the speakers understand, feel, and can do. Quote the repeated beat and describe the effect of the cut. Preserve operational confirmations, purposeful refrains, and quiet agreement when their function is audible on the page.

## Gate 3: Comeback scaffolding

For every punchline or sharp retort, test the preceding line on its own.

Fail when a line exists mainly to feed another speaker a comeback. Delete the setup line first, then decide whether the joke still belongs.

When several speakers are witty, identify who owns each joke, what it costs to make it, and how the others hear it. Flag a joke if the exchange requires someone to abandon an established motive or adopt another speaker’s voice to supply the setup.

## Gate 4: Interview sequencing

Read the question-and-answer sequence through its first consequence. Identify who needs the answer, why this person gives it now, and what it enables or costs. Preserve consecutive direct answers when they change knowledge, options, risk, permission, trust, or commitment. Apply the same test in a formal interview and in an ordinary conversation, including when the plan gives the exchange no special label.

In a hearing, asking for a known fact may place it on record and put the witness’s reputation at stake. Flag repetition or information gathering when the scene gives it no such purpose and you can show where the exchange loses pace or credibility. Quote the first beat where that happens. Combine redundant questions or put the useful answer where someone can act on it. A refusal, interruption, or evasion needs a motive the scene supports.

## Gate 5: Distributed conversational intelligence

Check whether all speakers can:

- identify subtext immediately
- formulate concise thematic observations
- produce dry humor on demand
- explain emotions elegantly
- catch every implication
- answer without stumbling or choosing the wrong emphasis

Fail when the same high-level conversational competence is distributed across the cast regardless of age, profession, culture, stress, or relationship.

Repair by returning to each speaker's first attention, knowledge limits, social strategy, and pressure leak. Some characters should miss implications, speak too concretely, overexplain, choose logistics, become less verbal, or decide the conversation is not worth having.

## Gate 6: Aphorism and thematic-summary density

Flag polished lines that compress the scene's theme into a quotable observation. One can land. A sequence makes characters sound authored.

Alien, noble, formal, academic, and emotionally perceptive characters are especially vulnerable. Replace excess aphorisms with specific observations, imperfect wording, silence, or action.

Fail when multiple characters take turns stating the chapter's meaning.

## Gate 7: Cultural and moral neatness

Flag exchanges that convert awkward history, prejudice, cultural difference, authority, or grief into a clean modern lesson within a few lines.

Fail when the speaker supplies the authorially correct formulation without hesitation, personal limitation, cost, or unresolved discomfort.

Repair through narrower experience, misreading, incomplete explanation, a boundary, or a practical response. Do not force a debate when the character would disengage.

## Gate 8: Objective and state change

For every dialogue block, state what each speaker wants and what changes by the end: knowledge, trust, status, permission, risk, intimacy, commitment, or available action.

Assess the exchange at the scale of the beat. An apparently small reply can prepare the next disclosure or let an earlier one be believed. Flag expendable lines when you can show what their removal preserves and where the exchange gains pace or force.

## Gate 9: Speakability and restraint

Read the exchange aloud or simulate performance. Flag lines that are too balanced, polished, complete, or abstract for the speaker under current pressure.

Do not roughen every line. Preserve clarity where the character would be clear. Add hesitation, incompletion, interruption, or silence only when motivated.

## Review output

For each confirmed failure, report:

```text
Location:
Gate:
Speakers:
What the exchange is doing now:
Why it fails for these characters:
Smallest structural repair:
Canon or voice risk:
Lines preserved:
```

End with a verdict:

- `PASS`: no material architecture failure.
- `REVISE`: line-level or local structural repair is sufficient.
- `REBUILD`: the conversation's objective or knowledge architecture must change before line editing.

Do not call dialogue complete while any material gate remains failed. A `REBUILD` verdict is a diagnosis, not authorization to perform the rewrite.
