#!/usr/bin/env python3
"""Regressions for narrative information delivered to a chapter writer."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'skills/book-status/scripts'))
import project_state as state


class NovelPacket(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        shutil.copytree(ROOT / 'tools/eval-fixtures/storycraft-book', self.root, dirs_exist_ok=True)
        self.previous = 'Chapters/Book-1/Chapter-001.md'
        self.plan = 'Wiki/Outline/Book-1/Chapter_02_Scene.md'
        self.write(self.previous, '# Chapter 1\n\nJo was dead, the paper said. The key was gone.\n')
        self.write(self.plan, ''.join(
            f'## Scene {n}\n- **POV:** Mara\n- **Story order:** {n + 1}\n- **Reader order:** {n + 1}\n'
            for n in (1, 2, 3)))

    def write(self, rel, content):
        path = self.root / rel
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_text(content, encoding='utf-8')
        return path

    def packet(self, book='Book-1'):
        return state.draft_packet(self.root, argparse.Namespace(book=book, chapter='2', window=3, key=None))

    def record(self, func, events):
        spec = self.write('events.json', json.dumps(events))
        func(self.root, argparse.Namespace(action='record', events=str(spec)))

    def test_rumor_exposure_and_missing_evidence_are_not_confirmed_irony(self):
        common = dict(source=self.previous, source_sha256=state.digest(self.root / self.previous),
                      story_order=1, reader_order=1, confirmed=True, event_kind='report')
        rumor = dict(common, id='R', fact_id='dead', observer='reader', state='exposed',
                     truth_status='false', quote='Jo was dead, the paper said.')
        key = dict(common, id='K', fact_id='key', observer='reader', state='knows',
                   truth_status='true', quote='The key was gone.')
        self.record(state.knowledge_event_state, [rumor, key])
        scene = self.packet()['scenes'][0]
        self.assertEqual(scene['dramatic_irony'], [])
        self.assertEqual(scene['knowledge_as_of']['reader']['state']['dead']['truth_status'], 'false')
        self.assertNotIn('key', scene['knowledge_as_of']['Mara']['state'])
        self.record(state.knowledge_event_state, [dict(key, id='M', observer='Mara', state='disbelieves')])
        irony = self.packet()['scenes'][0]['dramatic_irony']
        self.assertEqual([(e['fact_id'], e['truth_status'], e['pov_state']) for e in irony],
                         [('key', 'true', 'disbelieves')])
        self.assertEqual(irony[0]['source'], self.previous)

    def test_turn_inside_chapter_is_pending_until_earned_in_its_scene(self):
        character = self.write('Wiki/Characters/Mara.md',
            '## relationship_checkpoints\n### Jo\n'
            '- **book:** Book-1\n- **link_type:** rival\n- **chapter_start:** 1\n- **chapter_end:** 2\n'
            '- **book:** Book-1\n- **link_type:** ally\n- **chapter_start:** 2\n- **turn_scene:** 2\n'
            '- **chapter_end:** (open)\n- **notes:** Jo hands over the key.\n'
            '- **book:** Book-2\n- **link_type:** estranged\n- **chapter_start:** 2\n- **chapter_end:** (open)\n')
        first, turn, later = self.packet()['scenes']
        self.assertEqual([c['link_type'] for c in first['relationship_checkpoints']], ['rival'])
        self.assertEqual([c['link_type'] for c in turn['relationship_checkpoints']], ['rival'])
        self.assertEqual([c['link_type'] for c in turn['relationship_turns']], ['ally'])
        self.assertEqual([c['link_type'] for c in later['relationship_checkpoints']], ['ally'])
        self.assertEqual(later['relationship_turns'], [])
        character.write_text('## relationship_checkpoints\n### Jo\n- **link_type:** friend\n'
                             '- **chapter_start:** 1\n- **chapter_end:** (open)\n')
        self.assertEqual(self.packet()['scenes'][1]['relationship_checkpoints'][0]['link_type'], 'friend')

    def test_second_book_and_legacy_turn_timing(self):
        self.write('Wiki/Characters/Mara.md', '## relationship_checkpoints\n### Jo\n'
                   '- **link_type:** rival\n- **chapter_start:** 2\n- **chapter_end:** (open)\n'
                   '### Ren\n'
                   '- **book_id:** book-2\n- **link_type:** fellow travelers\n- **chapter_start:** 1\n'
                   '- **chapter_end:** (open)\n')
        first = self.packet()['scenes'][0]
        self.assertEqual(first['relationship_checkpoints'], [])
        self.assertEqual(first['relationship_timing_unresolved'][0]['link_type'], 'rival')
        self.write('Chapters/Book-2/Chapter-002.md', '# Chapter 2\n\nMara waited.\n')
        self.write('Wiki/Outline/Book-2/Chapter_02_Scene.md', '## Scene 1\n- **POV:** Mara\n')
        second = self.packet('Book-2')
        self.assertEqual([c['link_type'] for c in second['scenes'][0]['relationship_checkpoints']], ['fellow travelers'])
        self.assertEqual(len(second['unscoped_relationship_checkpoints']), 1)

    def test_unscoped_betrayal_after_second_book_seed_never_leaks_into_first_book(self):
        self.write('Wiki/Characters/Mara.md', '## relationship_checkpoints\n### Jo\n'
                   '- **book:** Book-2\n- **link_type:** allied\n- **chapter_start:** 1\n- **chapter_end:** 7\n'
                   '- **link_type:** betrayed\n- **chapter_start:** 8\n- **chapter_end:** (open)\n')
        for n in (8, 9):
            self.write(f'Chapters/Book-1/Chapter-{n:03d}.md', f'# Chapter {n}\n\nMara waited.\n')
            pkt = state.draft_packet(self.root, argparse.Namespace(book='Book-1', chapter=str(n), window=3, key=None))
            self.assertEqual(pkt['relationship_checkpoints'], [])
            self.assertEqual(pkt['scenes'][0]['relationship_checkpoints'], [])
            self.assertIn('ambiguous', pkt['unscoped_relationship_checkpoints'][0]['reason'])

    def test_sourced_relationship_state_is_resolved_per_scene(self):
        common = dict(relationship_id='Mara-Jo', observer='Mara', other='Jo', source=self.previous,
                      source_sha256=state.digest(self.root / self.previous), quote='The key was gone.')
        self.record(state.relationship_state, [
            dict(common, id='R1', stance='distrust', status='confirmed', book_id='Book-1',
                 scene_id='scene-1', story_order=1),
            dict(common, id='R2', stance='allied', status='planned', book_id='Book-1',
                 scene_id='scene-2', story_order=3),
            dict(common, id='R3', stance='wrong book', status='planned', book_id='Book-2',
                 scene_id='scene-2', story_order=3),
            dict(common, id='R4', stance='betrayed', status='confirmed', book_id='Book-2',
                 scene_id='scene-5', story_order=35, supersedes=['R1'])])
        first, turn, later = self.packet()['scenes']
        self.assertEqual(first['relationship_state_as_of']['established'][0]['stance'], 'distrust')
        self.assertEqual([e['stance'] for e in turn['relationship_state_as_of']['planned_transitions']], ['allied'])
        self.assertEqual(later['relationship_state_as_of']['planned_transitions'], [])
        self.assertEqual(later['relationship_state_as_of']['established'][0]['stance'], 'distrust')

    def test_cooling_counts_and_anchored_candidates(self):
        self.write(self.previous, '# Chapter 1\n\nHer jaw hurt. She rubbed her jaw.\n\n'
                   'At Mercy Street Station he waited. At Mercy Street Station he waved.\n\n'
                   'It shone like a silver coin. He folded the receipt. She folded the receipt.\n')
        cooling = self.packet()['cooling_list']
        self.assertEqual({c['word']: c['count'] for c in cooling['somatic_hotspots']}.get('jaw'), 2)
        self.assertEqual(cooling['repeated_similes'], [])
        self.assertFalse(any('mercy street' in c['ngram'] for c in cooling['repeated_ngrams']))
        candidate = next(c for c in cooling['repeated_ngrams'] if c['ngram'] == 'folded the receipt')
        self.assertEqual(candidate['count'], 2)
        self.assertEqual(candidate['examples'][0]['path'], self.previous)

    def test_protected_refrain_and_frequent_simile(self):
        self.write('Wiki/Style/style_guide.md', '## Cooling List Keeps\n- folded the receipt\n')
        self.write(self.previous, '# Chapter 1\n\nShe folded the receipt. He folded the receipt.\n\n'
                   'It shone like a silver coin. It fell like a silver coin.\n')
        cooling = self.packet()['cooling_list']
        self.assertFalse(any(c['ngram'] == 'folded the receipt' for c in cooling['repeated_ngrams']))
        simile = cooling['repeated_similes'][0]
        self.assertEqual((simile['phrase'], simile['count']), ('like a silver coin', 2))
        self.assertEqual(len(simile['examples']), 2)

    def test_pov_labels_and_scene_breaks_are_excluded_from_prose_examples(self):
        self.write(self.previous, '# Chapter 1\n\n<!-- POV: Mara -->\n\nShe folded the receipt.\n\n'
                   '* * *\n\n**POV:** Jo\n\nJo started walking.\n')
        pkt = self.packet()
        self.assertEqual(pkt['cooling_list']['recent_openers'][0]['opener'], 'She folded the receipt.')
        self.assertNotIn('POV', pkt['continuity_tail']['tail_excerpt'])

    def test_voice_index_and_selected_prose_are_delivered_to_correct_viewpoint(self):
        self.write('Wiki/Style/style_guide.md', '---\npov_mode: dual\npov_1: Mara\npov_2: Jo\n---\n')
        self.write('Wiki/Style/voice_prompt.md', '## Contrast\nMara compresses a moment. Jo lingers.\n')
        self.write('Wiki/Style/voice_prompt_Mara.md',
                   '## Author-selected voice anchors\nThe key was gone.\n')
        self.write('Wiki/Style/voice_prompt_Jo.md', '## Author-selected voice anchors\nI could wait.\n')
        self.write(self.plan, '## Scene 1\n- **POV:** Mara\n## Scene 2\n- **POV:** Jo\n')
        pkt = self.packet()
        self.assertEqual(pkt['voice_contrast_index']['path'], 'Wiki/Style/voice_prompt.md')
        self.assertEqual([s['voice_prompts'][0]['pov'] for s in pkt['scenes']], ['Mara', 'Jo'])
        self.assertEqual([lens['author_selected_anchors'] for lens in pkt['pov_lenses']],
                         ['The key was gone.', 'I could wait.'])

    def test_two_narrators_with_the_same_given_name_need_distinct_voice_files(self):
        self.write('Wiki/Style/style_guide.md', 'pov_mode: dual\npov_1: Jo Vale\npov_2: Jo Park\n')
        self.write('Wiki/Style/voice_prompt_Jo.md', 'Unassigned first-name file.\n')
        self.write('Wiki/Style/voice_prompt_Jo_Park.md', '## What They Notice\nOld stone.\n')
        self.write(self.plan, '## Scene 1\n- **POV:** Jo Vale\n## Scene 2\n- **POV:** Jo Park\n')
        vale, park = self.packet()['scenes']
        self.assertEqual(vale['voice_prompts'], [])
        self.assertEqual(park['voice_prompts'][0]['path'], 'Wiki/Style/voice_prompt_Jo_Park.md')

    def test_edit_review_tracks_only_relevant_voice_sources_and_contrast_index(self):
        self.write('Wiki/Style/style_guide.md', '---\npov_mode: dual\npov_1: Mara\npov_2: Jo\n---\n')
        default = 'Wiki/Style/voice_prompt.md'
        mara = 'Wiki/Style/voice_prompt_Mara.md'
        jo = 'Wiki/Style/voice_prompt_Jo.md'
        for name in (default, mara, jo):
            self.write(name, '# Voice\n')
        for kind in ('FullEdit', 'LineEdit'):
            with self.subTest(kind=kind):
                prepared = state.review_begin(self.root, 'Book-1', '2', kind)
                paths = {item['path'] for item in prepared['inputs']}
                self.assertTrue({mara, default}.issubset(paths))
                self.assertNotIn(jo, paths)
                self.write(prepared['report'], 'PASS\n')
                meta = state.review_finish(self.root, prepared['prepared'], 'PASS')['meta']
                self.write(jo, kind)
                self.assertEqual(state.freshness(self.root, self.root / meta)['freshness'], 'CURRENT')
                self.write(mara, kind)
                self.assertEqual(state.freshness(self.root, self.root / meta)['freshness'], 'STALE')


if __name__ == '__main__':
    unittest.main()
