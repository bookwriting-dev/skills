# State records and shared runtime

The portable contract ships at [state-contract.md](../skills/book-status/references/state-contract.md), alongside [project_state.py](../skills/book-status/scripts/project_state.py). It defines review preparation/finalization, freshness, finding dispositions, pipeline journals, editorial decisions, knowledge, ordered readers, revision campaigns, and pre-draft context/cooling packets (`draft-packet`). Use `python3 skills/book-status/scripts/project_state.py --help` for commands; put global --root/--book options before the command.

[Book continuity review](../skills/book-status/references/continuity-review.md) defines the evidence format and commands for chapter heading and POV checks and whole-book reconciliation.

Report verdict and freshness are independent. CURRENT evidence establishes which inputs were checked, not literary correctness. Legacy reports are UNKNOWN. Directory inventory changes and expected missing inputs participate in invalidation. All writes remain within the resolved project root. There is no network or provider API dependency.

The runtime is an explicit bundled dependency, declared as metadata.bundled-dependencies in consuming skills and checked by lint. Full scaffolded libraries contain it. Individually copied skills without that dependency must report incomplete installation and UNKNOWN evidence. All new records use JSON schema_version 1; existing promise YAML remains owned by the existing ledger skills.

The ChatGPT desktop and Claude Code plugins record the release version and a `plugin-skill` input for the review skill, shared runtime and declared bundled dependencies. Both builders hash the same files using the original desktop release's rendering before substituting host-specific command paths. Either host can check or finalize the saved evidence from the other. A change to a captured input makes the review stale. Version-only updates and moving the install preserve freshness.

Example saved-review lifecycle (prefer the ergonomic `review-begin` / `review-finish` commands, or use raw `--spec` files via `prepare` / `snapshot`):

1. Run `project_state.py --root ROOT --book Book-1 review-begin --chapter 1 --type Gate` to capture the chapter, predecessor, plan, style and review guides, ledgers, project rules, and review skill. Keep the `prepared` path returned by this call. Every begin creates a separate manifest under `_Edits/Book-1/review-captures/`.
2. Read and review those captured inputs. Persist a normal Markdown report at `_Edits/Book-1/Chapter-001_Gate.md` with stable finding IDs and exact quotes.
3. Pass the `prepared` path from step 1 as `CAPTURE` to `project_state.py --root ROOT --book Book-1 review-finish --prepared CAPTURE --verdict PASS`. It verifies the inputs, hashes the report, and writes `_Edits/Book-1/Chapter-001_Gate.meta.json`. Record a blocking finding with `--finding '{"id":"G1","blocking":true}'`.
4. `project_state.py --root ROOT --book Book-1 record-disposition --report _Edits/Book-1/Chapter-001_Gate.md --finding-id G1 --disposition applied --reason "Fixed"` records finding dispositions without hand-writing a JSON spec.
5. `step-start` / `step-complete` wrap schema-v2 `pipeline` journal steps with automatic subject hashing and `before`/`after` transformation lineage.
6. `project_state.py --root ROOT check --meta _Edits/Book-1/Chapter-001_Gate.meta.json`.
7. `project_state.py --root ROOT dashboard` returns check freshness, unresolved blocking finding IDs, and campaign state. Use `dashboard --view compact` for counts, the first affected chapter in reading order, campaign blockers, and personal read-through counts. Add `--chapter SELECTOR` for that chapter’s checks.

Input evidence must be collected before substantive review; retroactively wrapping an old review with today's hashes is invalid. Unsupported schemas are rejected, preserving files. Exclusive lock conflicts fail rather than overwriting another writer. Inspect a lock owner's PID and pending files before removing an abandoned lock.
