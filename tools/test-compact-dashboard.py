#!/usr/bin/env python3
"""Exercise compact status and chapter drill-down through the MCP and CLI."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'skills/book-status/scripts/project_state.py'
SERVER = ROOT / 'mcp/storycraft_mcp.py'


class CompactDashboard(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')

    def draft(self, number):
        self.write(f'Chapters/Book-1/Chapter-{number:03d}.md', f'# Chapter {number}\n\nThe tide turns.\n')

    def call(self, tool='dashboard', **options):
        request = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                   'params': {'name': 'storycraft_' + tool, 'arguments': {'root': str(self.root), **options}}}
        output = subprocess.check_output([sys.executable, '-B', str(SERVER)], input=json.dumps(request) + '\n',
                                         text=True)
        reply = json.loads(output)['result']
        self.assertFalse(reply['isError'], reply)
        return json.loads(reply['content'][0]['text'])

    def gate(self, number, findings=None):
        begin = self.call('review_begin', chapter=str(number), review_type='Gate')
        self.write(begin['report'], 'PASS\n')
        self.call('review_finish', prepared=begin['prepared'], verdict='PASS', findings=findings or [])
        return begin['report']

    def test_summary_stays_small_and_selector_keeps_book_counts(self):
        for number in range(1, 41):
            self.draft(number)
        full = self.call()
        self.assertEqual(len(full['chapters']), 40)
        compact = self.call(view='compact')
        self.assertLess(len(json.dumps(compact)), len(json.dumps(full)) // 10)
        self.assertEqual(compact['counts'], dict(expected=40, drafted=40, ready=0, needs_review=40, missing_drafts=0))
        first = compact['first_blocker']
        self.assertEqual(first['chapter_id'], full['chapters'][0]['chapter_id'])
        self.assertEqual(first['reason'], 'required review evidence is missing')
        self.assertEqual(self.call(view='compact', chapter=first['chapter_id'])['chapter'], full['chapters'][0])
        self.assertEqual(self.call(chapter='Chapter 2')['chapters'], full['chapters'][1:2])
        cli = json.loads(subprocess.check_output([sys.executable, '-B', str(STATE), '--root', str(self.root),
                                                  'dashboard', '--view', 'compact', '--chapter', '2'], text=True))
        self.assertEqual(cli['chapter'], full['chapters'][1])
        self.assertEqual(cli['counts'], compact['counts'])

    def test_missing_ranges_share_reading_order_with_gate_blockers(self):
        self.draft(1)
        self.draft(5)
        self.assertEqual(self.call(view='compact')['first_blocker']['label'], 'Chapter 1')
        self.gate(1)
        summary = self.call(view='compact')
        self.assertEqual(summary['counts'], dict(expected=5, drafted=2, ready=1, needs_review=1, missing_drafts=3))
        self.assertEqual(summary['first_blocker']['label'], 'Chapters 2 through 4')
        self.assertEqual(summary['first_blocker']['reason'], 'expected draft is missing')

    def test_resolved_finding_and_campaign_remain_distinct(self):
        self.draft(1)
        report = self.gate(1, [dict(id='G1', blocking=True)])
        summary = self.call(view='compact')
        self.assertIn('G1', summary['first_blocker']['reason'])
        self.call('record_disposition', report=report, finding_id='G1', disposition='applied', reason='Verified.')
        self.write('_Edits/Book-1/campaigns/line/campaign.json',
                   json.dumps(dict(schema_version=1, tasks=[{'status': 'pending'}])))
        summary = self.call(view='compact')
        self.assertEqual(summary['counts']['ready'], 1)
        self.assertIsNone(summary['first_blocker'])
        self.assertEqual(summary['campaigns']['needs_attention'], 1)
        self.assertTrue(summary['campaigns']['first_blocker'].endswith('line/campaign.json'))
        self.assertEqual(summary['author_read'], dict(personally_read=0, reported_complete=0))


if __name__ == '__main__':
    unittest.main()
