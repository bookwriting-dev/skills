---
name: compile-manuscript
description: "Compile and stitch drafted chapter files into a continuous, publication-ready manuscript with customizable front matter, scene breaks, table of contents, and export formatting. Use when user says 'compile manuscript', 'export book', 'stitch chapters', 'generate full book file', or 'create publication draft'."
metadata:
  author: Storycraft Skills
  version: "1.1.0"
  bundled-dependencies: book-status
  category: cross-cutting
---

# Compile Manuscript

## Resolve sources and profile

Read project instructions, select book and beta/submission/publication profile, and resolve authoritative chapter conventions. Use [scripts/compile_manuscript.py](scripts/compile_manuscript.py). The bundled dependency is [project_state.py](../book-status/scripts/project_state.py); read [state-contract.md](../book-status/references/state-contract.md). Configure project-specific paths and conventions in [export-config.json](assets/export-config.json), supplying actual title, front/back matter paths, scene marker, required checks and an optional submission reference DOCX. Recipient requirements determine submission formatting.

## Preflight

Run `python3 SCRIPT --root ROOT --book Book-N --profile beta --format md --format docx --check`, adding `--config FILE` if needed. Numerically ordered authoritative Chapter-NNN.md sources must start at 1 without duplicates or gaps. Unknown or unclosed internal comments block export. Only STORYCRAFT-marked comments and storycraft-internal fences are stripped. LitRPG blocks and ordinary paragraphs remain printable. Only explicit `* * *` scene markers normalize by default; never treat arbitrary blank lines as breaks.

Markdown requires Python 3 only. DOCX/EPUB require detected Pandoc; PDF also needs an explicitly configured available engine through --pdf-engine. Missing dependencies fail the requested format, never silently substitute. Do not install converters without authorization. The helper must be bundled with the skill library.

## Build package

Repeat without --check to export. Request formats with repeated --format md/docx/epub/pdf. Submission and publication require current configured PASS evidence and completed campaign work. An explicitly requested --unchecked-preview permits a clearly disclosed preview with unresolved warnings in the manifest. Beta packages record all warnings for reader use. Resolve meaningful failures before retrying.

The exporter stages a complete package, verifies sources did not change, and then replaces the profile output while retaining a .previous package for recovery. It never edits source chapters. Output lives under Chapters/Book-N/export/PROFILE with export-manifest.json recording ordered source hashes, configuration, converters, output hashes, and warnings.

## Verify delivery

Inspect chapter completeness, meaningful scene breaks, headings, front/back matter, and internal-note removal. The script verifies container integrity; visually inspect representative DOCX/EPUB/PDF pages using host rendering tools before claiming layout approval. Publication export is a delivery artifact, not proof of editorial or retailer acceptance. Return artifact links, profile/formats, source/check warnings and whether visual verification is complete. Offer beta-reader delivery or a targeted formatting adjustment.
