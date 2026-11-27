#!/usr/bin/env python3
"""Exercise manuscript report parity through the public MCP handlers and standalone ledger CLIs."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'mcp'))
import storycraft_mcp as server
import ledger_store


class ReportParity(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        shutil.copytree(ROOT / 'tools/eval-fixtures/storycraft-book', self.root, dirs_exist_ok=True)
        self.ledger = 'Wiki/Story/Book-1/promises.yaml'
        self.chapters = [
            {'id': 'cold-open', 'display_label': 'Prologue', 'reading_order': 10},
            {'id': 'east-72', 'display_label': 'Chapter 1', 'reading_order': 20},
            {'id': 'west-35', 'display_label': 'Chapter 2', 'reading_order': 30},
        ]
        for n, chapter in enumerate(self.chapters, 1):
            chapter['path'] = f'Chapters/Book-1/Chapter-{n:03}.md'
        self.write('.storycraft/project.json', json.dumps({
            'record_type': 'project_manifest', 'schema_version': 1, 'project_id': 'fiction',
            'books': [{'id': 'first-volume', 'display_label': 'Book-1', 'chapter_order': 'declared',
                       'chapters': self.chapters}]}))
        self.data = {'promises': [
            {'id': 'P1', 'promise': 'Scarf in the reeds', 'introduced_ch': 'cold-open', 'payoff_by_ch': 'east-72'},
            {'id': 'P2', 'promise': 'Painted door', 'introduced_ch': 'Chapter 1', 'payoff_by_ch': 2,
             'paid_in_ch': 'west-35'},
            {'id': 'P3', 'promise': 'Ferry crossing', 'introduced_ch': 'cold-open', 'payoff_by_ch': 'Chapter 2'}]}

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')

    def tool(self, name, **args):
        return server._call_tool('storycraft_' + name, {'root': str(self.root), 'book': 'first-volume', **args})

    def commit(self):
        ledger_store.commit(self.root, {
            'transaction_id': 'harvest-promises', 'expected_generation': None,
            'source_evidence': ledger_store.capture(self.root, [self.chapters[0]['path']]),
            'updates': {self.ledger: self.data}})

    def verify_reports(self):
        expected = {'P1': 'overdue', 'P2': 'paid_here', 'P3': 'due'}
        for selector in ('west-35', 'Chapter 2'):
            packet = self.tool('draft_packet', chapter=selector)['promises']
            self.assertEqual({item['id']: item['status'] for item in packet['items']}, expected)
            for args in ({}, {'ledger': self.ledger}):
                result = self.tool('promises', chapter=selector, **args)
                self.assertEqual(result['returncode'], 0, result['stderr'])
                self.assertRegex(result['stdout'], r'OVERDUE[^\n]+\(1\):\n    P1 ')
                self.assertRegex(result['stdout'], r'DUE THIS UNIT \(1\):\n    P3 ')
        board = self.tool('kanban', write_board=False)
        self.assertEqual(board['counts']['Drafting'], 3)
        self.assertEqual(board['overdue_promises'], 1)
        metrics = self.tool('rhythm_map', markdown=False)
        self.assertEqual([(row['chapter'], row['promises_opened'], row['promises_paid']) for row in metrics['chapters']],
                         [('Prologue', 2, 0), ('Chapter 1', 1, 0), ('Chapter 2', 0, 1)])

    def test_committed_only_without_wiki_or_mirror(self):
        self.commit()
        self.assertFalse((self.root / 'Wiki').exists())
        self.verify_reports()
        self.assertFalse((self.root / 'Wiki').exists())
        for skill in ('fiction-promises', 'promise-tracker'):
            script = ROOT / 'skills' / skill / 'scripts/promises.py'
            command = [sys.executable, '-B', str(script), '--ledger', str(self.root / self.ledger),
                       '--chapter', 'east-72']
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
            self.assertRegex(result.stdout, r'DUE (?:NEXT CHAPTER|SOON \(next unit\)) \(1\):\n    P3 ')

    def test_commit_overrides_stale_mirror(self):
        self.write(self.ledger, 'promises: []\n')
        self.commit()
        self.verify_reports()

    def test_unmanaged_ledger_and_declared_outline_order(self):
        self.write(self.ledger, json.dumps(self.data))
        self.write('Wiki/Outline/Book-1/outline.md', '# Book plan\n## Chapter 2 — Second numbered\n'
                   '## Prologue: Before the crossing\n## Chapter 1 - First numbered\n')
        self.verify_reports()
        board = self.tool('kanban', write_board=False)['markdown']
        positions = [board.index(label) for label in ('Prologue — Before the crossing', '001 — First numbered',
                                                       '002 — Second numbered')]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn('no-outline-entry', board)

    def test_unavailable_ledger_preserves_manuscript_metrics(self):
        for status in ('missing', 'unreadable'):
            if status == 'unreadable':
                self.write(self.ledger, 'promises: [')
            board = self.tool('kanban', write_board=False)
            self.assertEqual(board['promise_ledger_status'], status)
            self.assertIsNone(board['overdue_promises'])
            metrics = self.tool('rhythm_map')
            self.assertEqual(metrics['chapter_count'], 3)
            self.assertEqual(metrics['promise_ledger_status'], status)
            self.assertIsNone(metrics['chapters'][1]['promises_opened'])
            self.assertIn(status, metrics['markdown'])

    def test_individually_copied_skills_can_still_audit_an_unmanaged_ledger(self):
        self.write(self.ledger, json.dumps({'promises': [
            {'id': 'P1', 'promise': 'The old chart', 'introduced_ch': 1, 'payoff_by_ch': 'sec2.1'}]}))
        for skill in ('fiction-promises', 'promise-tracker'):
            standalone = self.root / 'standalone' / skill / 'scripts/promises.py'
            standalone.parent.mkdir(parents=True)
            shutil.copy2(ROOT / 'skills' / skill / 'scripts/promises.py', standalone)
            result = subprocess.run([sys.executable, '-B', str(standalone), '--book', 'Book-1', '--chapter', 'ch3'],
                                    cwd=self.root, capture_output=True, text=True, check=True)
            self.assertRegex(result.stdout, r'OVERDUE[^\n]+\(1\):\n    P1 ')


if __name__ == '__main__':
    unittest.main()
