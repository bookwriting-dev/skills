---
name: fiction-promises
description: "Track and audit the fiction Chekhov ledger at Wiki/Story/Book-N/promises.yaml, reporting overdue, due, and undated setups. Use when checking promises, loose ends, unresolved setups, 'chekhov', or closing a book. Runs with fiction-reviewchapter; non-fiction and hybrid projects use promise-tracker instead."
metadata:
  author: Fiction Toolkit
  version: "1.4.1"
  category: fiction-writing
  output-format: yaml
---

# Fiction Promises — the Chekhov ledger

Readers keep score whether or not the author does. A locked drawer mentioned twice in
chapter three is a debt. So is a skill a character mentions offhand, a question nobody
answers, a name dropped once with weight. Unpaid setups are the most common structural
complaint in reviews of otherwise competent novels, and they are entirely preventable
with bookkeeping.

The ledger lives at `Wiki/Story/Book-N/promises.yaml`, one ledger per book. When `.storycraft/ledger-current.json` exists, the committed generation is authoritative for reads. Do not edit committed generations or a legacy mirror directly; route managed writes through the shared ledger transaction tool. A setup
deliberately withheld for a later book is marked `deferred_to_series: true` and must
appear in the inter-book promise map in `Wiki/Story/series-arc.md` (maintained by
`fiction-series-outline`) — an unpaid setup is not less unpaid for being someone else's
book.

Routing: fiction projects use this skill; non-fiction and hybrid projects use
`promise-tracker` — it carries both kind vocabularies and the `project_type` field.
The two skills share the same ledger format and equivalent `scripts/promises.py`, and
both edit the *same* `Wiki/Story/Book-N/promises.yaml`, so never run both on one book:
mixing them saves the ledger twice over.

## Step 1: Locate the book and the ledger

Identify the book from the user's request or from `**/Wiki/Story/active-context.md`.
The ledger path is `Wiki/Story/Book-N/promises.yaml` for that book.

If there is no ledger yet, copy [assets/promises.yaml](assets/promises.yaml) to
`Wiki/Story/Book-N/promises.yaml` (create the folder if missing) and delete the blank
scaffold entry. Tell the user a ledger was created. An existing `promises.yaml` is
always adopted as-is, never re-seeded — copying the starter over a live ledger would
erase the book's promise history.

For managed writes, stage the updated YAML and any related knowledge/relationship changes together in one transaction spec, include exact source evidence and the expected current generation, then commit with `.agents/skills/book-status/scripts/ledger_transaction.py --root ROOT --spec SPEC.json`. Inspect `--status` after conflicts; do not retry a stale proposal with a refreshed expected generation until changes have been reconciled against the new source.

## Step 2: Read the ledger and the chapter

Read the whole ledger, then read the chapter the user names (or the most recent chapter
per active context). Read the chapter as a reader, not as the author: the author knows
which details are load-bearing, and a reader does not. Anything given weight registers
as a promise.

## Step 3: Harvest new promises

Ask, as a reader: *what did this chapter tell me to remember?*

- An object introduced with more detail than the scene needs
- A question a character asks and nobody answers
- A skill, tool, or ability mentioned in passing
- A threat, a debt, a vow, a prophecy
- A stranger named with weight
- Any rule of the world demonstrated in a way that begs a later exception
- An explicit forward reference — "that was the last quiet morning," "before the
  harvest festival," "when we reach the capital." The text has gone on the record that
  this moment will matter; that is the loudest promise there is, and readers audit
  forward references with due dates in mind. Weight: `loud`. The `payoff_by_ch` should
  not be far off whatever deadline the text itself named.

Record each in the ledger with:

- **promise**: what the reader now expects, written from the reader's side — "the locked
  drawer in Elena's study", not "foreshadowing".
- **introduced_ch**: the chapter where it was made. When the setup has a distinctive passage, record its exact words in optional `setup_quote`. The draft packet resolves the chapter path and includes the quote only while it still matches the manuscript.
- **kind**: object | skill | threat | question | debt | relationship | mystery | prophecy | rule
- **weight**: how loudly the text made it — `whisper` (subordinate clause), `plain`
  (normal scene weight), `loud` (chapter title, climactic beat, repeated mention).
- **payoff_by_ch**: the chapter by which the reader will start to feel cheated.
  **Every promise needs one.** An undated promise is one nobody will remember to pay —
  that is what the ledger exists to prevent, and "undated" is the bucket that quietly
  grows all book. If the honest answer is "not this book", set `deferred_to_series: true`
  and add it to the series promise map instead of leaving it undated.

## Step 4: Record payoffs

For anything paid in this chapter, fill in `paid_in_ch` and `paid_how`. Both fields or
neither: a payoff recorded without saying how tends to mean a mention rather than a
payoff.

A payoff has to be **on the page**. A gun that goes off in the author's head between
chapters is still loaded.

## Step 5: Run the ledger report

With the host's Python interpreter:

```
python3 <skill-dir>/scripts/promises.py --chapter chNN
```

It walks up from the working directory to find `Wiki/`, picks the ledger (pass
`--book Book-N` when several books keep ledgers), and buckets every promise: paid,
overdue, due this chapter, due next chapter, undated, open, deferred. If Python or
PyYAML is unavailable, read `Wiki/Story/Book-N/promises.yaml` and bucket by hand — the
script is a convenience, not the skill.

## Step 6: Act on what's due

- **Overdue** → the reader is already owed this. Either pay it in the next chapter or
  deliberately re-plan the payoff and move the date, with a note in `notes` saying why.
  Silently moving a deadline is how a promise stays permanently eighteen chapters away.
- **Due this chapter or next** → the standard draft packet surfaces these in `promises.items` alongside overdue obligations and payoffs already on the target page. Read the setup passage when deciding how this scene can change its meaning. A payoff lands
  best when the reader has stopped consciously expecting it but the debt is still warm.
- **Undated** → date it now, or defer it to the series map now. Leaving it undated is
  how the bucket grows.
- **Deferred** → confirm each one actually appears in `Wiki/Story/series-arc.md`'s
  inter-book promise map. If `series-arc.md` does not exist, say so and suggest running
  `fiction-series-outline`.

## Before closing a book

Run the report with `--final` (exit status 1 when anything is unpaid and not deferred):

```
python3 <skill-dir>/scripts/promises.py --final
```

A book that ends with unpaid, undeferred promises is not finished — it is abandoned
mid-debt. Pay them, defer them to the series map, or decide with the user that the
setup stays a loose thread on purpose (record that ruling in `notes`).

Return: the bucketed report, a count of promises harvested and paid this session, and
any ledger edits made.
