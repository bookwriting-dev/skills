#!/usr/bin/env python3
"""Return real beta DOCX exports with editor revisions and read them back."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from xml.etree import ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BETA = ROOT / 'skills/beta-feedback/scripts/beta_feedback.py'
RETURN = ROOT / 'skills/editor-return/scripts/editor_return.py'
MCP_SERVER = ROOT / 'mcp/storycraft_mcp.py'
EXPORT = ROOT / 'skills/compile-manuscript/scripts/compile_manuscript.py'
NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
W = '{' + NS + '}'


def element(tag, **attributes):
    return ET.Element(W + tag, {W + key: value for key, value in attributes.items()})


def revision(tag, *children, author='Ed'):
    node = element(tag, id='90', author=author, date='2026-11-27T00:00:00Z')
    node.extend(children)
    return node


def run(text, tag='t'):
    node = element('r')
    child = element(tag)
    child.text = text
    child.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    node.append(child)
    return node


def ins(text, **kw):
    return revision('ins', run(text), **kw)


def delete(text, **kw):
    return revision('del', run(text, 'delText'), **kw)


def text_of(paragraph):
    return ''.join(node.text or '' for node in paragraph.iter(W + 't'))


def find(tree, text):
    matches = [p for p in tree.iter(W + 'p') if text in text_of(p)]
    assert len(matches) == 1, (text, len(matches))
    return matches[0]


def rewrite(paragraph, *nodes):
    """Replace a paragraph's runs, keeping its properties and bookmarks."""
    keep = {W + 'pPr', W + 'bookmarkStart', W + 'bookmarkEnd'}
    for child in list(paragraph):
        if child.tag not in keep:
            paragraph.remove(child)
    paragraph.extend(nodes)


def mark(paragraph, tag):
    properties = paragraph.find(W + 'pPr')
    if properties is None:
        properties = element('pPr')
        paragraph.insert(0, properties)
    run_properties = element('rPr')
    run_properties.append(revision(tag))
    properties.append(run_properties)


def parent_of(tree, node):
    return next(p for p in tree.iter() if node in list(p))


def track(paragraph, *edits, inserted_style=None):
    """Mark (prefix, old, new) replacements as tracked changes, keeping each character's formatting."""
    for link in paragraph.findall(W + 'hyperlink'):  # keep a link's text in the rewritten runs
        position = list(paragraph).index(link)
        paragraph.remove(link)
        for offset, child in enumerate(link):
            paragraph.insert(position + offset, child)
    characters = [(char, node.find(W + 'rPr')) for node in paragraph.findall(W + 'r')
                  for char in ''.join(t.text or '' for t in node.findall(W + 't'))]
    text = ''.join(char for char, _ in characters)

    def runs(span, tag='t'):
        grouped = []
        for char, properties in span:
            if grouped and grouped[-1][1] is properties:
                grouped[-1][0].append(char)
            else:
                grouped.append(([char], properties))
        nodes = []
        for chars, properties in grouped:
            node = run(''.join(chars), tag)
            if properties is not None:
                node.insert(0, properties)
            nodes.append(node)
        return nodes

    spans = []
    for prefix, old, new in edits:
        assert text.count(prefix + old) == 1, (text, prefix + old)
        start = text.index(prefix + old) + len(prefix)
        spans.append((start, start + len(old), new))
    nodes, cursor = [], 0
    for start, end, new in sorted(spans):
        nodes.extend(runs(characters[cursor:start]))
        if end > start:
            nodes.append(revision('del', *runs(characters[start:end], 'delText')))
        if new:
            style = characters[start if end > start else max(start - 1, 0)][1]
            if inserted_style is not None:
                style = inserted_style
            nodes.append(revision('ins', *runs([(c, style) for c in new])))
        cursor = end
    rewrite(paragraph, *nodes, *runs(characters[cursor:]))


@unittest.skipUnless(shutil.which('pandoc'), 'Pandoc is required to export a real DOCX')
class ReturnedExport(unittest.TestCase):
    PARAGRAPHS = ('Clara locked the old door.', 'Nell took the brass key.',
                  'The sisters washed dishes.[^1]\n\n```\nSTATUS: tired\n```\n\n[^1]: A chipped bowl.')

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.chapters = []
        for index, text in enumerate(self.PARAGRAPHS, 1):
            chapter = self.root / f'Chapters/Book-1/Chapter-{index:03}.md'
            chapter.parent.mkdir(parents=True, exist_ok=True)
            chapter.write_text(f'# Chapter {index}\n\n{text}\n')
            self.chapters.append(chapter)
        self.edition = self.cli(EXPORT, '--format', 'docx')['beta_feedback']['export_id']
        self.frozen = self.root / 'Chapters/Book-1/export/beta/manuscript-combined.docx'

    def cli(self, script, *args, fail=False):
        completed = subprocess.run([sys.executable, '-B', str(script), '--root', str(self.root), *args],
                                   capture_output=True, text=True)
        if fail:
            self.assertNotEqual(completed.returncode, 0, completed.stdout)
            return completed.stderr
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout)

    def returned(self, edit=None, *, name='returned.docx', parts=None, add=None):
        """edit(tree) changes the body; parts maps other XML part names to their editors."""
        editors = dict(parts or {})
        if edit:
            editors['word/document.xml'] = edit
        target = self.root / name
        with zipfile.ZipFile(self.frozen) as source, zipfile.ZipFile(target, 'w') as out:
            for info in source.infolist():
                if info.filename in (add or {}):
                    continue
                data = source.read(info)
                if info.filename in editors:
                    tree = ET.fromstring(data)
                    editors[info.filename](tree)
                    data = ET.tostring(tree)
                out.writestr(info, data)
            for filename, data in (add or {}).items():
                out.writestr(filename, data)
        return target

    def read(self, docx, *args):
        return self.cli(RETURN, '--docx', str(docx), *args)


class EditorReturn(ReturnedExport):
    def test_unchanged_return_reports_nothing(self):
        report = self.read(self.returned())
        self.assertEqual((report['changes'], report['untracked'], report['comments']), ([], [], []))

    def test_text_changes_are_listed_by_chapter_without_touching_prose(self):
        def edit(tree):
            rewrite(find(tree, 'Clara'), run('Clara '), delete('locked'), ins('bolted'),
                    run(' the '), delete('old '), run('door.'))
            rewrite(find(tree, 'Nell'), run('Nell took the '), ins('small '), run('brass key.'))

        before = [p.read_text() for p in self.chapters]
        docx = self.returned(edit)
        report = self.read(docx)
        self.assertEqual([(c['type'], c['before'], c['after'], c['supported']) for c in report['changes']],
                         [('replace', 'locked', 'bolted', True), ('delete', 'old ', '', True),
                          ('insert', '', 'small ', True)])
        first, _, last = report['changes']
        self.assertEqual(first['location']['path'], 'Chapters/Book-1/Chapter-001.md')
        self.assertEqual(last['location']['path'], 'Chapters/Book-1/Chapter-002.md')
        self.assertEqual(first['paragraph_before'], 'Clara locked the old door.')
        self.assertEqual(first['paragraph_after'], 'Clara bolted the door.')
        self.assertEqual(first['offset'], len('Clara '))
        self.assertEqual(first['authors'], ['Ed'])
        self.assertEqual({c['status'] for c in report['changes']}, {'pending'})
        self.assertEqual(len({c['id'] for c in report['changes']}), 3)
        self.assertEqual(report['untracked'], [])
        self.assertEqual([p.read_text() for p in self.chapters], before)
        ledger = self.root / report['ledger']
        saved = json.loads(ledger.read_text())
        saved['changes'][0]['status'] = 'accepted'
        ledger.write_text(json.dumps(saved))
        self.assertEqual(self.read(docx)['changes'][0]['status'], 'accepted')

    def test_edits_made_with_tracking_off_are_caught(self):
        def edit(tree):
            rewrite(find(tree, 'Clara'), run('Clara barred the old door.'))
            removed = find(tree, 'Nell')
            parent_of(tree, removed).remove(removed)
            dishes = find(tree, 'sisters')
            parent = parent_of(tree, dishes)
            added = element('p')
            added.append(run('A new quiet line.'))
            parent.insert(list(parent).index(dishes) + 1, added)

        report = self.read(self.returned(edit))
        self.assertEqual(report['changes'], [])
        found = [(u['before'], u['after']) for u in report['untracked']]
        self.assertIn((['Clara locked the old door.'], ['Clara barred the old door.']), found)
        self.assertIn((['Nell took the brass key.'], []), found)
        self.assertIn(([], ['A new quiet line.']), found)
        self.assertEqual(len(found), 3)

    def test_untracked_text_beside_a_tracked_change_blocks_that_change(self):
        def edit(tree):
            rewrite(find(tree, 'Clara'), run('Clara barred the '), ins('very '), run('old door.'))

        report = self.read(self.returned(edit))
        self.assertEqual(len(report['untracked']), 1)
        self.assertFalse(report['changes'][0]['supported'])
        self.assertIn('untracked', report['changes'][0]['reason'])

    def test_structural_revisions_are_listed_as_manual(self):
        def edit(tree):
            first = find(tree, 'Clara')
            rewrite(first, revision('moveFrom', run('Clara locked the old door.')))
            second = find(tree, 'Nell')
            formatted = run('Nell took the brass key.')
            properties = element('rPr')
            properties.extend([element('i'), revision('rPrChange', element('rPr'))])
            formatted.insert(0, properties)
            rewrite(second, formatted, revision('customXmlInsRangeStart'))
            parent = parent_of(tree, second)
            moved = element('p')
            moved.append(revision('moveTo', run('Clara locked the old door.')))
            mark(moved, 'ins')
            parent.insert(list(parent).index(second) + 1, moved)

        report = self.read(self.returned(edit))
        kinds = sorted(c['type'] for c in report['changes'])
        self.assertEqual(kinds, ['customXmlInsRangeStart', 'format', 'move_from', 'move_to',
                                 'paragraph_insert'])
        self.assertFalse(any(c['supported'] for c in report['changes']))
        self.assertTrue(all(c['reason'] for c in report['changes']))
        self.assertEqual(report['untracked'], [])

    def test_split_and_merged_paragraphs_still_match_the_original(self):
        def edit(tree):
            first = find(tree, 'Clara')
            parent = parent_of(tree, first)
            head = element('p')
            head.append(run('Clara locked '))
            mark(head, 'ins')
            parent.insert(list(parent).index(first), head)
            rewrite(first, run('the old door.'))
            mark(find(tree, 'Nell'), 'del')

        report = self.read(self.returned(edit))
        self.assertEqual(report['untracked'], [])
        self.assertEqual(sorted(c['type'] for c in report['changes']),
                         ['paragraph_merge', 'paragraph_split'])

    def test_text_change_in_a_split_paragraph_is_manual(self):
        def edit(tree):
            first = find(tree, 'Clara')
            parent = parent_of(tree, first)
            head = element('p')
            head.extend([run('Clara '), delete('locked'), ins('bolted'), run(' ')])
            mark(head, 'ins')
            parent.insert(list(parent).index(first), head)
            rewrite(first, run('the old door.'))

        report = self.read(self.returned(edit))
        self.assertEqual(report['untracked'], [])
        self.assertFalse(any(c['supported'] for c in report['changes']))

    def test_footnote_changes_are_listed(self):
        def edit(tree):
            note = find(tree, 'chipped')
            for child in list(note.iter(W + 't')):
                if 'chipped' in child.text:
                    child.text = child.text.replace('chipped', 'cracked')

        report = self.read(self.returned(parts={'word/footnotes.xml': edit}))
        self.assertEqual(len(report['untracked']), 1)
        self.assertEqual(report['untracked'][0]['part'], 'word/footnotes.xml')

    def commented(self, *nodes):
        def edit(tree):
            start = element('commentRangeStart', id='0')
            end = element('commentRangeEnd', id='0')
            rewrite(find(tree, 'Clara'), start, *nodes, end)

        comments = element('comments')
        comment = element('comment', id='0', author='Ed')
        paragraph = element('p')
        paragraph.append(run('Stronger verb?'))
        comment.append(paragraph)
        comments.append(comment)
        return self.returned(edit, add={'word/comments.xml': ET.tostring(comments)})

    def test_comment_on_changed_text_anchors_to_the_original(self):
        docx = self.commented(run('Clara '), delete('locked'), ins('bolted'), run(' the old door.'))
        for report, notes in ((self.cli(BETA, '--docx', str(docx)), 'feedback'),
                              (self.read(docx), 'comments')):
            note = report[notes][0]
            self.assertEqual(note['location']['status'], 'ANCHORED', note['location'])
            self.assertEqual(note['quote'], 'Clara locked the old door.')
            self.assertEqual(note['revised_quote'], 'Clara bolted the old door.')

    def test_comment_on_untouched_text_keeps_its_earlier_shape(self):
        note = self.cli(BETA, '--docx', str(self.commented(run('Clara locked the old door.'))))['feedback'][0]
        self.assertEqual(note['location']['status'], 'ANCHORED')
        self.assertNotIn('revised_quote', note)

    def test_lost_bookmarks_need_the_export_id_and_wrong_ids_conflict(self):
        def strip(tree):
            for parent in list(tree.iter()):
                for child in list(parent):
                    if child.tag in (W + 'bookmarkStart', W + 'bookmarkEnd'):
                        parent.remove(child)
            rewrite(find(tree, 'Clara'), run('Clara locked the '), delete('old '), run('door.'))

        docx = self.returned(strip)
        self.assertIn('--export', self.cli(RETURN, '--docx', str(docx), fail=True))
        report = self.read(docx, '--export', self.edition)
        self.assertEqual(report['changes'][0]['location']['path'], 'Chapters/Book-1/Chapter-001.md')
        self.assertTrue(report['changes'][0]['supported'])
        other = self.cli(RETURN, '--docx', str(self.returned(name='ok.docx')), '--export', 'a' * 24, fail=True)
        self.assertIn('different beta export', other)

    def test_a_changed_archive_is_refused(self):
        docx = self.returned()
        copy = self.root / 'copy.docx'
        shutil.copyfile(docx, copy)
        with zipfile.ZipFile(self.frozen, 'a') as archive:
            archive.writestr('extra.txt', 'changed')
        self.assertIn('archived DOCX', self.cli(RETURN, '--docx', str(copy), fail=True))


class EditorPreview(ReturnedExport):
    PARAGRAPHS = (
        '"Clara locked the *old* door," Nell said -- twice, and didn\'t wait...',
        'He waited.\n\nNell took the <!-- STORYCRAFT: check metal --> brass key\n'
        'from the tin box.\n\nHe waited.',
        '> The “quoted” letter said — nothing.\n\n## A **late** hour')

    def preview(self, docx, *args):
        before = [p.read_bytes() for p in self.chapters]
        result = self.read(docx, '--preview', *args)['preview']
        self.assertEqual([p.read_bytes() for p in self.chapters], before)
        return result

    def tracked(self, *paragraph_edits, **options):
        """Each entry is (text identifying the paragraph, occurrence, *edits)."""
        def edit(tree):
            targets = []
            for containing, occurrence, *edits in paragraph_edits:
                matches = [p for p in tree.iter(W + 'p') if containing in text_of(p)]
                targets.append((matches[occurrence], edits))
            for paragraph, edits in targets:
                track(paragraph, *edits, **options)
        return self.returned(edit)

    def added(self, result):
        return [line[1:] for item in result['files'] for line in item['diff'].splitlines()
                if line.startswith('+') and not line.startswith('+++')]

    def test_source_punctuation_and_emphasis_are_kept(self):
        result = self.preview(self.tracked(
            ('Clara', 0, ('Clara ', 'locked', 'bolted'), ('the ', 'old', 'ancient'),
             ('said – ', 'twice', 'once'), ('and ', 'didn’t', 'wouldn’t'), ('wait', '…', ' — ever…'))))
        self.assertEqual(result['manual'], [])
        self.assertEqual(self.added(result),
                         ['"Clara bolted the *ancient* door," Nell said -- once, and wouldn\'t wait --- ever...'])
        self.assertEqual(len(result['files'][0]['changes']), 5)

    def test_edits_at_or_across_markup_are_manual(self):
        result = self.preview(self.tracked(
            ('Clara', 0, ('locked ', 'the old', 'an'), ('said', '', ' softly')),
            ('brass', 0, ('the ', 'brass', 'iron'))))
        self.assertEqual(len(result['manual']), 1)
        self.assertIn('markup', result['manual'][0]['reason'])
        joined = '\n'.join(self.added(result))
        self.assertIn('Nell said softly --', joined)
        self.assertIn('the *old* door', joined)
        self.assertIn('<!-- STORYCRAFT: check metal --> iron key', joined)

    def test_insertion_beside_emphasis_and_across_a_private_comment_are_manual(self):
        result = self.preview(self.tracked(('Clara', 0, ('the ', '', 'very ')),
                                           ('brass', 0, ('took ', 'the brass', 'a'))))
        self.assertEqual((result['files'], len(result['manual'])), ([], 2))

    def test_the_right_repeated_paragraph_changes(self):
        docx = self.tracked(('He waited', 1, ('He ', 'waited', 'left')))
        result = self.preview(docx)
        self.assertEqual(result['manual'], [])
        diff = result['files'][0]['diff']
        self.assertLess(diff.index('tin box'), diff.index('+He left.'))
        self.assertEqual(self.added(result), ['He left.'])
        chapter = self.chapters[1]
        chapter.write_text(chapter.read_text() + '\nA new ending.\n')
        stale = self.preview(docx)
        self.assertEqual(stale['files'], [])
        self.assertIn('more than once', stale['manual'][0]['reason'])

    def test_a_changed_chapter_keeps_unique_paragraphs_and_refuses_rewritten_ones(self):
        docx = self.tracked(('Clara', 0, ('Clara ', 'locked', 'bolted')),
                            ('brass', 0, ('the ', 'brass', 'iron')))
        first, second = self.chapters[:2]
        first.write_text(first.read_text().replace('twice', 'thrice'))
        second.write_text(second.read_text() + '\nA new ending.\n')
        result = self.preview(docx)
        self.assertEqual([f['path'] for f in result['files']], ['Chapters/Book-1/Chapter-002.md'])
        self.assertTrue(result['files'][0]['changed_since_export'])
        self.assertEqual(self.added(result), ['Nell took the <!-- STORYCRAFT: check metal --> iron key'])
        self.assertIn('current chapter', result['manual'][0]['reason'])

    def test_curly_style_blockquotes_and_headings(self):
        result = self.preview(self.tracked(
            ('letter', 0, ('The “', 'quoted', 'sealed’s'), ('said ', '—', '–')),
            ('hour', 0, ('A ', 'late', 'quiet'))))
        self.assertEqual(result['manual'], [])
        self.assertEqual(self.added(result), ['> The “sealed’s” letter said – nothing.', '## A **quiet** hour'])

    def test_list_items_links_and_a_quote_mark_inside_a_paragraph(self):
        chapter = self.chapters[2]
        chapter.write_text('# Chapter 3\n\n1. **First:** open the [tin box](https://example.com/box).\n'
                           '2. Second, wash the bowl.\n\nShe said this:\n> "Stay," he wrote.\n')
        self.cli(EXPORT, '--format', 'docx')
        exports = self.root / 'Chapters/Book-1/export/beta'
        self.frozen = exports / 'manuscript-combined.docx'
        result = self.preview(self.tracked(('First', 0, ('the tin ', 'box', 'chest')),
                                           ('Second', 0, ('wash the ', 'bowl', 'cup')),
                                           ('She said', 0, ('he ', 'wrote', 'begged'))))
        self.assertEqual(result['manual'], [])
        self.assertEqual(self.added(result), [
            '1. **First:** open the [tin chest](https://example.com/box).',
            '2. Second, wash the cup.', '> "Stay," he begged.'])

    def test_deleting_all_of_a_links_text_is_manual(self):
        chapter = self.chapters[2]
        chapter.write_text('# Chapter 3\n\nOpen the [box](https://example.com/box) now.\n')
        self.cli(EXPORT, '--format', 'docx')
        self.frozen = self.root / 'Chapters/Book-1/export/beta/manuscript-combined.docx'
        result = self.preview(self.tracked(('Open', 0, ('the ', 'box', ''))))
        self.assertEqual(result['files'], [])
        self.assertIn('markup', result['manual'][0]['reason'])

    def test_inserted_markdown_characters_stay_literal(self):
        result = self.preview(self.tracked(('Clara', 0, ('door,', '', ' [*sic*]'))))
        self.assertEqual(result['manual'], [])
        self.assertIn('\\*sic\\*', self.added(result)[0])

    def test_inserted_text_with_its_own_formatting_is_manual(self):
        italic = element('rPr')
        italic.append(element('i'))
        docx = self.tracked(('Clara', 0, ('Clara ', 'locked', 'bolted')), inserted_style=italic)
        result = self.preview(docx)
        self.assertEqual(result['files'], [])
        self.assertIn('formatting', result['manual'][0]['reason'])

    def test_selected_and_rejected_changes(self):
        docx = self.tracked(('Clara', 0, ('Clara ', 'locked', 'bolted'), ('said – ', 'twice', 'once')))
        report = self.read(docx)
        first, second = report['changes']
        chosen = self.preview(docx, '--change', second['id'])
        self.assertEqual(chosen['files'][0]['changes'], [second['id']])
        self.assertIn('locked', self.added(chosen)[0])
        self.assertIn('unknown change', self.cli(RETURN, '--docx', str(docx), '--preview',
                                                 '--change', 'EC-none', fail=True))
        ledger = self.root / report['ledger']
        saved = json.loads(ledger.read_text())
        saved['changes'][0]['status'] = 'rejected'
        ledger.write_text(json.dumps(saved))
        self.assertEqual(self.preview(docx)['files'][0]['changes'], [second['id']])


class EditorApply(ReturnedExport):
    PARAGRAPHS = ('"Clara locked the old door," Nell said, and waited.', 'Nell took the brass key.',
                  'The sisters washed dishes.')

    def sample(self):
        """Two wording changes and a comma in Chapter 1; one wording change in Chapter 2."""
        def edit(tree):
            track(find(tree, 'Clara'), ('Clara ', 'locked', 'bolted'), ('said', ',', ';'),
                  ('and ', 'waited', 'left'))
            track(find(tree, 'brass'), ('the ', 'brass', 'iron'))
        self.docx = self.returned(edit)
        report = self.read(self.docx)
        self.ledger = self.root / report['ledger']
        return {change['after']: change['id'] for change in report['changes']}

    def run_return(self, *args, **options):
        return self.cli(RETURN, '--docx', str(self.docx), *args, **options)

    def mark(self, status, *ids):
        return self.run_return('--mark', status, *[a for i in ids for a in ('--change', i)])['decision']

    def proposal(self):
        return self.run_return('--preview', '--accepted')['preview']

    def apply(self):
        return self.run_return('--apply', self.proposal()['apply_token'])['applied']

    def contents(self):
        return [path.read_bytes() for path in self.chapters]

    def statuses(self):
        return {c['after']: c['status'] for c in json.loads(self.ledger.read_text())['changes']}

    def test_accepting_nothing_writes_nothing(self):
        self.sample()
        before = self.contents()
        proposal = self.proposal()
        self.assertEqual((proposal['files'], proposal.get('apply_token')), ([], None))
        self.assertIn('do not match', self.run_return('--apply', 'nothing', fail=True))
        self.assertEqual(self.contents(), before)
        self.assertEqual(set(self.statuses().values()), {'pending'})

    def test_filters_show_matches_before_recording_them(self):
        self.sample()
        shown = self.run_return('--mark', 'accepted', '--punctuation-only', '--chapter', 'Chapter 1')['decision']
        self.assertFalse(shown['recorded'])
        self.assertEqual([c['after'] for c in shown['changes']], [';'])
        self.assertEqual(set(self.statuses().values()), {'pending'})
        self.run_return('--mark', 'accepted', '--chapter', 'Chapter 1', '--confirm', shown['confirm'], fail=True)
        self.assertEqual(set(self.statuses().values()), {'pending'})
        saved = self.run_return('--mark', 'accepted', '--punctuation-only', '--chapter', 'Chapter 1',
                                '--confirm', shown['confirm'])['decision']
        self.assertTrue(saved['recorded'])
        self.assertEqual(self.statuses(), {'bolted': 'pending', ';': 'accepted', 'left': 'pending',
                                           'iron': 'pending'})
        other = self.run_return('--mark', 'rejected', '--author', 'Someone else')['decision']
        self.assertEqual(other['changes'], [])

    def test_all_accepted_changes_are_written_exactly_with_a_copy_kept(self):
        self.sample()
        before = self.contents()
        shown = self.run_return('--mark', 'accepted', '--author', 'Ed')['decision']
        self.run_return('--mark', 'accepted', '--author', 'Ed', '--confirm', shown['confirm'])
        applied = self.apply()
        self.assertEqual(self.chapters[0].read_text(),
                         '# Chapter 1\n\n"Clara bolted the old door," Nell said; and left.\n')
        self.assertEqual(self.chapters[1].read_text(), '# Chapter 2\n\nNell took the iron key.\n')
        self.assertEqual(self.contents()[2], before[2])
        self.assertEqual([(self.root / f['backup']).read_bytes() for f in applied['written']], before[:2])
        self.assertEqual(set(self.statuses().values()), {'applied'})
        self.assertEqual(self.proposal()['files'], [])
        self.assertIn('already applied', self.run_return(
            '--mark', 'rejected', '--change', self.read(self.docx)['changes'][0]['id'], fail=True))

    def test_rejected_changes_stay_out_and_later_changes_can_follow(self):
        ids = self.sample()
        self.mark('accepted', ids['bolted'])
        self.mark('rejected', ids['iron'])
        self.apply()
        self.assertIn('"Clara bolted the old door," Nell said, and waited.', self.chapters[0].read_text())
        self.assertIn('brass', self.chapters[1].read_text())
        self.mark('accepted', ids['left'])
        self.apply()
        self.assertIn('"Clara bolted the old door," Nell said, and left.', self.chapters[0].read_text())

    def test_a_chapter_changed_after_the_preview_is_refused(self):
        ids = self.sample()
        self.mark('accepted', ids['bolted'], ids['iron'])
        token = self.proposal()['apply_token']
        self.chapters[0].write_text(self.chapters[0].read_text() + '\nA new ending.\n')
        before = self.contents()
        self.assertIn('do not match', self.run_return('--apply', token, fail=True))
        self.assertEqual(self.contents(), before)

    def test_one_unplaceable_change_holds_back_its_whole_chapter(self):
        ids = self.sample()
        self.mark('accepted', *ids.values())
        self.chapters[0].write_text(self.chapters[0].read_text().replace('waited', 'stood'))
        stale = self.chapters[0].read_bytes()
        proposal = self.proposal()
        self.assertEqual([f['path'] for f in proposal['files']], ['Chapters/Book-1/Chapter-002.md'])
        self.assertEqual(len([m for m in proposal['manual'] if m['path'].endswith('001.md')]), 3)
        self.run_return('--apply', proposal['apply_token'])
        self.assertEqual(self.chapters[0].read_bytes(), stale)
        self.assertIn('iron', self.chapters[1].read_text())
        self.assertEqual(self.statuses()['bolted'], 'accepted')

    def test_windows_line_endings_survive(self):
        ids = self.sample()
        self.chapters[1].write_bytes(self.chapters[1].read_bytes().replace(b'\n', b'\r\n'))
        self.mark('accepted', ids['iron'])
        self.apply()
        self.assertEqual(self.chapters[1].read_bytes(), b'# Chapter 2\r\n\r\nNell took the iron key.\r\n')

    def test_pieces_of_one_word_are_decided_together(self):
        def edit(tree):
            track(find(tree, 'Clara'), ('Clara ', 'lo', 'bo'), ('Clara lock', 'ed', 's'))
        self.docx = self.returned(edit)
        first, second = self.read(self.docx)['changes']
        decision = self.mark('accepted', first['id'])
        self.assertEqual([c['id'] for c in decision['changes']], [first['id'], second['id']])
        self.apply()
        self.assertIn('Clara bocks the', self.chapters[0].read_text())

    def test_manual_changes_cannot_be_accepted(self):
        italic = element('rPr')
        italic.append(element('i'))
        self.docx = self.returned(lambda tree: track(find(tree, 'brass'), ('the ', 'brass', 'iron'),
                                                     inserted_style=italic))
        change = self.read(self.docx)['changes'][0]
        self.assertIn('formatting', self.run_return('--mark', 'accepted', '--change', change['id'], fail=True))
        self.assertEqual(self.mark('rejected', change['id'])['changes'][0]['status'], 'rejected')

    def test_a_write_that_cannot_be_confirmed_is_restored(self):
        ids = self.sample()
        self.mark('accepted', ids['iron'])
        before = self.contents()
        token = self.proposal()['apply_token']
        sys.path.insert(0, str(RETURN.parent))
        import editor_apply
        report = json.loads(self.ledger.read_text())
        with mock.patch.object(editor_apply, 'confirmed', return_value=False):
            result = editor_apply.apply(self.root, 'Book-1', report, self.ledger, token)
        self.assertEqual((result['written'], len(result['failed'])), ([], 1))
        self.assertEqual(self.contents(), before)
        self.assertEqual(self.statuses()['iron'], 'accepted')


class EditorMcp(ReturnedExport):
    PARAGRAPHS = EditorApply.PARAGRAPHS

    def call(self, tool, fail=False, **arguments):
        request = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {
            'name': tool, 'arguments': {'root': str(self.root), 'docx': self.docx.name, **arguments}}}
        completed = subprocess.run([sys.executable, '-B', str(MCP_SERVER)], input=json.dumps(request) + '\n',
                                   capture_output=True, text=True, check=True)
        result = json.loads(completed.stdout)['result']
        self.assertEqual(result['isError'], fail, result)
        return json.loads(result['content'][0]['text'])

    def test_review_decide_and_apply_through_the_server(self):
        def edit(tree):
            track(find(tree, 'Clara'), ('Clara ', 'locked', 'bolted'), ('and ', 'waited', 'left'))
            track(find(tree, 'brass'), ('the ', 'brass', 'iron'))
        self.docx = self.returned(edit)
        report = self.call('storycraft_editor_return', limit=2)
        self.assertEqual(report['summary']['statuses'], {'pending': 3})
        self.assertEqual([c['after'] for c in report['changes']['items']], ['bolted', 'left'])
        self.assertEqual((report['changes']['total'], report['changes']['next_offset']), (3, 2))
        rest = self.call('storycraft_editor_return', offset=2)['changes']
        self.assertEqual(([c['after'] for c in rest['items']], rest['next_offset']), (['iron'], None))
        one = self.call('storycraft_editor_return', chapter='Chapter 2')['changes']
        self.assertEqual([c['after'] for c in one['items']], ['iron'])
        shown = self.call('storycraft_editor_decide', status='accepted', author='Ed', limit=1)['decision']
        self.assertEqual((shown['recorded'], shown['changes']['total'], len(shown['changes']['items'])),
                         (False, 3, 1))
        self.call('storycraft_editor_decide', status='accepted', author='Ed', confirm=shown['confirm'])
        preview = self.call('storycraft_editor_return', view='preview', accepted=True, limit=1)['preview']
        self.assertEqual((preview['files']['total'], preview['files']['next_offset']), (2, 1))
        self.assertIn('bolted', preview['files']['items'][0]['diff'])
        self.assertIn('brass', self.chapters[1].read_text())
        self.call('storycraft_editor_apply', fail=True, token='wrong')
        applied = self.call('storycraft_editor_apply', token=preview['apply_token'])['applied']
        self.assertEqual(len(applied['written']), 2)
        self.assertIn('iron', self.chapters[1].read_text())

    def test_the_server_lists_the_editor_tools_and_rejects_option_like_values(self):
        self.docx = self.returned()
        request = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}
        completed = subprocess.run([sys.executable, '-B', str(MCP_SERVER)], input=json.dumps(request) + '\n',
                                   capture_output=True, text=True, check=True)
        names = {tool['name'] for tool in json.loads(completed.stdout)['result']['tools']}
        self.assertTrue({'storycraft_editor_return', 'storycraft_editor_decide',
                         'storycraft_editor_apply'} <= names)
        self.call('storycraft_editor_decide', fail=True, status='accepted', changes=['--apply'])


if __name__ == '__main__':
    unittest.main()
