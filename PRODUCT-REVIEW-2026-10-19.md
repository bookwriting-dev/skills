# Product Review — storycraft-skills

**Date:** 2026-10-19
**Scope:** the whole package — 73 skills, 3 docs, the scaffolder, the toolchain, the templates.
**Method:** read every skill, ran the gate, verified each claim below against the actual files (and executed the scripts where the claim was behavioral). No code was changed.

---

## 1. The thesis

This is a genuinely good library with a **shape problem**.

The toolchain proves the library is *well-formed*: frontmatter parses, paths resolve, the catalog matches reality, the scaffolder survives `sed` metacharacters, CI runs on two platforms. `make check` is green. That is real engineering and it should be preserved.

But `make check` proves nothing about **whether the library works**. And it turns out the library does not fully work, in ways that are invisible to the gate and invisible to the author:

- `chapter-pipeline` — the one skill whose entire job is "run the chapter loop" — **cannot complete the chapter loop.** Its gate can never return PASS, and its polish step can be a no-op.
- `book-status` — the skill that answers "what needs attention?" — **has no output path at all**, and summarizes three artifacts that no skill ever writes to disk.
- Six fork points in the workflow have **two skills and no tiebreaker**, so which one runs is decided by a router black box the author cannot see or predict.
- Nine skills read a file the author wrote; the docs promise the whole planning pipeline reads it.

The pattern: **the gate validates the library's silhouette, not its behavior.** Everything the gate checks can be perfect while the pipeline still stalls on a real book. That is the single most important thing to fix, and it is not a bug list — it is a change in what "done" means for this package.

**The headline recommendation:** before adding any skill, make the library *provably runnable end to end* on a real chapter, and add a check that proves it. A green gate on a pipeline that cannot finish is worse than a red gate, because it is trusted.

---

## 2. What's working — preserve these

These are the package's real assets. Do not let cleanup efforts damage them.

| Asset | Why it matters |
|---|---|
| **Process architecture** | Canon-outranks-draft, the five-slot per-book layout, the Chekhov ledger, gates, diagnostics-that-never-edit, revision-plan-and-redraft instead of editing structure. This is differentiated thinking; most "AI writing" kits have none of it. |
| **Self-checking toolchain** | Lint + generated inventory + shell syntax pass + end-to-end smoke test + version pin. This is what turned a pile of prompts into a *library*. The CI-runs-the-Makefile decision (so the gate can't drift from what's enforced) is exactly right. |
| **Description-as-router discipline** | Descriptions carry trigger phrases *and* explicit do-not-use guidance. The `review-panel` / `reader-persona-review` and `fiction-promises` / `promise-tracker` boundaries are written down in prose in both directions. This is rare and it works. |
| **The audit habit** | `AUDIT-2026-10-11.md` → nine batched fix commits → the mechanical linter that encodes the audit's invariants. The linter *is* the institutional memory. |
| **Deletion-first editing** | Kill passes delete the crutch before rewriting, and touch only the target token. A genuinely correct editing philosophy, and hard to retrofit later. |
| **Fork discipline** | Declaring ownership on 2026-10-10 and treating upstream drift as an offer rather than an obligation. Correct, and worth continuing to make explicit. |

---

## 3. The five findings that matter

### 3.1 The pipeline cannot finish its own loop — **severity: critical**

`skills/chapter-pipeline/SKILL.md` is 27 lines and orchestrates the write loop. Two independent defects make it structurally unable to deliver:

**(a) The gate can never PASS.** `chapter-pipeline:24` runs `gate-check`. `gate-check:26` requires that any setup introduced in the chapter "must be registered in `promises.yaml` via `fiction-promises`." `chapter-pipeline` never invokes `fiction-promises`. So on any chapter that sets anything up, the gate fails on a technicality the pipeline caused.

**(b) The polish step can be a no-op.** `chapter-pipeline:26` polishes with `fiction-aiism-editor` or `kill-chapter`. `fiction-aiism-editor` only *reports* — its Step 5 saves `Chapter-NNN_AIisms.md` and then says "Offer to apply approved items with `fiction-revise`" (`fiction-aiism-editor:96-99`). The pipeline never calls `fiction-revise`. Choosing `fiction-aiism-editor` therefore produces a report file and leaves the chapter byte-identical.

Two more soft defects in the same file:
- It looks for `Wiki/Outline/Book-N/Chapter_[NN]_Scene.md` (`chapter-pipeline:17`). The authority file says `Chapter_NN_Scene.md` (`templates/AGENTS.md:16,34`). **In a standard scaffolded project the pipeline will not find the scene file it needs.**
- "Halts if major beat gaps exist" and "minor `WARN`" — neither "major" nor "minor" is defined anywhere in the library.

This is the sharpest possible evidence for the thesis: the single skill that exists to prove the pipeline works is the one that doesn't.

### 3.2 Producer/consumer contracts don't line up — **severity: critical, and silent**

Several skills read artifacts that other skills write, where the paths or formats don't match. The failure mode is not an error — it's work that quietly doesn't happen.

| Producer writes | Consumer reads | Consequence |
|---|---|---|
| `nonfiction-research` → `Wiki/Research/sources.yaml` (`:17`) | `nonfiction-factcheck:24` globs `**/Research/**/*.md` | The primary citation registry is **invisible** to the only skill that verifies claims. `.yaml` doesn't match `.md`. |
| `drift-check`, `burstiness-check` — report to console, never to a file | `book-status:27` "Summarizes latest `drift-check` and `burstiness-check` findings" | Reads files that will never exist. |
| `reader-persona-review` → `_synthesis.md` (no path anywhere) | `book-status:24` "consensus scores (`_synthesis.md`)" | Fiction routes to `review-panel`, which synthesizes in-conversation and writes nothing. Nothing to read. |
| `levelup:121` → `[chapter-name]_LevelUp.md`; `fragment-hunter:248` → `[chapter-name]_FragmentHunt.md` | `fiction-revise:28` looks for `Chapter-NNN_Review.md`, `Chapter-NNN_FullEdit.md`, `Chapter-NNN_LineEdit.md`, "etc." | Keyed on the chapter **number**. These two files are invisible to the reviser. Both skills then hand off to `fiction-revise`, which won't find their report. |
| `fiction-reviewchapter:189` harvests promises with fields `promise, introduced_ch, kind, weight, payoff_by_ch, deferred_to_series` | Both `promises.py` scripts key on `id` | Harvested promises print as `?` in every report. `book-reverse-engineer:100` specifies no schema at all for the ledger it seeds. |

Note the last two rows: `AUDIT-2026-10-11.md:107-112` claims all six report writers "now save `_Edits/Book-N/Chapter-NNN_<Type>.md`". Git shows `levelup` and `fragment-hunter` were never converted — the fix commit touched the folder path, not the filename. **The audit ledger over-claims a fix that did not land.** That matters beyond these two skills: it's the second time an audit assertion has outlived its implementation.

### 3.3 One ledger, four writers, two parsers that disagree — **severity: high**

`Wiki/Story/Book-N/promises.yaml` is written by `fiction-promises`, `promise-tracker`, `fiction-reviewchapter`, and `book-reverse-engineer`. The two ledger skills also ship *different* asset templates and **different parsers for the same field**:

| `payoff_by_ch` | `fiction-promises/scripts/promises.py:37-40` | `promise-tracker/scripts/promises.py:33-45` |
|---|---|---|
| `"sec2.1"` | **21** | **2** |
| `"ch3.5"` | **35** | **3** |
| `"Chapter 12"` | 12 | 12 |

`fiction-promises` concatenates every digit; `promise-tracker` takes the first integer. The second script's own docstring claims support for `'sec2.1'`, and `promise-tracker:57` explicitly invites section references. **On the same file, the two scripts disagree about what is overdue.**

Both skills also copy *their own* `assets/promises.yaml` over the target without checking whether a ledger already exists (`fiction-promises:36-38`, `promise-tracker:25-27`), and the two assets differ — `promise-tracker`'s has a `project_type` field, `fiction-promises`'s does not.

**Hybrid projects have no winner.** `new-book.sh --type hybrid` creates both the fiction and the non-fiction Wiki slots, so both ledger skills look in scope, and the documented tiebreaker is "pick the one that matches the project type" — when the project type is *hybrid*.

### 3.4 Six fork points with no tiebreaker — **severity: high**

The workflow forks, and at each fork two skills can plausibly answer. The docs often list both on one line; the router decides; the author can't predict it.

| Fork | Candidates | Tiebreaker? |
|---|---|---|
| Chapter gate | `fiction-reviewchapter` / `gate-check` | **None.** The two skills never mention each other. `USER.md:120` and `AGENTS.md:139` list both on one line; `AGENTS.md:181` lists them in the **reverse order**. |
| Persona review | `review-panel` / `reader-persona-review` | Good in prose, but `USER.md` contradicts itself: the decision tree (`:129`) sends both columns to `review-panel`; the recipe list (`:296`) and `AGENTS.md:160` send non-fiction to `reader-persona-review`. |
| Promise ledger | `fiction-promises` / `promise-tracker` | "Pick the one matching your project type" — undefined for hybrid. |
| Non-fiction crutch pass | `kill-crutch` is `category: fiction-editing` but is the general filler pass | It appears in **neither** column of the `USER.md:127` decision tree, nor in `AGENTS.md:158`. A user hunting for it won't find it. |
| Non-fiction dev editor | `nonfiction-dev-editor` | **`USER.md:119` says "(not yet built — re-plan + re-draft)".** It exists (1.0.0), is catalogued at `USER.md:230`, and is wired at `AGENTS.md:151,211`. The doc table is simply wrong. |
| Scene file name | `Chapter_NN_Scene.md` (authority) vs `Chapter_[NN]_Scene.md` | Both spellings are live in the library. |

This matters more than it looks. The author's mental model is "I ask for a review, I get a review." The system's actual model is "the router picks one of two overlapping skills, and the two produce different artifacts in different formats." Every fork is a place where the author's expectations and the system's behavior can diverge without anyone noticing.

### 3.5 The thin tail sits exactly where the glue is — **severity: high**

Distribution across 73 skills (procedure words in `SKILL.md`, excluding frontmatter): median 746, mean 803, 58,617 total. **10 skills are under 300 words; 28 are under 600; only 14 are at 1,200+.**

The 11 thinnest are not decorative. They are the connective tissue:

| Skill | Words | Problem |
|---|---|---|
| `book-status` | 223 | **No output path at all.** Reads three artifacts nobody writes. Calls `promises.py status check` — there is no `--status` flag (args are `--chapter/--book/--ledger/--final`), and it doesn't say *which* of the two copies. |
| `nonfiction-dev-editor` | 179 | Five diagnostic dimensions and nothing else — no procedure, no thresholds, no report format, no error handling, no `references/`. Three of its five dimensions (abstraction ladder, cognitive load, signposting) are already fully specified in `nonfiction-clarity-edit/references/`, which it never points at. |
| `nonfiction-research` | 177 | No schema for `sources.yaml`, `claims-matrix.md`, or `case-studies/` — six implied fields, none named as keys. Not in the numbered `AGENTS.md` workflow at all, though `factcheck` depends on it. |
| `chapter-pipeline` | 190 | See 3.1. |
| `compile-manuscript` | 159 | Promises Pandoc/Word/PDF/ePub; delivers one markdown file. "Normalizes scene breaks into standardized markers" — the target marker is never named. No TOC format. Output path includes `books/book-NN/`, which exists in no layout and is created by nothing. |
| `series-continuity` | 198 | Claims to audit "from Book 1 to Book N"; its procedure inspects "latest chapters of Book N-1 and opening chapters of Book N." Output name `Series_Continuity_Report.md` breaks the `Chapter-NNN_<Type>.md` convention every other writer uses. |
| `book-packaging` | 211 | No input step — never says what to read to write a blurb. Its sibling `social-media-marketing` has an explicit "Load Context" step *and* a fallback for missing files. Two output roots, one outside the layout. |
| `canon-guard` | 292 | "Unlock the single target file" has no mechanism — no lock file, no marker, no read-only contract in `fiction-writechapter`/`fiction-revise`. The guarantee is asserted here and unenforced there. Names `Wiki/Story/timeline.md`, which no skill creates and the layout doesn't declare. |
| `book-status` → `gate-check` | 571 | `gate-check` is fine as a checklist but duplicates 5 of 7 `fiction-reviewchapter` pillars with no cross-reference. |

**Root cause is visible in the git history.** Nine of these shipped in a single bulk commit (`58491ec`) that added ~842 lines for 9 skills — roughly 30 lines each. One skill in that commit got real substance (a 338-line reference file); the rest got summaries. **A bulk-add commit is the wrong unit of work for this library**, because a skill's value here *is* its depth, and depth doesn't compress.

### 3.6 Also worth knowing, lower severity

- **`town-generator`'s documented sweep produces garbage — reproduced.** `town-generator:20` says "enumerate every `data/*.txt` file." But `data/spanish-prefixes.txt` is a weighted prefix table with comment lines and a TAB-separated weight column, and `generate.py:46-50` reads every non-blank line verbatim. Running the skill's own command:
  ```
  $ python3 scripts/generate.py --list data/spanish-prefixes.txt --count 3 --min-len 4 --max-len 14 --order 2
  Peña	2
  San	3
  Fuertorra	8
  ```
  The weights are being emitted as part of the name. The worked example in `town-generator:44-45` has the same bug plus invented data: the rule "use the data filename without `.txt`" yields the heading "English" from `english.txt`, not "Anglo-Saxon," and three of the six sample names appear in no corpus. `name-generator:30-31` has a parallel problem — `Coyotl`, `Xiuhtla`, `Huitzin` are in no corpus file — and its corpus filenames produce headings like "Japanese-female" as a *culture* heading.
- **`drift-check` doesn't strip LitRPG system callouts; `burstiness-check` does.** `USER.md:88` claims "the burstiness diagnostic and prose linters automatically recognize and ignore these blocks so stat sheets never false-flag." `measure.py:44-49` strips `>` callouts and code fences. `drift.py:83` strips only `#` headings. So `> [!SYSTEM]` stat boxes are counted as prose by the book-level diagnostic — inflating word counts, opener clustering, and pet-word rates on exactly the books the claim protects.
- **Six paths live outside the declared layout.** `books/book-NN/` (`compile-manuscript:29`, `reader-persona-review:99`), `docs/` (`book-packaging:33`), `Wiki/Marketing/` (`social-media-marketing` ×6 — `new-book.sh` never creates it), `Wiki/Story/timeline.md` (`canon-guard:12`), `Wiki/Story/Book-N/packaging.md` (a slot the layout reserves for synopsis/plans/ledger).
- **`_Intake/` is over-promised.** The docs say the planning skills ingest intake so they don't "interrogate you cold." **Three of 73 skills read it** — `fiction-genre`, `fiction-synopsis`, `book-reverse-engineer`. `fiction-world` is specifically named in `USER.md:22` as one of the skills that reads it; it doesn't. So an author who invests an hour filling in `series-brief.md` gets it used by two skills.
- **The per-book synopsis has no producer.** `fiction-outline:21` says `**/Wiki/Story/Book-N/synopsis.md` is *required*. But `fiction-synopsis` only writes the series-level `Wiki/Story/synopsis.md` (`fiction-synopsis:13`). For Book 2 onward, `fiction-series-outline` and `fiction-outline` both read a file nothing writes.
- **"Revision plans" are in the layout with no writer.** `AGENTS.md:16` reserves `Wiki/Story/Book-N/` for "book synopsis, revision plans, `promises.yaml`." Nothing produces a revision plan. There's a gap between "review found problems" and "re-draft the chapter" — no skill plans a book-level re-plan.
- **Rule-sets are duplicated for the fiction kill passes.** `DEVELOPER.md:137` says rule-sets live in `references/`, and `kill-chapter` says its seven `references/*.md` are the single source. But the seven individual fiction `kill-*` skills keep their rules **inline in `SKILL.md`** — two sources of truth per rule-set. It has already drifted: `kill-chapter:37` lists 6 crutch tokens; `kill-chapter/references/crutch.md:3-4` lists 10.
- **The layer-isolation promise isn't met by the layer files.** `fiction-line-editor/references/agent-instructions.md:17` contains a section titled `### 3. AIisms` — the layer `fiction-aiism-editor` exists to own. `fiction-full-editor`'s dedup step ("if the same line is flagged across multiple criteria, merge") exists precisely because the layers collide.
- **`drift-check` and `burstiness-check` measure the same things** (opener concentration, lexical repetition) and neither names the other.

---

## 4. Recommendations

### Tier 0 — Trust (do these first; each one is currently losing or hiding work)

| # | Action | Effort | Why first |
|---|---|---|---|
| **0.1** | **Fix `chapter-pipeline` so the loop can complete.** Run `fiction-promises` before the gate; route the polish step through `fiction-revise` (or use `kill-chapter`, which does edit in place); correct the scene-file glob to `Chapter_NN_Scene.md`; define "major" and "minor WARN". | S | The pipeline skill is the library's proof of concept. |
| **0.2** | **Reconcile producer/consumer paths** (table in 3.2). Convert `levelup`/`fragment-hunter` to `Chapter-NNN_<Type>.md`; make `nonfiction-factcheck` glob `**/Research/**/*.{md,yaml}`; give the diagnostics a save step (or drop the `book-status` metric); give `_synthesis.md` a path; add `id` to the promise schema. | M | Each one is silent. A silently skipped fact-check is worse than a crash. |
| **0.3** | **One ledger, one owner.** Either merge `fiction-promises` into `promise-tracker` (keeping a thin fiction alias) or make them genuinely disjoint. Unify the parsers — one `chapter_number()` implementation, shared by both. Decide the hybrid case explicitly. | M | Two parsers disagreeing about overdue promises is a correctness bug, not a style issue. |
| **0.4** | **Add a tiebreaker to every fork** in `USER.md` and `AGENTS.md`, and make each pair cross-reference the other in its `description` (the router reads descriptions, not docs). Fix the reversed gate order at `AGENTS.md:139` vs `:181`. | S | Cheapest possible fix to the "I can't predict what ran" problem. |
| **0.5** | **Fix the doc facts.** `USER.md:119` (nonfiction dev editor exists); `USER.md:93` ("nine skills" — there are ten in the workflow); `DEVELOPER.md:274-280` (the reconciliation record says eight non-fiction skills are unbuilt; two of them were built); `USER.md:104` vs `:129` (review-panel's non-fiction status); `AGENTS.md:38` (missing `Wiki/Review/Book-N/`). | XS | These are minutes of work and they are the *first* thing a new user hits. |

### Tier 1 — Depth (make the glue load-bearing)

| # | Action | Effort | Notes |
|---|---|---|---|
| **1.1** | **Rewrite the 10 sub-300-word skills properly.** Use `fiction-reviewchapter` or `fantasy-settlement` as the template: explicit inputs, numbered steps, defined output path, report format, error handling, and a next step at the end. **One skill per commit** — do not repeat the bulk-add pattern. | L | This is the single biggest quality-per-effort win in the package. |
| **1.2** | **Give every skill an explicit output contract**: path, filename pattern, file schema. Make it machine-checkable. | M | Half of every finding in 3.2 and 3.5 is a missing output contract. |
| **1.3** | **Collapse the six paths that live outside the layout** into `Wiki/` and `_Edits/`, or add them to the layout and create them in `new-book.sh`. | S | `Wiki/Marketing/` in particular is created by no one. |
| **1.4** | **Make `_Intake/` real or stop promising it.** Either wire intake into the skills that plausibly need it (`fiction-characters`, `fiction-world`, `fiction-outline`, `fiction-theme`), or narrow the docs to the three that do. | M | Right now the author is promised a hand-off that mostly doesn't happen. |
| **1.5** | **Fill the two workflow holes:** a per-book synopsis producer (or relax `fiction-outline`'s "required"), and a revision-plan skill. | M | Book 2+ currently has a required input with no producer. |
| **1.6** | **Normalize rule-set ownership.** Move the seven fiction kill passes' rules into `references/` and have `kill-chapter` and the individual pass read the *same* file. | M | Currently two sources of truth per rule-set, already drifted. |

### Tier 2 — Product capability (the bigger investments)

| # | Action | Effort | Notes |
|---|---|---|---|
| **2.1** | **Build a behavioral eval harness.** This is the highest-leverage thing on this list. The library measures *prose* (`drift-check`, `burstiness-check`, `pangram`) but never measures *itself*. Add a fixture corpus — a few deliberately-bad chapters with known defects (a planted Chekhov violation, a broken POV, a stat-math error, a paragraph of AI-tells) — and assert that the right skill flags the right thing. Then a `make eval` target in the same gate. | L | Right now `make check` can be green on a library that produces nothing useful. This closes the gap the whole report is about. |
| **2.2** | **Prove the pipeline end to end on a real chapter.** Once, manually: scaffold → plan → draft → gate → revise → export, with a human in the loop at each step, and write down every place the agent stalled. That list is the real backlog. | M | 2.1 can't be built without this. Do it before 2.1. |
| **2.3** | **Make `compile-manuscript` actually export.** A real script: ordered concat, front matter, TOC, scene-break standardization to a *named* marker, and a clean reader-facing variant with a defined "what counts as an internal craft comment" list. | M | Publishing is the end of the value chain and it's currently a 159-word promise. |
| **2.4** | **Make the routing cost visible.** All 73 descriptions total ~24.5k characters (~6k tokens) that a host loads to choose one skill. Publish that number, and either trim descriptions or accept it consciously. Consider a short "common paths" file a host can read instead of the full catalog. | M | Real context cost, invisible today. |
| **2.5** | **Publish a cost/time model.** A 73-skill, worker-fanning, book-level workflow has a real token cost and wall-clock cost per chapter. Nothing in the library lets a user predict it. For a product, "what will this book cost me" is a legitimate first question. | M | |
| **2.6** | **Design a golden path.** One explicitly-scoped path (idea → outline → 3 chapters → gate) with a time estimate, as a first-run experience separate from the full catalog. | M | A new user currently meets 73 skills and a 2,300-word AGENTS.md at the same time. |

### Tier 3 — Scope decisions (explicit, so they stop being open questions)

| # | Decision | Notes |
|---|---|---|
| **3.1** | **Retire or productize `sync-check.sh`.** Upstream is a ZIP with no changelog, and the fork has been independent for nine days and 20 commits. The manifest is now larger than the delta it tracks. Either run it on a schedule and treat its output as a quarterly review, or delete it and say so in the README. | Maintenance cost with near-zero return now. |
| **3.2** | **Decide the non-fiction scope.** The non-fiction side is ~1/5 the depth of the fiction side: `nonfiction-dev-editor` and `nonfiction-research` are the two thinnest skills in the library, and `nonfiction-factcheck` can't see `sources.yaml`. Either fund non-fiction to parity or scope the library to fiction and say so plainly. Half-built is the worst of the three options. | |
| **3.3** | **Add a multi-project library dashboard.** `update-project.sh` exists, but projects drift silently — there's no "which of my four book projects are three library versions behind" view. Cheap to build on the existing `.storycraft-source` pin. | |
| **3.4** | **Add a human-beta-reader workflow.** The persona panels simulate readers well. Nothing supports the actual loop of sending a chapter to a human and folding the response back in — arguably the highest-signal feedback available to an author. | |
| **3.5** | **Record which skills actually get used.** Eight days of development produced no usage data. A one-line counter or a post-session log in `active-context.md` would tell you which skills earn their place and which are dead weight. | |

---

## 5. Explicitly *not* recommended

- **Do not add more skills.** 73 is already at the edge of what an agent can route. The gaps found here are *depth and wiring* problems, not coverage problems. Every added skill worsens 2.4 and 3.4.
- **Do not restructure the folder layout.** `Wiki/` / `Chapters/Book-N/` / `_Edits/Book-N/` is good, and the per-book slot discipline is the library's spine. Fix the six outliers; don't move the spine.
- **Do not soften the diagnostics' contract.** "Diagnostics never edit" is load-bearing for the routing tree. If `drift-check` starts editing, the tree collapses.
- **Do not add a second review layer to `make check`.** Extend the existing linter with the new invariants (output paths, schema shapes, fork tiebreakers) instead of adding a second tool that can drift.

---

## 6. Risks if nothing changes

| Risk | Likelihood | Impact |
|---|---|---|
| A book stalls mid-pipeline and the author can't tell whether it's the agent, the skill, or the gate | High | High — this is the core experience |
| Canon drifts silently because a fact-check or promise audit never ran | Medium | High — silently wrong output is the worst outcome |
| The author discovers the library's own docs are wrong (they are, in ~6 places) and stops trusting them | High | Medium |
| The pinned copy in existing projects drifts further behind with no upgrade path | High | Medium |
| A cleanup pass damages working skills | Medium | High — 58k words of procedure, high regression surface |

---

## 7. Bottom line

This package is further along than most, and the gap between it and finished is **not** a feature gap. It's three things, in order:

1. **Make the pipeline provably runnable end to end** — Tier 0 plus 2.2. One skill, one real chapter, every step verified.
2. **Give every skill an output contract and every fork a tiebreaker** — Tier 0.2, 0.4, 1.2. This is the boring work that makes the difference between "the agent did something" and "the agent did the right thing."
3. **Measure the library itself** — Tier 2.1. A golden corpus and an eval target, so the next 20 commits are checked against output quality rather than file shape.

The toolchain already knows how to make a rule permanent — it did it for frontmatter, paths, and doc drift. The same treatment applied to output contracts, fork tiebreakers, and end-to-end behavior would close most of this report.
