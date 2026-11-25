# Pass: kill "soft"

"soft" is a crutch word the model overuses. Correct for **physical texture** and a **quiet
speaking voice**; wrong almost everywhere else, especially stretched over an abstract,
temporal, atmospheric, or emotional noun for a writerly effect.

**KEEP (do not touch):**
- Physical texture you could touch: "soft fur," "soft skin," "the soft of her belly," "marble worn soft."
- **Quoted dialogue** and speaking softly / a soft voice: `"he said softly,"` `"her voice went soft,"` or spoken lines where `"soft"` is natural speech.
- Deliberate theme threads where "soft / softness" is a consciously-built character trait. When unsure if thematic, KEEP and flag.

**FIX (cut first in narration; reword only if the beat needs it):**
- "soft" in narration on an abstract / temporal / atmospheric / emotional noun: "the soft morning," "the soft dark," "a soft ache," "soft warmth / quiet / silence," "the room going soft at the edges."
- "soft" on a thing with no softness ("a soft heap of copper," "soft bracelets of scar").
- Repetition: same noun called "soft" twice within a few lines, or twice in one sentence.

Default move is **deletion** ("a soft ache" → "an ache"). Reword only when deletion loses
meaning; use the plain word (quiet, faint, low, weak, gentle, dull), never another mood word. Leave acoustic modifiers like `"a soft click"` alone if `"click"` needs the volume qualifier and it isn't repeated.

Verify grep (inspect remaining hits in context; dialogue and literal physical uses are KEEP):
`grep -rniE "soft (morning|day|night|dark|light|hour|ache|warmth|quiet|silence)" <files>`
