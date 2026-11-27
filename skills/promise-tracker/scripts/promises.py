#!/usr/bin/env python3
"""Unified promise tracker: every setup the text makes, and whether it paid.

Tracks promises for both fiction and non-fiction. A "promise" is anything
the text tells the reader to remember (Chekhov's guns, unanswered questions,
thesis threads, promised counterarguments/definitions, "we'll return to this",
unresolved tensions, etc.).

    python3 scripts/promises.py                     whole ledger
    python3 scripts/promises.py --chapter ch12      due/overdue/paid here
    python3 scripts/promises.py --book Book-2       pick ledger explicitly
    python3 scripts/promises.py --final             gate finished book

Ledger lives at Wiki/Story/Book-N/promises.yaml; walks up from CWD to find Wiki/ or the committed ledger pointer.
Exit status 1 under --final if anything unpaid and not deferred.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True
SHARED_SCRIPTS = Path(__file__).resolve().parents[2] / 'book-status' / 'scripts'
if (SHARED_SCRIPTS / 'promise_ledger.py').is_file():
    sys.path.insert(0, str(SHARED_SCRIPTS))
    import ledger_store
    import project_manifest
    from promise_ledger import PromiseChapters, read_entries
else:
    ledger_store = None

try:
    import yaml
except ImportError:
    yaml = None

WEIGHTS = {"whisper": 0, "plain": 1, "loud": 2}
LEDGER_REL = Path("Wiki") / "Story"


def chapter_number(value) -> int | None:
    """'ch12' / 12 / 'Chapter 12' / 'sec2.1' -> the first integer in the text.

    The two ledger skills (fiction-promises, promise-tracker) ship identical
    copies of this function on purpose: they must agree on what 'sec2.1' means,
    or the same ledger reads as overdue in one skill's report and current in
    the other's. tools/compile-check.py asserts the copies agree — change both
    or neither.
    """
    if value is None:
        return None
    text = str(value).strip().lower()
    digits = ""
    for c in text:
        if c.isdigit():
            digits += c
        elif digits:
            break
    return int(digits) if digits else None


def project_root(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if ((candidate / 'Wiki').is_dir() or (candidate / '.storycraft/ledger-current.json').is_file()
                or (candidate / '.storycraft/project.json').is_file()):
            return candidate
    return None


def find_ledger(root: Path, book: str | None) -> tuple[Path | None, str | None]:
    if book:
        return root / LEDGER_REL / book / 'promises.yaml', None
    story = root / LEDGER_REL
    candidates = set(story.glob('*/promises.yaml'))
    if ledger_store is not None:
        pointer = ledger_store.current_pointer(root) or {}
        candidates.update(root / name for name in pointer.get('ledgers', {})
                          if Path(name).match('Wiki/Story/*/promises.yaml'))
    if not candidates:
        return None, 'no ledger found under Wiki/Story/Book-N/'
    if len(candidates) > 1:
        return None, 'several ledgers found; pass --book to pick one'
    return candidates.pop(), None


def load(ledger_path: Path) -> tuple[list[dict], str | None]:
    if yaml is None:
        return [], 'PyYAML not importable; cannot read ledger'
    path = ledger_path.resolve()
    root = project_root(path.parent)
    if root is not None and ledger_store is not None:
        status, entries = read_entries(root, path.relative_to(root).as_posix())
        if status == 'missing':
            return [], f'no ledger at {path}'
        if status == 'unreadable':
            return [], f'{path} could not be parsed or verified'
        return entries, None
    if root is not None and (root / '.storycraft/ledger-current.json').is_file():
        return [], 'committed ledger requires the book-status runtime'
    if not path.is_file():
        return [], f'no ledger at {path}'
    try:
        data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        entries = data['promises']
        if not isinstance(entries, list) or not all(isinstance(p, dict) for p in entries):
            raise ValueError('expected a promises array')
        return [p for p in entries if str(p.get('promise') or '').strip()], None
    except (ValueError, TypeError, KeyError, OSError, yaml.YAMLError) as exc:
        return [], f'{path} could not be parsed: {exc}'


def is_paid(promise: dict) -> bool:
    return bool(str(promise.get("paid_in_ch") or "").strip())


def is_deferred(promise: dict) -> bool:
    return bool(promise.get("deferred_to_series"))


def status(promise: dict, current: int | None, position=chapter_number, next_order=None) -> str:
    if is_paid(promise):
        return "paid"
    if is_deferred(promise):
        return "deferred"
    due = position(promise.get("payoff_by_ch"))
    if due is None:
        return "undated"
    if current is None:
        return "open"
    if due < current:
        return "overdue"
    if due == current:
        return "due"
    if due == (current + 1 if next_order is None else next_order):
        return "due soon"
    return "open"


def describe(promise: dict) -> str:
    ident = str(promise.get("id") or "?")
    text = str(promise.get("promise") or "").strip()
    kind = str(promise.get("kind") or "").strip()
    ptype = str(promise.get("project_type") or "").strip()

    def chref(value: object, fallback: str) -> str:
        t = str(value or "").strip()
        return t if t else fallback

    where = chref(promise.get("introduced_ch"), "unknown")
    due = chref(promise.get("payoff_by_ch"), "no deadline")
    weight = str(promise.get("weight") or "plain")
    tag = f"/{ptype}" if ptype else ""
    return (f"{ident} [{kind or 'promise'}{tag}/{weight}] {text[:80]}\n"
            f"       made {where} · owed by {due}")


def report(promises: list[dict], current: int | None, position=chapter_number, next_order=None) -> str:
    if not promises:
        return ("Promise tracker — empty.\n"
                "  Nothing tracked. Every setup creating reader expectation is currently\n"
                "  unbooked; harvest from the text to populate the ledger.")
    buckets: dict[str, list[dict]] = {}
    for promise in promises:
        buckets.setdefault(status(promise, current, position, next_order), []).append(promise)
    paid = len(buckets.get("paid", []))
    out = [f"Promise tracker — {len(promises)} promise(s), {paid} paid"]
    for key, label in (
        ("overdue", "OVERDUE — reader already owed this"),
        ("due", "DUE THIS UNIT"),
        ("due soon", "DUE SOON (next unit)"),
        ("undated", "NO DEADLINE — will be forgotten"),
        ("open", "OPEN"),
        ("deferred", "DEFERRED TO LATER VOLUME"),
    ):
        items = buckets.get(key) or []
        if not items:
            continue
        items.sort(key=lambda p: -WEIGHTS.get(str(p.get("weight")), 1))
        out.append(f"\n  {label} ({len(items)}):")
        out += [f"    {describe(p)}" for p in items]
    if buckets.get("deferred"):
        out.append("\n  Deferred promises must appear in the series/inter-book promise map\n"
                   "  (e.g. Wiki/Story/series-arc.md) if tracked there.")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--chapter", help="evaluate as of this unit (e.g. ch12, sec3.2)")
    parser.add_argument("--book", help="book folder name (default: only ledger found)")
    parser.add_argument("--ledger", type=Path, help="explicit path to promises.yaml")
    parser.add_argument("--final", action="store_true",
                        help="exit 1 if any promise unpaid and not deferred")
    args = parser.parse_args()

    start = args.ledger.resolve().parent if args.ledger else Path.cwd()
    root = project_root(start)
    book = args.book
    if root and book and ledger_store is not None:
        book = project_manifest.artifact_book_label(root, book)
    if args.ledger:
        ledger_path, problem = args.ledger.resolve(), None
    elif root is None:
        ledger_path, problem = None, 'no Storycraft project or Wiki/ found above working directory'
    else:
        ledger_path, problem = find_ledger(root, book)

    if problem:
        print(f"Promise tracker — {problem}.")
        raise SystemExit(0 if not args.final else 1)

    promises, problem = load(ledger_path)
    positions = None
    if not problem and root and ledger_store is not None:
        in_story = ledger_path.parent.parent == root / LEDGER_REL
        book_label = ledger_path.parent.name if in_story else book
        if book_label and project_manifest.find_book(project_manifest.load(root), book_label):
            positions = PromiseChapters(project_manifest.resolve_book(root, book_label))
    position = positions.position if positions else chapter_number
    current = position(args.chapter) if args.chapter else None
    next_order = positions.next_order(current) if positions else None

    if args.final:
        if problem:
            print(f"Promise tracker unavailable ({problem}) — cannot certify final.")
            raise SystemExit(1)
        outstanding = [p for p in promises if not is_paid(p) and not is_deferred(p)]
        if outstanding:
            print(f"{len(outstanding)} promise(s) unpaid — not finished:")
            for p in outstanding:
                print(f"  {describe(p)}")
            print("\nPay them, mark deferred_to_series true (with series map), or record ruling in notes.")
            raise SystemExit(1)
        print(f"All {len(promises)} promise(s) paid or deliberately deferred.")
        return

    if problem:
        print(f"Promise tracker — {problem}.")
        return
    print(report(promises, current, position, next_order))


if __name__ == "__main__":
    main()
