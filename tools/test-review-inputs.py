#!/usr/bin/env python3
"""Chapter-specific review evidence discovery and preflight checks at normal entry points."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'mcp'))
import storycraft_mcp as server
import state_reviews


class ReviewInputs(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve() / 'book'
        shutil.copytree(ROOT / 'tools/eval-fixtures/storycraft-book', self.root)
        self.write('Chapters/Book-1/Chapter-001.md', '# Chapter 1\n\nMara reached the harbor.')

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')

    def call(self, name, **args):
        return server._call_tool('storycraft_' + name, dict(root=str(self.root), **args))

    def begin(self, **kwargs):
        capture = self.call('review_begin', chapter='1', review_type='Gate', **kwargs)
        self.write(capture['report'], 'The chapter passes.')
        return capture

    def check(self, meta):
        return state_reviews.freshness(self.root, self.root / meta)

    def old_review(self, report, review_type='Gate', extra_paths=()):
        capture = self.call('review_begin', chapter='1', review_type=review_type,
                            extra_paths=list(extra_paths))
        self.write(report, 'The chapter passes.')
        meta = self.call('review_finish', prepared=capture['prepared'], report=report, verdict='PASS')['meta']
        old = json.loads((self.root / meta).read_text())
        del old['review_selection'], old['capture_id']
        self.write(meta, json.dumps(old))
        return meta

    def test_new_and_overriding_sources_invalidate_only_their_chapter(self):
        plan = 'Wiki/Outline/Book-1/plan.md'
        self.write(plan, '# Plan\n\n## Chapter 1\nArrival.\n\n## Chapter 2\nDeparture.')
        capture = self.begin()
        meta = self.call('review_finish', prepared=capture['prepared'], verdict='PASS')['meta']
        self.write('Wiki/Characters/Ben.md', 'Ben lives abroad.')
        self.write('Wiki/Outline/Book-1/Chapter_02_Scene.md', 'Departure, in detail.')
        self.assertEqual(self.check(meta)['freshness'], 'CURRENT')

        new_inputs = {
            'Wiki/Style/style_guide.md': 'Short sentences.',
            'Wiki/Style/review_guide.md': 'Look for viewpoint drift.',
            'Wiki/Outline/Book-1/Chapter_01_Scene.md': 'Arrival, in detail.',
            'Wiki/Characters/The_Skipper.md': '---\naliases:\n  - Mara\n---\nHarbor pilot.',
            'Wiki/Psych/Book-1/Chapter_001_Psych.md': 'Mara fears the crossing.',
        }
        for name, text in new_inputs.items():
            with self.subTest(name=name):
                self.write(name, text)
                with self.assertRaisesRegex(ValueError, 'review inputs changed'):
                    self.call('review_finish', prepared=capture['prepared'], verdict='PASS')
                check = self.check(meta)
                self.assertEqual(check['freshness'], 'STALE')
                self.assertTrue(any(name in reason for reason in check['reasons']), check)
                (self.root / name).unlink()
                self.assertEqual(self.check(meta)['freshness'], 'CURRENT')

    def test_old_standard_sidecar_and_explicit_extra_paths(self):
        self.write('editor-note.md', 'Preserve the ending.')
        capture = self.begin(extra_paths=[str(self.root / 'editor-note.md')])
        meta = self.call('review_finish', prepared=capture['prepared'], verdict='PASS')['meta']
        old = json.loads((self.root / meta).read_text())
        del old['review_selection']
        self.write(meta, json.dumps(old))
        self.assertEqual(self.check(meta)['freshness'], 'CURRENT')
        self.write('editor-note.md', 'Change the ending.')
        self.assertEqual(self.check(meta)['freshness'], 'STALE')
        self.write('editor-note.md', 'Preserve the ending.')
        self.write('Wiki/Style/Review Guide.md', 'Use local spellings.')
        self.assertEqual(self.check(meta)['freshness'], 'STALE')

    def test_first_shared_sources_with_only_later_chapter_material(self):
        self.write('_Edits/Book-1/evidence/Chapter-001.json',
                   json.dumps({'schema_version': 1, 'sources': ['early-notes.md']}))
        capture = self.call('review_begin', chapter='1', review_type='FactCheck')
        self.write(capture['report'], 'All claims verified.')
        meta = self.call('review_finish', prepared=capture['prepared'], verdict='PASS')['meta']
        knowledge = 'Wiki/Story/Book-1/knowledge.json'
        plan = 'Wiki/Outline/Book-1/plan.md'
        self.write(plan, '# Plan\n\n## Chapter 2\nDeparture.')
        self.write(knowledge, json.dumps({'events': [{'source': 'Chapters/Book-1/Chapter-002.md'}]}))
        self.write('Wiki/Research/later-notes.md', 'A later chapter uses this source.')
        self.assertEqual(self.check(meta)['freshness'], 'CURRENT')
        self.write(plan, '# Plan\n\nAll dates follow the local calendar.\n\n## Chapter 2\nDeparture.')
        self.write(knowledge, json.dumps({'events': [{'source': 'Chapters/Book-1/Chapter-001.md'}]}))
        self.write('Wiki/Research/early-notes.md', 'Source for the first chapter.')
        reasons = self.check(meta)['reasons']
        for name in (knowledge, plan, 'Wiki/Research'):
            self.assertTrue(any(name in reason for reason in reasons), reasons)

    def test_custom_historical_report_recovers_review_type_from_plugin_or_pinned_skill(self):
        pinned = '.agents/skills/nonfiction-factcheck/SKILL.md'
        source = '_Edits/Book-1/evidence/Chapter-001.json'
        for kind in ('plugin', 'pinned'):
            with self.subTest(kind=kind):
                digests = {'nonfiction-factcheck': 'fact-check content'} if kind == 'plugin' else {}
                if kind == 'pinned':
                    self.write(pinned, 'Check the cited sources.')
                with patch.dict('state_core._PLUGIN_DIGESTS', digests, clear=True):
                    meta = self.old_review(f'_Edits/Book-1/{kind}-audit.md', 'FactCheck')
                    self.assertEqual(self.check(meta)['freshness'], 'CURRENT')
                    self.write(source, '{"sources": ["S1"]}')
                    self.assertIn('changed input: ' + source, self.check(meta)['reasons'])
                    (self.root / source).unlink()

    def test_custom_historical_report_with_unknown_check_rediscovers_shared_inputs(self):
        self.write('extra.md', 'House preference.')
        meta = self.old_review('_Edits/Book-1/arrival.md', extra_paths=['extra.md'])
        # A raw snapshot can also have one chapter, a book and a named report. Its explicit
        # evidence list is authoritative and contains no chapter-selection projections.
        raw = json.loads((self.root / meta).read_text())
        raw['inputs'] = [item for item in raw['inputs'] if item['path'] in raw['subject_paths']]
        self.write('raw.meta.json', json.dumps(raw))
        self.assertEqual(self.check(meta)['freshness'], 'CURRENT')
        self.write('Wiki/Style/review_guide.md', 'Check the sources.')
        self.assertEqual(self.check(meta)['freshness'], 'STALE')
        self.assertEqual(self.check('raw.meta.json')['freshness'], 'CURRENT')
        (self.root / 'Wiki/Style/review_guide.md').unlink()
        self.write('extra.md', 'New preference.')
        self.assertIn('changed input: extra.md', self.check(meta)['reasons'])

    def test_legacy_shared_plan_superseded_by_an_already_captured_extra(self):
        plan = 'Wiki/Outline/Book-1/plan.md'
        alternative = 'Wiki/Outline/Book-1/alternative.md'
        self.write(plan, '# Plan\n\n## Chapter 1\nArrival.')
        self.write(alternative, 'Different arrival.')
        meta = self.old_review('_Edits/Book-1/Chapter-001_Gate.md', extra_paths=[alternative])
        self.assertEqual(self.check(meta)['freshness'], 'CURRENT')
        manifest = state_reviews.project_manifest_module().propose(self.root)['manifest']
        manifest['books'][0]['chapters'][0]['scene_plan_path'] = alternative
        self.write('.storycraft/project.json', json.dumps(manifest))
        self.assertTrue(any(plan in reason for reason in self.check(meta)['reasons']))

    def test_release_number_does_not_affect_unchanged_plugin_skill(self):
        with patch.dict('state_core._PLUGIN_DIGESTS', {'gate-check': 'same skill'}):
            with patch.object(state_reviews, 'PLUGIN_VERSION', 'first'):
                capture = self.begin()
            with patch.object(state_reviews, 'PLUGIN_VERSION', 'next'):
                meta = self.call('review_finish', prepared=capture['prepared'], verdict='PASS')['meta']
                self.assertEqual(self.check(meta)['freshness'], 'CURRENT')

    def test_mcp_and_cli_preflight_surface_format_findings_and_undrafted_status(self):
        path = 'Chapters/Book-1/Chapter-001.md'
        self.write(path, '# Shipwreck\n\nA shadow crossed the bridge.\n')
        packet = self.call('chapter_preflight', chapter='1')['draft_packet']
        result = packet['chapter_format_check']
        self.assertEqual(packet['chapter_format']['heading_label'], 'Chapter 1')
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['findings'], self.call('chapter_finalize', chapter='1')['chapter_format']['findings'])
        self.assertEqual((result['findings'][0]['path'], result['findings'][0]['line']), (path, 1))
        cli = subprocess.check_output([sys.executable, '-B', str(ROOT / 'skills/book-status/scripts/project_state.py'),
                                       '--root', str(self.root), 'chapter-preflight', '--chapter', '1'], text=True)
        self.assertEqual(json.loads(cli)['draft_packet']['chapter_format_check'], result)
        self.write(path, '# Chapter 1\n\nA shadow crossed the bridge.\n')
        self.assertEqual(self.call('chapter_preflight')['draft_packet']['chapter_format_check'],
                         {'status': 'PASS', 'findings': []})
        self.assertEqual(self.call('chapter_preflight', chapter='4')['draft_packet']['chapter_format_check'],
                         {'status': 'PENDING', 'findings': []})


if __name__ == '__main__':
    unittest.main()
