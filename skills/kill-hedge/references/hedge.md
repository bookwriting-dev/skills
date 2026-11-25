# Pass: kill hedge words and qualifiers

Targets the hedge tokens the model overuses to pad, soften, and back a claim off
its own edge: `somewhat`, `tends to`, `in a sense`, `arguably`, `essentially`,
`basically`, `virtually`, `practically`, `kind of`, `sort of`, `rather`, `fairly`,
`quite`, `relatively`, `comparatively`, `in some ways`, `to some extent`,
`more or less`.

**The deletion-first rule:** in most cases the hedge can simply be **deleted** without
changing the meaning. Prefer outright deletion over swapping in another qualifier.
Never replace one hedge with another ("essentially" → "basically" is not a fix).

Examples:
- "the theory essentially explains X" → "the theory explains X"
- "this approach is quite effective" → "this approach is effective" (or cite the measured figure; preserve `"quite"` if the book uses a British/period register)
- "somewhat effective" → "effective" (if the degree matters, add a concrete comparison; do not trade "somewhat" for "slightly")

**KEEP:**
- **Empirical & epistemic calibration:** Never upgrade a correlational, probabilistic, or tentative claim into a categorical assertion (`"results virtually confirm"`, `"tends to"`, `"to some extent"`, `"arguably"` when evidence strength does not prove causation). Upgrading a calibrated hedge into `"results confirm"` causes a `nonfiction-factcheck` overclaiming error!
- Genuine epistemic uncertainty that is the point the sentence makes (measured claims about limits of knowledge: "evidence suggests," "with X still unresolved").
- Quoted speech and direct discussion of hedging (the hedge is the subject).
- Idiomatic / field-standard phrasing where the qualifier carries meaning, not padding.
- Comparative qualifiers with an explicit referent when the comparison is the work ("relatively low, compared to Y").

**FIX:**
- "essentially/basically/practically X" filler padding on an already-supported claim — DELETE, commit the claim.
- "somewhat/fairly/quite X" vague volume knobs — DELETE or replace with the concrete figure (keep if period/British voice).
- "in a sense/in some ways/more or less" that smear a point — DELETE or rewrite so any real caveat sits explicitly on the condition where it holds.
- "kind of/sort of" filler hesitation — DELETE.
- The same hedge twice within a few lines — cut at least that one.

Verify grep (remaining hits should be only KEEP-classified, by eye):
`grep -rniE "\b(somewhat|tends to|in a sense|arguably|essentially|basically|virtually|practically|kind of|sort of|rather|fairly|quite|relatively|comparatively|in some ways|to some extent|more or less)\b" <files>`

For before/after counts: `grep -rioE "\b(somewhat|tends to|in a sense|arguably|essentially|basically|virtually|practically|kind of|sort of|fairly|quite|relatively|comparatively|more or less)\b" <files> | wc -l`.
