#!/usr/bin/env python3
"""Integration tests for the Storycraft MCP server and plugin bundle."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
MCP_SERVER = ROOT / 'mcp' / 'storycraft_mcp.py'


class StorycraftMcpTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.book = Path(self.temp.name) / 'book'
        shutil.copytree(ROOT / 'tools' / 'eval-fixtures' / 'storycraft-book', self.book)

    def tearDown(self):
        self.temp.cleanup()

    def _rpc_session(self, requests, *, command=None, env=None):
        payload = '\n'.join(json.dumps(r) for r in requests) + '\n'
        proc = subprocess.run(
            command or [sys.executable, str(MCP_SERVER)],
            input=payload, capture_output=True, text=True, check=False,
            env=env or {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]

    def test_mcp_initialize_list_and_tool_calls(self):
        responses = self._rpc_session([
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}},
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
            {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {
                'name': 'storycraft_dashboard',
                'arguments': {'root': str(self.book), 'book': 'Book-1'},
            }},
            {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {
                'name': 'storycraft_rhythm_map',
                'arguments': {'root': str(self.book), 'book': 'Book-1', 'markdown': True},
            }},
            {'jsonrpc': '2.0', 'id': 5, 'method': 'tools/call', 'params': {
                'name': 'storycraft_review_begin',
                'arguments': {'root': str(self.book), 'book': 'Book-1', 'chapter': '1', 'review_type': 'Gate'},
            }},
        ])
        self.assertEqual(len(responses), 5)
        self.assertEqual(responses[0]['result']['serverInfo']['name'], 'storycraft-state')
        tool_names = {t['name'] for t in responses[1]['result']['tools']}
        self.assertGreaterEqual(len(tool_names), 13)
        self.assertTrue({'storycraft_compile', 'storycraft_kanban', 'storycraft_reanchor',
                         'storycraft_chapter_preflight', 'storycraft_chapter_finalize'}.issubset(tool_names))

        dash = json.loads(responses[2]['result']['content'][0]['text'])
        self.assertEqual(dash['project_type'], 'FICTION')
        self.assertEqual(len(dash['chapters']), 3)

        rmap = json.loads(responses[3]['result']['content'][0]['text'])
        self.assertEqual(rmap['chapter_count'], 3)
        self.assertIn('# Rhythm & Thread Matrix', rmap['markdown'])

        begun = json.loads(responses[4]['result']['content'][0]['text'])
        self.assertTrue((self.book / begun['prepared']).is_file())

    def test_plugin_manifest_and_mcp_config_valid(self):
        plugin_manifest = json.loads((ROOT / 'plugin' / 'plugin.json').read_text(encoding='utf-8'))
        allowed_keys = {
            'name', 'description', 'logo', 'suggestedPrompts', 'displayName',
            'version', 'author', 'homepage', 'repository', 'disabled',
        }
        self.assertTrue(set(plugin_manifest).issubset(allowed_keys))
        self.assertEqual(plugin_manifest['name'], 'storycraft-skills')
        self.assertLessEqual(len(plugin_manifest.get('suggestedPrompts', [])), 3)

        mcp_cfg = json.loads((ROOT / 'plugin' / 'mcp_config.json').read_text(encoding='utf-8'))
        self.assertIn('storycraft-state', mcp_cfg.get('mcpServers', {}))
        self.assertIn('${CLAUDE_PLUGIN_ROOT}', mcp_cfg['mcpServers']['storycraft-state']['args'][0])

    def test_generic_package_runs_without_site_packages(self):
        temp = Path(self.temp.name)
        bundle = temp / 'Generic package'
        subprocess.run(['make', 'plugin-dist', f'PLUGIN_DIST_DIR={bundle}'], cwd=ROOT,
                       capture_output=True, text=True, check=True)
        version = (ROOT / 'VERSION').read_text().strip()
        manifest = json.loads((bundle / 'plugin.json').read_text())
        self.assertEqual(manifest['version'], version)
        rules = (bundle / 'rules/AGENTS.md').read_text()
        self.assertIn('Storycraft Suite', rules)
        self.assertNotIn('__SERIES_TITLE__', rules)
        self.assertNotIn('__PROJECT_TYPE__', rules)

        venv = temp / 'runtime'
        subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(venv)], check=True)
        cfg = json.loads((bundle / 'mcp_config.json').read_text())['mcpServers']['storycraft-state']
        command = [word.replace('${CLAUDE_PLUGIN_ROOT}', str(bundle)) for word in [cfg['command'], *cfg['args']]]
        env = {'PATH': os.environ['PATH'], 'STORYCRAFT_PYTHON': str(venv / 'bin/python'),
               'PYTHONNOUSERSITE': '1', **cfg.get('env', {})}
        ledger = self.book / 'Wiki/Story/Book-1/promises.yaml'
        ledger.parent.mkdir(parents=True)
        ledger.write_text('promises:\n  - id: P1\n    promise: Letter in the attic\n'
                          '    introduced_ch: ch1\n    payoff_by_ch: ch2\n')
        responses = self._rpc_session([
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {
                'name': 'storycraft_promises', 'arguments': {'root': str(self.book)}}},
            {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {
                'name': 'storycraft_review_begin', 'arguments': {'root': str(self.book), 'review_type': 'Gate'}}},
        ], command=command, env=env)
        self.assertEqual(responses[0]['result']['serverInfo']['version'], version)
        self.assertFalse(responses[1]['result']['isError'], responses[1])
        self.assertIn('Letter in the attic', responses[1]['result']['content'][0]['text'])
        review = json.loads(responses[2]['result']['content'][0]['text'])
        self.assertEqual(review['storycraft_version'], version)
        digests = json.loads((bundle / 'review-skill-digests.json').read_text())
        self.assertIn({'kind': 'plugin-skill', 'path': 'gate-check', 'sha256': digests['gate-check']},
                      review['inputs'])

    def _compile(self, **arguments):
        response, = self._rpc_session([{'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {
            'name': 'storycraft_compile', 'arguments': {'root': str(self.book), **arguments}}}])
        return response['result']

    def test_compile_reads_project_relative_config(self):
        config = self.book / 'Export settings.json'
        config.write_text(json.dumps({'schema_version': 1, 'title': 'Fixture book'}))
        result = self._compile(config=config.name)
        self.assertFalse(result['isError'], result)
        self.assertEqual(json.loads(result['content'][0]['text'])['config']['title'], 'Fixture book')
        for invalid_path in (str(config.resolve()), '../settings.json'):
            with self.subTest(config=invalid_path):
                self.assertTrue(self._compile(config=invalid_path)['isError'])
        config.write_text(json.dumps({'schema_version': 1, 'pdf_engine': 'unknown-engine'}))
        self.assertTrue(self._compile(formats=['pdf'], config=config.name)['isError'])

    @unittest.skipUnless(shutil.which('pandoc') and shutil.which('typst'), 'Pandoc and Typst required')
    def test_compile_pdf_preflight_and_build(self):
        config = self.book / 'export.json'
        config.write_text(json.dumps({'schema_version': 1, 'pdf_engine': 'typst'}))
        preflight = self._compile(formats=['pdf'], config=config.name)
        self.assertFalse(preflight['isError'], preflight)
        plan = json.loads(preflight['content'][0]['text'])
        self.assertEqual((plan['delivery_status'], plan['pdf_engine']), ('PREFLIGHTED_NOT_BUILT', 'typst'))
        config.write_text(json.dumps({'schema_version': 1, 'pdf_engine': 'pdflatex'}))
        engine = shutil.which('typst')
        build = self._compile(formats=['pdf'], config=config.name, pdf_engine=engine, check=False)
        self.assertFalse(build['isError'], build)
        plan = json.loads(build['content'][0]['text'])
        self.assertEqual((plan['structural_checks']['pdf'], plan['pdf_engine']), ('PASS', engine))
        pdf = Path(plan['output']) / 'manuscript-combined.pdf'
        self.assertTrue(pdf.read_bytes().startswith(b'%PDF-'))

    def test_mcp_lsp_framing_with_extra_headers_and_tier3_tools(self):
        init_req = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}}).encode('utf-8')
        kanban_req = json.dumps({
            'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
            'params': {'name': 'storycraft_kanban', 'arguments': {'root': str(self.book), 'book': 'Book-1'}},
        }).encode('utf-8')
        stream = (
            b'\n\nContent-Type: application/vscode-jsonrpc; charset=utf-8\r\n'
            + f'Content-Length: {len(init_req)}\r\n\r\n'.encode('ascii') + init_req
            + f'Content-Length: {len(kanban_req)}\r\nContent-Type: application/json\r\n\r\n'.encode('ascii')
            + kanban_req
        )
        proc = subprocess.run(
            [sys.executable, str(MCP_SERVER)],
            input=stream, capture_output=True, check=False,
            env={'PATH': '/usr/bin:/bin:/opt/homebrew/bin', 'PYTHONDONTWRITEBYTECODE': '1'},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode('utf-8', errors='replace'))
        bodies = proc.stdout.split(b'Content-Length:')
        self.assertEqual(len(bodies), 3)
        k_resp = json.loads(bodies[2].split(b'\r\n\r\n', 1)[1])
        k_data = json.loads(k_resp['result']['content'][0]['text'])
        self.assertEqual(k_data['path'], 'Wiki/Story/Book-1/kanban.md')
        self.assertTrue((self.book / 'Wiki/Story/Book-1/kanban.md').is_file())


if __name__ == '__main__':
    unittest.main()
