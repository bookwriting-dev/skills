## Developmental Editing — What It Is and Isn't

Developmental editing operates at the story level. It answers: "Does this work as a narrative?" It does NOT answer: "Is this sentence good?"

### The Core Questions

1. **Why is this scene here?** Name what the reader would lose if the scene disappeared. A single gesture can complete a farewell, reveal a change in trust, or give grief its first moment of rest.

2. **What does the POV character want?** Identify who acts and whose viewpoint lets the reader understand the event. In a witness account, locate the observation that changes the meaning of what we saw.

3. **What earns the intended effect?** For a pressure turn, identify the obstacle or the price paid in the success itself. For cooperation, aftermath, humor, or closure, quote the action, detail, silence, or direct answer that delivers the intended experience. Read it beside the earlier scene that gives it meaning. Two sisters washing dishes can be their first act of trust, or a restatement of a reconciliation the reader already witnessed. Identify what the shared work adds before suggesting a cut.

4. **Pacing diagnosis.** Not about sentence rhythm — about emotional rhythm across chapters. Read a run of similar intensity for accumulating effects or a repeated beat. Use passage evidence before diagnosing fatigue or boredom.

5. **Character motivation.** Are people acting for their own reasons, or are they being moved around by the plot? Characters with their own agendas create natural tension. Characters who show up because the plot needs them feel hollow.

6. **Redundancy.** Are two scenes doing the same narrative work? When a gesture, conversation or thought returns, compare its context and effect with the earlier passage. Flag repetition when it leaves the reader in the same place.

7. **Setup without payoff / payoff without setup.** Promises made to the reader that go nowhere feel like broken contracts. Moments that land without having been earned feel cheap. Both are structural problems.

### What a Good Dev Edit Report Looks Like

- **Specific**: "Chapter 250 and 252 both establish that the crew is tired of politics. One of these can be cut or merged."
- **Actionable**: "The sisters already agreed about the key in Chapter 8. At the start of Chapter 9 they reach the same agreement again. Begin Chapter 9 with the first object they pack together."
- **Balanced**: Always identify what's working, not just what isn't. An author needs to know what to protect.
- **Structural**: The fix is never "rewrite this sentence." The fix is "move this scene," "cut this chapter," "combine these two conversations," "add a scene where X confronts Y."

---

### 4-Chapter / Act Developmental Checkpoint

Every 4 chapters (or at each break in the chosen form), audit the trailing block of chapters together with `rhythm-map`, `drift.py`, and `cast --gap 4`:

1. **Choices and consequences:** In an act or movement driven by a secondary character, find what they did for their own reasons while the lead was occupied. Cite the action and the later choice it made harder or possible. An offstage petition can first appear through the notice the lead opens. If its cost lies in undrafted chapters, distinguish the intention in the outline from what the reader has seen. For a solitary or contemplative strand, trace the relevant change in options or understanding.
2. **Cadence Breathing Room:** Check the sequence of `cadence_role` values (`pressure_turn` vs `aftermath_valley` / `payoff_catharsis` / `tonal_counterpoint`). Inspect a run of four similar chapters. Cite the repeated effect and its cost before flagging a pacing defect. A sequence of quiet witness accounts may accumulate evidence across changes in viewpoint.
3. **Emotional Velocity & Relationship Continuity:** Compare `relationship_checkpoints` transitions against on-page scenes; flag abrupt hostility-to-intimacy or suspicion-to-trust jumps missing intermediate earned beats.
4. **Opening Exposition Load (Chapters 1–2 checkpoint):** Trace where front-loaded history, names, or backstory obscure the intended opening experience. Identify the moment when the reader needs the information.
5. **Seam & Hook Honesty:** Read each closing page beside the next opening when a chapter follows. Flag a raised threat that the next page waves away. For earned closure, including the final chapter, identify the earlier promise and the action or image that fulfills it.
6. **Cast Bloat & Role Duplication:** Audit newly introduced named minor characters across the 4-chapter block; recommend merging redundant single-function characters (`cut` or fold into existing supporting cast) and clarifying confusing shared first names or long-gap returns (`>4` chapters).
