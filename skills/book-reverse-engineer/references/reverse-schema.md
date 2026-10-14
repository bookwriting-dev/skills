# Reverse-Scaffold Analysis Report Schema

This document defines the structure of `_Edits/Book-N/reverse-analysis.md` produced during Step 2 of `book-reverse-engineer`.

---

```markdown
# Manuscript Analysis: <Title>

**Source:** `<path to raw manuscript or chapter files>`
**Units detected:** `<number of chapters>`
**Total words:** `<total word count>`
**Analysis date:** `<YYYY-MM-DD>`

> [!IMPORTANT]
> Everything below is inferred by reading the manuscript prose, not fact-checked ground truth.
> Review every `CANON GAP`, `CANON CONFLICT`, `DROPPED THREAD`, and `LOW CONFIDENCE` tag before running the import step.
> Your decisions on these items will become the authoritative `Wiki/` canon defended by Storycraft.

---

## 1. Character Roster

### <Character Name>
- **Role:** Protagonist / Antagonist / Supporting / Cameo / Historical
- **First appearance:** ch<NN>
- **Age:** <Age or `CANON GAP`>
- **Physical description:** <Confirmed traits from text or `CANON GAP`>
- **Psychology / Core Want:** <Internal want, external need, flaws>
- **Relationships:** <Key connections to other characters>
- **Flags / Inconsistencies:** <e.g. `CANON CONFLICT — eye color blue in ch1, brown in ch8`>

---

## 2. Setting & World Rules

### Locations
- **<Location Name>:** <Description, key events hosted, spatial relation to other places. Tag gaps/conflicts.>

### Rules, Systems & Lore
- **<System / Lore Rule>:** <Rules of magic, technology, law, or society established in prose. Tag contradictions.>

### Factions & Institutions
- **<Faction Name>:** <Powers, goals, key figures.>

---

## 3. Timeline & Chronology

- **Story Order vs. Told Order:** <Reconstruction of underlying timeline events.>
- **Timeline Conflicts:** <`CANON CONFLICT` or `LOW CONFIDENCE` regarding travel durations, calendar dates, elapsed days.>

---

## 4. Retrofitted Chapter Beats

### Chapter <NN>: <Title>
- **POV:** <POV character name> (<1st person / 3rd limited / omniscient>, <past / present>)
- **Scene Goal:** <What the POV character enters the scene wanting>
- **Conflict / Obstacle:** <What opposes them>
- **Turn / Outcome:** <How the situation changes by chapter close>
- **Key Beats:**
  1. <Beat 1>
  2. <Beat 2>
  3. <Beat 3>
- **Words:** <Word count>

---

## 5. Chekhov Ledger & Open Threads

| ID | Setup / Promise | Introduced | Paid Off | Status (`paid` / `unpaid` / `abandoned`) | Notes |
|---|---|---|---|---|---|
| P01 | <Loaded gun / mystery hook> | ch<NN> | ch<NN> | <status> | <Details> |

---

## 6. Voice & Style Profile

### Mechanical Profile
- **POV:** <Primary POV and person>
- **Tense:** <Past / Present>
- **Dialogue Ratio:** <Estimated % dialogue vs prose>
- **Sentence Variance / Rhythm:** <Short/punchy vs long/lyrical, burstiness notes>

### Voice Inconsistencies
- `- VOICE BREAK — <description of tense shift, POV leak, or tone break in chNN>`

### Representative Anchor Passages
1. *<Passage 1 excerpt citing chapter>*
2. *<Passage 2 excerpt citing chapter>*
...

---

## 7. Open Questions / Discrepancy Punch List
*(Aggregated flags from above requiring human decision before importing into Wiki)*

- `- CANON CONFLICT — <finding description with chNN>`
- `- DROPPED THREAD — <finding description with chNN>`
- `- CANON GAP — <missing information with chNN>`
- `- LOW CONFIDENCE — <inference that needs verification>`
```
