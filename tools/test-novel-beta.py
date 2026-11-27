#!/usr/bin/env python3
"""Exercise novel-scale beta observations through the normal export and intake commands."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BETA = ROOT / 'skills/beta-feedback/scripts/beta_feedback.py'
EXPORT = ROOT / 'skills/compile-manuscript/scripts/compile_manuscript.py'


class NovelBetaFeedback(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.chapters = []
        for index, text in enumerate(('Clara locked the door.', 'Nell took the key.',
                                      'The sisters washed dishes.'), 1):
            chapter = self.root / f'Chapters/Book-1/Chapter-{index:03}.md'
            chapter.parent.mkdir(parents=True, exist_ok=True)
            chapter.write_text(f'# Chapter {index}\n\n{text}\n')
            self.chapters.append(chapter)
        self.edition = self.run_cli(EXPORT)['beta_feedback']['export_id']

    def run_cli(self, script, *args, fail=False):
        completed = subprocess.run([sys.executable, '-B', str(script), '--root', str(self.root), *args],
                                   capture_output=True, text=True)
        if fail:
            self.assertNotEqual(completed.returncode, 0, completed.stdout)
            return completed.stderr
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout)

    def notes(self, notes, *, reader='Nora', edition=None):
        path = self.root / 'feedback.json'
        path.write_text(json.dumps(dict(schema_version=1, reader=reader, notes=notes)))
        return self.run_cli(BETA, '--export', edition or self.edition, '--notes', str(path))

    def test_scope_and_strengths_survive_selection_without_changing_prose(self):
        source = [p.read_text() for p in self.chapters]
        notes = [{'comment': 'I forgot why the sisters needed each other.'},
                 {'chapter_range': ['Chapter 2', 'Chapter 3'], 'comment': 'The middle repeats a choice.'},
                 {'chapter': 'Chapter 3', 'kind': 'strength', 'comment': 'I loved the quiet ending.'},
                 {'quote': 'Clara locked the door.', 'comment': 'Which door is this?'}]
        report = self.notes(notes)
        whole, middle, strength, line = report['feedback']
        self.assertEqual(self.notes(notes)['added'], 0)
        self.assertEqual([g['scope']['kind'] for g in report['scope_groups']], ['book', 'range', 'chapter'])
        args = [arg for n in report['feedback'] for arg in ('--select', n['id'])]
        campaign = self.run_cli(BETA, '--export', self.edition, '--campaign', 'beta', *args)
        broad, scoped, local = campaign['tasks']
        relative = [p.relative_to(self.root).as_posix() for p in self.chapters]
        self.assertEqual([broad['files'], scoped['files'], local['files']], [relative, relative[1:], relative[:1]])
        self.assertEqual([t['kind'] for t in campaign['tasks']], ['developmental-diagnosis'] * 2 + ['prose-repair'])
        self.assertEqual([t['feedback'][0] for t in campaign['tasks']], [whole, middle, line])
        self.assertTrue(all(t['status'] == 'pending' for t in campaign['tasks']))
        self.assertEqual(local['depends_on'], [broad['id']])
        self.assertEqual(campaign['preserve'], [strength])
        self.assertEqual([p.read_text() for p in self.chapters], source)

    def test_prior_general_notes_bad_ranges_and_unverified_quotes(self):
        raw = [{'chapter': 'Chapter 2', 'comment': 'Her reason disappears.'},
               {'chapter_range': ['Chapter 3', 'Chapter 1'], 'comment': 'Invalid range'},
               {'chapter_range': ['Chapter 9', 'Chapter 2'], 'comment': 'Missing chapter'},
               {'quote': 'A line the book never contained.', 'comment': 'I liked this line.'}]
        old, reversed_note, unknown, missing_quote = self.notes(raw)['feedback']
        ledger = self.root / f'_Edits/Book-1/beta-feedback/{self.edition}.json'
        record = json.loads(ledger.read_text())
        record['feedback'][0]['location'].pop('scope', None)  # earlier editions lack resolved scope
        ledger.write_text(json.dumps(record))
        self.chapters[1].write_text('# Chapter 2\n\nNell left the key in the lock.\n')
        plan = self.run_cli(BETA, '--export', self.edition, '--campaign', 'prior', '--select', old['id'])
        task = plan['tasks'][0]
        self.assertEqual(task['kind'], 'developmental-diagnosis')
        self.assertEqual(task['files'], [self.chapters[1].relative_to(self.root).as_posix()])
        self.assertNotEqual(task['archived_inputs'][0]['sha256'], task['before'][0]['sha256'])
        for item in (reversed_note, unknown, missing_quote):
            self.assertEqual(item['location']['status'], 'UNRESOLVED')
            self.run_cli(BETA, '--export', self.edition, '--campaign', 'unresolved',
                         '--select', item['id'], fail=True)

    def test_preserving_an_existing_comment_creates_no_repair(self):
        note = self.notes([{'quote': 'Nell took the key.', 'comment': 'Please keep her agency here.'}])['feedback'][0]
        saved = self.run_cli(BETA, '--export', self.edition, '--campaign', 'strength',
                             '--preserve', note['id'])
        self.assertEqual(saved['preserve'], [note])
        self.assertEqual(saved['tasks'], [])

    def test_author_can_diagnose_a_broader_effect_reported_in_one_margin(self):
        note = self.notes([{'quote': 'The sisters washed dishes.', 'comment': 'The reconciliation felt sudden.'}])['feedback'][0]
        broad = self.run_cli(BETA, '--export', self.edition, '--campaign', 'whole', '--diagnose', note['id'])
        task = broad['tasks'][0]
        self.assertEqual(task['reader_scope']['kind'], 'book')
        self.assertEqual(task['feedback'][0]['location']['status'], 'ANCHORED')
        ranged = self.run_cli(BETA, '--export', self.edition, '--campaign', 'setup', '--diagnose', note['id'],
                              '--chapter-range', 'Chapter 1', 'Chapter 2')['tasks'][0]
        self.assertEqual(ranged['files'], [p.relative_to(self.root).as_posix() for p in self.chapters[:2]])
        self.assertEqual(ranged['feedback'][0], note)

    def test_scoped_quote_must_be_inside_the_range(self):
        quote = {'chapter_range': ['Chapter 2', 'Chapter 3'], 'quote': 'Nell took the key.', 'comment': 'This starts a pattern.'}
        valid, outside = self.notes([quote, dict(quote, quote='Clara locked the door.')])['feedback']
        self.assertEqual(valid['location']['status'], 'ANCHORED')
        self.assertEqual(outside['location']['status'], 'UNRESOLVED')
        task = self.run_cli(BETA, '--export', self.edition, '--campaign', 'pattern', '--select', valid['id'])['tasks'][0]
        self.assertEqual(task['kind'], 'developmental-diagnosis')
        self.assertEqual(task['feedback'][0]['quote'], 'Nell took the key.')

    @unittest.skipUnless(shutil.which('pandoc'), 'Pandoc is required for a real returning-reader packet')
    def test_range_reread_retains_scope_and_reader_identity(self):
        note = {'chapter_range': ['Chapter 2', 'Chapter 3'], 'comment': 'Her loyalty faded here.'}
        self.notes([note])
        self.notes([{'comment': 'Another reader private comment.'}], reader='Lee')
        self.chapters[1].write_text('# Chapter 2\n\nNell kept the key.\n')
        new = self.run_cli(EXPORT)['beta_feedback']['export_id']
        reread = self.run_cli(BETA, '--export', self.edition, '--reread-to', new, '--reader', 'Nora')
        packet = json.loads((Path(reread['output']) / 'beta-passages.json').read_text())
        content = '\n'.join(s['reader_text'] for s in packet['sections'])
        self.assertIn('Chapter 2 through Chapter 3', content)
        self.assertIn(note['comment'], content)
        self.assertNotIn('Another reader private comment.', content)
        reply = self.notes([dict(note, comment='I can follow her now.', kind='strength')],
                           edition=reread['packet_id'])['feedback'][0]
        self.assertEqual(reply['export_id'], new)
        self.assertEqual(reply['packet_id'], reread['packet_id'])
        self.assertEqual(reply['location']['scope']['kind'], 'range')
        scene = next(s for s in packet['sections'] if s.get('origin'))
        for selector in (scene['label'], scene['path']):
            saved = self.notes([{'chapter': selector, 'quote': 'Nell kept the key.', 'comment': 'This works.'}],
                               edition=reread['packet_id'])['feedback'][-1]
            self.assertEqual(saved['location']['status'], 'ANCHORED', saved)
            self.assertEqual(saved['location']['path'], scene['origin']['path'])
            self.assertEqual(saved['chapter'], selector)
            self.assertEqual(saved['packet_id'], reread['packet_id'])
        widens = self.notes([{'chapter': scene['label'], 'quote': note['comment'],
                              'comment': 'This text is outside the manuscript scene.'}],
                            edition=reread['packet_id'])['feedback'][-1]
        self.assertEqual(widens['location']['status'], 'UNRESOLVED')


if __name__ == '__main__':
    unittest.main()
