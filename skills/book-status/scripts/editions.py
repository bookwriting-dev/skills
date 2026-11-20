"""Immutable reader editions and cross-edition comparisons. Offsets are Unicode code points."""
from collections import defaultdict
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def passages(text, marker):
    """Keep verse, headings and fenced examples intact. Scene delimiters are whole lines."""
    scenes, paragraphs = [], []
    start = None
    end = offset = 0
    fence = None

    def close_paragraph():
        nonlocal start
        if start is not None:
            paragraphs.append({'start': start, 'end': end, 'text': text[start:end]})
            start = None

    def close_scene():
        close_paragraph()
        if paragraphs:
            first, last = paragraphs[0]['start'], paragraphs[-1]['end']
            scenes.append({'start': first, 'end': last, 'sha256': digest(text[first:last]),
                           'paragraphs': paragraphs.copy()})
            paragraphs.clear()

    for line in text.splitlines(keepends=True):
        body = line.rstrip('\r\n')
        value = body.strip()
        if not fence and value in {marker, '* * *'}:
            close_scene()
        elif not fence and not value:
            close_paragraph()
        else:
            if start is None:
                start = offset
            end = offset + len(body)
            run = re.match(r'^(~{3,}|\x60{3,})', value)
            if run and fence and value.rstrip(fence[0]) == '' and len(value) >= len(fence):
                fence = None
            elif run and not fence:
                fence = run[0]
        offset += len(line)
    close_scene()
    return scenes


def enrich(section, marker='* * *'):
    return dict(section, scenes=passages(section['reader_text'], marker))


def section_id(section):
    return section.get('chapter_id') or section['path']


def open_beta(root, book, edition, *, with_directory=False):
    import project_state as state
    if not re.fullmatch(r'[a-f0-9]{24}', edition):
        raise ValueError('expected a beta edition ID')
    directory = state.path_at(root, f'Chapters/{book}/export')
    packets = state.path_at(root, f'_Edits/{book}/beta-rereads')
    for path in (directory / 'beta', *sorted(directory.glob('beta.previous-*')), packets / edition):
        manifest = state.path_at(root, path / 'export-manifest.json')
        if not manifest.is_file():
            continue
        record = state.load(manifest)
        meta = record.get('beta_feedback', {})
        if meta.get('export_id') != edition:
            continue
        if meta.get('map') != 'beta-passages.json':
            raise ValueError('unknown beta passage map')
        source = state.path_at(root, path / meta['map'])
        if state.digest(source) != meta.get('sha256'):
            raise ValueError('archived beta passage map changed')
        version = state.load(source)
        if version.get('export_id') != edition:
            raise ValueError('archived beta passage map has the wrong export ID')
        marker = record.get('config', {}).get('scene_break', '* * *')
        version['sections'] = [s if 'scenes' in s else enrich(s, marker) for s in version['sections']]
        return (version,path) if with_directory else version
    raise ValueError(f'beta export {edition} could not be found in {book}')


def current(root, book, *, source_lines=False, allow_empty=False, through=None):
    import project_state as state
    resolver = state.project_manifest_module()
    record = resolver.resolve_book(root, book)
    marker = record.get('chapter_format', {}).get('scene_break', '* * *')
    text_runtime = state.reader_text_module()
    fmt = state.chapter_format_module()
    sections = []
    for ch in sorted(record['chapters'], key=lambda c: c['reading_order']):
        if through is not None and ch['reading_order'] > through:
            break
        p = state.path_at(root, ch['path'])
        if not p.is_file():
            continue
        source = p.read_bytes().decode('utf-8')
        extracted = text_runtime.extract(source, source=ch['path'], scene_break=marker,
                                         pov_comment_lines=fmt.comment_lines(source, marker))
        sections.append(enrich({'chapter_id': ch['id'], 'path': ch['path'],
                                'label': ch.get('display_label', ch['id']),
                                'source_sha256': extracted['raw_sha256'], 'reader_text': extracted['text']}, marker))
        if source_lines:
            sections[-1]['source_lines'] = extracted['source_lines']
    if not sections and not allow_empty:
        raise ValueError('no drafted chapters to read')
    if resolver.resolve_book(root, book) != record or any(
            state.digest(state.path_at(root, s['path'])) != s['source_sha256'] for s in sections):
        raise ValueError('manuscript changed while freezing the edition')
    identifier = digest(json.dumps(sections, ensure_ascii=False, sort_keys=True))
    return {'schema_version': 1, 'export_id': identifier, 'sections': sections}


def scenes_by_key(edition):
    return {(section_id(s), i): scene for s in edition['sections'] for i, scene in enumerate(s['scenes'])}


def compare(old, new):
    """Match unique scene text, then unique shared paragraphs, then bounded one-to-one gaps."""
    before, after = scenes_by_key(old), scenes_by_key(new)
    matched, used = {}, set()

    def pair(a, b):
        matched[a] = b
        used.add(b)

    def index(source, skip, field):
        result = defaultdict(set)
        for key, scene in source.items():
            if key in skip:
                continue
            values = [scene['sha256']] if field == 'sha256' else [p['text'] for p in scene['paragraphs']]
            for v in values:
                result[v].add(key)
        return result

    for field in ('sha256', 'paragraphs'):
        left, right = index(before, matched, field), index(after, used, field)
        proposals, reverse = defaultdict(set), defaultdict(set)
        for token in left.keys() & right.keys():
            if len(left[token]) == len(right[token]) == 1:
                a, b = next(iter(left[token])), next(iter(right[token]))
                proposals[a].add(b)
                reverse[b].add(a)
        for a, bs in proposals.items():
            if len(bs) == 1:
                b = next(iter(bs))
                if len(reverse[b]) == 1:
                    pair(a, b)

    def gaps(source, anchors):
        groups = defaultdict(list)
        last = {}
        pending = []
        for key in source:
            chapter, _ = key
            if pending and pending[0][0] != chapter:
                groups[(pending[0][0], last.get(pending[0][0]), None)] = pending
                pending = []
            if key in anchors:
                if pending:
                    groups[(chapter, last.get(chapter), anchors[key])] = pending
                    pending = []
                last[chapter] = anchors[key]
            else:
                pending.append(key)
        if pending:
            groups[(pending[0][0], last.get(pending[0][0]), None)] = pending
        return groups

    left = gaps(before, matched)
    right = gaps(after, {b: b for b in used})
    uncertain_old, uncertain_new = set(), set()
    for anchor in left.keys() & right.keys():
        a, b = left[anchor], right[anchor]
        if len(a) == len(b) and all(before[x]['sha256'] == after[y]['sha256'] for x, y in zip(a, b)):
            for x, y in zip(a, b):
                pair(x, y)
        elif len(a) == len(b) == 1:
            pair(a[0], b[0])
        else:
            uncertain_old.update(a)
            uncertain_new.update(b)

    # Insertions before an intact scene do not make it a move.
    stationary = set()
    chapter_before = [section_id(s) for s in old['sections']]
    chapter_after = [section_id(s) for s in new['sections']]
    for tag, i, j, k, l in SequenceMatcher(None, chapter_before, chapter_after, autojunk=False).get_opcodes():
        if tag != 'equal':
            continue
        for chapter in chapter_before[i:j]:
            originals = [matched[a] for a in before if a[0] == chapter and a in matched and matched[a][0] == chapter]
            destinations = sorted(originals)
            for block in SequenceMatcher(None, originals, destinations, autojunk=False).get_matching_blocks():
                stationary.update(originals[block.a:block.a + block.size])
    result = []
    inverse = {b: a for a, b in matched.items()}
    for b, scene in after.items():
        a = inverse.get(b)
        if a is None:
            status = 'unresolved' if b in uncertain_new else 'added'
        elif before[a]['sha256'] != scene['sha256']:
            status = 'edited' if b in stationary else 'moved-edited'
        else:
            status = 'unchanged' if b in stationary else 'moved'
        result.append({'before': a, 'after': b, 'status': status})
    result.extend({'before': a, 'after': None, 'status': 'unresolved' if a in uncertain_old else 'deleted'}
                  for a in before if a not in matched)
    return result


def paragraph_changes(before, after):
    a = before['paragraphs'] if before else []
    b = after['paragraphs'] if after else []
    diff = SequenceMatcher(None, [p['text'] for p in a], [p['text'] for p in b], autojunk=False)
    return [{'kind': tag, 'before': a[i:j], 'after': b[k:l], 'old_position': i}
            for tag, i, j, k, l in diff.get_opcodes() if tag != 'equal']


def proof(root, book, which, base, *, allow_empty=False):
    import project_state as state
    if which == 'current':
        return current(root, book, allow_empty=allow_empty)
    if not re.fullmatch('[0-9a-f]{24}|[0-9a-f]{64}', which):
        raise ValueError('invalid edition ID')
    path = state.path_at(root, base / 'editions' / (which + '.json'))
    if path.is_file():
        record = state.load(path)
        if record['export_id'] != which or record.get('snapshot_sha256') != digest(
                json.dumps(record['sections'], sort_keys=True, ensure_ascii=False)):
            raise ValueError('author edition snapshot changed')
        return record
    return open_beta(root, book, which)


def reading_status(root, book, log, base, target):
    baseline = {}
    snapshots = {}
    def snapshot(edition):
        if edition not in snapshots:
            snapshots[edition] = proof(root, book, edition, base)
        return snapshots[edition]
    new_scenes = scenes_by_key(target)
    changes, completed, bookmark = [], [], None
    histories = log.get('history', {})
    marks = dict(log.get('marks', {}))
    for cid, records in histories.items():
        exact = [m for m in records if m['edition'] == target['export_id']]
        if exact:
            marks[cid] = next((m for m in reversed(exact) if m['whole']), exact[-1])
    targets = {section_id(s): s for s in target['sections']}
    for cid, records in histories.items():
        if cid in targets:
            for m in reversed(records):
                if m['whole'] and any(section_id(s) == cid and s['reader_text'] == targets[cid]['reader_text']
                                      for s in snapshot(m['edition'])['sections']):
                    marks[cid] = m
                    break
    for cid, mark in marks.items():
        edition = mark['edition']
        if edition not in baseline:
            old = snapshot(edition)
            baseline[edition] = (old, scenes_by_key(old), compare(old, target))
        old, scenes, comparison = baseline[edition]
        section = next(s for s in old['sections'] if section_id(s) == cid)
        target_section = next((s for s in target['sections'] if section_id(s) == cid), None)
        if mark['whole'] and target_section and target_section['reader_text'] == section['reader_text']:
            completed.append(cid)
        for item in comparison:
            a, b = item['before'], item['after']
            previous = scenes.get(a)
            if a and a[0] != cid or not a and (not b or b[0] != cid):
                continue
            if previous and previous['start'] >= mark['end'] or item['status'] == 'unchanged':
                continue
            following = new_scenes.get(b)
            if not a and not mark['whole']:
                # A new scene belongs to the read prefix only if a later matched scene was read.
                if not any(x['after'] and x['after'][0] == cid and x['after'][1] > b[1] and
                           x['before'] and x['before'][0] == cid and scenes[x['before']]['start'] < mark['end']
                           for x in comparison):
                    continue
            details = paragraph_changes(previous, following)
            if previous and not mark['whole']:
                details = [d for d in details if
                           (d['before'] and d['before'][0]['start'] < mark['end']) or
                           (not d['before'] and d['old_position'] < len(previous['paragraphs']) and
                            previous['paragraphs'][d['old_position']]['start'] < mark['end'])]
                for d in details.copy():
                    old_rows = d['before']
                    if not old_rows:
                        continue
                    visible = [p for p in old_rows if p['start'] < mark['end']]
                    if len(visible) < len(old_rows):
                        d['after'] = d['after'][:len(visible)] if len(old_rows) == len(d['after']) else []
                    d['before'] = visible
                    if visible and visible[-1]['end'] > mark['end']:
                        p = visible[-1]
                        length = mark['end'] - p['start']
                        prefix = p['text'][:length]
                        if len(d['after']) == len(visible) and d['after'][-1]['text'].startswith(prefix):
                            d['before'] = visible[:-1]
                            d['after'] = d['after'][:-1]
                            if not d['before'] and not d['after']:
                                details.remove(d)
                        else:
                            visible[-1] = dict(p, end=mark['end'], text=prefix)
            if details or item['status'] in ('moved', 'moved-edited', 'unresolved'):
                changes.append(dict(item, paragraphs=details))
    latest = log.get('marks', {}).get(log.get('last'))
    if latest:
        cid = log['last']
        old = snapshot(latest['edition'])
        old_sections = {section_id(s): s for s in old['sections']}
        target_sections = {section_id(s): s for s in target['sections']}
        source = old_sections[cid]
        bookmark = dict(latest, chapter_id=cid, status='unresolved')
        location = target_sections.get(cid)
        if location and source['reader_text'] == location['reader_text']:
            bookmark.update(status='located', current_end=latest['end'], current_chapter_id=cid)
        else:
            scene_no = next((i for i, scene in reversed(list(enumerate(source['scenes'])))
                             if scene['start'] < latest['end']), None)
            pair = next((v for v in compare(old, target) if v['before'] == (cid, scene_no)), None)
            if pair and pair['after']:
                dest, index = pair['after']
                other = target_sections[dest]
                start = other['scenes'][index]['start']
                text = other['reader_text'][start:other['scenes'][index]['end']]
                anchor = latest['anchor']
                if anchor and text.find(anchor) == text.rfind(anchor) != -1:
                    bookmark.update(status='located', current_chapter_id=dest,
                                    current_end=start + text.index(anchor) + len(anchor))
        if bookmark['status'] == 'located':
            for change in changes:
                after = change['after']
                if after and after[0] == bookmark['current_chapter_id'] and not latest['whole']:
                    end = bookmark['current_end']
                    for delta in change['paragraphs']:
                        delta['after'] = [dict(p, end=min(end,p['end']), text=p['text'][:end-p['start']])
                                          for p in delta['after'] if p['start'] < end]
            target_order = list(target_sections)
            cut = target_order.index(bookmark['current_chapter_id'])
            old_order = list(old_sections)
            old_cut = old_order.index(cid)
            recorded = {(tuple(v['after']), v['status']) for v in changes if v['after']}
            for item in compare(old, target):
                a, b = item['before'], item['after']
                if not b or (b, item['status']) in recorded or item['status'] == 'unchanged':
                    continue
                if not target_sections[b[0]].get('chapter_id'):
                    continue
                dest = target_sections[b[0]]['scenes'][b[1]]
                inside = (target_order.index(b[0]) < cut or
                          (b[0] == bookmark['current_chapter_id'] and dest['start'] < bookmark['current_end']))
                if not inside:
                    continue
                new_chapter = b[0] not in old_sections
                crossed = a and (old_order.index(a[0]) > old_cut or
                                 (a[0] == cid and old_sections[cid]['scenes'][a[1]]['start'] >= latest['end']))
                if (new_chapter and not a) or (crossed and item['status'] in ('moved', 'moved-edited')):
                    changes.append(dict(item, paragraphs=paragraph_changes(
                        old_sections[a[0]]['scenes'][a[1]] if a else None, dest)))
    reported = {cid for cid, mark in log.get('marks', {}).items() if mark['whole']}
    reported.update(cid for cid, records in histories.items() if any(m['whole'] for m in records))
    return {'personally_read': len(completed), 'current_chapter_ids': completed,
            'reported_complete': len(reported),
            'bookmark': bookmark, 'changes': changes, 'edition': target['export_id']}


def author_read(root, args):
    import project_state as state
    base = state.path_at(root, f'_Edits/{args.book}/author-read')
    path = base / 'progress.json'
    with state.locked(path):
        log = state.load(path) if path.exists() else {'schema_version': 1, 'marks': {}}
        if args.action == 'start':
            version = proof(root, args.book, args.edition or 'current', base)
            snapshot = {'schema_version': 1, 'export_id': version['export_id'], 'sections': version['sections']}
            snapshot['snapshot_sha256'] = digest(json.dumps(snapshot['sections'], sort_keys=True, ensure_ascii=False))
            state.write(base / 'editions' / (version['export_id'] + '.json'), snapshot)
            log['edition'] = version['export_id']
            state.write(path, log)
            return {'edition': log['edition'], 'chapters': [s['label'] for s in version['sections'] if s.get('chapter_id')]}
        if 'edition' not in log:
            raise ValueError('start the author read-through on the edition being read')
        if args.action == 'mark':
            version = proof(root, args.book, log['edition'], base)
            options = [s for s in version['sections'] if s.get('chapter_id')]
            if args.chapter:
                selector = 'Chapter ' + str(int(args.chapter)) if args.chapter.isdigit() else args.chapter
                options = [s for s in options if selector in (s['chapter_id'], s['label'], s['path'])]
            if args.quote:
                hits = [(s, m.start() + len(args.quote)) for s in options for m in re.finditer('(?=' + re.escape(args.quote) + ')', s['reader_text'])]
                if len(hits) != 1:
                    raise ValueError('quote is absent or repeated; give the chapter and a unique neighboring line')
                section, end = hits[0]
                anchor = args.quote
            elif args.chapter and len(options) == 1:
                section = options[0]
                end = len(section['reader_text'])
                anchor = section['reader_text'].rstrip().split('\n')[-1]
            else:
                raise ValueError('mark requires a unique completed chapter or quote')
            mark = {'edition': log['edition'], 'end': end, 'whole': not args.quote, 'anchor': anchor}
            cid = section['chapter_id']
            history = log.setdefault('history', {}).setdefault(cid, [])
            for record in (log['marks'].get(cid), mark):
                if record and record not in history:
                    history.append(record)
            log['marks'][cid] = mark
            log['last'] = cid
            state.write(path, log)
            return dict(mark, chapter_id=cid)
        if args.action not in ('resume', 'changes', 'status'):
            raise ValueError('unsupported author-read action')
        return reading_status(root, args.book, log, base, proof(root, args.book, args.edition or 'current', base, allow_empty=True))
