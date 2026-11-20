#!/usr/bin/env python3
"""Import a returned beta edition's comments and turn selected findings into revision tasks."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
from xml.etree import ElementTree as ET
import zipfile

sys.dont_write_bytecode = True
SKILLS = Path(__file__).resolve().parents[2]


def bundled(name, path):
    spec = importlib.util.spec_from_file_location(name, SKILLS / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


exchange = bundled('storycraft_beta_exchange', 'compile-manuscript/scripts/beta_exchange.py')
state = bundled('storycraft_state', 'book-status/scripts/project_state.py')
WORD = exchange.WORD
normal = exchange.normal


open_export = state.editions.open_beta


def word_edition(document):
    names = (exchange.bookmark_name(node) for node in document.iter(WORD + 'bookmarkStart'))
    return {name.removeprefix('sc_export_') for name in names if name.startswith('sc_export_')}


def word_notes(path, edition, passages):
    with zipfile.ZipFile(path) as archive:
        document = ET.fromstring(archive.read('word/document.xml'))
        if 'word/comments.xml' not in archive.namelist():
            raise ValueError('no Word margin comments found in the returned DOCX')
        comments = ET.fromstring(archive.read('word/comments.xml'))
    export_marks = word_edition(document)
    if export_marks and export_marks != {edition}:
        raise ValueError('returned DOCX belongs to a different beta export')
    ranges = {}
    active = set()
    for paragraph in document.iter(WORD + 'p'):
        ids = {exchange.bookmark_name(node) for node in paragraph.iter(WORD + 'bookmarkStart')}
        ids &= passages.keys()
        for identifier in active:
            ranges[identifier]['quote'].append('\n')
            ranges[identifier]['anchors'].update(ids)
        for node in paragraph.iter():
            tag = node.tag
            identifier = node.get(WORD + 'id')
            if tag in (WORD + 'commentRangeStart', WORD + 'commentReference'):
                entry = ranges.setdefault(identifier, {'quote': [], 'anchors': set()})
                entry['anchors'].update(ids)
                if tag == WORD + 'commentRangeStart':
                    active.add(identifier)
            elif tag == WORD + 'commentRangeEnd':
                active.discard(identifier)
            elif tag in (WORD + 't', WORD + 'br', WORD + 'tab', WORD + 'cr'):
                value = (node.text or '') if tag == WORD + 't' else ' '
                for active_id in active:
                    ranges[active_id]['quote'].append(value)
    notes = []
    for comment in comments.iter(WORD + 'comment'):
        identifier = comment.get(WORD + 'id')
        entry = ranges.get(identifier, {'quote': [], 'anchors': set()})
        content = '\n'.join(exchange.paragraph_text(p) for p in comment.iter(WORD + 'p')).strip()
        if not content:
            continue
        notes.append({'reader': comment.get(WORD + 'author') or 'Unknown reader', 'comment': content,
                      'quote': normal(''.join(entry['quote'])),
                      'anchors': sorted(entry['anchors']), 'origin': 'word',
                      'comment_id': identifier, 'date': comment.get(WORD + 'date')})
    return notes


def pasted_notes(path):
    spec = state.load(path)
    reader = spec.get('reader')
    notes = spec.get('notes')
    if not isinstance(reader, str) or not reader.strip() or not isinstance(notes, list) or not notes:
        raise ValueError('pasted notes require a reader name and at least one note')
    for entry in notes:
        if not isinstance(entry, dict) or not isinstance(entry.get('comment'), str) or not entry['comment'].strip():
            raise ValueError('each pasted note needs nonempty comment text')
        for field in ('chapter', 'quote', 'anchor'):
            if field in entry and not isinstance(entry[field], str):
                raise ValueError(f'{field} in a pasted note must be a string')
        note = {key: entry[key] for key in ('chapter', 'quote', 'comment') if key in entry}
        note.update(reader=reader.strip(), origin='pasted', anchors=[entry['anchor']] if entry.get('anchor') else [])
        yield note


def location(note, version):
    """Prefer archived Word anchors. Resolve pasted quotes only when the match is unique."""
    quote = normal(note.get('quote', ''))
    anchors = note.get('anchors', [])
    sections = {item['bookmark']: item for item in version['sections']}
    paragraphs = version['word_passages'] or version.get('text_passages', {})
    chapter = note.get('chapter')
    allowed = {key for key, item in sections.items() if not chapter or chapter.casefold() in {
        str(item.get('label', '')).casefold(), str(item.get('chapter_id', '')).casefold(),
        item['path'].casefold(), Path(item['path']).stem.casefold()}}
    if chapter and len(allowed) != 1:
        return {'status': 'UNRESOLVED', 'reason': 'chapter reference is missing or ambiguous'}

    def binding(section, paragraph_ids, text):
        content = sections[section]
        return {'status': 'ANCHORED', 'chapter_id': content['chapter_id'], 'chapter': content['label'],
                'path': content['path'], 'source_sha256': content['source_sha256'],
                'passages': paragraph_ids, 'anchor_text': text}

    if anchors:
        if any(anchor in version.get('text_passages', {}) for anchor in anchors):
            paragraphs = version['text_passages']
        if any(anchor not in paragraphs for anchor in anchors):
            return {'status': 'UNRESOLVED', 'reason': 'returned passage anchor is absent from archived export'}
        candidates = {paragraphs[item]['section'] for item in anchors}
        if len(candidates) != 1 or not candidates <= allowed:
            return {'status': 'UNRESOLVED', 'reason': 'comment crosses chapter boundaries or disagrees with the supplied chapter'}
        section = next(iter(candidates))
        # Preserve document order even when the Word comment spans several paragraphs.
        ordered = [item for item in paragraphs if item in anchors]
        text = ' '.join(paragraphs[item]['text'] for item in ordered)
        if quote and quote not in text:
            return {'status': 'UNRESOLVED', 'reason': 'comment selection differs from its archived passage'}
        if not text.strip():
            return {'status': 'UNRESOLVED', 'reason': 'archived passage has no reader text'}
        return binding(section, ordered, text)

    if not quote:
        return {'status': 'GENERAL', 'chapter': chapter, 'reason': 'feedback has no quoted passage'}
    matches = [(anchor, item) for anchor, item in paragraphs.items()
               if item['section'] in allowed and quote in item['text']]
    if matches:
        if len(matches) == 1 and matches[0][1]['text'].count(quote) == 1:
            anchor, item = matches[0]
            return binding(item['section'], [anchor], item['text'])
        return {'status': 'UNRESOLVED', 'reason': 'quote appears more than once in the archived passages'}
    matches = [section for section in allowed if quote in normal(sections[section]['reader_text'])]
    if len(matches) == 1 and normal(sections[matches[0]]['reader_text']).count(quote) == 1:
        return binding(matches[0], [], quote)
    return {'status': 'UNRESOLVED', 'reason': 'quote is absent or ambiguous in the archived export'}


def add_notes(document, raw, version):
    records = {item['id']: item for item in document['feedback']}
    count = 0
    for note in raw:
        key = json.dumps(note, sort_keys=True, ensure_ascii=False).encode()
        identifier = 'BF-' + hashlib.sha256(key).hexdigest()[:16]
        if identifier in records:
            continue
        records[identifier] = {'id': identifier, **note, 'export_id': version['export_id'],
                               'location': location(note, version)}
        count += 1
    document['feedback'] = list(records.values())
    return count


def summarize(document):
    groups = {}
    for note in document['feedback']:
        place = note['location']
        if place['status'] != 'ANCHORED':
            continue
        group = place['path'], tuple(place['passages']) or (place['anchor_text'],)
        groups.setdefault(group, []).append(note)
    return [{'path': path, 'passages': list(passage), 'feedback_ids': [item['id'] for item in items],
              'reader_count': len({item['reader'] for item in items})}
            for (path, passage), items in groups.items()]


def draft_campaign(root, book, campaign_id, document, choice):
    records = {item['id']: item for item in document['feedback']}
    by_file = {}
    for identifier in dict.fromkeys(choice):
        item = records.get(identifier)
        if item is None:
            raise ValueError(f'unknown feedback {identifier}')
        place = item['location']
        if place['status'] != 'ANCHORED' or not place.get('chapter_id'):
            raise ValueError(f'{identifier} needs an anchored chapter passage before revision')
        name = place['path']
        file = state.path_at(root, name)
        if not file.is_file():
            raise ValueError(f'{identifier}: chapter moved or is missing; reconcile the feedback anchor')
        raw = file.read_bytes()
        current = exchange.sha256(raw)
        quote = normal(item.get('quote') or place['anchor_text'])
        if current != place['source_sha256'] and normal(raw.decode('utf-8')).count(quote) != 1:
            raise ValueError(f'{identifier}: quoted passage changed or is ambiguous in the current chapter')
        target = by_file.setdefault(name, {'sha256': current, 'notes': []})
        if target['sha256'] != current:
            raise ValueError(f'{name} changed while resolving selected feedback')
        target['notes'].append(item)
    tasks = []
    for index, (name, target) in enumerate(by_file.items(), 1):
        tasks.append({'id': f'beta-{index}', 'files': [name], 'depends_on': [], 'kind': 'prose-repair',
                      'acceptance': ['Address the selected reader observations and verify the resulting chapter.'],
                      'scope': 'Selected observations and their quoted passages.',
                      'feedback': target['notes'],
                      'expected_inputs': [{'path': name, 'kind': 'file', 'sha256': target['sha256']}]})
    spec = {'schema_version': 1, 'outcome': 'Address selected beta-reader feedback',
            'authorization': 'Selected for revision planning: ' + ', '.join(dict.fromkeys(choice)),
            'preserve': [], 'tasks': tasks}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'campaign.json'
        state.write(path, spec)
        return state.campaign(root, argparse.Namespace(book=book, run=campaign_id, action='init', spec=path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--book', default='Book-1')
    parser.add_argument('--export', metavar='ID', help='beta edition ID, inferred from a bookmarked DOCX when omitted')
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--docx', type=Path)
    source.add_argument('--notes', type=Path)
    source.add_argument('--campaign', metavar='ID')
    parser.add_argument('--select', action='append', default=[], metavar='FEEDBACK_ID')
    args = parser.parse_args()
    if not args.export and args.docx:
        with zipfile.ZipFile(args.docx) as archive:
            marks = word_edition(ET.fromstring(archive.read('word/document.xml')))
        if len(marks) == 1:
            args.export = next(iter(marks))
    if not re.fullmatch(r'[\w-]+', args.book) or not re.fullmatch(r'[a-f0-9]{24}', args.export or ''):
        parser.error('use a book identifier and the ID from its beta export')
    if bool(args.campaign) != bool(args.select) or (args.campaign and not re.fullmatch(r'[\w-]+', args.campaign)):
        parser.error('--campaign requires a safe run ID and one or more --select feedback IDs')
    root = args.root.resolve()
    version = open_export(root, args.book, args.export)
    path = state.path_at(root, f'_Edits/{args.book}/beta-feedback/{args.export}.json')
    if args.docx or args.notes:
        raw = (word_notes(args.docx, args.export, version['word_passages']) if args.docx
               else list(pasted_notes(args.notes)))
        with state.locked(path):
            document = state.document(path, 'feedback')
            count = add_notes(document, raw, version)
            if count or not path.exists():
                state.write(path, document)
    else:
        document = state.document(path, 'feedback')
        count = 0
    if args.campaign:
        print(json.dumps(draft_campaign(root, args.book, args.campaign, document, args.select),
                         indent=2, ensure_ascii=False))
    else:
        print(json.dumps({'export_id': args.export, 'added': count, 'feedback': document['feedback'],
                          'groups': summarize(document)},
                         indent=2, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile, ET.ParseError) as exc:
        sys.exit(str(exc))
