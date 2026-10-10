---
name: name-generator
description: Generate names using a Markov chain model trained on name lists. Use when
user says "generate names", "create names", "make up names", "fantasy names", or
"name generator", or when a generated name needs a collision check before it
enters project canon.
metadata:
  author: Custom
  version: "1.1.0"
  category: utilities
---

# Markov Name Generator

Generates names using a Markov chain model trained on name lists in `data/`.

## Default Behavior: Full Sweep

By default, generate **3 names from every list** in `data/` and present them all grouped by culture. Do NOT ask questions first — just run it and show the results.

Enumerate every `data/*.txt` file. For each file, use [scripts/generate.py](scripts/generate.py) with the host's available Python interpreter and these arguments:

```text
--list <data-file> --count 3 --min-len 4 --max-len 12 --order 2
```

Use the data filename without `.txt` as the culture heading.

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
