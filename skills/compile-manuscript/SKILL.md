---
name: compile-manuscript
description: "Compile and stitch drafted chapter files into a delivery package with customizable front matter, scene breaks, table of contents, and export formatting. Structural conversion does not imply rendered, author, or publication approval. Use when user says 'compile manuscript', 'export book', 'stitch chapters', 'generate full book file', or 'create publication draft'."
metadata:
  author: Storycraft Skills
  version: "1.9.0"
  bundled-dependencies: book-status
  category: cross-cutting
---

# Compile Manuscript

## Resolve sources and profile

Read project instructions, select book and beta/submission/publication profile, and resolve authoritative chapter conventions. Use [scripts/compile_manuscript.py](scripts/compile_manuscript.py). The bundled dependencies are [project_state.py](../book-status/scripts/project_state.py) and its shared [reader_text.py](../book-status/scripts/reader_text.py) extractor; read [state-contract.md](../book-status/references/state-contract.md). Use the shared workflow policy for required reviews. Export configuration may override it for that delivery. An approved import's front matter is included by default. Configure project-specific paths and conventions in [export-config.json](assets/export-config.json), supplying actual title, front/back matter paths, scene marker, required checks and an optional submission reference DOCX. Recipient requirements determine submission formatting.

## Preflight

Run `python3 SCRIPT --root ROOT --book Book-N --profile beta --format md --format docx --check`, adding `--config FILE` if needed. Release preflight checks every registered chapter and interlude in declared order. It also reports gaps in conventional numbering and unfinished chapter headings in conventional outlines and plans. The beta profile lists missing chapters while including available drafts. Unknown or unclosed internal comments block export. Only STORYCRAFT-marked comments and storycraft-internal fences are stripped. LitRPG blocks and ordinary paragraphs remain printable. Only explicit `* * *` scene markers normalize by default; never treat arbitrary blank lines as breaks.

Markdown requires Python 3 only. DOCX/EPUB require detected Pandoc; PDF also needs an explicitly configured available engine through --pdf-engine. Missing dependencies fail the requested format, never silently substitute. Do not install converters without authorization. The helper must be bundled with the skill library.

Preflight checks every chapter heading and POV tag against the book's format and reruns active book-wide continuity on the exact export sources. Inspect the returned findings and coverage. For stale or missing continuity evidence, review the relevant chapters with [book continuity review](../book-status/references/continuity-review.md) and rerun preflight. Confirmed contradictions and incomplete active coverage block submission and publication. Unclear scopes and other interpretive continuity findings remain review notes. Beta exposes findings and coverage gaps in the package manifest.

Preflight revalidates the sources cited by [load-bearing assertions](../book-status/references/evidence-chain.md). The export manifest binds those local source revisions, including inspected research records and retained snapshots.

## Build package

Repeat without --check to export. Request formats with repeated --format md/docx/epub/pdf. Submission and publication require current configured PASS evidence and completed campaign work. An explicitly requested --unchecked-preview permits a clearly disclosed preview with unresolved warnings in the manifest. Beta packages record all warnings for reader use. Resolve meaningful failures before retrying.

The exporter stages a complete package, verifies sources did not change, and then replaces the profile output while retaining a .previous package for recovery. It never edits source chapters. Output lives under Chapters/Book-N/export/PROFILE with export-manifest.json recording ordered source hashes, configuration, converters, output hashes, and warnings.

The beta profile includes an export ID and a [reader passage map](scripts/beta_exchange.py). The map freezes ordered reader scenes and paragraphs for later comparisons. Beta DOCX files carry the ID and passage bookmarks. Share the manuscript file with readers and retain the export manifest and passage map locally for `beta-feedback`, including previous beta editions.

## Verify delivery

Inspect chapter completeness, meaningful scene breaks, headings, front/back matter, and internal-note removal. The script verifies container integrity; visually inspect representative DOCX/EPUB/PDF pages using host rendering tools before claiming layout approval. Publication export is a delivery artifact, not proof of editorial or retailer acceptance. Return artifact links, profile/formats, source/check warnings and whether visual verification is complete. Offer beta-reader delivery or a targeted formatting adjustment.

## EPUB navigation and imported matter

A preflight records EPUB navigation as PENDING. The built artifact is checked by following its actual contents, internal links, note references and any return links. The export saves epub-navigation.json alongside the EPUB. Recheck a returned file with [epub_navigation.py](scripts/epub_navigation.py) FILE --expect EXPECTATIONS. An incorrect or broken destination warns on a beta and blocks verified publication. Missing optional note returns are advisory. The exporter uses the imported book's front/back matter, illustrations, title and language by default. Supply title and language in the export configuration to override them.
