"""Collect payoff obligations visible at the selected chapter, with verified setup text."""
from promise_ledger import PromiseChapters, read_entries
from state_core import chapter_format_module, path_at, reader_text_module
from state_projections import NON_LIFECYCLE_STATUSES


def promise_context(root, book, chapter):
    label = book.get('display_label', book['id'])
    logical = f'Wiki/Story/{label}/promises.yaml'
    status, entries = read_entries(root, logical)
    result = {'path': logical, 'status': status, 'items': [], 'unresolved': []}
    if status == 'unreadable':
        result['reason'] = 'Check the ledger YAML, promises array, and availability of PyYAML.'
    if entries is None:
        return result

    source_texts = {}
    scene_break = book.get('chapter_format', {}).get('scene_break', '* * *')
    chapters = PromiseChapters(book)
    current = chapter['reading_order']
    next_order = chapters.next_order(current)

    for entry in entries:
        name = str(entry.get('promise') or '').strip()
        disposition = str(entry.get('status') or '').strip().lower()
        if not name or entry.get('deferred_to_series') or disposition in NON_LIFECYCLE_STATUSES:
            continue
        start = chapters.position(entry.get('introduced_ch'))
        due = chapters.position(entry.get('payoff_by_ch'))
        paid = chapters.position(entry.get('paid_in_ch'))
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
        if start in chapters.records:
            path = chapters.records[start]['path']
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
