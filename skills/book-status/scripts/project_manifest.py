#!/usr/bin/env python3
"""Versioned project identity and path resolver with a legacy-layout adapter."""
import hashlib
import json
import re
from pathlib import Path

SCHEMA_VERSION = 1
PLANNED_SCHEMA_VERSION = 2
MANIFEST_PATH = '.storycraft/project.json'
TYPE_CHECKS = {
    'FICTION': ('Gate',),
    'NONFICTION': ('FactCheck', 'ClarityEdit'),
    'HYBRID': ('Gate', 'FactCheck', 'ClarityEdit'),
}


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
    version = manifest.get('schema_version')
    if version not in (SCHEMA_VERSION, PLANNED_SCHEMA_VERSION):
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
            if not resolved.is_file() and (version == SCHEMA_VERSION or resolved.exists()):
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


def imported_chapters(root, label):
    path = contained(root, f'Chapters/{label}/.storycraft-import.json')
    if not path.is_file():
        return None
    data = json.loads(path.read_text()).get('epub')
    if data is None:
        return None
    chapters = []
    for unit in data['units']:
        if unit['role'] != 'narrative':
            continue
        filename = unit['filename']
        if not re.fullmatch(r'(?:Chapter-\d+|Unit-[a-f0-9]{18})\.md', filename):
            raise ValueError('invalid imported reading unit filename')
        chapters.append({'id':unit.get('chapter_id') or 'chapter-' + _hash(label + '/' + unit['id'])[:16],
                         'display_label':unit['title'],'path':f'Chapters/{label}/{filename}',
                         'reading_order':len(chapters)+1, 'predecessor_id':chapters[-1]['id'] if chapters else None})
    return chapters


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
        imported = imported_chapters(root, book_dir.name)
        if imported is not None:
            books.append({'id':book_dir.name.lower(), 'display_label':book_dir.name,
                          'chapter_order':'declared','chapters':imported})
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
            if number < 1:
                unresolved.append(f'chapter number must be positive: {relative}')
                continue
            chapters.append(numbered_chapter(book_dir.name, number, relative))
        chapters.sort(key=lambda c: (c['reading_order'], c['path']))
        for i, chapter in enumerate(chapters):
            if i and chapter['reading_order'] == chapters[i - 1]['reading_order']:
                unresolved.append(f"duplicate reading order in {book_dir.name}: {chapter['reading_order']}")
            if i:
                chapter['predecessor_id'] = chapters[i - 1]['id']
        books.append({'id': book_dir.name.lower(), 'display_label': book_dir.name,
                      'chapter_order': 'conventional', 'chapters': chapters})
    manifest = {
        'record_type': 'project_manifest', 'schema_version': SCHEMA_VERSION,
        'record_id': 'manifest-' + _hash(str(root))[:16],
        'project_id': 'project-' + _hash(str(root))[:16],
        'producer': {'name': 'storycraft-project-resolver', 'version': '1'},
        'books': books,
    }
    if any(b.get('chapter_order')=='declared' for b in books):
        manifest['schema_version'] = PLANNED_SCHEMA_VERSION
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


def conventional_book(book_id):
    return {'id': book_id.lower(), 'display_label': book_id,
            'chapter_order': 'conventional', 'chapters': []}


def find_book(manifest, book_id):
    matches = [book for book in manifest['books']
               if book['id'] == book_id or book.get('display_label') == book_id]
    if len(matches) == 1:
        return matches[0]


def resolve_book(root, book_id):
    manifest = load(root)
    book = find_book(manifest, book_id)
    saved = contained(root, MANIFEST_PATH).exists()
    if saved and re.fullmatch(r'Book-[1-9]\d*', book_id):
        imported = imported_chapters(root, book_id)
        if imported is not None:
            existing = book or conventional_book(book_id)
            registered = {c['path'] for c in existing['chapters']}
            receipt = contained(root, f'Chapters/{book_id}/.storycraft-import.json')
            retired = json.loads(receipt.read_text())['epub'].get('retired_paths',[])
            if registered - {c['path'] for c in imported} - set(retired):
                raise ValueError('imported roster conflicts with registered chapters')
            by_path = {c['path']:c for c in existing['chapters']}
            return dict(existing, chapter_order='declared', chapters=[
                {**by_path.get(c['path'],{}), **c} for c in imported])
    if book is None and not saved and re.fullmatch(r'Book-[1-9]\d*', book_id):
        if any(contained(root, f'{area}/{book_id}').is_dir()
               for area in ('_Intake', 'Wiki/Outline', 'Wiki/Story')):
            return conventional_book(book_id)
    if book is None:
        raise ValueError(f'book must resolve uniquely through project manifest: {book_id}')
    if 'chapter_order' not in book and manifest.get('producer', {}).get('name') == 'storycraft-project-resolver':
        book = dict(book, chapter_order='conventional')
    if not saved or book.get('chapter_order') != 'conventional':
        return book
    # Older adopted manifests may predate drafts saved manually in the conventional tree.
    current = propose(root)
    observed = find_book(current['manifest'], book_id)
    if observed is None:
        return book
    label = book.get('display_label', book['id'])
    conflicts = [message for message in current['unresolved']
                 if f'/{label}/' in message or message.endswith(f' in {label}')]
    if conflicts:
        raise ValueError('conventional chapter layout is ambiguous: ' + '; '.join(conflicts))
    known = {chapter['path'] for chapter in book['chapters']}
    merged = book['chapters'] + [chapter for chapter in observed['chapters'] if chapter['path'] not in known]
    orders = [chapter['reading_order'] for chapter in merged]
    if len(set(orders)) != len(orders):
        raise ValueError(f'multiple chapter paths claim the same reading order in {label}')
    return dict(book, chapters=merged)


def predecessor(book, chapter):
    ordered = sorted(book['chapters'], key=lambda item: item['reading_order'])
    if book.get('chapter_order') != 'conventional' and 'predecessor_id' in chapter:
        return chapter['predecessor_id']
    previous = [item for item in ordered if item['reading_order'] < chapter['reading_order']]
    return previous[-1]['id'] if previous else None


def register(root, book_id, specification, current):
    """Add expected chapters while preserving the IDs of adopted drafts."""
    book = find_book(current, book_id)
    if book is None:
        if not re.fullmatch(r'Book-[1-9]\d*', book_id):
            raise ValueError('a new book needs a Book-N identifier')
        book = conventional_book(book_id)
        current['books'].append(book)
    else:
        resolved = resolve_book(root, book_id)
        book.update(resolved)
    label = book.get('display_label', book_id)
    additions = specification.get('chapters')
    if not isinstance(additions, list) or not additions:
        raise ValueError('registration needs a nonempty chapters array')
    order = specification.get('chapter_order', book.get('chapter_order', 'declared'))
    if order not in ('conventional', 'declared'):
        raise ValueError('chapter_order must be conventional or declared')
    if book.get('chapter_order') == 'conventional' and order == 'declared':
        for chapter in book['chapters']:
            chapter.pop('predecessor_id', None)
    book['chapter_order'] = order
    by_path = {chapter['path']: chapter for chapter in book['chapters']}
    registered = set()
    replace_expected = specification.get('replace_expected', False)
    if type(replace_expected) is not bool:
        raise ValueError('replace_expected must be boolean')
    for claim in additions:
        if not isinstance(claim, dict):
            raise ValueError('expected a chapter object')
        if set(claim) - {'number', 'id', 'display_label', 'path', 'reading_order', 'predecessor_id',
                          'scene_plan_path', 'psych_path', 'report_stem', 'mode'}:
            raise ValueError('unknown chapter registration field')
        if 'mode' in claim and claim['mode'] not in ('narrative', 'expository', 'blended'):
            raise ValueError('chapter mode must be narrative, expository, or blended')
        if 'number' in claim:
            number = claim['number']
            if type(number) is not int or number < 1:
                raise ValueError('chapter number must be a positive integer')
            default_path = f'Chapters/{label}/Chapter-{number:03d}.md'
            default = numbered_chapter(label, number, default_path)
            default.pop('predecessor_id')
            existing = by_path.get(claim.get('path', default_path))
            entry = dict(existing or default, **{key: val for key, val in claim.items() if key != 'number'})
        else:
            if not all(claim.get(key) for key in ('id', 'display_label', 'path')) or 'reading_order' not in claim:
                raise ValueError('custom chapter requires id, display_label, path and reading_order')
            entry = claim
        if not isinstance(entry['path'], str):
            raise ValueError('chapter path must be a relative Markdown path')
        path = Path(entry['path'])
        if path.is_absolute() or '..' in path.parts or path.suffix.lower() != '.md':
            raise ValueError('chapter path must be a relative Markdown path')
        entry = dict(entry, path=path.as_posix())
        registered.add(entry['path'])
        old = by_path.get(entry['path'])
        if old:
            if old['id'] != entry['id']:
                raise ValueError(f"chapter path already belongs to {old['id']}: {entry['path']}")
            if old['reading_order'] != entry['reading_order'] or old.get('display_label') != entry.get('display_label'):
                raise ValueError(f"registered chapter differs from existing authority: {entry['path']}")
            old.update(entry)
        else:
            book['chapters'].append(entry)
            by_path[entry['path']] = entry
    if replace_expected:
        book['chapters'] = [chapter for chapter in book['chapters']
                            if chapter['path'] in registered or contained(root, chapter['path']).is_file()]
    book['chapters'].sort(key=lambda chapter: chapter['reading_order'])
    current['schema_version'] = PLANNED_SCHEMA_VERSION
    return validate(current, root)


HYBRID_MODE_CHECKS = {
    'narrative': ['Gate'],
    'expository': ['FactCheck', 'ClarityEdit'],
    'blended': ['Gate', 'FactCheck', 'ClarityEdit'],
}


def chapter_mode(root, chapter):
    """Resolve explicit chapter mode (narrative|expository|blended) from manifest or file frontmatter."""
    if isinstance(chapter, dict):
        mode = chapter.get('mode')
        if mode in HYBRID_MODE_CHECKS:
            return mode
        rel = chapter.get('path')
        if rel:
            p = contained(root, rel)
            if p.is_file():
                head = p.read_text(encoding='utf-8', errors='replace')[:600]
                m = re.search(r'^[ \t]*(?:chapter_)?mode:[ \t]*["\']?(narrative|expository|blended)\b',
                              head, re.M | re.I)
                if m:
                    return m.group(1).lower()
    return None


def workflow(root, book, required_checks=None, chapter=None):
    """Apply the project type and explicit overrides (and per-chapter HYBRID mode) consistently."""
    instructions = contained(root, 'AGENTS.md')
    project_type = 'FICTION'
    if instructions.is_file():
        declared = [item.upper() for item in re.findall(
            r'^This project is:[ \t]*(?:\*\*)?([A-Z]+)\b',
            instructions.read_text(encoding='utf-8'), re.M | re.I)]
        if declared:
            if len(set(declared)) != 1 or declared[0] not in TYPE_CHECKS:
                raise ValueError('invalid project type declaration in AGENTS.md')
            project_type = declared[0]
    mode = chapter_mode(root, chapter) if project_type == 'HYBRID' and chapter is not None else None
    default_checks = HYBRID_MODE_CHECKS[mode] if mode else list(TYPE_CHECKS[project_type])
    if required_checks is not None:
        required = required_checks
    elif mode and not book.get('required_checks'):
        required = HYBRID_MODE_CHECKS[mode]
    else:
        required = book.get('required_checks', default_checks)
    if not isinstance(required, list) or not required or not all(
            isinstance(name, str) and re.fullmatch(r'[A-Za-z]+', name) for name in required):
        raise ValueError('required_checks must name at least one configured check')
    result = {'project_type': project_type, 'required_checks': list(dict.fromkeys(required))}
    if mode:
        result['chapter_mode'] = mode
    return result


def report_stem(chapter):
    override = chapter.get('report_stem')
    if override is not None:
        if not isinstance(override, str) or not re.fullmatch(r'[\w-]+', override):
            raise ValueError('invalid chapter report_stem')
        return override
    numbered = re.fullmatch(r'Chapter[- ]0*(\d+)', chapter.get('display_label', ''))
    if numbered:
        return f'Chapter-{int(numbered[1]):03}'
    identifier = chapter['id']
    return identifier if re.fullmatch(r'[\w-]+', identifier) else 'chapter-' + _hash(identifier)[:16]


def legacy_report_stem(chapter):
    match = re.search(r'\d+', chapter.get('display_label', ''))
    number = int(match[0]) if match else chapter['reading_order']
    return f'Chapter-{number:03}'


def outline_paths(book):
    label = book.get('display_label', book['id'])
    return [f'Wiki/Outline/{label}/{name}.md' for name in ('outline', 'plan')]


def missing_chapters(root, book):
    missing = [{'label': chapter.get('display_label', chapter['id']), 'path': chapter['path']}
               for chapter in sorted(book['chapters'], key=lambda item: item['reading_order'])
               if not contained(root, chapter['path']).is_file()]
    if book.get('chapter_order') != 'conventional':
        return missing
    orders = sorted({chapter['reading_order'] for chapter in book['chapters']})
    last = orders[-1] if orders else 0
    for name in outline_paths(book):
        path = contained(root, name)
        if path.is_file():
            numbers = re.findall(r'^#{1,3}[ \t]+Chapter[ \t]+(\d+)(?=[ \t:\n]|$)',
                                 path.read_text(encoding='utf-8'), re.M | re.I)
            if numbers:
                last = max(last, max(map(int, numbers)))
    label = book.get('display_label', book['id'])
    for before, after in zip([0, *orders], [*orders, last + 1]):
        if after == before + 2:
            missing.append({'label': f'Chapter {before + 1}', 'path': f'Chapters/{label}/Chapter-{before + 1:03d}.md'})
        elif after > before + 2:
            missing.append({'label': f'Chapters {before + 1} through {after - 1}'})
    return missing


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
    if not matches and allow_new and book.get('chapter_order') == 'conventional':
        match = re.fullmatch(r'(?:Chapter[- ]?)?(\d+)', value, re.I)
        label = book.get('display_label', '')
        if match and int(match[1]) > 0 and re.fullmatch(r'Book-\d+', label):
            number = int(match[1])
            path = f'Chapters/{label}/Chapter-{number:03d}.md'
            if not contained(root, path).exists():
                chapter = numbered_chapter(label, number, path)
                return book, dict(chapter, predecessor_id=predecessor(book, chapter))
    if len(matches) != 1:
        suggestion = '; register planned chapters with register-chapters' if allow_new else ''
        raise ValueError(f'chapter selector is missing or ambiguous in {book_id}: {selector}{suggestion}')
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
