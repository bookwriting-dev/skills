# State records and shared runtime

The portable contract ships at [state-contract.md](../skills/book-status/references/state-contract.md), alongside [project_state.py](../skills/book-status/scripts/project_state.py). It defines review preparation/finalization, freshness, finding dispositions, pipeline journals, editorial decisions, knowledge, ordered readers, and revision campaigns. Use `python3 skills/book-status/scripts/project_state.py --help` for commands; put global --root/--book options before the command.

Report verdict and freshness are independent. CURRENT evidence establishes which inputs were checked, not literary correctness. Legacy reports are UNKNOWN. Directory inventory changes and expected missing inputs participate in invalidation. All writes remain within the resolved project root. There is no network or provider API dependency.

The runtime is an explicit bundled dependency, declared as metadata.bundled-dependencies in consuming skills and checked by lint. Full scaffolded libraries contain it. Individually copied skills without that dependency must report incomplete installation and UNKNOWN evidence. All new records use JSON schema_version 1; existing promise YAML remains owned by the existing ledger skills.

Example saved-review lifecycle:

1. Write a spec containing schema_version, report, verdict, and paths.
2. `project_state.py --root ROOT prepare --spec SPEC.json --output _Edits/Book-1/run-inputs.json`.
3. Read and review those inputs. Persist a normal Markdown report with stable finding IDs and exact quotes. Put any machine findings into the prepared spec as findings [{id, blocking, ...}].
4. Set final verdict in the prepared spec, preserving captured inputs.
5. `project_state.py --root ROOT snapshot --spec PREPARED.json --output _Edits/Book-1/Chapter-001_Gate.meta.json`.
6. `project_state.py --root ROOT check --meta _Edits/Book-1/Chapter-001_Gate.meta.json`.
7. `project_state.py --root ROOT dashboard` returns check freshness, unresolved blocking finding IDs, and campaign state. The agent renders board/status views from this evidence and configured completion requirements.

Input evidence must be collected before substantive review; retroactively wrapping an old review with today's hashes is invalid. Unsupported schemas are rejected, preserving files. Exclusive lock conflicts fail rather than overwriting another writer. Inspect a lock owner's PID and pending files before removing an abandoned lock.
