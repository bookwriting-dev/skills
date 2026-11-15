#!/usr/bin/env python3
"""Versioned project identity and path resolver with a legacy-layout adapter."""
import hashlib
import json
import re
from pathlib import Path

SCHEMA_VERSION = 1
MANIFEST_PATH = '.storycraft/project.json'


def _hash(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def contained(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f'path escapes project root: {relative}')
    return path


def numbered_chapter(book_label, number, path, predecessor_id=None):
    return {
        'id': 'chapter-' + _hash(f'{book_label}/{number}')[:16],
        'display_label': f'Chapter {number}',
        'path': path,
        'reading_order': number,
        'predecessor_id': predecessor_id,
    }


def validate(manifest, root):
    if not isinstance(manifest, dict) or manifest.get('record_type') != 'project_manifest':
        raise ValueError('invalid project manifest record_type')
    if manifest.get('schema_version') != SCHEMA_VERSION:
        raise ValueError(f"unsupported project manifest schema_version: {manifest.get('schema_version')}")
    if not manifest.get('project_id') or not isinstance(manifest.get('books'), list):
        raise ValueError('manifest requires project_id and books')
    book_ids, chapter_ids, canonical_paths = set(), set(), set()
    for book in manifest['books']:
        if not book.get('id') or book['id'] in book_ids:
            raise ValueError(f"missing or duplicate book ID: {book.get('id')}")
        book_ids.add(book['id'])
        chapters = book.get('chapters')
        if not isinstance(chapters, list):
            raise ValueError(f"book {book['id']} requires chapters")
        order_values = set()
        local_chapters = {}
        for chapter in chapters:
            cid, path, order = chapter.get('id'), chapter.get('path'), chapter.get('reading_order')
            if not cid or cid in chapter_ids:
                raise ValueError(f'missing or duplicate chapter ID: {cid}')
            chapter_ids.add(cid)
            if not isinstance(path, str) or not path:
                raise ValueError(f'chapter {cid} requires a path')
            resolved = contained(root, path)
            if not resolved.is_file():
                raise ValueError(f'chapter {cid} path does not exist: {path}')
            canonical = resolved.relative_to(Path(root).resolve()).as_posix()
            if canonical in canonical_paths:
                raise ValueError(f'duplicate authoritative chapter path for {cid}: {path}')
            canonical_paths.add(canonical)
            if type(order) is not int or order in order_values:
                raise ValueError(f'missing or duplicate reading_order for chapter {cid}')
            order_values.add(order)
            local_chapters[cid] = chapter
        for chapter in chapters:
            predecessor = chapter.get('predecessor_id')
            if predecessor is not None and predecessor not in local_chapters:
                raise ValueError(f"chapter {chapter['id']} predecessor is missing or belongs to another book: {predecessor}")
            if predecessor == chapter['id']:
                raise ValueError(f"chapter {chapter['id']} cannot precede itself")
        for chapter in chapters:
            seen = set()
            cursor = chapter
            while cursor.get('predecessor_id') is not None:
                predecessor = cursor['predecessor_id']
                if predecessor in seen:
                    raise ValueError(f"predecessor cycle in book {book['id']} at chapter {predecessor}")
                seen.add(predecessor)
                cursor = local_chapters[predecessor]
    return manifest


def propose(root):
    """Read an unambiguous conventional layout without writing project files."""
    root = Path(root).resolve()
    books = []
    unresolved = []
    for book_dir in sorted((root / 'Chapters').glob('Book-*')):
        if not book_dir.is_dir():
            continue
        match = re.fullmatch(r'Book-(\d+)', book_dir.name)
        if not match:
            unresolved.append(f'unsupported book directory label: {book_dir.relative_to(root)}')
            continue
        chapters = []
        candidates = sorted(book_dir.glob('Chapter-*.md'))
        for path in candidates:
            cm = re.fullmatch(r'Chapter-(\d+)\.md', path.name)
            if not cm:
                unresolved.append(f'ambiguous chapter filename: {path.relative_to(root)}')
                continue
            number = int(cm.group(1))
            relative = path.relative_to(root).as_posix()
            chapters.append(numbered_chapter(book_dir.name, number, relative))
        chapters.sort(key=lambda c: (c['reading_order'], c['path']))
        for i, chapter in enumerate(chapters):
            if i and chapter['reading_order'] == chapters[i - 1]['reading_order']:
                unresolved.append(f"duplicate reading order in {book_dir.name}: {chapter['reading_order']}")
            if i:
                chapter['predecessor_id'] = chapters[i - 1]['id']
        books.append({'id': book_dir.name.lower(), 'display_label': book_dir.name,
                      'chapters': chapters})
    manifest = {
        'record_type': 'project_manifest', 'schema_version': SCHEMA_VERSION,
        'record_id': 'manifest-' + _hash(str(root))[:16],
        'project_id': 'project-' + _hash(str(root))[:16],
        'producer': {'name': 'storycraft-project-resolver', 'version': '1'},
        'books': books,
    }
    if not unresolved:
        validate(manifest, root)
    return {'manifest': manifest, 'unresolved': unresolved}


def load(root):
    root = Path(root).resolve()
    path = contained(root, MANIFEST_PATH)
    if path.is_file():
        return validate(json.loads(path.read_text(encoding='utf-8')), root)
    result = propose(root)
    if result['unresolved']:
        raise ValueError('legacy project layout is ambiguous: ' + '; '.join(result['unresolved']))
    return result['manifest']


def resolve_book(root, book_id):
    manifest = load(root)
    matches = [book for book in manifest['books']
               if book['id'] == book_id or book.get('display_label') == book_id]
    if len(matches) != 1:
        raise ValueError(f'book must resolve uniquely through project manifest: {book_id}')
    return matches[0]


def chapters(root, book_id):
    return sorted(resolve_book(root, book_id)['chapters'], key=lambda c: c['reading_order'])


def resolve_chapter(root, book_id, selector, *, allow_new=False):
    book = resolve_book(root, book_id)
    value = str(selector).strip()
    matches = [chapter for chapter in book['chapters'] if value in (
        chapter.get('id'), chapter.get('display_label'), chapter.get('path'),
        Path(chapter.get('path', '')).stem)]
    if not matches and re.fullmatch(r'\d+', value):
        matches = [chapter for chapter in book['chapters']
                   if chapter.get('display_label') in (value, f'Chapter {int(value)}', f'Chapter-{int(value):03d}')]
    if not matches and allow_new and not contained(root, MANIFEST_PATH).exists():
        match = re.fullmatch(r'(?:Chapter[- ]?)?(\d+)', value, re.I)
        label = book.get('display_label', '')
        if match and int(match[1]) > 0 and re.fullmatch(r'Book-\d+', label):
            number = int(match[1])
            path = f'Chapters/{label}/Chapter-{number:03d}.md'
            if not contained(root, path).exists():
                previous = [item for item in book['chapters'] if item['reading_order'] < number]
                predecessor_id = previous[-1]['id'] if previous else None
                return book, numbered_chapter(label, number, path, predecessor_id)
    if len(matches) != 1:
        raise ValueError(f'chapter selector is missing or ambiguous in {book_id}: {selector}')
    return book, matches[0]


def resolve_style_guide(root, book_id):
    """Resolve one declared or unambiguous legacy style authority without merging files."""
    root = Path(root).resolve()
    manifest_path = contained(root, MANIFEST_PATH)
    if manifest_path.is_file():
        manifest = validate(json.loads(manifest_path.read_text(encoding='utf-8')), root)
        book = next((item for item in manifest['books']
                     if item['id'] == book_id or item.get('display_label') == book_id), None)
        if book is None:
            raise ValueError(f'book not found in project manifest: {book_id}')
        declared = book.get('style_authority')
        if declared:
            path = contained(root, declared)
            if not path.is_file():
                raise ValueError(f'declared style authority is missing: {declared}')
            return {'status': 'RESOLVED', 'path': path.relative_to(root).as_posix(),
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'source': 'manifest'}
    style_dir = root / 'Wiki' / 'Style'
    names = ('style_guide.md', 'Style Guide.md', 'style.md')
    present = [style_dir / name for name in names if (style_dir / name).is_file()]
    if not present:
        return {'status': 'MISSING', 'paths': []}
    hashes = {hashlib.sha256(path.read_bytes()).hexdigest() for path in present}
    if len(hashes) > 1:
        return {'status': 'CONFLICT', 'paths': [p.relative_to(root).as_posix() for p in present],
                'sha256': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in present}}
    selected = present[0]
    return {'status': 'RESOLVED', 'path': selected.relative_to(root).as_posix(),
            'sha256': next(iter(hashes)), 'source': 'legacy-unambiguous'}
