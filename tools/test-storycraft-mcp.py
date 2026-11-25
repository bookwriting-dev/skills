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
        self.assertEqual(len(tool_names), 9)
        self.assertIn('storycraft_compile', tool_names)

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


if __name__ == '__main__':
    unittest.main()
