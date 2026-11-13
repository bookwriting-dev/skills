---
name: name-generator
description: Generate character and people proper names using a Markov chain model trained on culture/style name lists. Use when user says "generate character names", "character names", "people names", "create names", "fantasy names", or "name generator" for characters. Do not use for settlements, towns, or geographic places.
metadata:
  author: Custom
  version: "1.4.0"
  category: utilities
---

# Name Generator

Supports three visibly distinct modes. A Markov corpus is a source of invented candidates only; corpus membership does not establish authenticity, historical fit, legal clearance, or uniqueness.

- **`invented`** — use for clear fantasy invention and as the documented generic creative default. Label the result as invented. Use [scripts/generate.py](scripts/generate.py) with `--mode invented`; `--json` records the seed, parameters, and corpus hash.
- **`contemporary_grounded`** — use when the request requires names evidenced in a real contemporary locale or language and a declared date window. Supply inspected exact-form records with stable source ID, source title/locator, date, region or language, and `inspection_status: inspected` via `--evidence`.
- **`historical_attested`** — use when a requested historical period/context requires evidence for that period. Supply matching inspected source records, the period window, and requested region or language. Current usage alone is not historical attestation.

Evidence modes return only exact forms from eligible records and do not require an invented-mode name list. A supplied `--seed` reproducibly shuffles eligible exact forms without changing spelling or provenance. If fewer records qualify than requested, report the shortfall; never fill it with Markov output. The script checks record completeness and filter membership only. It does not inspect the cited source or prove the record true, so source review and uncertainty remain explicit. Preserve exact spelling, diacritics, compounds, and transliteration as recorded.

## Default Behavior: Full Sweep

For an ordinary creative request with no attestation requirement, generate **3 invented names from every list** in `data/` and present them grouped by corpus label. Do NOT imply the output is historically or culturally attested.

Enumerate every `data/*.txt` file. For each file, use [scripts/generate.py](scripts/generate.py) with the host's available Python interpreter and these arguments:

```text
--list <data-file> --count 3 --min-len 4 --max-len 12 --order 2
```

Use the data filename without `.txt` as the culture heading.

When the caller needs names from a *specific* culture rather than a full sweep, read [references/culture-map.md](references/culture-map.md) to match the setting's culture to the right `data/` list (or lists), then generate from those lists only. The culture map is what the world-building skills consult when they route name generation here.

Present the output as a clean grouped list, e.g.:

**Anglo** — Wulfstan, Eadric, Aethelmere
**Aztec** — Coyotl, Xiuhtla, Huitzin
...

## After Showing Results

Offer to:
- Generate more from a specific list
- Re-roll the full sweep
- Adjust count or Markov order

## Before a Name Enters Canon

A generated name is a candidate, not canon. Before writing a name into a project's canon (character file, outline entry, world entry), collision-check the shortlist: search the web for each finalist against existing fictional characters, games, and brands, and prefer the cleanest name when candidates tie. Canonize the winner everywhere the project requires it, so no placeholder survives.

If a character's anonymity is deliberate — the story treats them as unnamed — leave them unnamed: resolve any placeholder with an accurate description instead of inventing a name.

## Refreshing a corpus

The `data/*.txt` lists come from the tekeli.li onomastikon. To add or refresh a list, use [scripts/scrape.py](scripts/scrape.py): `python3 scrape.py <url> [output_name]` saves to `data/`, or `python3 scrape.py --batch urls.txt` for the curated batch in `scripts/urls.txt`. Treat scraped output as a starting list — skim it for duplicates and artifacts before relying on it.
