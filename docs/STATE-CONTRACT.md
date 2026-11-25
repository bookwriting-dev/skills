# State records and shared runtime

The portable contract ships at [state-contract.md](../skills/book-status/references/state-contract.md), alongside [project_state.py](../skills/book-status/scripts/project_state.py). It defines review preparation/finalization, freshness, finding dispositions, pipeline journals, editorial decisions, knowledge, ordered readers, revision campaigns, and pre-draft context/cooling packets (`draft-packet`). Use `python3 skills/book-status/scripts/project_state.py --help` for commands; put global --root/--book options before the command.

[Book continuity review](../skills/book-status/references/continuity-review.md) defines the evidence format and commands for chapter heading and POV checks and whole-book reconciliation.

Report verdict and freshness are independent. CURRENT evidence establishes which inputs were checked, not literary correctness. Legacy reports are UNKNOWN. Directory inventory changes and expected missing inputs participate in invalidation. All writes remain within the resolved project root. There is no network or provider API dependency.

The runtime is an explicit bundled dependency, declared as metadata.bundled-dependencies in consuming skills and checked by lint. Full scaffolded libraries contain it. Individually copied skills without that dependency must report incomplete installation and UNKNOWN evidence. All new records use JSON schema_version 1; existing promise YAML remains owned by the existing ledger skills.

Example saved-review lifecycle (prefer the ergonomic `review-begin` / `review-finish` commands, or use raw `--spec` files via `prepare` / `snapshot`):

1. `project_state.py --root ROOT --book Book-1 review-begin --chapter 1 --type Gate` (auto-resolves chapter, predecessor, plan, style/review guides, ledgers, `AGENTS.md`, and skill dir into `_Edits/Book-1/Chapter-001_Gate.prepared.json`).
2. Read and review those captured inputs. Persist a normal Markdown report at `_Edits/Book-1/Chapter-001_Gate.md` with stable finding IDs and exact quotes.
3. `project_state.py --root ROOT --book Book-1 review-finish --prepared _Edits/Book-1/Chapter-001_Gate.prepared.json --verdict PASS` (optionally passing `--finding '{"id":"G1","blocking":true}'`) verifies inputs did not drift, hashes the report, and writes `_Edits/Book-1/Chapter-001_Gate.meta.json`.
4. `project_state.py --root ROOT --book Book-1 record-disposition --report _Edits/Book-1/Chapter-001_Gate.md --finding-id G1 --disposition applied --reason "Fixed"` records finding dispositions without hand-writing a JSON spec.
5. `step-start` / `step-complete` wrap schema-v2 `pipeline` journal steps with automatic subject hashing and `before`/`after` transformation lineage.
6. `project_state.py --root ROOT check --meta _Edits/Book-1/Chapter-001_Gate.meta.json`.
7. `project_state.py --root ROOT dashboard` returns check freshness, unresolved blocking finding IDs, and campaign state. The agent renders board/status views from this evidence and configured completion requirements.

Input evidence must be collected before substantive review; retroactively wrapping an old review with today's hashes is invalid. Unsupported schemas are rejected, preserving files. Exclusive lock conflicts fail rather than overwriting another writer. Inspect a lock owner's PID and pending files before removing an abandoned lock.
