#!/usr/bin/env python3
"""The Chekhov ledger: every setup the text has made, and whether it paid.

Readers keep score whether or not the author does. A locked drawer mentioned
twice in chapter three is a debt. So is a skill a character mentions offhand,
a question nobody answers, a name dropped once with weight. An unpaid setup
is the most common structural complaint in reviews of otherwise competent
novels.

    python3 scripts/promises.py                     the whole ledger
    python3 scripts/promises.py --chapter ch12      due, overdue, paid here
    python3 scripts/promises.py --book Book-2       pick a ledger explicitly
    python3 scripts/promises.py --final             gate a "finished" book

The ledger lives at Wiki/Story/Book-N/promises.yaml; the script walks up from
the working directory to find the project's Wiki/. Exit status is 1 under
--final when anything is unpaid, so a book cannot be called finished over a
debt.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

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


def find_wiki_root() -> Path | None:
    """Walk up from the working directory looking for a Wiki/ folder."""
    for candidate in (Path.cwd(), *Path.cwd().parents):
        if (candidate / "Wiki").is_dir():
            return candidate
    return None


def managed_ledger_paths(root: Path) -> set[str]:
    store_path = Path(__file__).parents[2] / 'book-status' / 'scripts' / 'ledger_store.py'
    if not store_path.is_file():
        return set()
    spec = importlib.util.spec_from_file_location('storycraft_promise_ledger_store', store_path)
    store = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(store)
    pointer = store.current_pointer(root)
    return set(pointer.get('ledgers', {})) if pointer else set()


def find_ledger(root: Path, book: str | None) -> tuple[Path | None, str | None]:
    story = root / LEDGER_REL
    managed = managed_ledger_paths(root)
    if book:
        path = story / book / "promises.yaml"
        logical = path.relative_to(root).as_posix()
        return (path, None) if path.exists() or logical in managed else (None, f"no ledger at {path}")
    candidates = sorted(set(story.glob("Book-*/promises.yaml")) |
                        {root / item for item in managed if item.startswith('Wiki/Story/Book-') and item.endswith('/promises.yaml')})
    if not candidates:
        return None, ("no ledger found under Wiki/Story/Book-N/ — copy the skill's "
                      "assets/promises.yaml there to start tracking setups")
    if len(candidates) > 1:
        names = ", ".join(str(c.parent.name) for c in candidates)
        return None, f"several ledgers found ({names}) — pass --book to pick one"
    return candidates[0], None


def load(ledger_path: Path) -> tuple[list[dict], str | None]:
    if yaml is None:
        return [], "PyYAML is not importable, so the ledger cannot be read"
    try:
        resolved = ledger_path.resolve()
        root = next((parent for parent in resolved.parents if (parent / 'Wiki').is_dir()), None)
        raw = None
        if root is not None:
            store_path = Path(__file__).parents[2] / 'book-status' / 'scripts' / 'ledger_store.py'
            if store_path.is_file():
                spec = importlib.util.spec_from_file_location('storycraft_promise_ledger_store', store_path)
                store = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(store)
                relative = resolved.relative_to(root).as_posix()
                raw = store.load_ledger_bytes(root, relative)
        data = yaml.safe_load(raw.decode('utf-8') if raw is not None else
                              ledger_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return [], f"{ledger_path} could not be parsed: {exc}"
    promises = [p for p in (data.get("promises") or []) if isinstance(p, dict)]
    # A template's blank scaffold entry is not a promise.
    return [p for p in promises if str(p.get("promise") or "").strip()], None


def is_paid(promise: dict) -> bool:
    return bool(str(promise.get("paid_in_ch") or "").strip())


def is_deferred(promise: dict) -> bool:
    return bool(promise.get("deferred_to_series"))


def status(promise: dict, current: int | None) -> str:
    if is_paid(promise):
        return "paid"
    if is_deferred(promise):
        return "deferred"
    due = chapter_number(promise.get("payoff_by_ch"))
    if due is None:
        return "undated"
    if current is None:
        return "open"
    if due < current:
        return "overdue"
    if due == current:
        return "due"
    if due - current <= 1:
        return "due soon"
    return "open"


def describe(promise: dict) -> str:
    ident = str(promise.get("id") or "?")
    text = str(promise.get("promise") or "").strip()
    kind = str(promise.get("kind") or "").strip()

    def chref(value: object, fallback: str) -> str:
        raw = str(value or "").strip()
        if not raw or not any(c.isdigit() for c in raw):
            return fallback
        if raw.lower().startswith(("ch", "sec")):
            return raw
        return f"ch{raw}"

    where = chref(promise.get("introduced_ch"), "chapter unknown")
    due = chref(promise.get("payoff_by_ch"), "no deadline")
    weight = str(promise.get("weight") or "plain")
    return (f"{ident} [{kind or 'promise'}/{weight}] {text[:72]}\n"
            f"       made {where} · owed by {due}")


def report(promises: list[dict], current: int | None) -> str:
    if not promises:
        return ("Chekhov ledger — empty.\n"
                "  Nothing is being tracked. Every setup the text makes is currently "
                "the reader's\n  job to remember and nobody's job to pay.")

    buckets: dict[str, list[dict]] = {}
    for promise in promises:
        buckets.setdefault(status(promise, current), []).append(promise)

    paid = len(buckets.get("paid", []))
    out = [f"Chekhov ledger — {len(promises)} promise(s), {paid} paid"]

    for key, label in (("overdue", "OVERDUE — the reader is already owed this"),
                       ("due", "DUE THIS CHAPTER"),
                       ("due soon", "DUE NEXT CHAPTER"),
                       ("undated", "NO DEADLINE — will be forgotten by whoever set it up"),
                       ("open", "OPEN"),
                       ("deferred", "DEFERRED TO A LATER BOOK")):
        items = buckets.get(key) or []
        if not items:
            continue
        items.sort(key=lambda p: -WEIGHTS.get(str(p.get("weight")), 1))
        out.append(f"\n  {label} ({len(items)}):")
        out += [f"    {describe(p)}" for p in items]

    if buckets.get("deferred"):
        out.append("\n  Deferred promises must be carried in Wiki/Story/series-arc.md's "
                   "inter-book\n  promise map (fiction-series-outline) — an unpaid setup "
                   "is not less unpaid\n  for being someone else's book.")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--chapter", help="evaluate as of this chapter (e.g. ch12)")
    parser.add_argument("--book", help="book folder name, e.g. Book-2 (default: the only ledger)")
    parser.add_argument("--ledger", type=Path, help="explicit path to a promises.yaml")
    parser.add_argument("--final", action="store_true",
                        help="exit 1 if any promise is unpaid (gates a finished book)")
    args = parser.parse_args()

    root = find_wiki_root()
    if args.ledger:
        ledger_path = args.ledger
        problem = None if ledger_path.exists() else f"no ledger at {ledger_path}"
    elif root is None:
        ledger_path, problem = None, "no Wiki/ found above the working directory"
    else:
        ledger_path, problem = find_ledger(root, args.book)

    if problem:
        print(f"Chekhov ledger — {problem}.")
        raise SystemExit(0 if not args.final else 1)

    promises, problem = load(ledger_path)
    current = chapter_number(args.chapter) if args.chapter else None

    if args.final:
        if problem:
            print(f"Chekhov ledger unavailable ({problem}) — cannot certify a final book.")
            raise SystemExit(1)
        outstanding = [p for p in promises if not is_paid(p) and not is_deferred(p)]
        if outstanding:
            print(f"{len(outstanding)} promise(s) unpaid — this is not a finished book:")
            for promise in outstanding:
                print(f"  {describe(promise)}")
            print("\nPay them, mark them deferred_to_series with the series promise map "
                  "carrying them,\nor record the deliberate ruling in notes.")
            raise SystemExit(1)
        print(f"All {len(promises)} promise(s) paid or deliberately deferred.")
        return

    if problem:
        print(f"Chekhov ledger — {problem}.")
        return
    print(report(promises, current))


if __name__ == "__main__":
    main()
