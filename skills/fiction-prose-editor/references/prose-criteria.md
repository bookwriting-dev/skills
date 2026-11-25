## Prose Craft Criteria

Check every line in your assigned chunk against ALL of the following categories.

### Narrative Fragments
- Verbless fragments in narrative prose that stall reading or confuse grammar ("Dust. Silence. Nothing.")
- Complete short sentences (`"The door was locked."`, `"She didn't move."`) are NOT fragments — do not flag them unless part of a monotonous staccato run
- **Exception:** Dialogue can have fragments. Check the resolved `style-policy` (`register_preset` / `punctuation.fragments`) and scoped `editorial-memory` decisions before flagging intentional rhythmic fragments in lyrical or comic presets.

### Choppy Constructions
- Colon-list constructions: "Three things: first, second, third."
- Stacked independent observations with no connective tissue (reads like a camera panning)
- Ellipsis-separated lists
- Excessive rapid-fire action fragments (more than 2-3 in a row)
- Sentences that feel like bullet points converted to prose

### S-V-O Chains (Sentence Variety)
- Flag runs of 3 or more consecutive simple Subject-Verb-Object sentences
- The fix is to mix in varied structures (without introducing filter words or comma splices):
  - Prepositional phrase lead: "From the doorway, Mara kept her hand on the latch..."
  - Consequence-first lead: "Confidence didn't survive the stairwell."
  - Compound predicate: "He checked the door and found it locked."
  - Absolute construction: "Rifle raised, the sentry moved forward."
  - Participial lead: "Crossing the deck, she checked the rigging."

### Cadence Flatline (Consecutive Same-Length Sentences)
- Flag runs of 3 or more consecutive narrative sentences within a few words of the same length (e.g., 18, 20, 19, 21 words in a row) — an isochronous machine cadence the reader stops hearing
- Two near-identical sentences in a row is normal human prose; three or more is the tell
- **Exception:** deliberate parallelism (anaphora, a rhythmic triple in dialogue or a stylized beat) — flag it and note the exception rather than auto-fixing
- **Fix:** break the run — shorten one sentence hard, expand another, or combine two

### Simile Overuse
- Review paragraphs and chapters against the resolved `style-policy` limits (`max_per_paragraph: 1`, and preset/guide `max_per_chapter` or ~2–3 per 1,000 words when scaled). Treat an author-approved example, `lyrical-literary` preset, or scoped KEEP as deliberate in its stated context.
- Cite the passage effect when suggesting a cut, such as explaining an emotion the action already shows or importing a comparison outside the viewpoint.
- Weak "explain-it" similes that don't add voice or clarity should be replaced with concrete physical details, cause-and-effect observations, or character judgment.
- Simile markers to look for: "like a", "like the", "as if", "as though"

### Rule of Threes
- Check `style-policy` (`tricolon` / `register_preset`): flag "X, Y, and Z" saturation when used as mechanical AI emphasis in `tight-thriller` prose
- Functional/literal lists are fine ("guns, ammo, and food"), and comedic `"setup, setup, punch"` triples in `comic-ironic` or rhythmic parallels in `lyrical-literary` are allowed unless overused

### Gerund Chains
- Two or more comma-linked -ing actions: "Running forward, dodging bullets, he reached the door"
- These create simultaneous-action confusion and feel mechanical
- Fix: Sequence the actions or pick the most important one

### Escalation Patterns
- "Not just [X], but [Y]"
- "More than [X] — this was [Y]"
- "Beyond [X]"
- These are AI-typical emphasis patterns. State the thing directly.

### Show vs Tell
- Unearned generic emotion labels or quality-adverb tags: "her voice warm and curious," "his expression grim," "she said convincingly" (note: purposeful, voice-earned emotional naming in close interiority is allowed per `gate-check` when it carries judgment rather than summary padding)
- Emotion-body stock formulas: "fear gripped his chest," "dread coiled in his stomach," "anger flared in his gut"
- Vague emotional descriptors: "that brightness in her eyes"
- **The show-then-tell pattern:** showing something through action/dialogue then explaining it with narration. If the action/dialogue already conveys the emotion, cut the follow-up explanation.

### Info Dumps
- Paragraphs of exposition with no scene anchor
- History/context delivered as narration rather than through dialogue or discovery
- Summary statements that skip lived experience
- **Test:** Is there a character actively processing this information in-scene, or is the narrator lecturing?
