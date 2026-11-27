"""Place an editor's text changes in current Markdown chapters and show the diff. Writes nothing."""
from difflib import unified_diff
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from xml.etree import ElementTree as ET
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'beta-feedback/scripts'))
import beta_feedback as beta
import revisions

state = beta.state
normal = beta.normal
# Markup that Word text never shows. It may be stepped over, never edited across.
MARKS = set('*_`[]~^')
EQUIVALENTS = {'—': ('---', '—'), '–': ('--', '–'), '…': ('...', '…'),
               '“': ('"', '“'), '”': ('"', '”'), '‘': ("'", '‘'), '’': ("'", '’')}
HIDDEN = (r'<!--.*?-->',
          r'(?ms)^[ \t]*(`{3,}|~{3,})storycraft-internal[ \t]*$.*?^[ \t]*\1[ \t]*$')
UNSEEN = (r'(?<=\])\((?:[^()\n]|\([^()\n]*\))*\)', r'(?<=\])\[[^\]\n]*\]', r'(?<=\])\{[^}\n]*\}',
          r'\[\^[^\]\n]+\]', r'(?m)(?<=[ \t])\{[#.][^}\n]*\}[ \t]*$')
QUOTE = re.compile(r'(?m)^[ \t]*(?:>[ \t]?)+')
BLOCK_PREFIX = re.compile(r'[ \t]*(?:>[ \t]?)*(?:#{1,6}[ \t]+|(?:[-*+]|\d+[.)])[ \t]+)')
LIST_ITEM = re.compile(r'[ \t]*(?:[-*+]|\d+[.)])[ \t]')


def masked(source):
    """Flag every source character that has no counterpart in the Word text."""
    mask = bytearray(len(source))
    for pattern in (*HIDDEN, *UNSEEN):
        flags = re.S if pattern == HIDDEN[0] else 0
        for match in re.finditer(pattern, source, flags):
            mask[match.start():match.end()] = b'\x01' * (match.end() - match.start())
    return mask


def blocks(source, mask, marker):
    """Spans of paragraphs and headings outside fenced blocks."""
    result, start, fence, offset = [], None, None, 0

    def close(end):
        nonlocal start
        if start is not None:
            result.append((start, end))
            start = None

    for line in source.splitlines(keepends=True):
        end = offset + len(line)
        body = line.strip()
        run = re.match(r'(`{3,}|~{3,})', body)
        hidden = bool(mask[offset])
        if fence:
            if run and body == run[1] and run[1].startswith(fence):
                fence = None
        elif run and not hidden:
            close(offset)
            fence = run[1]
        elif not hidden and (not body or body in (marker, '* * *')):
            close(offset)
        elif not hidden and re.match(r'#{1,6}[ \t]', body):
            close(offset)
            result.append((offset, end))
        # A list marker starts a new item only inside a list; elsewhere it is ordinary text.
        elif start is None or LIST_ITEM.match(line) and LIST_ITEM.match(source, start):
            close(offset)
            start = offset
        offset = end
    close(offset)
    return result


def align(source, start, end, mask, rendered):
    """The source span of each rendered character, or None when the block is not that paragraph."""
    prefix = BLOCK_PREFIX.match(source, start, end)
    position = prefix.end() if prefix else start
    spans = []
    index = 0
    while index < len(rendered):
        if position >= end:
            return None
        if mask[position]:
            position += 1
            continue
        wanted = rendered[index]
        found = None
        if wanted == ' ':
            stop = position
            while stop < end and source[stop].isspace() and not mask[stop]:
                stop += 1
            found = stop if stop > position else None
        else:
            for text in EQUIVALENTS.get(wanted, (wanted,)):
                if source.startswith(text, position) and not any(mask[position:position + len(text)]):
                    found = position + len(text)
                    break
        if found is not None:
            spans.append((position, found))
            position = found
            index += 1
        elif (source[position] in MARKS or source[position] == '\\'
              or source[position].isspace() and (not index or rendered[index - 1] == ' ')):
            position += 1
        else:
            return None
    rest = (source[i] for i in range(position, end) if not mask[i])
    return spans if all(c.isspace() or c in MARKS or c in '\\#' for c in rest) else None


def source_range(source, block, mask, spans, first, last):
    """Source offsets for rendered characters [first, last), unless markup makes them unclear."""
    if last > first:
        if any(spans[i][1] != spans[i + 1][0] for i in range(first, last - 1)):
            return None
        return spans[first][0], spans[last - 1][1]
    if 0 < first < len(spans):
        point = spans[first][0]
        return (point, point) if spans[first - 1][1] == point else None
    if first == 0:
        prefix = BLOCK_PREFIX.match(source, *block)
        gap = range(prefix.end() if prefix else block[0], spans[0][0])
        point = spans[0][0]
    else:
        point = spans[-1][1]
        gap = range(point, block[1])
    return (point, point) if all(mask[i] == 0 and source[i].isspace() for i in gap) else None


def house_style(text, visible):
    """Write inserted punctuation the way the chapter already writes it."""
    if sum(map(visible.count, '“”‘’')) <= sum(map(visible.count, '"\'')):
        text = text.translate(str.maketrans('“”‘’', '""\'\''))
    if re.search(r'[^-\n]--|--[^-\n]', visible):
        text = text.replace('—', '---').replace('–', '--')
    if '...' in visible:
        text = text.replace('…', '...')
    return text


def render(markdown):
    """Non-empty Word paragraphs for Markdown, produced the way the beta export produces them."""
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / 'chapter.docx'
        subprocess.run(['pandoc', '--from=markdown', '--standalone', '-o', str(target)],
                       input=markdown, text=True, capture_output=True, check=True)
        with zipfile.ZipFile(target) as archive:
            document = ET.fromstring(archive.read('word/document.xml'))
    texts = (normal(''.join(revisions.value(node) for node, _ in revisions.walk(paragraph)
                            if node.tag in revisions.TEXT))
             for paragraph in document.iter(revisions.WORD + 'p'))
    return [text for text in texts if text]


def spliced(text, edits):
    for start, end, value in sorted(edits, reverse=True):
        text = text[:start] + value + text[end:]
    return text


class Chapter:
    def __init__(self, source, name, marker):
        self.source, self.name, self.marker = source, name, marker
        self.mask = masked(source)
        self.blocks = blocks(source, self.mask, marker)
        for start, end in self.blocks:
            # ">" marks a quotation only when it opens the block; later it can be literal text.
            if source[start:end].lstrip().startswith('>'):
                for match in QUOTE.finditer(source, start, end):
                    self.mask[match.start():match.end()] = b'\x01' * len(match[0])
        self.visible = self.read(source)
        self.rendered = render(self.visible)

    def read(self, source):
        lines = state.chapter_format_module().comment_lines(source, self.marker)
        return state.reader_text_module().extract(
            source, source=self.name, scene_break=self.marker, pov_comment_lines=lines)['text']

    def locate(self, paragraph, location, unchanged):
        """The block holding this paragraph and the index of its rendered counterpart."""
        found = [(block, spans) for block in self.blocks
                 if (spans := align(self.source, *block, self.mask, paragraph))]
        if not found:
            raise ValueError('the paragraph is not in the current chapter, or its markup is not supported')
        count, occurrence = location.get('occurrences'), location.get('occurrence')
        if len(found) == 1 and count == 1:
            choice = 0
        elif unchanged and len(found) == count:
            choice = occurrence - 1
        else:
            raise ValueError('the paragraph appears more than once and the copies cannot be told apart')
        matches = [i for i, text in enumerate(self.rendered) if text == paragraph]
        if len(matches) != len(found):
            raise ValueError('the paragraph could not be matched to the current chapter')
        return (*found[choice], matches[choice])

    def verified(self, edits):
        """The edited source if it reads exactly as the editor's changes say it should."""
        source = spliced(self.source, [(*e['source'], e['value']) for e in edits])
        expected = list(self.rendered)
        for index in {e['index'] for e in edits}:
            mine = [(*e['rendered'], e['after']) for e in edits if e['index'] == index]
            expected[index] = normal(spliced(self.rendered[index], mine))
        try:
            actual = render(self.read(source))
        except ValueError:
            return None
        self.expected = [text for text in expected if text]
        return source if actual == self.expected else None


def plan(chapter, changes, unchanged):
    """Candidate source edits for one chapter, and the changes that cannot be placed."""
    edits, manual = [], []
    for change in changes:
        try:
            paragraph = change['paragraph_before']
            block, spans, index = chapter.locate(paragraph, change['location'], unchanged)
            first = change['offset']
            before = re.sub(r'\s', ' ', change['before'])
            last = first + len(before)
            if paragraph[first:last] != before:
                raise ValueError('unusual spacing prevents an exact match')
            where = source_range(chapter.source, block, chapter.mask, spans, first, last)
            if where is None:
                raise ValueError('the change touches or crosses markup')
            if any(e['index'] == index and first <= e['rendered'][1] and e['rendered'][0] <= last
                   for e in edits):
                raise ValueError('the change overlaps another change')
            start, end = where
            if (not change['after'] and chapter.source[:start].endswith(('[', *MARKS))
                    and chapter.source[end:].startswith((']', *MARKS))):
                raise ValueError('deleting this text would leave empty markup behind')
            if not normal(spliced(paragraph, [(first, last, change['after'])])):
                raise ValueError('the change would empty the paragraph')
            edits.append({'id': change['id'], 'index': index, 'rendered': (first, last), 'source': where,
                          'after': change['after'], 'value': house_style(change['after'], chapter.visible)})
        except ValueError as exc:
            manual.append((change['id'], str(exc)))
    return edits, manual


def settle(chapter, edits):
    """Verify together; if that fails, find which edits hold up, escaping Markdown when needed."""
    source = chapter.verified(edits)
    if source is not None:
        return source, edits, []
    good, bad = [], []
    for edit in edits:
        escaped = dict(edit, value=re.sub(r'([\\`*_{}\[\]<>#~^$|@])', r'\\\1', edit['value']))
        passing = next((e for e in (edit, escaped) if chapter.verified([e]) is not None), None)
        (good if passing else bad).append(passing or edit)
    source = chapter.verified(good)
    if source is None:
        bad, good = bad + good, []
    return source, good, [(e['id'], 'the edited Markdown would not read as the editor intended') for e in bad]


def paragraph_key(change):
    return (change['part'], change['location']['path'], change['location'].get('occurrence'),
            change['paragraph_before'])


def rebased(change, applied):
    """Restate a change against its paragraph after earlier changes there were written."""
    earlier = [a for a in applied if paragraph_key(a) == paragraph_key(change)]
    if not earlier:
        return change
    edits = [(a['offset'], a['offset'] + len(a['before']), a['after']) for a in earlier]
    shift = sum(len(a['after']) - len(a['before']) for a in earlier if a['offset'] < change['offset'])
    return {**change, 'paragraph_before': normal(spliced(change['paragraph_before'], edits)),
            'offset': change['offset'] + shift,
            # The paragraph now reads differently, so only a unique match will do.
            'location': {**change['location'], 'occurrence': 1, 'occurrences': 1}}


def propose(root, book, report, selected=(), *, accepted=False):
    """Edited chapters for the chosen changes. Accepted changes go into a chapter all together."""
    known = {change['id'] for change in report['changes']}
    if unknown := [identifier for identifier in selected if identifier not in known]:
        raise ValueError('unknown change: ' + ', '.join(unknown))
    record = state.project_manifest_module().resolve_book(root, book)
    marker = record.get('chapter_format', {}).get('scene_break', '* * *')
    paths = {chapter['id']: chapter['path'] for chapter in record['chapters']}
    manual, grouped, held = [], {}, set()

    def skip(identifier, path, reason):
        manual.append({'id': identifier, 'path': path, 'reason': reason})

    applied = [c for c in report['changes'] if c['status'] == 'applied']
    wanted = ('accepted',) if accepted else ('pending', 'accepted')
    for change in report['changes']:
        if change['status'] not in wanted or selected and change['id'] not in selected:
            continue
        location = change.get('location') or {}
        if not change['supported']:
            skip(change['id'], location.get('path'), change['reason'])
        elif 'occurrence' not in location:
            skip(change['id'], location.get('path'), 'this saved report predates previews; remove it and import again')
        else:
            grouped.setdefault(location['chapter_id'], []).append(rebased(change, applied))
    files = []
    for chapter_id, changes in grouped.items():
        name = paths.get(chapter_id)
        try:
            if not name or not state.path_at(root, name).is_file():
                raise ValueError('the chapter is no longer in the book')
            raw = state.path_at(root, name).read_bytes()
            chapter = Chapter(raw.decode('utf-8'), name, marker)
        except ValueError as exc:
            for change in changes:
                skip(change['id'], name, str(exc))
            continue
        altered = hashlib.sha256(raw).hexdigest() != changes[0]['location']['source_sha256']
        edits, failed = plan(chapter, changes, not altered)
        source, edits, rejected = settle(chapter, edits) if edits else (None, [], [])
        for identifier, reason in failed + rejected:
            skip(identifier, name, reason)
        if accepted and (failed or rejected):
            for edit in edits:
                skip(edit['id'], name, 'held back: another accepted change in this chapter cannot be placed')
            held.add(name)
        elif edits:
            diff = unified_diff(chapter.source.splitlines(), source.splitlines(), name, name, lineterm='')
            files.append({'path': name, 'changed_since_export': altered, 'changes': [e['id'] for e in edits],
                          'diff': '\n'.join(diff), 'before': raw, 'after': source.encode('utf-8'),
                          'chapter': chapter, 'expected': chapter.expected})
    token = None
    if accepted and files:
        shown = [(f['path'], f['changes'], hashlib.sha256(f['before']).hexdigest(),
                  hashlib.sha256(f['after']).hexdigest()) for f in files]
        token = hashlib.sha256(json.dumps(shown).encode()).hexdigest()[:16]
    return {'files': files, 'manual': manual, 'token': token}


def preview(root, book, report, selected=(), *, accepted=False):
    proposal = propose(root, book, report, selected, accepted=accepted)
    shown = ('path', 'changed_since_export', 'changes', 'diff')
    return {'files': [{key: item[key] for key in shown} for item in proposal['files']],
            'manual': proposal['manual'], **({'apply_token': proposal['token']} if proposal['token'] else {})}
