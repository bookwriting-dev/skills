# Diction and clock time

In contemporary narration and dialogue, use the everyday wording the speaker or narrator would reach for. Write “She had two weeks left” for “She had a fortnight left,” “while” for “whilst,” and “between” for “betwixt.” Keep the meaning of the whole phrase. “They met fortnightly” becomes “They met every two weeks.”

Judge the voice of the passage. A British character who routinely says “fortnight” can keep it. A historical letter inside a modern novel keeps its own diction. In a dual-timeline book, apply the contemporary rule to the relevant scenes. Preserve verbatim quotations, titles, and wording the author has chosen for a particular voice.

Write exact clock times according to the book's `style-policy` (`clock_mode: digits` vs `clock_mode: words`). For contemporary technical/thriller prose using `digits`, “Meet me at ten thirty” becomes “Meet me at 10:30,” “Seven oh five” becomes “7:05,” and “ten o’clock” becomes “10:00.” For historical, period, fantasy, literary, and dialogue-heavy trade fiction using `words` (per Chicago Manual of Style §§ 9.37–9.39) or spoken dialogue (`--skip-dialogue`), preserve spelled-out times in speech and prose (“Meet me at half past four,” “ten o’clock”). Preserve qualifiers, any stated daypart, and ordinary expressions such as “half an hour,” “two weeks,” “at dawn,” “noon,” and “midnight.” An explicit book convention or verbatim source governs its own passage.

## Checking a draft

Run the read-only scan on the authoritative chapter path. Include `--modern` when the chapter contains a contemporary voice. Pass `--clock-mode words` when the book uses spelled-out clock prose (historical, fantasy, literary presets), and `--skip-dialogue` when characters speak in natural spoken rhythm. The script also accepts several chapter paths in one run.

```bash
python3 .agents/skills/book-status/scripts/prose_style.py --modern Chapters/Book-1/Chapter-001.md
```

Read each candidate in its sentence. Prices, room numbers, quantities, and clock-face directions can sound like times of day. Check quotation boundaries and scoped author decisions before proposing a change. During drafting, fix confirmed slips before handoff. During review, quote the passage and give the smallest correction. Include this reference and the scanner among the inputs for a saved review. Also check unlisted wording against the passage’s voice.
