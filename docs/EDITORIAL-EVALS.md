# Editorial preservation evaluations

Run `make eval-editorial` to emit 36 neutral packets under /tmp/storycraft-editorial-packets (32 short `calibration` cases plus 4 multi-paragraph `held_out` scene/chapter cases; filter with `--split calibration|held_out`). Cases contain paired protected choices and real defects spanning fragments, repetition, metaphor, dialect, quiet endings, interiority, POV, numeric assertions, knowledge, negation, sensory detail, silence, subtext-unsaid, dialogue-interview, micro-friction, relationship-checkpoint fidelity, and multi-paragraph chapter-interaction cases. `cases.json` records `category_tolerances`, and `--results` scoring reports per-category rates alongside `tolerance_failures`. The three-chapter synthetic book exercises interaction and ordered reading; it is a short integration fixture, not a substitute for chapter-length author-selected examples.

Labels are provisional until author review. Candidate contexts receive source/rules/skill instructions, never labels or protected-span answers. Use tools/eval-editorial.py --packets DIR --baseline-ref COMMIT for an earlier skill revision; use the same cases, model/host configuration, and preselected repeat count for candidate and baseline. Keep held-out cases out of skill-tuning examples. Do not claim improvement from a single model run or a test that copies expected labels into output.

Recorded strict results use opaque IDs and a frozen run manifest (including the private mapping hash, expected coordinates, positive repeat count, variants, packet/source/configuration/skill hashes, permissions, and permitted context). Keep the private map produced beside the packet directory outside candidate-visible files; score with `python3 tools/eval-editorial.py --results FILE --mapping PRIVATE_MAP.json`. Candidate findings never carry author ratings or semantic-repair judgments. Record attributed author judgments separately in `human_judgments` and evaluator judgments in `semantic_judgments`, bound to the exact run, selected output, attempt, and rubric. Missing judgments remain pending. Complete execution coverage alone never makes a study release-eligible; predeclared release conditions and required author-judgment coverage must also pass.

The deterministic CI gate validates runtime behavior, scope and evidence mechanics. Literary evaluation requires a blind author comparison with candidate identities hidden where practical. Author-selected full chapters and category tolerances should be fixed after the pilot, before candidate comparison. Preserve and explain every regression. Model assistance may organize findings but cannot impersonate the author's decisions.

Release execution requirements: no unsupported source quotations, no edits outside authorized scope, and no future-only content in blind-reader packets. Passing those checks does not establish prose superiority. The repository ships the evaluation tool and provisional corpus; a validated author-scored baseline/candidate study remains an explicit human evaluation step.

## Evidence-chain prose regressions

Run `python3 tools/eval-evidence-chain.py RUN_DIR` from the library to emit two neutral packets from seven pairs of unannotated excerpts. Use a fresh review worker for each packet and pass only its contents. Each worker sees one variant of each pair. Keep the private answers outside the review context. Score the two JSON results with `python3 tools/eval-evidence-chain.py RUN_DIR --results REVIEW1.json REVIEW2.json`. The scorer checks coverage, classifications and exact source citations. Re-run from a separate directory after changing the rules to keep the baseline frozen.

The November 15 pilot scored 14 of 14 before and after the changes, with zero unsupported citations in either pass. These short cases were reviewed in isolation with synthetic source material. The paired runtime tests in `make check` exercise the evidence records, revision checks, and release behavior. The pilot measures performance on this specific set of excerpts.


## Private full-chapter study

Keep private pilot material outside the library checkout. Choose three full chapters that cover a quiet ending, a viewpoint handoff, and a deliberate voice choice. Edit the annotations before comparing versions. The corpus JSON has a cases array. Each case supplies id, category, source_file relative to the corpus file, rules, protected_spans, and defect_spans. Use exact strings for unique passages, or give start, end, and quote for a repeated passage. Offsets count Unicode code points. Keep a separate configuration file with host and the exact model. The built-in live runner accepts host codex. Use a model name for repeatable runs or default to exercise the local CLI's selection.

The following commands use variables for paths in a private directory. Set BASELINE and CANDIDATE to the exact Git revisions you want to compare.

```bash
python3 tools/eval-editorial.py --corpus "$CORPUS" --packets "$PACKETS" \
  --baseline-ref "$BASELINE" --candidate-ref "$CANDIDATE" \
  --configuration "$CONFIGURATION" --repeats 2

python3 tools/eval-editorial.py --run-study "$STUDY" --packets "$PACKETS" \
  --output-results "$RESULTS"

python3 tools/eval-editorial.py --corpus "$CORPUS" --results "$RESULTS" \
  --mapping "$PRIVATE_MAP" --blind-review "$BLIND" --blind-review-html "$BLIND_HTML"
```

The first command prints the frozen study manifest and private map paths. Give the model just the assigned packet. The live runner (`--run-study`) dispatches across `codex`, `claude`, `gemini`, `ollama`, and `openai_compatible` endpoints (set `"host": "ollama"` or `"openai_compatible"` with `"endpoint": "http://localhost:11434/v1/chat/completions"` and optional `"api_key_env"` in your configuration JSON). An interrupted run can resume from its results file. For external hosts, record results against the same frozen manifest and packet hashes. Choose a host authorized to receive the chapters before starting a live run.

Give the author the blind review file or open the self-contained HTML scorecard (`--blind-review-html`, which saves progress in `localStorage` and downloads `ratings.json` directly). Save ratings as JSON with evaluator_id and a ratings array. Each rating has a review_id, dimension, accepted boolean, and reason. Rate useful_repair and voice_preserved for each output. In the useful_repair rating, list the one-based finding numbers you would keep in kept_findings. An explicit empty list records a review with zero repairs selected. Run the scoring command again with `--author-scores "$RATINGS"` in place of `--blind-review "$BLIND"`. It reports defects caught, proposals touching protected spans, and author-accepted repairs by version. The pilot's human ratings are still pending until the author supplies them.

## Skill routing in Codex

`make eval-routing` runs six ordinary-language requests in disposable scaffolded books using the installed Codex CLI. It checks tool evidence for the skill read or invoked and compares actual chapter, report, and intake files. A host may replay recorded observations through `tools/eval-routing.py --score FILE`. The offline fixture and scorer check runs with `make check`. Use `ROUTING_ARGS='--case opening --output /tmp/storycraft-routing.json'` to run and record one live case. Default live runs use the host's selected model.

The November 17 verification used Codex CLI 0.169.0 on synthetic books. All six routing cases passed. Both review phrasings left chapter prose unchanged. The cleanup kept the closing image and the numbered-edit case applied exactly the two selected fixes. The opening trial wrote its intake sample, and beta intake anchored a note and wrote its feedback record. A synthetic matched editorial run completed four recorded attempts with identical baseline and candidate revisions to verify the runner. The private author's comparison remains pending.

## Novel planning and review examples

The 16 cases in eight pairs in [the novel planning corpus](../tools/eval-fixtures/novel-planning/cases.json) exercise premise scale, plot and theme, secondary character choices, alternate forms, quiet endings, and direct dialogue. The funeral-kitchen pair uses the same closing paragraph twice. Only the preceding scene changes, so the reviewer must decide whether washing the bowl earns the reconciliation or repeats it. Use the normal preservation runner with the relevant skill. Labels are provisional until author review.

```sh
python3 -B tools/eval-editorial.py --corpus tools/eval-fixtures/novel-planning/cases.json --skill fiction-reviewchapter --packets /tmp/storycraft-novel-review
```

## Blind comparison of generated fiction

Use the drafting study to compare an opening, a consequential middle choice, and a payoff written from the same brief. The default brief is synthetic. Each sample runs in its own disposable project with its frozen package, model, reasoning effort, and per-excerpt word budget. Use a fresh directory for each independent pair.

```sh
python3 -B tools/eval-drafting.py prepare dist/novel-study --baseline HEAD --candidate WORKTREE --model gpt-6.2-astra
python3 -B tools/eval-drafting.py run dist/novel-study
```

Use two Git revisions for a release comparison. The optional `WORKTREE` candidate freezes the current source, including new skill files. Supply `--brief` to use a different text, and use `--min-words` and `--max-words` to adjust the shared range. A retry reuses a completed, verified sample. A sample outside the agreed budget must be regenerated before the reader packet can be produced.

Share only the `readers/` folder. Ask each reader to save their own copy of `blank-ballot.json`, enter a reader name or pseudonym, and record their choice (`A`, `B`, `both`, or `neither`) and their reasons. The study asks which version they would keep reading, which choice felt particular to a character, and which earlier detail gained meaning at the end. Unblind after collecting the ballots.

```sh
python3 -B tools/eval-drafting.py score dist/novel-study path/to/reader-one.json path/to/reader-two.json
```

The response report attributes each judgment to its reader and the specific pair they read. A pair can inform a revision decision. A claim about a whole genre or about sustained novel quality requires broader reading.
