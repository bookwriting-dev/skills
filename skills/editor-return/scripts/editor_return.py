#!/usr/bin/env python3
"""Review an editor's changes in a returned beta DOCX. Only --apply writes chapters."""
import argparse
from collections import Counter
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from xml.etree import ElementTree as ET
import zipfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'beta-feedback/scripts'))
import beta_feedback as beta
import editor_apply
import editor_preview
import revisions

state = beta.state
WORD = revisions.WORD
normal = beta.normal
BODY = 'word/document.xml'
TEXT_PARTS = re.compile(r'word/(document|footnotes|endnotes|header\d*|footer\d*)\.xml')
TYPES = {'ins': 'insert', 'del': 'delete', 'moveFrom': 'move_from', 'moveTo': 'move_to'}
# Content inside a revision that plain before and after text cannot describe.
NON_TEXT = {WORD + tag for tag in (
    'drawing', 'pict', 'object', 'sym', 'noBreakHyphen', 'softHyphen', 'footnoteReference',
    'endnoteReference', 'fldChar', 'fldSimple', 'instrText', 'delInstrText', 'tab', 'br', 'cr')}
STYLES = {WORD + tag for tag in (
    'rStyle', 'b', 'i', 'u', 'strike', 'dstrike', 'vertAlign', 'smallCaps', 'caps', 'highlight', 'color')}
UNSIGNED_REVISIONS = {WORD + 'tblGridChange'}


def local(node):
    return node.tag.rsplit('}', 1)[-1]


def contents_nodes(tree):
    """Elements inside a generated table of contents, which Word rewrites on its own."""
    skipped = set()
    for block in tree.iter(WORD + 'sdt'):
        gallery = block.find(f'{WORD}sdtPr/{WORD}docPartObj/{WORD}docPartGallery')
        if gallery is not None and gallery.get(WORD + 'val') == 'Table of Contents':
            skipped.update(block.iter())
    return skipped


def paragraphs(tree):
    skipped = contents_nodes(tree)
    return [node for node in tree.iter(WORD + 'p') if node not in skipped]


def groups(tree):
    """Join paragraphs across inserted breaks, restoring the paragraphs the editor received."""
    following = {}
    for parent in tree.iter():
        children = [c for c in parent if c.tag in (WORD + 'p', WORD + 'tbl', WORD + 'sdt')]
        following.update(zip(children, children[1:]))
    result, pending = [], []
    for paragraph in paragraphs(tree):
        if pending and following.get(pending[-1]) is not paragraph:
            result.append(pending)
            pending = []
        pending.append(paragraph)
        mark = revisions.paragraph_mark(paragraph)
        if mark is None or mark.tag not in revisions.INSERTED:
            result.append(pending)
            pending = []
    if pending:
        result.append(pending)
    return result


def views(paragraph):
    original, revised = [], []
    for node, wrappers in revisions.walk(paragraph):
        if node.tag in revisions.TEXT:
            if revisions.in_original(wrappers):
                original.append(revisions.value(node))
            if revisions.in_revised(wrappers):
                revised.append(revisions.value(node))
    return ''.join(original), ''.join(revised)


def style(run):
    properties = run.find(WORD + 'rPr')
    return tuple(sorted((local(node), node.get(WORD + 'val') or '')
                        for node in (properties if properties is not None else ()) if node.tag in STYLES))


def check_formatting(change):
    """Markdown cannot show that new text was styled differently from what it joins."""
    styles = change.pop('styles', None)
    if not styles or change['blocked'] or not styles['new']:
        return
    if styles['old'] and len(styles['old'] | styles['new']) > 1:
        change['blocked'] = 'the change crosses formatting or markup, or alters it'
    elif not styles['old'] and (len(styles['new']) > 1 or not styles['new'] <= styles['around']):
        change['blocked'] = 'the inserted text has its own formatting'


def signed(node, kind, before='', after='', offset=0, blocked=None):
    return {'type': kind, 'before': before, 'after': after, 'offset': offset,
            'authors': [node.get(WORD + 'author') or 'Unknown editor'],
            'dates': [d for d in [node.get(WORD + 'date')] if d], 'blocked': blocked}


def paragraph_revisions(paragraph, prefix, consumed):
    """Changes in one paragraph. `prefix` is the original text of earlier joined paragraphs."""
    found = []
    original = prefix
    last = None  # the text change that the next adjacent revision may extend
    previous, waiting = None, []  # style of the preceding text, and changes awaiting the following one
    for node, wrappers in revisions.walk(paragraph):
        offset = len(normal(original + 'x')) - 1
        if node.tag in revisions.INSERTED | revisions.DELETED:
            consumed.add(node)
            if wrappers:
                continue
            inner = list(revisions.walk(node, (node,)))
            before = ''.join(revisions.value(n) for n, w in inner
                             if n.tag in revisions.TEXT and revisions.in_original(w))
            after = ''.join(revisions.value(n) for n, w in inner
                            if n.tag in revisions.TEXT and revisions.in_revised(w))
            blocked = None
            if any(n.tag in revisions.INSERTED | revisions.DELETED for n, _ in inner):
                blocked = 'revisions are nested inside one another'
            elif any(n.tag in NON_TEXT for n, _ in inner):
                blocked = 'the change includes content that is not plain text'
            change = signed(node, TYPES[local(node)], before, after, offset, blocked)
            used = {'new': set(), 'old': set()}
            for n, w in inner:
                if n.tag == WORD + 'r':
                    used['new' if node.tag in revisions.INSERTED else 'old'].add(style(n))
            if change['type'] in ('move_from', 'move_to'):
                change['blocked'] = 'moves are applied by hand'
                found.append(change)
                last = None
            elif last:
                last['before'] += before
                last['after'] += after
                last['blocked'] = last['blocked'] or blocked
                last['type'] = ('replace' if last['before'] and last['after']
                                else 'insert' if last['after'] else 'delete')
                for key in ('new', 'old'):
                    last['styles'][key] |= used[key]
                for key in ('authors', 'dates'):
                    last[key] = list(dict.fromkeys(last[key] + change[key]))
            else:
                change['styles'] = {**used, 'around': {previous}}
                last = change
                found.append(change)
                waiting.append(change)
        elif node.tag in revisions.TEXT and not wrappers:
            original += revisions.value(node)
            last = None
        elif node.tag in revisions.TEXT and revisions.in_original(wrappers):
            original += revisions.value(node)
        elif node.tag == WORD + 'r':
            if not wrappers and any(child.tag in revisions.TEXT for child in node):
                previous = style(node)
                for change in waiting:
                    change['styles']['around'].add(previous)
                waiting = []
            for formatting in node.findall(f'{WORD}rPr/{WORD}rPrChange'):
                consumed.add(formatting)
                text = ''.join(revisions.value(n) for n in node if n.tag in revisions.TEXT)
                found.append(signed(formatting, 'format', text, text, offset,
                                    'formatting changes are applied by hand'))
    for change in found:
        check_formatting(change)
    mark = revisions.paragraph_mark(paragraph)
    if mark is not None:
        consumed.add(mark)
        before, after = views(paragraph)
        if mark.tag in revisions.INSERTED:
            kind = 'paragraph_split' if before.strip() else 'paragraph_insert'
        else:
            kind = 'paragraph_merge' if after.strip() else 'paragraph_delete'
        found.append(signed(mark, kind, before, after, len(normal(prefix + 'x')) - 1,
                            'paragraph breaks are applied by hand'))
    for formatting in paragraph.findall(f'{WORD}pPr/{WORD}pPrChange'):
        consumed.add(formatting)
        text = views(paragraph)[0]
        found.append(signed(formatting, 'format', text, text, len(normal(prefix + 'x')) - 1,
                            'formatting changes are applied by hand'))
    return found


def baseline(tree, version):
    """Non-empty paragraphs of the archived DOCX, each with the chapter it belongs to."""
    sections = {item['bookmark']: item for item in version['sections']}
    passages = version['word_passages']
    result, place = [], None
    for paragraph in paragraphs(tree):
        anchors = [name for name in map(beta.exchange.bookmark_name, paragraph.iter(WORD + 'bookmarkStart'))
                   if name in passages]
        if anchors:
            section = sections[passages[anchors[0]]['section']]
            place = {'chapter_id': section['chapter_id'], 'chapter': section['label'],
                     'path': section['path'], 'source_sha256': section['source_sha256']}
        text = normal(views(paragraph)[0])
        if text:
            result.append({'text': text, 'location': place and {**place, 'passages': anchors}})
    totals = Counter((item['location']['path'], item['text']) for item in result if item['location'])
    seen = Counter()
    for item in result:
        if item['location']:
            key = item['location']['path'], item['text']
            seen[key] += 1
            item['location'] = {**item['location'], 'occurrence': seen[key], 'occurrences': totals[key]}
    return result


def align(old, new):
    """Return ({new index: old index} for identical text, untracked differences)."""
    matcher = SequenceMatcher(None, old, new, autojunk=False)
    matched, differences = {}, []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            matched.update(zip(range(j1, j2), range(i1, i2)))
            continue
        cursor = i1
        for j in range(j1, j2):
            scores = [(SequenceMatcher(None, old[i], new[j], autojunk=False).ratio(), i)
                      for i in range(cursor, i2)]
            score, i = max(scores, key=lambda s: (s[0], -s[1]), default=(0, None))
            if score >= 0.5:
                differences.extend((k, None) for k in range(cursor, i))
                differences.append((i, j))
                cursor = i + 1
            else:
                differences.append((None, j))
        differences.extend((k, None) for k in range(cursor, i2))
    return matched, differences


def read_part(name, returned, archived, version):
    """Changes and untracked differences in one XML part of the returned document."""
    empty = ET.Element(WORD + 'document')
    tree = returned if returned is not None else empty
    old = baseline(archived if archived is not None else empty, version)
    joined = groups(tree) if TEXT_PARTS.fullmatch(name) else []
    texts = [normal(''.join(views(p)[0] for p in group)) for group in joined]
    filled = [index for index, text in enumerate(texts) if text]
    matched, differences = align([item['text'] for item in old], [texts[i] for i in filled])
    matched = {filled[j]: i for j, i in matched.items()}
    untracked, altered, place = [], {}, None
    for i, j in differences:
        group = None if j is None else filled[j]
        location = old[i]['location'] if i is not None else None
        if group is not None:
            altered[group] = location
        untracked.append({'part': name, 'location': location, 'group': group,
                          'before': [] if i is None else [old[i]['text']],
                          'after': [] if group is None else [texts[group]]})
    consumed, changes = set(), []
    tables = {node for table in tree.iter(WORD + 'tbl') for node in table.iter()}
    for index, group in enumerate(joined):
        if index in matched:
            place = old[matched[index]]['location']
        elif index in altered:
            place = altered[index] or place
        for item in untracked:
            if item['group'] == index and item['location'] is None:
                item['location'] = place
        prefix = ''
        revised = normal(''.join(views(p)[1] + (' ' if revisions.paragraph_mark(p) is None else '')
                                 for p in group))
        for paragraph in group:
            for change in paragraph_revisions(paragraph, prefix, consumed):
                reason = change.pop('blocked')
                if not reason and index in altered:
                    reason = 'the paragraph also has untracked edits'
                elif not reason and (len(group) > 1 or any(revisions.paragraph_mark(p) is not None for p in group)):
                    reason = 'the paragraph break changed'
                elif not reason and paragraph in tables:
                    reason = 'table changes are applied by hand'
                elif not reason and name != BODY:
                    reason = 'changes outside the body text are applied by hand'
                elif not reason and (index not in matched or not place):
                    reason = 'the paragraph is not part of an archived chapter'
                changes.append({**change, 'part': name, 'location': place,
                                'paragraph_before': texts[index], 'paragraph_after': revised,
                                'supported': not reason, **({'reason': reason} if reason else {})})
            prefix += views(paragraph)[0]
    for node in tree.iter():
        if node in consumed or local(node) in ('moveFromRangeStart', 'moveToRangeStart'):
            continue
        if node.get(WORD + 'author') is None and node.tag not in UNSIGNED_REVISIONS:
            continue
        changes.append({**signed(node, local(node)), 'blocked': None, 'part': name, 'location': None,
                        'paragraph_before': '', 'paragraph_after': '', 'supported': False,
                        'reason': 'this kind of revision is applied by hand'})
        changes[-1].pop('blocked')
    for item in untracked:
        item.pop('group')
    return changes, untracked


def xml_parts(path):
    with zipfile.ZipFile(path) as archive:
        return {name: ET.fromstring(archive.read(name)) for name in archive.namelist()
                if re.fullmatch(r'word/[^/]+\.xml', name) and not name.startswith(('word/comments', 'word/people'))}


def archived_docx(root, book, edition):
    version, directory = state.editions.open_beta(root, book, edition, with_directory=True)
    if version.get('target_edition'):
        raise ValueError('editor returns need a full beta export, not a changed-scene packet')
    outputs = state.load(state.path_at(root, directory / 'export-manifest.json')).get('outputs', {})
    path = state.path_at(root, directory / 'manuscript-combined.docx')
    expected = outputs.get(path.name)
    if not expected:
        raise ValueError('this beta export has no DOCX; the editor needs a copy exported with --format docx')
    if state.digest(path) != expected:
        raise ValueError('the archived DOCX for this export is missing or changed')
    return version, path


def build(root, book, edition, docx):
    version, source = archived_docx(root, book, edition)
    digest = state.digest(docx)
    returned, archived = xml_parts(docx), xml_parts(source)
    changes, untracked = [], []
    for name in sorted(returned.keys() | archived.keys(), key=lambda n: (n != BODY, n)):
        found, differences = read_part(name, returned.get(name), archived.get(name), version)
        changes.extend(found)
        untracked.extend(differences)
    for number, change in enumerate(changes):
        key = f'{digest}:{number}'.encode()
        changes[number] = {'id': 'EC-' + hashlib.sha256(key).hexdigest()[:16], **change, 'status': 'pending'}
    comments = []
    with zipfile.ZipFile(docx) as archive:
        has_comments = 'word/comments.xml' in archive.namelist()
    if has_comments:
        beta.add_notes(document := {'feedback': comments}, beta.word_notes(docx, edition, version['word_passages']),
                       version)
        comments = document['feedback']
    return {'schema_version': 1, 'export_id': edition, 'docx': docx.name, 'docx_sha256': digest,
            'changes': changes, 'untracked': untracked, 'comments': comments}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--book', default='Book-1')
    parser.add_argument('--docx', required=True, type=Path, help='the DOCX the editor returned')
    parser.add_argument('--export', metavar='ID', help='beta edition ID, needed if its bookmark was lost')
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--preview', action='store_true', help='show the Markdown diff of supported changes')
    action.add_argument('--mark', choices=('accepted', 'rejected', 'pending'), help='record a decision')
    action.add_argument('--apply', metavar='TOKEN', help='write the changes shown by --preview --accepted')
    parser.add_argument('--accepted', action='store_true', help='preview exactly what --apply would write')
    parser.add_argument('--change', action='append', default=[], metavar='ID', help='a change to preview or mark')
    parser.add_argument('--chapter', help='filter for --mark')
    parser.add_argument('--author', help='filter for --mark')
    parser.add_argument('--punctuation-only', action='store_true', help='filter for --mark')
    parser.add_argument('--confirm', metavar='TOKEN', help='record the matches a filter showed')
    args = parser.parse_args()
    if args.change and not (args.preview or args.mark):
        parser.error('--change is used with --preview or --mark')
    if args.accepted and (not args.preview or args.change):
        parser.error('--accepted is used with --preview, without --change')
    if not args.mark and (args.chapter or args.author or args.punctuation_only or args.confirm):
        parser.error('filters and --confirm are used with --mark')
    with zipfile.ZipFile(args.docx) as archive:
        marks = beta.word_edition(ET.fromstring(archive.read(BODY)))
    if args.export and marks and marks != {args.export}:
        raise ValueError('returned DOCX belongs to a different beta export')
    edition = args.export or (next(iter(marks)) if len(marks) == 1 else '')
    if not re.fullmatch(r'[\w-]+', args.book) or not re.fullmatch(r'[a-f0-9]{24}', edition):
        parser.error('pass --export with the ID of the beta export the editor received, and a book identifier')
    root = args.root.resolve()
    resolver = state.project_manifest_module()
    record = resolver.artifact_book(root, args.book)
    ledger = state.path_at(root, resolver.edit_artifact(
        root, record, f'editor-returns/{edition}/{state.digest(args.docx)}.json'))
    extra = {}
    with state.locked(ledger):
        if ledger.exists():
            report = state.load(ledger)
        else:
            report = build(root, args.book, edition, args.docx)
            state.write(ledger, report)
        if args.mark:
            extra['decision'] = editor_apply.decide(
                report, args.mark, ids=args.change, chapter=args.chapter, author=args.author,
                punctuation=args.punctuation_only, confirm=args.confirm)
            if extra['decision']['recorded']:
                state.write(ledger, report)
        elif args.apply:
            extra['applied'] = editor_apply.apply(root, args.book, report, ledger, args.apply)
        elif args.preview:
            extra['preview'] = editor_preview.preview(root, args.book, report, args.change,
                                                      accepted=args.accepted)
    output = {'ledger': ledger.relative_to(root).as_posix(), **report, **extra}
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile, ET.ParseError, subprocess.CalledProcessError) as exc:
        sys.exit(str(exc))
