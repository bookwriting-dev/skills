#!/usr/bin/env python3
"""Exercise capture identity through the CLI and the stdio MCP server."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / 'skills/book-status/scripts/project_state.py'
MCP = ROOT / 'mcp/storycraft_mcp.py'


class ReviewCaptures(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.book = Path(temp.name).resolve() / 'book'
        shutil.copytree(ROOT / 'tools/eval-fixtures/storycraft-book', self.book)

    def cli(self, *args, success=True):
        result = subprocess.run([sys.executable, '-B', str(CLI), '--root', str(self.book), *args],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0 if success else 2, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def mcp(self, name, **arguments):
        request = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                   'params': {'name': 'storycraft_' + name,
                              'arguments': {'root': str(self.book), **arguments}}}
        result = subprocess.run([sys.executable, '-B', str(MCP)], input=json.dumps(request) + '\n',
                                capture_output=True, text=True, check=True)
        response = json.loads(result.stdout)['result']
        self.assertFalse(response['isError'], response['content'])
        return json.loads(response['content'][0]['text'])

    def test_interleaved_captures_bind_to_the_reviewed_revision(self):
        first = self.mcp('review_begin', chapter='1', review_type='Gate')
        capture = self.book / first['prepared']
        original = capture.read_bytes()
        chapter = self.book / first['subject_paths'][0]
        with chapter.open('a', encoding='utf-8') as stream:
            stream.write('\nShe gave him the key.\n')
        second = self.cli('chapter-finalize', '--chapter', '1')['prepared']
        self.assertNotEqual(first['prepared'], second['prepared'])
        self.assertNotEqual(first['capture_id'], second['capture_id'])
        self.assertNotEqual(first['inputs'], second['inputs'])
        self.assertEqual(original, capture.read_bytes())

        report = self.book / first['report']
        report.write_text('Review of the earlier chapter.\n', encoding='utf-8')
        self.cli('review-finish', '--prepared', first['prepared'], '--verdict', 'PASS', success=False)
        self.assertFalse(report.with_suffix('.meta.json').exists())
        report.write_text('Verified the revised ending.\n', encoding='utf-8')
        finished = self.mcp('review_finish', prepared=second['prepared'], verdict='PASS')
        self.assertEqual(finished['capture_id'], second['capture_id'])
        self.assertEqual(finished['inputs'], second['inputs'])
        self.assertTrue(self.mcp('dashboard')['chapters'][0]['ready'])

    def test_each_begin_is_distinct_and_explicit_capture_paths_are_create_only(self):
        explicit = 'review/first.json'
        first = self.cli('review-begin', '--chapter', '1', '--type', 'Gate', '--output', explicit)
        capture = self.book / explicit
        original = capture.read_bytes()
        collision = self.cli('chapter-finalize', '--chapter', '1', '--output', explicit, success=False)
        self.assertIn('already exists', collision['error'])
        self.assertEqual(capture.read_bytes(), original)

        second = self.mcp('chapter_finalize', chapter='1')['prepared']
        self.assertEqual(first['inputs'], second['inputs'])
        self.assertNotEqual(first['capture_id'], second['capture_id'])
        report = self.book / first['report']
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text('A saved review.\n', encoding='utf-8')
        self.cli('review-finish', '--prepared', explicit, '--verdict', 'PASS',
                 '--output', explicit, success=False)
        self.assertEqual(capture.read_bytes(), original)

    def test_existing_prepared_file_can_still_be_finished_by_path(self):
        review = self.cli('review-begin', '--chapter', '1', '--type', 'Gate')
        legacy = (self.book / review['report']).with_suffix('.prepared.json')
        spec = {key: review[key] for key in
                ('schema_version', 'book_id', 'report', 'verdict', 'subject_paths', 'inputs')}
        legacy.write_text(json.dumps(spec), encoding='utf-8')
        self.mcp('review_begin', chapter='1', review_type='Gate')
        self.assertEqual(json.loads(legacy.read_text(encoding='utf-8')), spec)
        (self.book / spec['report']).write_text('A saved review.\n', encoding='utf-8')
        result = self.mcp('review_finish', prepared=str(legacy.relative_to(self.book)), verdict='PASS')
        self.assertEqual(result['verdict'], 'PASS')
        self.assertEqual(result['inputs'], spec['inputs'])


if __name__ == '__main__':
    unittest.main()
