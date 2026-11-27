"""Read the authoritative promise ledger and match references to manuscript reading order."""
from collections import defaultdict
from pathlib import Path
import re

import ledger_store
from state_projections import promise_entries


LEGACY_CHAPTER = re.compile(r'(?:(?:ch(?:apter)?|sec(?:tion)?)[ .#-]*)?(\d+)(?:\.\d+)*', re.I)


def read_entries(root, logical):
    try:
        raw = ledger_store.load_ledger_bytes(root, logical)
    except (ValueError, OSError):
        return 'unreadable', None
    if raw is None:
        return 'missing', None
    entries = promise_entries(raw)
    if entries is None:
        return 'unreadable', None
    return 'available', [item for item in entries if str(item.get('promise') or '').strip()]


class PromiseChapters:
    def __init__(self, book):
        self.conventional = book.get('chapter_order') == 'conventional'
        self.records = {row['reading_order']: row for row in book['chapters']}
        self.exact = defaultdict(set)
        self.numbered = defaultdict(set)
        for order, row in self.records.items():
            for alias in (row['id'], row.get('display_label'), row['path'], Path(row['path']).stem):
                if alias:
                    self.exact[alias].add(order)
            label = LEGACY_CHAPTER.fullmatch(str(row.get('display_label', '')))
            if label:
                self.numbered[int(label[1])].add(order)

    def position(self, reference):
        value = str(reference).strip() if reference is not None else ''
        matches = self.exact.get(value)
        if matches is None:
            numeric = LEGACY_CHAPTER.fullmatch(value)
            if numeric is None:
                return None
            number = int(numeric[1])
            matches = self.numbered.get(number)
            if matches is None:
                # Consecutive, numbered projects may owe a payoff beyond the registered chapters.
                return number if self.conventional and number > 0 else None
        return next(iter(matches)) if len(matches) == 1 else None

    def next_order(self, order):
        if order is None:
            return None
        if self.conventional:
            return order + 1
        return min((future for future in self.records if future > order), default=None)
