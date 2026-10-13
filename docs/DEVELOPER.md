# Developer Guide

How this repository is built, how a skill is structured, and how to change the library
without breaking the projects that pin it. For the writing workflow itself — what the
skills do and when to run them — see [USER.md](USER.md).

## What this repo is

An owned fork of [Open Storycraft](https://storycraft.lanternkey.fyi/), independently
developed since 2026-10-10. The lineage:

- **Origin.** Vendored from the mermaid project's `.agents/skills/` at its commit
  `dc010ca` (2026-09-11) — at that point a verbatim copy of Open Storycraft's 42 skills.
- **Fork declaration.** 2026-10-10. From that commit on, this is ordinary development:
  there is no re-apply-the-deltas ritual, no tracked-deltas copy. Change, bump, log, commit.
- **Upstream relationship.** Open Storycraft has no public repo or changelog — a
  structured ZIP is its only distribution channel. `./sync-check.sh` diffs us against
  the current ZIP and classifies every difference. Upstream drift is an offer, not an
  obligation.

**This repo is the source of truth for the library.** Book projects get a *pinned copy*
of `skills/` at `.agents/skills/` when scaffolded (a real `cp -R`, not a symlink), so
every project versions its own library and can fork it freely. Changes here do not
propagate to existing projects automatically — that is by design.

Scale today: **72 skills** — 42 inherited from upstream at the fork point, 30 added
since (8 fiction, 13 cross-cutting/pipeline/publishing, 9 non-fiction).

## Repository layout

```
storycraft-skills/
├── skills/              # the library — one folder per skill
├── templates/           # AGENTS.md + CLAUDE.md skeletons, rendered per project
├── new-book.sh          # scaffold a new series project
├── sync-check.sh        # diff against the upstream ZIP
├── sync-manifest.txt    # files we own that may differ from upstream
├── CHANGELOG.md         # every change, with the why
└── docs/                # this guide and USER.md
```

## Anatomy of a skill

```
skills/skill-name/
├── SKILL.md        # required — frontmatter + procedure
├── references/     # domain knowledge, criteria, rule-sets, JSON schemas, (sometimes) scripts
├── assets/         # templates copied into the project (output templates, yaml scaffolds)
├── scripts/        # executable Python, invoked host-neutrally
└── data/           # name/town corpus .txt files (generators only)
```

Not every skill has every folder. `references/` is by far the most common; generators
(`name-generator`, `town-generator`) carry `data/` corpora.

### SKILL.md frontmatter contract

```yaml
---
name: kebab-case-name          # must match the folder name
description: "What it does + when to trigger it, including the literal
  phrases a user would say. Under 1,024 chars, no < or >."
metadata:
  author: Fiction Toolkit
  version: "1.2.3"             # quoted string; bumps with EVERY change
  category: fiction-writing
---
```

- **`name` must equal the folder name.** A rename is directory + frontmatter `name` +
  title + every template reference + manifest paths + version bump, or it isn't done —
  the 2026-10-11 reconciliation pass fixed the one historical violation of this
  (see the reconciliation record at the end).
- **`description` is the router.** Agent hosts match user phrasing against it, so it
  carries concrete trigger phrases ("use when user says 'check promises', 'loose
  ends'…") and, for skills with narrow scope, explicit *do-not-use* guidance ("use
  fiction-full-editor for general editing; use this only when isolating one layer").
- **`metadata.version` bumps with every change**; `CHANGELOG.md` records the why.
  Practice from the history: major for behavior/model changes (kill-chapter 1.0 → 2.0
  orchestrator), minor for new capability or criteria (fiction-promises 1.0 → 1.1 loud
  forward references), patch for narrow fixes (fiction-style 7.0.1 buzzword bans).
- **`category` values in use:** `fiction-writing`, `fiction-editing`,
  `nonfiction-writing`, `nonfiction-editing`, `cross-cutting`, `utilities`, `meta`.
- Legacy routing fields (`workflow-position`, `requires`, `next-skill`) were removed in
  the 2026-10-10 consolidation (R0). **`templates/AGENTS.md` is the single authoritative
  workflow order** — skills do not encode their own position in the pipeline.

### Body conventions

SKILL.md bodies are step-structured procedures. The recurring shapes across the library:

| Heading pattern | Used by |
|---|---|
| `## Step 1: Locate the Project…` → `## Step N: Save and Report` | project-aware pipeline skills |
| `## Arguments` / `## Procedure` | generator + diagnostic skills |
| `## Worker Instructions` | orchestrators that fan out focused workers |
| `## What to keep vs. fix` | kill passes and editors |

Four architectural patterns cover the whole library (formalized by `skill-builder`):

1. **Document / Asset Creator** — produces a Wiki file (`fiction-genre`,
   `fiction-outline`).
2. **Workflow Orchestrator** — multi-step pipeline with focused workers
   (`kill-chapter`, `fiction-reviewchapter`).
3. **Generator + Script** — wraps a Python script and presents results
   (`name-generator`, `town-generator`, `drift-check`).
4. **Reference + Advisor** — loads criteria from `references/` and applies them
   (`coldread`, `fiction-dialogue`).

### Conventions that carry across skills

These are load-bearing; breaking them breaks other skills' assumptions:

- **Focused workers get self-contained instructions.** Workers do not reliably inherit
  conversation context. Each worker receives its exact file list, the relevant
  rule-set *verbatim* from `references/`, and its output format (typically a per-file
  verdict list: `KEEP-reason` / `DELETED` / `REWORDED` with before→after).
- **Parallel where the host allows, sequential where it doesn't.** Skills phrase this
  as "use one focused worker per group in parallel when the host supports workers;
  otherwise process the groups sequentially" — provider-neutral by rule
  (skill-builder's validation checklist enforces it).
- **Consecutive, not parallel, for in-place multi-pass editors.** `kill-chapter` runs
  its seven passes strictly one after another because each pass already fans out
  workers that edit files in place; two passes at once would clobber the same files.
  After every pass, re-read before any follow-up edit — worker edits make in-context
  file state stale.
- **Diagnostics never edit.** `drift-check`, `burstiness-check`, and `pangram` are
  measurement-only passes: they report numbers and trend flags and route the fix to an
  editing skill. A diagnostic that edits breaks the separation the routing tree relies on.
- **Deletion-first editing.** Kill passes delete the crutch before considering a
  rewrite, and touch only the target token — a worker that "helpfully" fixes an
  adjacent word is out of scope and gets reverted.
- **Rule-sets live in `references/`, not SKILL.md.** kill-chapter states it directly:
  the seven `references/*.md` are the single source of each pass's keep/fix rules;
  tune behavior there, not in the orchestrator.
- **Book-agnostic where it must be.** Generators and kill passes carry no character
  names, settings, or canon. Book-specific KEEP exceptions are passed at invocation.
- **Skill scripts are standalone** — no plugin dependencies (`fiction-promises`'
  `scripts/promises.py` is the stated example). Invoke with `python3` and a relative
  path; don't assume a provider-specific shell.

### Script inventory

| Script | Owner | Purpose |
|---|---|---|
| `drift-check/references/drift.py` | drift-check | book-level drift metrics (pet words, negation pivots, opener/closer formulas, noun-swapped dies, specifics density) |
| `burstiness-check/references/measure.py` | burstiness-check | sentence/paragraph variance, openings, dialogue ratio |
| `fiction-promises/scripts/promises.py` | fiction-promises | Chekhov ledger report |
| `promise-tracker/scripts/promises.py` | promise-tracker | unified fiction/non-fiction ledger report |
| `name-generator/scripts/generate.py` + `scrape.py` | name-generator | name sampling from `data/*.txt`; corpus refresh |
| `town-generator/scripts/generate.py`, `generate_town.py`, `epithet.py`, `scrape.py` | town-generator | settlement naming |
| `fantasy-settlement/scripts/generate_settlement.py` | fantasy-settlement | settlement dossier generation |

Quirk worth normalizing someday: most scripts live in `scripts/`, but the two
diagnostics keep theirs in `references/`.

## Making a change

The ordinary-dev loop (this replaces the old tracked-deltas ritual):

1. **Change the skill.** For new skills, run `skill-builder` — it walks use-case →
   pattern → structure → SKILL.md → supporting files → validation, and its checklist is
   the library's quality bar (name/folder match, description with trigger phrases under
   1,024 chars, self-contained worker instructions, resolvable relative paths, no
   provider-specific assumptions, a next step at the end).
2. **Bump `metadata.version`** in the SKILL.md frontmatter.
3. **Add a CHANGELOG entry** — newest first, with the *why*, not just the what.
4. **Register new files in `sync-manifest.txt`** (paths relative to repo root, one per
   line). The manifest tells `sync-check.sh` which differing files are ours; an
   unregistered changed file shows up as false "UPSTREAM DRIFT".
5. **Wire into `templates/AGENTS.md`** if the change affects the workflow: the
   start-of-book order, the editing decision tree, or the skill index. The template is
   the single source of workflow authority — a skill that isn't in the index is a skill
   the next project never runs.
6. **Commit.**

Two template-rendering notes: `templates/AGENTS.md` is the full instruction file and
`templates/CLAUDE.md` is a one-line `@AGENTS.md` import (never give CLAUDE.md its own
content). `new-book.sh` renders both with `sed` on the `__SERIES_TITLE__` placeholder —
any new placeholder needs matching script support.

## Scaffolding: new-book.sh

```
./new-book.sh <slug> ["Series Title"]                # → ~/Projects/Books/<slug>  (fiction)
BOOKS_DIR=/some/where ./new-book.sh <slug>           # → /some/where/<slug>
./new-book.sh <slug> "Title" --type nonfiction       # or hybrid
```

Creates the project folder, `cp -R`s the library to `.agents/skills/`, makes the Wiki
skeleton (shared: `Characters/`, `World/{Places,Factions,Systems,Events}`, `Style/`,
`Review/`, `Story/Book-1`; per-book: `Story/`, `Outline/`, `Psych/` under `Wiki/*/Book-1`
plus `Chapters/Book-1/`, `_Edits/Book-1/`), renders the templates, `git init`s (with a
fallback to the Xcode git binary when the CLT license blocks `git`), and commits.

`--type` sets the `__PROJECT_TYPE__` line in the rendered `AGENTS.md` and creates
`Wiki/Concept/` + `Wiki/Research/` for `nonfiction` and `hybrid`; fiction scaffolds are
unchanged. Slug validation: no slashes, no leading dot; refuses to overwrite an
existing folder.

## Upstream sync: sync-check.sh

```
./sync-check.sh                 # fetch the current upstream ZIP
./sync-check.sh /path/to/zip    # check against a local copy
```

Downloads/unpacks the ZIP, `diff -rq`s its `skills/` against ours, and classifies each
difference using `sync-manifest.txt`:

| Classification | Meaning | Action |
|---|---|---|
| `ours (expected)` | changed by us, listed in the manifest | none |
| `ours (deleted)` | a file we deliberately removed, still listed in the manifest | none (keep the manifest entry as the tombstone) |
| `fork addition` | only we have it | none (register it in the manifest) |
| `UPSTREAM DRIFT` | changed upstream, we never touched it | review: port if good (then manifest + CHANGELOG), or record why skipped |
| `NEW UPSTREAM` | upstream has it, we don't | same review |

When you delete an inherited file, **keep its `sync-manifest.txt` entry** — the entry
is what lets `sync-check.sh` classify the upstream-only leftover as
`ours (deleted)` instead of an unexplained finding.

Exit codes: `0` everything accounted for, `1` unexplained findings (so it can gate a
periodic check), `2` environment/usage error. Policy in one line: **this repo is the
source of truth; upstream drift is an offer, not an obligation** — but every offer gets
an explicit answer (ported or skipped-with-reason).

## Reconciliation record (2026-10-11)

The first version of this guide documented eight gaps between the doc layer and the
library; all eight are fixed. The record stays because each item explains a convention
the next change should preserve:

1. **Phantom skills removed from `templates/AGENTS.md`.** The template referenced eight
   non-fiction skills that don't exist (`nonfiction-research`, `nonfiction-style`,
   `nonfiction-dev-editor`, `nonfiction-reviewchapter`, `nonfiction-revise`,
   `nonfiction-sources`, `nonfiction-claims`, `nonfiction-terminology`). They were
   **un-referenced, not built** — a deliberate scope decision recorded in the
   CHANGELOG. If you build them, wire them into the workflow, decision tree, and index
   in the same change that adds the files.
2. **`review-panel` rename completed** (`skills/fiction-review-panel/` →
   `skills/review-panel/`, 1.1.0). The original rename changed only the frontmatter
   `name:` — the incident behind the rename rule above.
3. **`sync-manifest.txt` matches disk.** Three misnamed `promise-tracker/references/`
   entries corrected, two template entries for files that never existed removed, one
   duplicate entry removed.
4. **No build artifacts tracked.** `.gitignore` covers `__pycache__/` and `*.pyc`; the
   committed `.pyc` is gone.
5. **Version bumps caught up.** `drift-check` 1.1.0 (its non-fiction metrics had
   shipped without the bump) and `coldread` 1.0.1 (description generalized to fiction
   or non-fiction — the template's non-fiction tree routes to it).
6. **`new-book.sh --type fiction|nonfiction|hybrid`** implemented: renders the
   `__PROJECT_TYPE__` line and creates `Wiki/Concept/` + `Wiki/Research/` for
   non-fiction/hybrid projects.
7. **CHANGELOG corrected.** The 2026-10-11 non-fiction entry now records what its
   commit actually shipped, with a correction note; the deleted audit report is cited
   as git history (`git show e84222e^:AUDIT-REPORT-2026-10-10.md`), not as a file.

Still open, by choice: three non-fiction layers remain unbuilt — research/source
management, a non-fiction developmental editor, and a non-fiction revise skill (the
seven-skill non-fiction workflow routes around them; see USER.md's non-fiction section
for how) — and the two diagnostics keep their scripts in `references/`
instead of `scripts/` — a harmless inconsistency; normalize it if you're touching
those skills anyway.
