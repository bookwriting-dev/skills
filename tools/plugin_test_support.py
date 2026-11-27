"""Fixtures for exercising the packaged Storycraft servers over stdio."""

import json
import os
import shutil
import subprocess
import unittest

from skill_lib import ROOT


def copy_plugin_source(source):
    for folder in ('skills', 'mcp', 'plugin'):
        shutil.copytree(ROOT / folder, source / folder)
    (source / 'tools').mkdir()
    for script in ('build-claude-plugin.py', 'build-desktop-plugin.py', 'plugin_bundle.py', 'skill_lib.py'):
        shutil.copy2(ROOT / 'tools' / script, source / 'tools' / script)
    shutil.copy2(ROOT / 'VERSION', source / 'VERSION')


class PluginTestCase(unittest.TestCase):
    def rpc(self, bundle, project, requests):
        claude = (bundle / '.mcp.json').is_file()
        config_file = bundle / ('.mcp.json' if claude else 'mcp.json')
        config = json.loads(config_file.read_text())['mcpServers']['storycraft-state']
        root_var = '${CLAUDE_PLUGIN_ROOT}' if claude else '${PLUGIN_ROOT}'
        cwd = config.get('cwd', str(project)).replace(root_var, str(bundle))
        command = [value.replace(root_var, str(bundle)) for value in [config['command'], *config['args']]]
        env = {**os.environ, **{k: v.replace(root_var, str(bundle)) for k, v in config.get('env', {}).items()}}
        proc = subprocess.run(command, input=''.join(json.dumps(req) + '\n' for req in requests),
                              cwd=cwd, env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        responses = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual([msg['id'] for msg in responses], [req['id'] for req in requests])
        for msg in responses:
            self.assertNotIn('error', msg, msg)
        return [msg['result'] for msg in responses]

    def call(self, bundle, project, *calls):
        requests = [{'jsonrpc': '2.0', 'id': index, 'method': 'tools/call', 'params': {
            'name': f'storycraft_{tool}', 'arguments': {'root': str(project), **params},
        }} for index, (tool, params) in enumerate(calls)]
        results = self.rpc(bundle, project, requests)
        for result in results:
            self.assertFalse(result.get('isError'), result['content'])
        return [json.loads(result['content'][0]['text']) for result in results]
