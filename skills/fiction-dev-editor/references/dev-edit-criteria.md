## Developmental Editing — What It Is and Isn't

Developmental editing operates at the story level. It answers: "Does this work as a narrative?" It does NOT answer: "Is this sentence good?"

### The Core Questions

1. **Why is this scene here?** Every scene must advance plot, reveal character, or raise stakes. The best scenes do two or three simultaneously. A scene that only accomplishes one may be a candidate for tightening or merging.

2. **What does the POV character want?** In every chapter, the protagonist should have an active want driving their behavior. If the character is only reacting to events or observing the world, the scene lacks agency. Observation chapters work only after high-action sequences (cool-down beats).

3. **Where does tension live?** Every scene needs a source of friction. It doesn't have to be conflict — it can be uncertainty, disagreement, time pressure, an uncomfortable truth, or the gap between what a character wants and what they can have. If you can't point to the friction, the scene is flat.

4. **Pacing diagnosis.** Not about sentence rhythm — about emotional rhythm across chapters. Three consecutive high-intensity chapters exhaust the reader. Three consecutive low-intensity chapters bore them. Look for the pattern, not individual beats.

5. **Character motivation.** Are people acting for their own reasons, or are they being moved around by the plot? Characters with their own agendas create natural tension. Characters who show up because the plot needs them feel hollow.

6. **Redundancy.** Are two scenes doing the same narrative work? Is the same information delivered via dialogue AND narration AND internal monologue? Overlap is waste.

7. **Setup without payoff / payoff without setup.** Promises made to the reader that go nowhere feel like broken contracts. Moments that land without having been earned feel cheap. Both are structural problems.

### What a Good Dev Edit Report Looks Like

- **Specific**: "Chapter 250 and 252 both establish that the crew is tired of politics. One of these can be cut or merged."
- **Actionable**: Not "the pacing feels off" but "Chapters 249-251 are all medium-intensity dialogue scenes — consider adding a high-tension beat or cutting one."
- **Balanced**: Always identify what's working, not just what isn't. An author needs to know what to protect.
- **Structural**: The fix is never "rewrite this sentence." The fix is "move this scene," "cut this chapter," "combine these two conversations," "add a scene where X confronts Y."

---

### 4-Chapter / Act Developmental Checkpoint

Every 4 chapters (or at every Act break), audit the trailing block of chapters together with `rhythm-map`, `drift.py`, and `cast --gap 4`:

1. **Causal Escalation vs. Lateral Wheel-Spinning:** Did the protagonist's options, cost, or knowledge irreversibly tighten from Chapter `N-3` to Chapter `N`, or did multiple chapters merely replay lateral obstacles at steady tension (Act II sag)?
2. **Cadence Breathing Room:** Check the sequence of `cadence_role` values (`pressure_turn` vs `aftermath_valley` / `payoff_catharsis` / `tonal_counterpoint`). Flag four consecutive `pressure_turn` chapters with zero valley/counterpoint, or multiple chapters with zero irreversible pressure.
3. **Emotional Velocity & Relationship Continuity:** Compare `relationship_checkpoints` transitions against on-page scenes; flag abrupt hostility-to-intimacy or suspicion-to-trust jumps missing intermediate earned beats.
4. **Opening Exposition Load (Chapters 1–2 checkpoint):** Measure front-loaded lore, proper-noun density, and premise delay; push unmotivated history dumps out of opening scenes into active conflict.
5. **Seam & Hook Honesty:** Read each chapter's closing page beside `Chapter-(N+1)`'s opening paragraphs. Flag false cliffhangers deflated immediately on line 1 (e.g., manufactured danger revealed as a friend knocking) or forgotten unresolved threats.
6. **Cast Bloat & Role Duplication:** Audit newly introduced named minor characters across the 4-chapter block; recommend merging redundant single-function characters (`cut` or fold into existing supporting cast) and clarifying confusing shared first names or long-gap returns (`>4` chapters).
