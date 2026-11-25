#!/usr/bin/env python3
"""Integration tests for the Storycraft MCP server and plugin bundle."""
import json
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

    def _rpc_session(self, requests):
        payload = '\n'.join(json.dumps(r) for r in requests) + '\n'
        proc = subprocess.run(
            [sys.executable, str(MCP_SERVER)],
            input=payload, capture_output=True, text=True, check=False,
            env={'PATH': '/usr/bin:/bin:/opt/homebrew/bin', 'PYTHONDONTWRITEBYTECODE': '1'},
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
