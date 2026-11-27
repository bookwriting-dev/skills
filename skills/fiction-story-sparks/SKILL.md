---
name: fiction-story-sparks
description: "Generate story sparks, writing exercises and batches of premises at the requested scale. Use for explicit requests such as 'give me novel ideas', 'brainstorm novel-length premises', a random prompt, or card-style story ideas. Keep ordinary outlining and ongoing-book work in their own workflows."
metadata:
  author: Fiction Toolkit
  version: "1.3.0"
  category: fiction-writing
  output-format: markdown
---

# Fiction Story Sparks

Generate playful starting material without silently opening a new project, changing an existing book, or treating a random combination as canon. This is the text equivalent of Writer's Tavern's Fortune Room spread.

## Choose the deck

Use the user's genre or setting when supplied. Otherwise offer or infer one broad deck only when needed: fantasy, science fiction, horror or eldritch, historical adventure, pirates, romance, mystery, contemporary, or a clearly requested custom setting.

For an established project, read its applicable instructions and current premise or synopsis before drawing. Keep the spark inside canon unless the user explicitly requests an alternate or wild-card idea. Do not save anything into the project unless asked.

## Pass the premise gate

Every viable result must state all three before it can be presented:

- **Premise:** the concrete unstable situation: who wants what, what has changed, and what resists them.
- **Reader promise:** the specific experience and payoff the story undertakes to deliver. This is not mood alone.
- **Dramatic question:** the concrete outcome the reader follows. A thematic question concerns the values this outcome puts in tension.

The premise creates the question. The promise tells the reader why following that question will be satisfying. The ending delivers what the question led the reader to expect, including deliberate ambiguity when the chosen form calls for it. If those four parts describe different stories, discard or repair the spark.

Every generated component must complicate the dramatic question, change the cost of answering it, or help deliver the promised experience. Cut decorative cards that do none of those things.

## Choose the mode

- **Card spread:** Default for a singular “spark,” card-style prompt, writing exercise, or surprise. Deal one compact combination.
- **Premise batch:** Generate six ideas unless the user specifies a count. Use the requested scale. For a novel, keep premises that can sustain the middle: give the protagonist a plausible first solution, show the complication that solution causes, and give another character a reason to act on it. Name one later choice made harder by those decisions. For a one-shot or novelette, keep the existing short targets (3,000–7,500 or 25,000–35,000 words). When scale is unspecified, label each idea with its natural length.

## Deal the spread

Default spread:

- **Someone:** a role plus one pressure-bearing quality, not a full character profile.
- **Somewhere:** a location with one usable environmental or social constraint.
- **Something:** an object, creature, technology, secret, resource, or obligation that matters.
- **It happens:** a disruptive event expressed as an action or reversal.

Optional cards, included only when requested or when the user asks for a full spread:

- **The twist:** changes the interpretation, allegiance, cost, identity, or causal relationship; it should not merely add another threat.
- **How it ends:** a directional ending image or consequence, not a complete synopsis and not necessarily a happy ending.

Keep components generative rather than exhaustive. The combination should contain a decision: someone wants or must protect something, the event changes their available choices, and the location makes the response harder.

When a draft combination reads generic — it could headline any book in the genre — force a collision before presenting it: pair the premise with one unrelated, high-specificity domain (a trade, era, toolset, or material culture) and let that domain's concrete vocabulary reshape at least one core component. The collision is a seed, not decoration: it must be explainable inside the story, and it should make the premise harder to summarize in one stock phrase.

## Proper names

Do not add proper names unless the user asks for them or the supplied setting requires them. When any proper name is invented, use the sibling `name-generator` skill and select from a culture-appropriate pool; never freehand it. Preserve canon names.

## Present a card spread

For one request, return one spread. If the user asks for choices, return three spreads with materially different engines, not cosmetic reskins. Use this compact format:

```markdown
Someone: ...
Somewhere: ...
Something: ...
It happens: ...
The twist: ...
How it ends: ...

Premise: The concrete unstable situation.
Reader promise: The experience and payoff this combination promises.
Dramatic question: The concrete outcome the reader follows.
Answer and payoff: How the ending answers that question and fulfills the promise.
```

Omit unrevealed optional cards rather than filling them with placeholders. If the user wants surprise, present the four core cards first and ask whether to reveal the twist or ending; if uninterrupted completion is preferred, reveal the full spread. The premise, promise, and dramatic question are never optional, even when the twist or ending remains concealed.

## Present a premise batch

Each premise includes:

```markdown
Title: ...
Scale and target: one-shot (...) | novelette (...) | novel (author’s target if given)
Genre: ...
Logline: Who wants what, and what stands in the way.
Premise: The concrete unstable situation in one or two sentences.
Reader promise: The specific experience and payoff offered.
Dramatic question: The dramatic question the final choice answers.
How the middle grows (novel): First solution, its consequence, and someone else’s independent move.
The turn: A consequential change in the choices available.
Final choice: The costly decision only this protagonist can make.
Ending image: One concrete final image.
Answer and payoff: How the choice answers the dramatic question and pays the promise.
What changes permanently: ...
Main risk: The most likely craft or scale failure.
Why it ends: What makes the story finite.
```

Across a batch, vary protagonist position, relationship dynamic, primary situation, reversal, final choice, and ending shape. Vary subgenres only within the author’s requested range. Different names, species, eras, or props do not constitute different story engines. When prior ideas are available, compare against their premise, question, turn, final choice, and ending before presenting the batch.

Do not turn the result into a synopsis, outline, character sheet, or world package unless the user asks. When they choose one, the natural next step is `fiction-synopsis` for a new story or a bounded brainstorming note for an existing project.

## Quality check

Verify that:

- the components fit one genre or intentionally explained collision;
- any forced domain collision is load-bearing — it changes what the story asks or costs, not just its surface flavor;
- the event forces a decision rather than merely decorating the situation;
- the premise is concrete and unstable rather than a setting description;
- the reader promise names an experience and payoff the ending can deliver;
- the dramatic question arises from the premise and can be answered by the final choice;
- the location constrains action;
- the object or creature matters to the conflict;
- the twist reinterprets something already present;
- the ending answers the dramatic question, pays the reader promise, and uses the core cards;
- any invented proper name came from `name-generator`;
- no new project or canon file was created without a direct request.
