#!/usr/bin/env python3
"""Collect book-scoped source passages for editorial milestones and narration."""

import argparse
from collections import defaultdict
from difflib import SequenceMatcher
from itertools import combinations
import json
from pathlib import Path
import re
import sys
import unicodedata

sys.dont_write_bytecode = True
import editions
import project_manifest as manifest
import project_state as state
import reader_text

FOLDERS = {
    'Characters': 'character',
    'Locations': 'place',
    'World/Locations': 'place',
    'World/Places': 'place',
    'World/Terms': 'term',
    'Glossary': 'term',
    'Terms': 'term',
    'Organizations': 'term',
    'World/Organizations': 'term',
    'Systems': 'term',
    'World/Systems': 'term',
}


def clean_chapter(root, book, selector):
    book_record, ch = manifest.resolve_chapter(root, book, selector)
    source = state.path_at(root, ch['path']).read_text(encoding='utf-8')
    marker = book_record.get('chapter_format', {}).get('scene_break', '* * *')
    text = reader_text.extract(
        source,
        source=ch['path'],
        scene_break=marker,
        pov_comment_lines=state.chapter_format_module().comment_lines(source, marker),
    )['text']
    # Manuscript-level YAML metadata is not part of the exercise delivered to the reader.
    header = re.match(r'\A---[ \t]*\n(?=[\w-]+:).*?\n(?:---|\.\.\.)[ \t]*\n', text, re.S)
    if header:
        text = text[header.end() :].lstrip('\n')
    return {'chapter': ch['display_label'], 'text': text}


def profiles(root):
    try:
        import yaml
    except ImportError as exc:
        raise ValueError('PyYAML is required to read the project Wiki profiles') from exc
    records = []
    for folder, category in FOLDERS.items():
        directory = state.path_at(root, 'Wiki/' + folder)
        for path in sorted(directory.rglob('*.md')):
            rel = path.relative_to(root).as_posix()
            raw = state.path_at(root, rel).read_text(encoding='utf-8')
            header = re.match(r'\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|$)', raw, re.S)
            try:
                data = (yaml.safe_load(header[1]) or {}) if header else {}
            except yaml.YAMLError as exc:
                raise ValueError('invalid Wiki front matter in ' + rel) from exc
            if not isinstance(data, dict):
                raise ValueError('invalid Wiki profile: ' + rel)
            name = data.get('name') or data.get('term') or path.stem.replace('_', ' ')
            aliases = []
            for field in ('aliases', 'also_known_as'):
                seq = data.get(field) or []
                aliases.extend([seq] if isinstance(seq, str) else seq)
            records.append(
                {
                    'name': str(name),
                    'category': category,
                    'aliases': aliases,
                    'path': rel,
                    'body': raw[header.end() :].strip() if header else raw.strip(),
                }
            )
    return records


def _token_pattern(raw_value, *, case_sensitive):
    escaped = re.escape(raw_value.strip())
    return escaped if case_sensitive else f'(?i:{escaped})'


def forms(records):
    owners = defaultdict(set)
    exact_full_owners = defaultdict(set)
    raw_forms = {}
    for record in records:
        name = record['name']
        exact_full_owners[name.casefold()].add(name)
        values = [name, *record['aliases']]
        if record['category'] == 'character':
            first = name.split()[0] if name.split() else ''
            if first and first.casefold() != name.casefold():
                values.append(first)
        for value in values:
            if isinstance(value, str) and value.strip():
                key = value.strip().casefold()
                owners[key].add(name)
                raw_forms.setdefault((name, key), value.strip())

    compiled = {}
    for r in records:
        name = r['name']
        is_char = r['category'] == 'character'
        name_cf = name.casefold()
        tokens = [k for k, v in owners.items() if v == {name}]
        parts = []
        for k in sorted(tokens, key=len, reverse=True):
            raw = raw_forms[(name, k)]
            cs = is_char and any(ch.isupper() for ch in raw)
            parts.append(_token_pattern(raw, case_sensitive=cs))
        # Preserve an unambiguous exact single-token character name (e.g. "Mara" when "Mara Chen"
        # also exists), rejecting matches followed by a longer competing full name's surname/tail.
        if is_char and exact_full_owners.get(name_cf) == {name} and name_cf not in tokens:
            tails = []
            for other in exact_full_owners:
                if other != name_cf and other.startswith(name_cf + ' '):
                    tails.append(re.escape(other[len(name_cf) + 1 :].strip()))
            raw = name.strip()
            cs = any(ch.isupper() for ch in raw)
            pat = _token_pattern(raw, case_sensitive=cs)
            if tails:
                pat += r'(?!\s+(?i:' + '|'.join(sorted(tails, key=len, reverse=True)) + r')(?!\w))'
            parts.append(pat)
        if parts:
            compiled[name] = re.compile(r'(?<!\w)(?:' + '|'.join(parts) + r')(?!\w)')
    return compiled


def source_line(section, offset):
    return section['source_lines'][section['reader_text'].count('\n', 0, offset)]


def lines_by_chapter(sections):
    result = []
    for section in sections:
        rows = []
        for index, scene in enumerate(section['scenes'], 1):
            for paragraph in scene['paragraphs']:
                if paragraph['text'].lstrip().startswith('#'):
                    continue
                rows.append(
                    {
                        'path': section['path'],
                        'chapter': section['label'],
                        'scene': index,
                        'line': source_line(section, paragraph['start']),
                        'quote': paragraph['text'],
                    }
                )
        result.append(rows)
    return result


def mentions(sections, patterns):
    result = defaultdict(lambda: defaultdict(list))
    lines = lines_by_chapter(sections)
    for n, chapter in enumerate(lines):
        for j, row in enumerate(chapter):
            for name, pattern in patterns.items():
                match = pattern.search(row['quote'])
                if match:
                    result[name][n].append((j, dict(row, character=match.start() + 1)))
    return lines, result


def sound(value):
    text = ''.join(x for x in unicodedata.normalize('NFD', value.upper()) if 'A' <= x <= 'Z')
    codes = {
        c: str(i)
        for i, chars in enumerate(('', 'BFPV', 'CGJKQSXZ', 'DT', 'L', 'MN', 'R'))
        for c in chars
    }
    if not text:
        return ''
    result, last = text[0], codes.get(text[0], '')
    for c in text[1:]:
        code = codes.get(c, '')
        if code and code != last:
            result += code
        last = code
    return result.ljust(4, '0')[:4]


def cast(sections, records, gap):
    if gap < 0:
        raise ValueError('return gap must be nonnegative')
    people = [r for r in records if r['category'] == 'character']
    lines, hits = mentions(sections, forms(people))
    collisions, returns = [], []
    for a, b in combinations(hits, 2):
        x, y = a.split()[0].casefold(), b.split()[0].casefold()
        if (
            x != y
            and not (sound(x) and sound(x) == sound(y))
            and SequenceMatcher(None, x, y).ratio() < 0.74
        ):
            continue
        pair = min(((abs(i - j), i, j) for i in hits[a] for j in hits[b]), default=None)
        if pair and pair[0] <= 1:
            i, j = pair[1:]
            collisions.append({'names': [a, b], 'evidence': [hits[a][i][0][1], hits[b][j][0][1]]})
    for name, appearances in hits.items():
        for a, b in zip(appearances, list(appearances)[1:]):
            if b - a - 1 >= gap:
                k, row = appearances[b][0]
                returns.append(
                    {
                        'name': name,
                        'gap': b - a - 1,
                        'previous': appearances[a][-1][1],
                        'return_line': row,
                        'context': lines[b][max(0, k - 1) : k + 3],
                    }
                )
    return {'collisions': collisions, 'returns': returns}


def scene_packet(root, book, sections, selector, index, records, place=None):
    _, chapter = manifest.resolve_chapter(root, book, selector)
    position = next((i for i, s in enumerate(sections) if s['chapter_id'] == chapter['id']), None)
    if position is None or not 1 <= index <= len(sections[position]['scenes']):
        raise ValueError('requested scene is outside the drafted chapter')

    def scene_text(section, n):
        block = section['scenes'][n]
        return {
            'chapter': section['label'],
            'path': section['path'],
            'scene': n + 1,
            'start_line': source_line(section, block['start']),
            'text': section['reader_text'][block['start'] : block['end']],
        }

    items = [scene_text(s, n) for s in sections for n in range(len(s['scenes']))]
    k = next(i for i, v in enumerate(items) if v['path'] == chapter['path'] and v['scene'] == index)
    target = items[k]
    places = [r for r in records if r['category'] == 'place']
    patterns = forms(places)
    mentioned = [p for p in places if p['name'] in patterns and patterns[p['name']].search(target['text'])]
    if place:
        choices = [p for p in places if place.casefold() in {str(n).casefold() for n in (p['name'], *p['aliases'])}]
        if len(choices) != 1:
            raise ValueError('place is missing or ambiguous in the project Wiki: ' + place)
        if choices[0] not in mentioned:
            mentioned.append(choices[0])
    evidence = [
        {'name': r['name'], 'path': r['path'], 'text': r['body']}
        for r in mentioned
    ]
    return dict(
        target,
        before=items[:k],
        after=[x for x in items[k + 1 :] if x['path'] == chapter['path']],
        later=[x for x in items[k + 1 :] if x['path'] != chapter['path']],
        places=evidence,
    )


def pronunciation(root, sections, records, args):
    path = state.path_at(root, 'Wiki/Style/pronunciations.json')

    def load():
        return state.load(path) if path.exists() else {'schema_version': 1, 'approved': {}}

    saved = load()
    listed = {r['name'].casefold() for r in records}
    terms = [*args.term, *[v['term'] for k, v in saved['approved'].items() if k.startswith('term:')]]
    if args.approve:
        terms.append(args.approve)
    for name in terms:
        if name.strip() and name.casefold() not in listed:
            records.append(
                {'name': name, 'category': 'term', 'aliases': [], 'path': 'term:' + name.casefold()}
            )
            listed.add(name.casefold())
    _, appearances = mentions(sections, forms(records))
    by_name = {r['name']: r for r in records if r['name'] in appearances}
    if args.approve or args.reading:
        if args.approve not in by_name or not args.reading or not args.reading.strip():
            raise ValueError(
                'approve a term present in this book with its author-supplied stressed reading'
            )
        with state.locked(path):
            saved = load()
            saved['approved'][by_name[args.approve]['path']] = {
                'term': args.approve,
                'reading': args.reading.strip(),
            }
            state.write(path, saved)
    saved = load()
    entries = []
    for name, r in by_name.items():
        first = min(appearances[name])
        row = appearances[name][first][0][1]
        item = saved['approved'].get(r['path'], saved['approved'].get('term:' + name.casefold(), {}))
        approved = item.get('term') == name
        entries.append(
            (
                first,
                row['line'],
                {
                    'term': name,
                    'category': r['category'],
                    'first_appearance': row,
                    'status': 'approved' if approved else 'pending',
                    'reading': item.get('reading') if approved else None,
                },
            )
        )
    return {
        'entries': [
            e
            for _, _, e in sorted(
                entries, key=lambda v: (v[0], v[1], v[2]['first_appearance']['character'], v[2]['term'])
            )
        ]
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--book', default='Book-1')
    sub = parser.add_subparsers(dest='cmd', required=True)
    cast_parser = sub.add_parser('cast')
    cast_parser.add_argument('--gap', type=int, default=4)
    cast_parser.add_argument('--through', help='last narrative unit of the act or range being reviewed')
    scene = sub.add_parser('scene')
    scene.add_argument('--chapter', required=True)
    scene.add_argument('--scene', required=True, type=int)
    scene.add_argument('--place', help='established location to check when the scene only implies it')
    audio = sub.add_parser('pronunciation')
    audio.add_argument(
        '--term', action='append', default=[], help='include a manuscript term without a Wiki profile'
    )
    audio.add_argument('--approve')
    audio.add_argument('--reading')
    sub.add_parser('walkthrough').add_argument('--chapter', required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.cmd == 'walkthrough':
        result = clean_chapter(root, args.book, args.chapter)
    else:
        through = None
        if args.cmd == 'cast' and args.through:
            _, last = manifest.resolve_chapter(root, args.book, args.through)
            through = last['reading_order']
        sections = editions.current(root, args.book, source_lines=True, through=through)['sections']
        records = profiles(root)
        if args.cmd == 'cast':
            result = cast(sections, records, args.gap)
        elif args.cmd == 'scene':
            result = scene_packet(root, args.book, sections, args.chapter, args.scene, records, args.place)
        else:
            result = pronunciation(root, sections, records, args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as exc:
        sys.exit(str(exc))
