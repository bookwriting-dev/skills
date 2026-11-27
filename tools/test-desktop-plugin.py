#!/usr/bin/env python3
"""Verify shared desktop release selection and review freshness with two fixture repos."""

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from plugin_test_support import PluginTestCase, copy_plugin_source
from skill_lib import ROOT


class DesktopPluginTest(PluginTestCase):
    def test_two_books_share_upgrades_and_recheck_review_evidence(self):
        with tempfile.TemporaryDirectory(prefix='storycraft-plugin-check-') as directory:
            temp = Path(directory)
            source = temp / 'source'
            copy_plugin_source(source)
            bundle = temp / 'installed plugin'
            self.build(source, bundle, '1.0.0')

            projects = []
            for label in ('Author A', 'Author B'):
                project = temp / label
                shutil.copytree(ROOT / 'tools/eval-fixtures/storycraft-book', project)
                subprocess.run(['git', 'init', '-q', str(project)], check=True)
                ledger = project / 'Wiki/Story/Book-1/promises.yaml'
                ledger.parent.mkdir(parents=True)
                ledger.write_text(f'promises:\n  - id: P1\n    promise: Payoff for {label}\n'
                                  '    introduced_ch: ch1\n    payoff_by_ch: ch2\n', encoding='utf-8')
                self.assertFalse((project / '.agents/skills').exists())
                dashboard, preflight, promises, review = self.call(bundle, project,
                    ('dashboard', {}), ('chapter_preflight', {'chapter': '1'}), ('promises', {}),
                    ('review_begin', {'review_type': 'Gate'}))
                self.assertEqual(dashboard['storycraft_version'], '1.0.0')
                self.assertEqual(len(dashboard['chapters']), 3)
                self.assertTrue(preflight['draft_packet'])
                self.assertIn(f'Payoff for {label}', promises['stdout'])
                self.assertEqual(review['storycraft_version'], '1.0.0')
                self.assertTrue(any(item['kind'] == 'plugin-skill' for item in review['inputs']))
                (project / review['report']).write_text('Fixture gate report.\n', encoding='utf-8')
                self.call(bundle, project, ('review_finish', {'prepared': review['prepared'], 'verdict': 'PASS'}))
                projects.append(project)

            # A version bump with identical review rules retains the evidence in both repos.
            self.build(source, bundle, '1.0.1')
            for project in projects:
                dashboard, = self.call(bundle, project, ('dashboard', {}))
                self.assertEqual(dashboard['storycraft_version'], '1.0.1')
                self.assertEqual(dashboard['chapters'][0]['checks'][0]['freshness'], 'CURRENT')

            gate = source / 'skills/gate-check/SKILL.md'
            with gate.open('a', encoding='utf-8') as handle:
                handle.write('\nA changed review input for the release fixture.\n')
            self.build(source, bundle, '1.0.2')
            for project in projects:
                dashboard, = self.call(bundle, project, ('dashboard', {}))
                self.assertEqual(dashboard['storycraft_version'], '1.0.2')
                check = dashboard['chapters'][0]['checks'][0]
                self.assertEqual(check['freshness'], 'STALE')
                self.assertIn('changed plugin review skill: gate-check', check['reasons'])
                self.assertFalse((project / '.agents').exists())

    def build(self, source, bundle, version):
        (source / 'VERSION').write_text(version + '\n', encoding='utf-8')
        proc = subprocess.run([sys.executable, '-B', str(source / 'tools/build-desktop-plugin.py'), str(bundle)],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == '__main__':
    unittest.main()
