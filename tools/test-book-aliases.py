#!/usr/bin/env python3
"""Stable book IDs and display labels share manuscript artifacts across the CLI and MCP."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/book-status/scripts'
sys.path.insert(0, str(SCRIPTS))
sys.dont_write_bytecode = True
import project_manifest as resolver


class BookAliases(unittest.TestCase):
    stable_id = 'harbor-novel'
    label = 'Book-1'

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        shutil.copytree(ROOT / 'tools/eval-fixtures/storycraft-book', self.root, dirs_exist_ok=True)
        manifest = resolver.propose(self.root)['manifest']
        self.book = manifest['books'][0]
        self.book['id'] = self.stable_id
        self.write_json(resolver.MANIFEST_PATH, manifest)

    def write_json(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
        return path

    def cli(self, book, *args):
        proc = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'project_state.py'),
                               '--root', str(self.root), '--book', book, *args],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def mcp(self, tool, book, **args):
        if book is not None:
            args['book'] = book
        request = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                   'params': {'name': 'storycraft_' + tool, 'arguments': {
                       'root': str(self.root), **args}}}
        proc = subprocess.run([sys.executable, '-B', str(ROOT / 'mcp/storycraft_mcp.py')],
                              input=json.dumps(request) + '\n', capture_output=True, text=True, check=True)
        result = json.loads(proc.stdout)['result']
        self.assertFalse(result['isError'], result)
        return json.loads(result['content'][0]['text'])

    def test_gate_saved_by_stable_id_is_current_for_both_dashboard_views_and_selectors(self):
        capture = self.mcp('review_begin', self.stable_id, chapter='1', review_type='Gate')
        (self.root / capture['report']).write_text('PASS\nThe ending pays off the opening question.\n')
        saved = self.mcp('review_finish', None, prepared=capture['prepared'], verdict='PASS')
        self.assertEqual(saved['meta'], f'_Edits/{self.label}/Chapter-001_Gate.meta.json')
        for selector in (self.stable_id, self.label):
            full = self.mcp('dashboard', selector)['chapters'][0]
            compact = self.mcp('dashboard', selector, view='compact', chapter='1')
            self.assertEqual(compact['chapter'], full)
            self.assertEqual(compact['counts']['ready'], 1)
            self.assertTrue(full['ready'])
            check, = full['checks']
            self.assertEqual((check['path'], check['verdict'], check['freshness'], check['readiness']),
                             (saved['meta'], 'PASS', 'CURRENT', 'ELIGIBLE'))

    def test_cli_and_mcp_select_one_artifact_tree(self):
        chapter = self.book['chapters'][0]['path']
        spec = self.write_json('campaign.json', {'schema_version': 1, 'tasks': [{'id': 'revise', 'files': [chapter]}]})
        campaign = self.cli(self.stable_id, 'campaign', '--run', 'proof', '--action', 'init', '--spec', str(spec))
        self.assertEqual(self.cli(self.label, 'campaign', '--run', 'proof', '--action', 'status'), campaign)
        self.cli(self.stable_id, 'author-read', '--action', 'start')
        self.cli(self.label, 'author-read', '--action', 'mark', '--chapter', '1')
        status = self.cli(self.stable_id, 'author-read', '--action', 'status')
        self.assertEqual(status['personally_read'], 1)
        canonical = self.root / '_Edits' / self.label
        (canonical / 'report.md').write_text('One finding.')
        self.mcp('record_disposition', self.stable_id, report=f'_Edits/{self.label}/report.md',
                 finding_id='1', disposition='deferred', reason='Later pass')
        self.assertTrue((canonical / 'decisions.jsonl').is_file())
        for selector in (self.stable_id, self.label):
            dashboard = self.mcp('dashboard', selector)
            self.assertEqual(dashboard['author_read']['personally_read'], 1)
            self.assertEqual([row['path'] for row in dashboard['campaigns']],
                             [f'_Edits/{self.label}/campaigns/proof/campaign.json'])
        plan = self.mcp('compile', self.stable_id)
        self.assertEqual(plan, self.mcp('compile', self.label))
        self.assertIn(f'unfinished campaign: _Edits/{self.label}/campaigns/proof/campaign.json', plan['warnings'])
        self.assertFalse((self.root / '_Edits' / self.stable_id).exists())

    def test_existing_id_records_remain_accessible_with_canonical_precedence(self):
        self.cli(self.label, 'author-read', '--action', 'start')
        self.cli(self.label, 'author-read', '--action', 'mark', '--chapter', '1')
        canonical = self.root / '_Edits' / self.label
        legacy = self.root / '_Edits' / self.stable_id
        canonical.rename(legacy)
        for run in ('both', 'legacy'):
            self.write_json(f'_Edits/{self.stable_id}/campaigns/{run}/campaign.json',
                            {'schema_version': 1, 'tasks': [], 'cancelled': True})
        self.write_json(f'_Edits/{self.label}/campaigns/both/campaign.json',
                        {'schema_version': 1, 'tasks': [], 'sealed': True})
        self.cli(self.label, 'author-read', '--action', 'mark', '--chapter', '2')
        for selector in (self.stable_id, self.label):
            dash = self.mcp('dashboard', selector)
            self.assertEqual(dash['author_read']['personally_read'], 2)
            self.assertEqual([(row['sealed'], row['cancelled']) for row in dash['campaigns']],
                             [(True, False), (False, True)])
            self.assertTrue(self.cli(selector, 'campaign', '--run', 'both', '--action', 'status')['sealed'])
        self.assertFalse((canonical / 'author-read/progress.json').exists())
        shutil.copytree(legacy / 'author-read', canonical / 'author-read')
        self.cli(self.stable_id, 'author-read', '--action', 'mark', '--chapter', '3')
        self.assertEqual(len(json.loads((canonical / 'author-read/progress.json').read_text())['marks']), 3)
        self.assertEqual(len(json.loads((legacy / 'author-read/progress.json').read_text())['marks']), 2)

    def test_saved_conventional_roster_merges_later_drafts_for_either_selector(self):
        (self.root / 'Chapters/Book-1/Chapter-004.md').write_text('# Chapter 4\n\nWater fell.\n')
        book = resolver.resolve_book(self.root, self.stable_id)
        self.assertEqual(book, resolver.resolve_book(self.root, self.label))
        self.assertEqual(len(book['chapters']), 4)

    def test_another_books_display_folder_never_becomes_a_legacy_fallback(self):
        other_id = 'volume-two'
        chapter = 'Chapters/Book-2/Chapter-001.md'
        path = self.root / chapter
        path.parent.mkdir()
        path.write_text('# Chapter 1\n\nA different narrator spoke.\n')
        manifest = resolver.load(self.root)
        other = {'id': other_id, 'display_label': self.stable_id, 'chapter_order': 'declared',
                 'chapters': [{'id': 'volume-two-intro', 'display_label': 'Chapter 1',
                               'reading_order': 1, 'path': chapter}]}
        manifest['books'].append(other)
        self.write_json(resolver.MANIFEST_PATH, manifest)
        spec = self.write_json('tasks.json', {'schema_version': 1, 'tasks': []})
        self.cli(other_id, 'campaign', '--run', 'proof', '--action', 'init', '--spec', str(spec))
        self.cli(other_id, 'author-read', '--action', 'start')
        self.cli(other_id, 'author-read', '--action', 'mark', '--chapter', '1')

        owner = self.mcp('dashboard', other_id)
        self.assertEqual(len(owner['campaigns']), 1)
        self.assertEqual(owner['author_read']['personally_read'], 1)
        first = self.mcp('dashboard', self.label)
        self.assertEqual(first['campaigns'], [])
        self.assertEqual(first['author_read']['personally_read'], 0)
        self.cli(self.label, 'campaign', '--run', 'proof', '--action', 'init', '--spec', str(spec))
        self.assertTrue((self.root / f'_Edits/{self.label}/campaigns/proof/campaign.json').is_file())

        # A filesystem alias of the owner's directory carries the same ownership.
        original = self.root / '_Edits' / self.stable_id
        other['display_label'] = self.stable_id.upper()
        other_folder = self.root / '_Edits' / other['display_label']
        if not other_folder.exists():
            other_folder.symlink_to(original, target_is_directory=True)
        self.write_json(resolver.MANIFEST_PATH, manifest)
        self.assertEqual(resolver.edit_roots(self.root, self.book), [self.root / '_Edits' / self.label])

    def test_saved_import_order_is_the_same_for_either_selector(self):
        units = [{'id': row['id'], 'chapter_id': row['id'], 'role': 'narrative',
                  'filename': Path(row['path']).name, 'title': row['display_label']}
                 for row in reversed(self.book['chapters'])]
        self.write_json(f'Chapters/{self.label}/.storycraft-import.json', {'epub': {'units': units}})
        book = resolver.resolve_book(self.root, self.stable_id)
        self.assertEqual(book, resolver.resolve_book(self.root, self.label))
        self.assertEqual([row['id'] for row in book['chapters']], [unit['id'] for unit in units])

    @unittest.skipUnless(importlib.util.find_spec('yaml'), 'PyYAML required for promise audit')
    def test_promise_audit_reads_the_manuscript_ledger_by_stable_id(self):
        self.write_json(f'Wiki/Story/{self.label}/promises.yaml', {'promises': [
            {'id': 'P1', 'promise': 'Letter in the attic', 'introduced_ch': 'ch1', 'payoff_by_ch': 'ch2'}]})
        result = self.mcp('promises', self.stable_id, chapter='ch3')
        self.assertEqual(result, self.mcp('promises', self.label, chapter='ch3'))
        self.assertIn('Letter in the attic', json.dumps(result))

    def test_shell_only_run_does_not_require_a_manifest(self):
        (self.root / resolver.MANIFEST_PATH).unlink()
        shutil.rmtree(self.root / 'Chapters')
        spec = self.write_json('empty-campaign.json', {'schema_version': 1, 'tasks': []})
        self.cli('scratch', 'campaign', '--run', 'prep', '--action', 'init', '--spec', str(spec))
        self.assertTrue((self.root / '_Edits/scratch/campaigns/prep/campaign.json').is_file())


if __name__ == '__main__':
    unittest.main()
