#!/usr/bin/env python3
"""Install the local Claude marketplace and exchange saved reviews with the desktop plugin."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

from plugin_test_support import PluginTestCase, copy_plugin_source
from skill_lib import ROOT


def claude_binary():
    if os.environ.get('CLAUDE_BIN'):
        return os.environ['CLAUDE_BIN']
    if executable := shutil.which('claude'):
        return executable
    desktop = Path.home() / 'Library/Application Support/Claude/claude-code'
    builds = list(desktop.glob('*/*/claude.app/Contents/MacOS/claude'))
    if builds:
        return str(max(builds, key=lambda path: path.stat().st_mtime))
    raise FileNotFoundError('Set CLAUDE_BIN to the Claude Code executable to run the marketplace test.')


class ClaudeMarketplaceTest(PluginTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='storycraft-claude-check-')
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.source = root / 'source'
        copy_plugin_source(self.source)
        self.desktop = root / 'Desktop plugin'
        self.marketplace = root / 'Claude marketplace'
        self.book = root / 'Manuscript workspace'
        shutil.copytree(ROOT / 'tools/eval-fixtures/storycraft-book', self.book)
        subprocess.run(['git', 'init', '-q', str(self.book)], check=True)
        ledger = self.book / 'Wiki/Story/Book-1/promises.yaml'
        ledger.parent.mkdir(parents=True)
        ledger.write_text('promises:\n  - id: P1\n    promise: Letter in the attic\n'
                          '    introduced_ch: ch1\n    payoff_by_ch: ch2\n', encoding='utf-8')
        self.cli = claude_binary()
        self.env = {**os.environ, 'CLAUDE_CONFIG_DIR': str(root / 'Claude settings'),
                    'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1', 'DISABLE_AUTOUPDATER': '1'}

    def build(self, host, output):
        subprocess.run([sys.executable, '-B', str(self.source / f'tools/build-{host}-plugin.py'), str(output)],
                       check=True, capture_output=True, text=True, timeout=30)

    def claude(self, *args):
        proc = subprocess.run([self.cli, *map(str, args)], cwd=self.book, env=self.env,
                              capture_output=True, text=True, timeout=45)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return proc.stdout

    def install(self):
        bundle = self.marketplace / 'plugins/storycraft'
        self.claude('plugin', 'validate', '--strict', self.marketplace)
        validation = json.loads(self.claude('plugin', 'validate', '--strict', '--json', bundle))
        expected = {'storycraft:' + path.parent.name for path in (self.source / 'skills').glob('*/SKILL.md')}
        self.assertEqual(set(validation['provides']['skills']), expected | {'storycraft:storycraft-workspace'})
        self.claude('plugin', 'marketplace', 'add', self.marketplace)
        self.claude('plugin', 'install', 'storycraft@storycraft-local')
        plugins = json.loads(self.claude('plugin', 'list', '--json'))
        entry = next(p for p in plugins if p['id'] == 'storycraft@storycraft-local')
        self.assertTrue(entry['enabled'])
        self.assertEqual(entry['version'], (self.source / 'VERSION').read_text().strip())
        status = self.claude('mcp', 'get', 'plugin:storycraft:storycraft-state')
        self.assertRegex(status, r'(?m)^\s*Status:\s*(?:[✔✓]\s*)?Connected\s*$')
        # Newer clients load a local marketplace in place. Older clients use their install cache.
        installed = Path(entry.get('readFromFolder') or entry['installPath'])
        self.assertEqual(entry['mcpServers'], json.loads((installed / '.mcp.json').read_text())['mcpServers'])
        return installed

    def save_gate(self, begin_host, finish_host, chapter):
        review, = self.call(begin_host, self.book, ('review_begin', {'chapter': chapter, 'review_type': 'Gate'}))
        self.assertTrue(any(item['kind'] == 'plugin-skill' for item in review['inputs']))
        (self.book / review['report']).write_text(f'Saved editorial review for chapter {chapter}.\n')
        finished, = self.call(finish_host, self.book, ('review_finish', {'prepared': review['prepared'],
                                                                        'verdict': 'PASS'}))
        return finished['meta']

    def check_gates(self, bundle, saved, freshness):
        dashboard, = self.call(bundle, self.book, ('dashboard', {}))
        checks = {check['path']: check for chapter in dashboard['chapters'] for check in chapter['checks']}
        for path, original_bytes in saved.items():
            check = checks[path]
            self.assertEqual((check['verdict'], check['freshness']), ('PASS', freshness), check)
            if freshness == 'STALE':
                self.assertIn('changed plugin review skill: gate-check', check['reasons'])
            self.assertEqual((self.book / path).read_bytes(), original_bytes)

    def test_concurrent_builds_preserve_catalog_entries(self):
        path = self.marketplace / '.claude-plugin/marketplace.json'
        path.parent.mkdir(parents=True)
        neighbor = {'name': 'another-plugin', 'source': './plugins/another-plugin'}
        path.write_text(json.dumps({'name': 'personal', 'owner': {'name': 'Author'}, 'plugins': [neighbor]}))
        with ThreadPoolExecutor(max_workers=3) as pool:
            builds = [pool.submit(self.build, 'claude', self.marketplace) for _ in range(3)]
            for build in builds:
                build.result()
        catalog = json.loads(path.read_text())
        self.assertEqual(catalog['name'], 'personal')
        self.assertEqual(catalog['plugins'][0], neighbor)
        self.assertEqual([entry['name'] for entry in catalog['plugins']], ['another-plugin', 'storycraft'])
        self.assertTrue((self.marketplace / catalog['plugins'][1]['source'] / '.mcp.json').is_file())

    def test_marketplace_and_review_handoff(self):
        self.build('desktop', self.desktop)
        first = self.save_gate(self.desktop, self.desktop, '1')
        saved = {first: (self.book / first).read_bytes()}
        self.build('claude', self.marketplace)
        installed = self.install()
        self.check_gates(installed, saved, 'CURRENT')
        self.assertEqual((installed / 'review-skill-digests.json').read_bytes(),
                         (self.desktop / 'review-skill-digests.json').read_bytes())

        for chapter, begin, finish in [('2', installed, installed), ('3', self.desktop, installed)]:
            meta = self.save_gate(begin, finish, chapter)
            saved[meta] = (self.book / meta).read_bytes()
        for host in (self.desktop, installed):
            self.check_gates(host, saved, 'CURRENT')

        preflight, promises = self.call(installed, self.book, ('chapter_preflight', {'chapter': '1'}), ('promises', {}))
        self.assertTrue(preflight['draft_packet'])
        self.assertEqual(promises['returncode'], 0, promises)
        self.assertIn('Letter in the attic', promises['stdout'])
        # Execute the fallback printed in the installed skill from a book with no local skill library.
        skill = installed / 'skills/promise-tracker'
        example = next(line for line in (skill / 'SKILL.md').read_text().splitlines() if line.endswith(' --chapter chNN'))
        command = example.replace('${CLAUDE_PLUGIN_ROOT}', str(installed)).replace('${CLAUDE_SKILL_DIR}', str(skill))
        output = subprocess.check_output(shlex.split(command.replace('chNN', 'ch1')), cwd=self.book, text=True)
        self.assertIn('Letter in the attic', output)
        yaml_file = subprocess.check_output([str(installed / 'run-python'), '-c', 'import yaml; print(yaml.__file__)'],
                                            cwd=self.book, text=True).strip()
        self.assertTrue(Path(yaml_file).resolve().is_relative_to((installed / 'python').resolve()), yaml_file)
        self.assertFalse((self.book / '.agents').exists())

        # Both hosts must still invalidate the saved sidecars when editorial inputs really change.
        with (self.source / 'skills/gate-check/SKILL.md').open('a', encoding='utf-8') as gate:
            gate.write('\nVerify the cited chapter ending against its approved scene plan.\n')
        self.build('desktop', self.desktop)
        self.check_gates(self.desktop, saved, 'STALE')
        self.check_gates(installed, saved, 'CURRENT')
        self.build('claude', self.marketplace)
        self.check_gates(self.marketplace / 'plugins/storycraft', saved, 'STALE')


if __name__ == '__main__':
    unittest.main()
