#!/usr/bin/env python3
"""Exercise personal read-throughs through the public CLIs on disposable books."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / 'skills/book-status/scripts/project_state.py'
EXPORT = ROOT / 'skills/compile-manuscript/scripts/compile_manuscript.py'


class AuthorRead(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def chapter(self, number, *scenes):
        text = '\n\n* * *\n\n'.join(scenes)
        return self.write(f'Chapters/Book-1/Chapter-{number:03}.md', f'# Chapter {number}\n\n{text}\n')

    def cli(self, script, *args, fail=False):
        result = subprocess.run([sys.executable, '-B', str(script), '--root', str(self.root), *args],
                                capture_output=True, text=True)
        if fail:
            self.assertNotEqual(result.returncode, 0, result.stdout)
            return result.stderr.strip() or result.stdout.strip()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return json.loads(result.stdout)

    def read(self, action, *args, fail=False):
        return self.cli(STATE, 'author-read', '--action', action, *args, fail=fail)

    def manifest(self, ordered_numbers):
        chapters = [{'id': f'C{n}', 'display_label': f'Chapter {n}',
                     'path': f'Chapters/Book-1/Chapter-{n:03}.md', 'reading_order': i}
                    for i, n in enumerate(ordered_numbers, start=1)]
        self.write('.storycraft/project.json', json.dumps({
            'schema_version': 1, 'record_type': 'project_manifest', 'project_id': 'fixture',
            'books': [{'id': 'B1', 'display_label': 'Book-1', 'chapters': chapters}]}))

    def test_dashboard_counts_explicit_completed_chapters(self):
        first = self.chapter(1, 'A lit window.')
        self.chapter(2, 'Footsteps on the stairs.')
        last = self.chapter(3, 'Zoë reached the landing.', 'Rain tapped the glass.')
        report = '_Edits/Book-1/Chapter-001_Gate.md'
        spec = self.write('gate.json', json.dumps({'schema_version': 1, 'verdict': 'PASS',
                          'report': report, 'paths': [first.relative_to(self.root).as_posix()]}))
        self.cli(STATE, 'prepare', '--spec', str(spec), '--output', 'prepared.json')
        self.write(report, 'PASS\n')
        self.cli(STATE, 'snapshot', '--spec', str(self.root / 'prepared.json'), '--output',
                 report.replace('.md', '.meta.json'))
        board = self.cli(STATE, 'dashboard')
        self.assertTrue(board['chapters'][0]['ready'])
        self.assertEqual(board['author_read']['personally_read'], 0)

        frozen = self.read('start')['edition']
        self.assertIsNone(self.read('resume')['bookmark'])
        complete = self.read('mark', '--chapter', '1')
        quote = 'Zoë reached'
        partial = self.read('mark', '--quote', quote)
        self.assertEqual(partial['edition'], frozen)
        self.assertFalse(partial['whole'])
        self.assertEqual(partial['end'], last.read_text().index(quote) + len(quote))
        status = self.read('resume')
        self.assertEqual(status['current_chapter_ids'], [complete['chapter_id']])
        self.assertEqual(status['changes'], [])
        self.assertEqual(self.read('changes'), status)
        self.assertEqual(self.cli(STATE, 'dashboard')['author_read']['bookmark'], status['bookmark'])

        self.chapter(1, 'The window went dark.')
        board = self.cli(STATE, 'dashboard')
        self.assertFalse(board['chapters'][0]['ready'])
        author = board['author_read']
        self.assertEqual((author['personally_read'], author['reported_complete']), (0, 1))
        self.assertEqual(author['bookmark']['anchor'], quote)

    def test_repeated_or_absent_quotes_preserve_the_last_position(self):
        self.chapter(1, 'The bell rang. Once.', 'The bell rang. Twice.', 'She whispered, “go on go on go on.”')
        self.chapter(2, 'The bell rang. They left.')
        self.read('start')
        self.read('mark', '--quote', 'Once.')
        original = self.read('resume')
        for args in [('--quote', 'The bell rang.'), ('--chapter', '1', '--quote', 'The bell rang.'),
                     ('--chapter', '1', '--quote', 'go on go on'),
                     ('--chapter', '2', '--quote', 'Missing words.')]:
            with self.subTest(args=args):
                self.read('mark', *args, fail=True)
                self.assertEqual(self.read('resume'), original)
        resolved = self.read('mark', '--chapter', '2', '--quote', 'The bell rang.')
        self.assertEqual(self.read('resume')['bookmark']['chapter_id'], resolved['chapter_id'])
        self.chapter(2, 'The bell rang. They left. The bell rang.')
        self.assertEqual(self.read('resume')['bookmark']['status'], 'unresolved')

    def test_stop_inside_paragraph_excludes_unread_edits(self):
        quote = 'Mara lifted the key.'
        self.chapter(1, 'She faced the door.', 'Zoë came in. ' + quote + ' The lock remained silent.')
        self.read('start')
        self.read('mark', '--chapter', '1', '--quote', quote)
        self.chapter(1, 'She faced the door.', 'Zoë came in. ' + quote + ' A bell rang behind her.')
        status = self.read('changes')
        self.assertEqual(status['bookmark']['status'], 'located')
        self.assertEqual(status['changes'], [])
        self.chapter(1, 'She faced the door.', 'Inez came in. ' + quote + ' A bell rang behind her.')
        result = self.read('changes')
        change, = result['changes']
        passage, = change['paragraphs']
        self.assertIn('Zoë', passage['before'][0]['text'])
        self.assertIn('Inez', passage['after'][0]['text'])
        self.assertLessEqual(passage['before'][0]['end'], result['bookmark']['end'])
        self.assertLessEqual(passage['after'][0]['end'], result['bookmark']['current_end'])

    def test_adjacent_paragraph_edits_stop_at_the_read_boundary(self):
        self.chapter(1, 'An ordinary morning.\n\nLast line read.\n\nA later revelation.')
        self.read('start')
        self.read('mark', '--quote', 'Last line read.')
        self.chapter(1, 'An ordinary morning.\n\nA different last line.\n\nA different revelation.')
        result = self.read('changes')
        self.assertEqual(result['bookmark']['status'], 'unresolved')
        excerpts = json.dumps(result['changes'])
        self.assertIn('Last line read.', excerpts)
        self.assertIn('A different last line.', excerpts)
        self.assertNotIn('revelation', excerpts)

    def test_identical_refrains_in_an_unchanged_chapter(self):
        self.chapter(1, 'Opening.', 'Again, again.', 'Again, again.', 'The final bell.')
        self.chapter(2, 'The sun came up.')
        self.read('start')
        self.read('mark', '--chapter', '1')
        self.assertEqual(self.read('changes')['changes'], [])
        self.chapter(2, 'The fog burned off.')
        self.assertEqual(self.read('changes')['changes'], [])

    def test_scene_edits_deletions_additions_and_moves_through_partial_chapter(self):
        self.chapter(1, 'A room above the quay.\n\nThe walls were blue.', 'A discarded ticket.',
                     'A train crossed the bridge.', 'Mara tucked the brass key away.',
                     'The platform was empty.', 'The tide turned.', 'An unread promise.', 'Another unread scene.')
        self.chapter(2, 'The harbor at night.')
        self.manifest([1, 2])
        self.read('start')
        self.read('mark', '--quote', 'The tide turned.')
        self.chapter(1, 'A room above the quay.\n\nThe walls were green.', 'A train crossed the bridge.',
                     'A new letter arrived.', 'The platform was empty.', 'The tide turned.',
                     'A revised unread promise.', 'A new unread scene.')
        self.chapter(2, 'The harbor at night.', 'Mara tucked the brass key away.')
        changes = self.read('changes')['changes']
        positions = {(row['status'], tuple(row['before'] or ()), tuple(row['after'] or ())) for row in changes}
        self.assertEqual(positions, {('edited', ('C1', 0), ('C1', 0)),
                                     ('deleted', ('C1', 1), ()), ('added', (), ('C1', 2)),
                                     ('moved', ('C1', 3), ('C2', 1))})
        passages = json.dumps(changes)
        for phrase in ('The walls were blue.', 'The walls were green.', 'A discarded ticket.',
                       'A new letter arrived.'):
            self.assertIn(phrase, passages)
        self.assertNotIn('unread', passages)

    def test_move_of_the_bookmark_to_another_chapter(self):
        quote = 'I carried the lamp.'
        scene = 'The street was quiet.\n\n' + quote + ' Then the snow fell.'
        self.chapter(1, 'The empty shed.', scene, 'The barn doors closed.')
        self.chapter(2, 'Sleet began before midnight.')
        self.manifest([1, 2])
        self.read('start')
        self.read('mark', '--chapter', '1', '--quote', quote)
        self.chapter(1, 'The empty shed.', 'The barn doors closed.')
        target = self.chapter(2, 'Sleet began before midnight.', scene)
        status = self.read('resume')
        bookmark = status['bookmark']
        self.assertEqual(bookmark['status'], 'located')
        self.assertEqual(bookmark['current_chapter_id'], 'C2')
        self.assertEqual(bookmark['current_end'], target.read_text().index(quote) + len(quote))
        self.assertTrue(any(row['status'] == 'moved' and row['after'] == ['C2', 1]
                            for row in status['changes']))
        self.chapter(2, 'Sleet began before midnight.', scene.replace('the snow fell', 'the plows arrived'))
        report = self.read('changes')
        self.assertEqual(report['bookmark']['current_chapter_id'], 'C2')
        moved, = report['changes']
        self.assertIn(moved['status'], ('moved', 'moved-edited'))
        self.assertEqual((moved['before'], moved['after'], moved['paragraphs']), (['C1', 1], ['C2', 1], []))

    def test_scenes_moved_from_unread_material_into_the_read_prefix(self):
        original = ['The yard was empty.', 'A baker swept the step.', 'An unlit lamp.', 'Here I stopped.',
                    'A blue window.', 'A red window.', 'Later rain fell.', 'The doors were closed.']
        self.chapter(1, *original)
        self.manifest([1])
        self.read('start')
        self.read('mark', '--quote', 'Here I stopped.')
        self.chapter(1, *(original[:4] + original[5:7] + [original[4], original[7]]))
        self.assertEqual(self.read('changes')['changes'], [])
        self.chapter(1, *(original[:1] + [original[6]] + original[1:6] + original[7:]))
        changes = self.read('changes')['changes']
        self.assertEqual([(row['status'], row['before'], row['after']) for row in changes],
                         [('moved', ['C1', 6], ['C1', 1])])

    def test_chapters_added_deleted_or_edited_either_side_of_a_bookmark(self):
        originals = {11: 'The dinghy set out.', 12: 'Mara checked the tide.', 13: 'The pier receded.',
                     14: 'She tied the line. Beyond lay the bay.', 15: 'Later a wave rose.', 16: 'The sea calmed.'}
        for number, text in originals.items():
            self.chapter(number, text)
        self.manifest([11, 12, 13, 14, 15, 16])
        self.read('start')
        for number in (11, 12, 13):
            self.read('mark', '--chapter', str(number))
        self.read('mark', '--chapter', '14', '--quote', 'She tied the line.')
        self.chapter(12, 'Mara checked the rope.')
        self.chapter(15, 'Later two waves rose.')
        self.chapter(20, 'A new stop at the jetty.')
        self.chapter(21, 'A new turn out at sea.')
        self.manifest([11, 20, 12, 14, 15, 21])
        status = self.read('changes')
        self.assertEqual(status['personally_read'], 1)
        self.assertEqual(status['reported_complete'], 3)
        changes = status['changes']
        self.assertEqual({(row['status'], tuple(row['before'] or ()), tuple(row['after'] or ())) for row in changes},
                         {('edited', ('C12', 0), ('C12', 0)), ('deleted', ('C13', 0), ()),
                          ('added', (), ('C20', 0))})

    def test_progress_on_two_editions_and_a_repeated_chapter(self):
        self.chapter(1, 'The first stone.')
        self.chapter(2, 'Blue water covered the steps.')
        self.chapter(3, 'The old inn stood empty.')
        self.manifest([1, 2, 3])
        old = self.read('start')['edition']
        self.read('mark', '--chapter', '1')
        self.read('mark', '--chapter', '2')
        self.chapter(1, 'The first stone was gone.')
        new = self.read('start')['edition']
        self.assertNotEqual(old, new)
        self.assertEqual(self.read('resume')['current_chapter_ids'], ['C2'])
        self.read('mark', '--chapter', '3')
        self.read('mark', '--chapter', '1', '--quote', 'The first stone')
        current = self.read('changes', '--edition', new)
        self.assertEqual(current['reported_complete'], 3)
        self.assertEqual(set(current['current_chapter_ids']), {'C2', 'C3'})
        historical = self.read('changes', '--edition', old)
        self.assertIn('C1', historical['current_chapter_ids'])
        self.assertEqual(historical['changes'], [])
        self.assertEqual(historical['reported_complete'], 3)

    def test_moved_chapters_on_either_side_of_the_bookmark(self):
        for number in range(1, 9):
            self.chapter(number, f'Prose for {number}.')
        self.manifest(range(1, 9))
        self.read('start')
        for number in (1, 2, 3):
            self.read('mark', '--chapter', str(number))
        self.read('mark', '--chapter', '4', '--quote', 'Prose for 4.')
        self.manifest([1, 2, 3, 4, 8, 5, 6, 7])
        self.assertEqual(self.read('changes')['changes'], [])
        self.manifest([1, 7, 2, 3, 4, 5, 6, 8])
        incoming = self.read('changes')
        self.assertEqual(incoming['personally_read'], 3)
        self.assertEqual([(r['status'], r['after']) for r in incoming['changes']], [('moved', ['C7', 0])])
        self.manifest([1, 3, 4, 5, 6, 7, 2, 8])
        outgoing = self.read('changes')['changes']
        self.assertEqual([(r['status'], r['before']) for r in outgoing], [('moved', ['C2', 0])])

    def test_partial_reread_retains_full_credit_for_identical_prose(self):
        self.chapter(1, 'The cat came home.')
        self.chapter(2, 'The dog left.')
        self.manifest([1, 2])
        self.read('start')
        self.read('mark', '--chapter', '1')
        self.chapter(2, 'The dog stayed.')
        self.read('start')
        self.read('mark', '--chapter', '1', '--quote', 'The cat')
        status = self.read('resume')
        self.assertEqual(status['current_chapter_ids'], ['C1'])
        self.assertEqual(status['reported_complete'], 1)
        self.assertFalse(status['bookmark']['whole'])
        self.assertEqual(status['bookmark']['anchor'], 'The cat')

    def test_read_an_archived_beta_which_predates_scene_indexes(self):
        old_line = 'Mara paused beside the mill.'
        self.chapter(1, 'The wheel turned.', old_line)
        self.chapter(2, 'The loft was dark.')
        first = self.cli(EXPORT, '--format', 'md')
        edition = first['beta_feedback']['export_id']
        active = Path(first['output'])
        passages = active / 'beta-passages.json'
        manifest = active / 'export-manifest.json'
        content = json.loads(passages.read_text())
        for section in content['sections']:
            section.pop('scenes')
        passages.write_text(json.dumps(content), encoding='utf-8')
        info = json.loads(manifest.read_text())
        info['beta_feedback']['sha256'] = hashlib.sha256(passages.read_bytes()).hexdigest()
        manifest.write_text(json.dumps(info), encoding='utf-8')
        self.chapter(1, 'The wheel stopped.', 'The mill was boarded up.')
        newer = self.cli(EXPORT, '--format', 'md')['beta_feedback']['export_id']
        self.assertNotEqual(edition, newer)
        self.assertEqual(self.read('start', '--edition', edition)['edition'], edition)
        self.assertEqual(self.read('mark', '--quote', old_line)['edition'], edition)
        old = self.read('resume', '--edition', edition)
        self.assertEqual(old['bookmark']['status'], 'located')
        self.assertEqual(old['changes'], [])
        new = self.read('changes', '--edition', newer)
        self.assertEqual(new['bookmark']['status'], 'unresolved')
        self.assertTrue(new['changes'])
        self.assertIn(old_line, json.dumps(new['changes']))


if __name__ == '__main__':
    unittest.main()
