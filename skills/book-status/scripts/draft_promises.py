"""Collect payoff obligations visible at the selected chapter, with verified setup text."""
from collections import defaultdict
from pathlib import Path
import re

from state_core import chapter_format_module, ledger_store_module, path_at, reader_text_module
from state_projections import NON_LIFECYCLE_STATUSES, promise_entries


LEGACY_CHAPTER = re.compile(r'(?:(?:ch(?:apter)?|sec(?:tion)?)[ .#-]*)?(\d+)(?:\.\d+)*', re.I)


def promise_context(root, book, chapter):
    label = book.get('display_label', book['id'])
    logical = f'Wiki/Story/{label}/promises.yaml'
    result = {'path': logical, 'status': 'missing', 'items': [], 'unresolved': []}
    raw = ledger_store_module().load_ledger_bytes(root, logical)
    if raw is None:
        return result
    entries = promise_entries(raw)
    if entries is None:
        return dict(result, status='unreadable',
                    reason='Check the ledger YAML, promises array, and availability of PyYAML.')

    source_texts = {}
    scene_break = book.get('chapter_format', {}).get('scene_break', '* * *')
    result['status'] = 'available'
    chapters = {row['reading_order']: row for row in book['chapters']}
    current = chapter['reading_order']
    conventional = book.get('chapter_order') == 'conventional'
    next_order = current + 1 if conventional else min((order for order in chapters if order > current), default=None)
    exact = defaultdict(set)
    numbered = defaultdict(set)
    for order, row in chapters.items():
        for alias in (row['id'], row.get('display_label'), row['path'], Path(row['path']).stem):
            if alias:
                exact[alias].add(order)
        chapter_label = LEGACY_CHAPTER.fullmatch(str(row.get('display_label', '')))
        if chapter_label:
            numbered[int(chapter_label[1])].add(order)

    def position(reference):
        value = str(reference).strip() if reference is not None else ''
        matches = exact.get(value)
        if matches is None:
            numeric = LEGACY_CHAPTER.fullmatch(value)
            if numeric is None:
                return None
            number = int(numeric[1])
            matches = numbered.get(number)
            if matches is None:
                # A numbered book can owe a payoff in a chapter still to be registered.
                return number if conventional and number > 0 else None
        return next(iter(matches)) if len(matches) == 1 else None

    for entry in entries:
        name = str(entry.get('promise') or '').strip()
        disposition = str(entry.get('status') or '').strip().lower()
        if not name or entry.get('deferred_to_series') or disposition in NON_LIFECYCLE_STATUSES:
            continue
        start = position(entry.get('introduced_ch'))
        due = position(entry.get('payoff_by_ch'))
        paid = position(entry.get('paid_in_ch'))
        if (start is not None and start > current) or (paid is not None and paid < current):
            continue
        unknown = [field for field, order in (('introduced_ch', start), ('paid_in_ch', paid),
                                               ('payoff_by_ch', due))
                   if order is None and entry.get(field) not in (None, '')]
        if paid is None and disposition in ('paid', 'resolved') and 'paid_in_ch' not in unknown:
            unknown.append('paid_in_ch')
        if unknown:
            for field in unknown:
                result['unresolved'].append({'id': entry.get('id'), 'field': field, 'reference': entry.get(field)})
            # A verified payoff in the selected chapter stands even when its old due date is unresolved.
            if paid != current:
                continue
        if paid == current:
            status = 'paid_here'
        elif due is None:
            continue
        elif due < current:
            status = 'overdue'
        elif due == current:
            status = 'due'
        elif due == next_order:
            status = 'due_next'
        else:
            continue
        item = {key: entry[key] for key in ('id', 'kind', 'weight', 'introduced_ch', 'payoff_by_ch')
                if key in entry}
        item.update(promise=name, status=status)
        if start in chapters:
            path = chapters[start]['path']
            setup = {'path': path}
            quote = entry.get('setup_quote')
            if isinstance(quote, str) and quote.strip():
                if path not in source_texts:
                    source = path_at(root, path)
                    source_texts[path] = ''
                    if source.is_file():
                        content = source.read_text(encoding='utf-8')
                        try:
                            source_texts[path] = reader_text_module().extract(
                                content, source=path, scene_break=scene_break, strip_pov=True,
                                pov_comment_lines=chapter_format_module().comment_lines(content, scene_break)
                            )['text']
                        except ValueError:
                            # Unclassified markup cannot establish a reader-facing quotation.
                            pass
                if quote in source_texts[path]:
                    setup['quote'] = quote
                else:
                    setup['quote_status'] = 'unverified'
            item['setup'] = setup
        result['items'].append(item)
    return result
