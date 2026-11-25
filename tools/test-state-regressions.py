#!/usr/bin/env python3
"""Regressions for the 2026-11-25 Tier 0 state-engine fixes.

Each test models a real multi-chapter authoring sequence that the earlier single-step
fixtures never exercised: drafting forward must not invalidate earlier chapters, committed
ledgers must participate in freshness, multi-step editorial runs must survive prose edits,
and completed campaigns need an explicit way to stop pinning old file hashes.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / 'skills/book-status/scripts'
spec = importlib.util.spec_from_file_location('state', SCRIPTS / 'project_state.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)

try:
    import yaml  # noqa: F401
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False

CH1 = '# Chapter 1\n\nMara Vance walked the Harbor Wall at dusk.\n\nThe drawer stayed locked.\n'
CH2 = '# Chapter 2\n\nJo waited by the ferry.\n'


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        shutil.copytree(ROOT / 'tools/eval-fixtures/storycraft-book', self.root, dirs_exist_ok=True)
        self.ch1, self.ch2 = 'Chapters/Book-1/Chapter-001.md', 'Chapters/Book-1/Chapter-002.md'
        (self.root / self.ch1).write_text(CH1)
        (self.root / self.ch2).write_text(CH2)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, text):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text if isinstance(text, str) else json.dumps(text), encoding='utf-8')
        return str(p)

    def review(self, n, kind='Gate'):
        begun = s.review_begin(self.root, 'Book-1', str(n), kind)
        self.write(begun['report'], 'PASS\n')
        return s.review_finish(self.root, begun['prepared'], 'PASS')['meta']

    def fresh(self, meta):
        return s.freshness(self.root, self.root / meta)['freshness']

    def append(self, name, text):
        p = self.root / name
        p.write_text(p.read_text() + text)


@unittest.skipUnless(HAVE_YAML, 'PyYAML required for promise projections')
class ReviewFreshnessProjection(Base):
    LEDGER = 'Wiki/Story/Book-1/promises.yaml'

    def promises(self, *entries):
        lines = ['promises:']
        for e in entries:
            lines.append('  - ' + '\n    '.join(f'{k}: {v}' for k, v in e.items()))
        self.write(self.LEDGER, '\n'.join(lines) + '\n')

    def test_forward_drafting_does_not_stale_earlier_chapters(self):
        p1 = dict(id='P001', promise='the locked drawer', introduced_ch=1, payoff_by_ch=8)
        self.promises(p1)
        m1, m2 = self.review(1), self.review(2)
        # Chapter 2 plants a promise: chapter 1 stays current, chapter 2 must be re-reviewed.
        p2 = dict(id='P002', promise='the ferry bell', introduced_ch=2, payoff_by_ch=9)
        self.promises(p1, p2)
        self.assertEqual(self.fresh(m1), 'CURRENT')
        self.assertEqual(self.fresh(m2), 'STALE')
        m2 = self.review(2)
        # Chapter 3 plants one and pays chapter 1's drawer: neither earlier review is affected.
        p3 = dict(id='P003', promise='the grey coat', introduced_ch=3, payoff_by_ch=9)
        self.promises(dict(p1, paid_in_ch=3, paid_how='opened', status='paid'), p2, p3)
        self.assertEqual(self.fresh(m1), 'CURRENT')
        self.assertEqual(self.fresh(m2), 'CURRENT')
        # Editing what chapter 1 itself planted does invalidate it.
        self.promises(dict(p1, promise='the drawer that never opened'), p2, p3)
        self.assertEqual(self.fresh(m1), 'STALE')

    def test_promise_payoff_on_or_before_chapter_invalidates(self):
        p1 = dict(id='P001', promise='the locked drawer', introduced_ch=1, payoff_by_ch=8)
        self.promises(p1)
        m2 = self.review(2)
        self.promises(dict(p1, paid_in_ch=2, paid_how='opened'))
        self.assertEqual(self.fresh(m2), 'STALE')

    def test_committed_ledgers_participate_in_freshness(self):
        store = s.ledger_store_module()
        logical = 'Wiki/Story/knowledge-events.json'

        def event(eid, chapter, order):
            return {'id': eid, 'fact_id': 'f' + eid, 'observer': 'Jo', 'state': 'knows', 'truth_status': 'true',
                    'event_kind': 'witnessed', 'story_order': order, 'reader_order': order, 'confirmed': True,
                    'source': chapter, 'source_sha256': s.digest(self.root / chapter), 'quote': 'x'}

        events = [event('K1', self.ch1, 1)]
        s.commit_ledger(self.root, logical, {'schema_version': 1, 'events': events}, 'tx1', [self.ch1], None)
        m1, m2 = self.review(1), self.review(2)
        self.assertFalse((self.root / logical).exists(), 'committed ledgers never touch the logical path')
        generation = store.current_pointer(self.root)['generation_id']
        events.append(event('K2', self.ch2, 2))
        s.commit_ledger(self.root, logical, {'schema_version': 1, 'events': events}, 'tx2', [self.ch2], generation)
        self.assertEqual(self.fresh(m1), 'CURRENT')
        self.assertEqual(self.fresh(m2), 'STALE')
        m2 = self.review(2)
        generation = store.current_pointer(self.root)['generation_id']
        events.append(event('K3', self.ch1, 1))
        s.commit_ledger(self.root, logical, {'schema_version': 1, 'events': events}, 'tx3', [self.ch1], generation)
        self.assertEqual(self.fresh(m1), 'STALE')
        self.assertEqual(self.fresh(m2), 'STALE')

    def test_editorial_decisions_project_by_scope(self):
        path = 'Wiki/Style/editorial-decisions.json'
        base = dict(status='active', rule_category='fragments', reusable=True, reason='keep')
        d_other = dict(base, id='D1', scope='Book-1/Chapter-002')
        self.write(path, dict(schema_version=1, decisions=[d_other]))
        m1 = self.review(1)
        self.write(path, dict(schema_version=1, decisions=[dict(d_other, reason='changed')]))
        self.assertEqual(self.fresh(m1), 'CURRENT', 'a decision scoped to another chapter is irrelevant')
        self.write(path, dict(schema_version=1, decisions=[d_other, dict(base, id='D2', scope='series')]))
        self.assertEqual(self.fresh(m1), 'STALE')

    def test_referenced_canon_files_are_inputs(self):
        self.write('Wiki/Characters/Mara_Vance.md', '---\nname: Mara Vance\n---\n## want\nSafety.\n')
        self.write('Wiki/Characters/Zed.md', '---\nname: Zed\n---\n## want\nNothing.\n')
        self.write('Wiki/World/Places/Harbor_Wall.md', '---\nname: Harbor Wall\n---\nGranite.\n')
        self.write('Wiki/World/Places/Quarry.md', '---\nname: Quarry\n---\nDust.\n')
        m1 = self.review(1)
        self.append('Wiki/Characters/Zed.md', 'edit\n')
        self.append('Wiki/World/Places/Quarry.md', 'edit\n')
        self.assertEqual(self.fresh(m1), 'CURRENT')
        self.append('Wiki/Characters/Mara_Vance.md', 'edit\n')
        self.assertEqual(self.fresh(m1), 'STALE')
        m1 = self.review(1)
        self.append('Wiki/World/Places/Harbor_Wall.md', 'edit\n')
        self.assertEqual(self.fresh(m1), 'STALE')

    def test_nonfiction_plan_section_and_research_projection(self):
        plan = 'Wiki/Outline/Book-1/plan.md'
        self.write(plan, '# Plan\n\n## Chapter 01\nClaim A.\n\n## Chapter 02\nClaim B.\n')
        self.write('Wiki/Research/sources.yaml', 'sources:\n  - id: SRC-001\n    title: A\n  - id: SRC-002\n    title: B\n')
        self.write('_Edits/Book-1/evidence/Chapter-001.json', json.dumps({'schema_version': 1, 'sources': ['SRC-001']}))
        m1 = self.review(1, 'FactCheck')
        self.append(plan, '\n## Chapter 03\nClaim C.\n')
        self.write('Wiki/Research/sources.yaml',
                   'sources:\n  - id: SRC-001\n    title: A\n  - id: SRC-002\n    title: B\n  - id: SRC-003\n    title: C\n')
        self.write('Wiki/Research/chapter-3-notes.md', 'new research\n')
        self.assertEqual(self.fresh(m1), 'CURRENT')
        self.write(plan, '# Plan\n\n## Chapter 01\nClaim A revised.\n\n## Chapter 02\nClaim B.\n')
        self.assertEqual(self.fresh(m1), 'STALE')


class PipelineSubjectLineage(Base):
    ROLES = (('developmental_assessment', False, None), ('developmental_repair', True, '\nRepair.\n'),
             ('developmental_checkpoint', False, None), ('line_edit', True, '\nPolish.\n'),
             ('integration_read', False, None), ('ledger_reconciliation', False, None), ('final_gate', False, None))

    def step(self, run, step_id, role, transform=False, edit=None):
        out = f'_Edits/Book-1/{run}-{step_id}.md'
        s.step_start(self.root, 'Book-1', run=run, step_id=step_id, profile='full_editorial_candidate',
                     stage_role=role, chapter_selector='1', write_paths=[out],
                     transform_paths=[self.ch1] if transform else None, predecessor_exists=False)
        if edit:
            self.append(self.ch1, edit)
        self.write(out, f'{role}\n')
        return s.step_complete(self.root, 'Book-1', run=run, step_id=step_id, output_paths=[out])

    def test_multi_step_run_survives_prose_edits(self):
        for index, (role, transform, edit) in enumerate(self.ROLES):
            self.step('multi', f's{index}', role, transform, edit)
        blockers = s.operation_profile_blockers(
            self.root, {'operation_id': 'multi', 'book_id': 'Book-1'}, 'full_editorial_candidate', [self.ch1])
        self.assertEqual(blockers, [])

    def test_edit_outside_recorded_transformations_is_rejected(self):
        self.step('drift', 's0', 'developmental_assessment')
        self.append(self.ch1, '\nUnrecorded author edit.\n')
        with self.assertRaisesRegex(ValueError, 'outside recorded transformations'):
            self.step('drift', 's1', 'developmental_checkpoint')

    def test_subject_identity_cannot_change_mid_run(self):
        self.step('ident', 's0', 'developmental_assessment')
        with self.assertRaisesRegex(ValueError, 'subjects differs'):
            s.step_start(self.root, 'Book-1', run='ident', step_id='s1', profile='full_editorial_candidate',
                         stage_role='line_edit', chapter_selector='2', predecessor_exists=False)


class CampaignLifecycle(Base):
    def camp(self, action, task=None, spec=None, run='default'):
        return s.campaign(self.root, argparse.Namespace(book='Book-1', run=run, action=action, task=task, spec=spec))

    def campaign_state(self, run='default'):
        return next(c for c in s.dashboard(self.root, 'Book-1')['campaigns'] if f'/{run}/' in c['path'])

    def test_seal_reconcile_and_cancel(self):
        self.camp('init', spec=self.write('c.json', dict(schema_version=1, tasks=[
            dict(id='setup', files=[self.ch1], depends_on=[])])))
        self.camp('start', 'setup')
        self.append(self.ch1, '\nCampaign edit.\n')
        meta = self.review(1)
        self.camp('complete', 'setup', spec=self.write('checks.json', dict(schema_version=1, checks=[meta])))
        self.assertTrue(self.campaign_state()['current'])
        # A later proofreading fix makes the unsealed campaign stale, as designed.
        self.append(self.ch1, '\nProofread fix.\n')
        self.assertFalse(self.campaign_state()['current'])
        with self.assertRaisesRegex(ValueError, 'reconcile'):
            self.camp('seal')
        self.camp('reconcile', 'setup')
        self.assertFalse(self.campaign_state()['current'], 'checks are stale until the chapter is re-reviewed')
        with self.assertRaisesRegex(ValueError, 'checks'):
            self.camp('seal')
        self.review(1)
        self.camp('seal')
        self.assertTrue(self.campaign_state()['sealed'])
        self.append(self.ch1, '\nAnother later fix.\n')
        self.assertTrue(self.campaign_state()['current'], 'a sealed campaign stops pinning file hashes')
        with self.assertRaisesRegex(ValueError, 'sealed'):
            self.camp('recover', 'setup')

    def test_cancel_unfinished_campaign(self):
        self.camp('init', run='c2', spec=self.write('c2.json', dict(schema_version=1, tasks=[
            dict(id='x', files=[self.ch2], depends_on=[])])))
        self.assertFalse(self.campaign_state('c2')['current'])
        self.camp('cancel', run='c2', spec=self.write('why.json', dict(schema_version=1, reason='scope changed')))
        state = self.campaign_state('c2')
        self.assertTrue(state['current'] and state['cancelled'])
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            self.camp('start', 'x', run='c2')


class SyncEdits(Base):
    def git(self, *args):
        subprocess.run(['git', *args], cwd=self.root, check=True, capture_output=True)

    @unittest.skipUnless(shutil.which('git'), 'git required')
    def test_committed_edit_diffs_against_previous_commit(self):
        self.git('init', '-q')
        self.git('config', 'user.email', 't@example.com')
        self.git('config', 'user.name', 't')
        self.git('add', '-A')
        self.git('commit', '-qm', 'draft')
        self.append(self.ch1, '\nA new paragraph the author added.\n')
        self.git('commit', '-qam', 'author edit')
        result = s.sync_edits(self.root, 'Book-1', '1')
        self.assertTrue(result['baseline_source'].startswith('git:'), result['baseline_source'])
        self.assertTrue(result['changed_paragraphs'], 'committed edits must not diff against themselves')

    def test_continuity_claims_use_the_ledger_filename(self):
        cid = s.project_manifest_module().resolve_chapter(self.root, 'Book-1', '1')[1]['id']
        name = s.continuity_module().filename(cid)
        self.write(f'_Edits/Book-1/continuity/{name}', dict(schema_version=1, claims=[
            dict(key='drawer', kind='state', quote='The drawer was welded shut.')]))
        result = s.sync_edits(self.root, 'Book-1', '1', baseline=self.ch2)
        self.assertEqual([c['key'] for c in result['affected_continuity_claims']], ['drawer'])

    def test_frozen_beta_edition_is_the_baseline(self):
        import editions
        sys.path.insert(0, str(SCRIPTS))
        reader = editions.current(self.root, 'Book-1')['sections'][0]['reader_text']
        edition = 'a' * 24
        cid = s.project_manifest_module().resolve_chapter(self.root, 'Book-1', '1')[1]['id']
        base = 'Chapters/Book-1/export/beta'
        passages = self.root / base / 'beta-passages.json'
        s.write(passages, dict(schema_version=1, export_id=edition, sections=[
            dict(chapter_id=cid, path=self.ch1, label='Chapter 1', source_sha256='x', reader_text=reader)]))
        s.write(self.root / base / 'export-manifest.json', dict(schema_version=1, beta_feedback=dict(
            export_id=edition, map='beta-passages.json', sha256=s.digest(passages))))
        self.append(self.ch1, '\nPost-beta paragraph.\n')
        result = s.sync_edits(self.root, 'Book-1', '1')
        self.assertTrue(result['baseline_source'].startswith('edition:'), result['baseline_source'])
        self.assertTrue(result['changed_paragraphs'])


class PacketParsers(Base):
    def test_psych_accepts_typographic_apostrophes_and_variants(self):
        text = ('# Chapter 01: Psychological Interior Pass\n\n## Beat-by-Beat Interior Cost\n\n### Beat\n'
                '* **What they won\u2019t say:** I was afraid.\n- **What they won\'t say:** I knew.\n\n'
                '### Show\u2011Don\u2019t\u2011Tell Gaps\n| Beat | Draft | Instead |\n|---|---|---|\n| door | she noticed | she stopped |\n')
        path = Path(self.write('psych.md', text))
        parsed = s.parse_psych(path)
        self.assertEqual(parsed['what_they_wont_say'], ['I was afraid.', 'I knew.'])
        self.assertEqual(parsed['show_dont_tell_gaps'][0]['beat'], 'door')

    def test_checkpoints_are_book_scoped_and_order_independent(self):
        text = ('## relationship_checkpoints\n\n### Jo\n- **chapter_start:** 6\n- **link_type:** rival\n'
                '- **book:** Book-2\n- **chapter_end:** (open)\n\n### Sam\n- **link_type:** ally\n- **book:** Book-1\n'
                '- **chapter_start:** 1\n- **chapter_end:** 5\n\n### Pat\n- **link_type:** friend\n'
                '- **chapter_start:** 1\n- **chapter_end:** (open)\n')
        path = Path(self.write('Mara.md', text))
        book2 = s.parse_checkpoints(path, 7, book='Book-2', unscoped_ok=False)
        self.assertEqual([c['other_character'] for c in book2], ['Jo'])
        self.assertEqual(book2[0]['link_type'], 'rival')
        skipped = []
        book1 = s.parse_checkpoints(path, 3, book='Book-1', unscoped_ok=True, skipped=skipped)
        self.assertEqual(sorted(c['other_character'] for c in book1), ['Pat', 'Sam'])
        s.parse_checkpoints(path, 3, book='Book-2', unscoped_ok=False, skipped=skipped)
        self.assertEqual([x['other_character'] for x in skipped], ['Pat'])

    def test_passage_scoped_decisions_apply_to_their_chapter_only(self):
        decision = dict(scope='Book-1/Chapter-001/Passage/p1', source=self.ch1, status='active')
        books, chapters = ('Book-1', 'book-id'), ('Chapter-001', 'chapter-id')
        self.assertTrue(s.decision_applies(decision, books, chapters, None, chapter_path=self.ch1))
        self.assertFalse(s.decision_applies(decision, books, chapters, None, chapter_path=self.ch2))
        self.assertFalse(s.decision_applies(decision, books, chapters, None))


class EditorialEvalVariants(unittest.TestCase):
    def test_tolerances_are_scored_per_variant(self):
        sys.path.insert(0, str(ROOT / 'tools'))
        spec = importlib.util.spec_from_file_location('eval_editorial', ROOT / 'tools/eval-editorial.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cell = lambda harmful: {'cases': 1, 'findings': 1, 'protected': 1, 'harmful': harmful, 'defects': 1, 'detected': 1}
        failures = module.tolerance_failures(
            {'baseline': {'quiet-endings': cell(1)}, 'candidate': {'quiet-endings': cell(0)}},
            {'quiet-endings': {'max_harmful_edit_rate': 0.0}})
        self.assertEqual([(f['variant'], f['metric']) for f in failures], [('baseline', 'harmful_edit_rate')])


class Tier1VoiceAndPacketEnrichment(Base):
    def test_style_policy_resolves_register_presets_and_overrides(self):
        self.write('Wiki/Style/style_guide.md', '---\nregister_preset: lyrical-literary\n---\n\n## Style\nLyrical.\n')
        lyrical = s.style_policy(self.root, argparse.Namespace(book='Book-1', simile_count=12))
        self.assertEqual(lyrical['register_preset'], 'lyrical-literary')
        self.assertIsNone(lyrical['simile']['max_per_chapter'])
        self.assertEqual(lyrical['clock_mode'], 'words')
        self.assertFalse(lyrical['chapter_simile_budget_exceeded'])
        self.assertIn('Allowed with restraint', lyrical['punctuation']['em_dash'])

        self.write('Wiki/Style/review_guide.md',
                   '---\nregister_preset: historical-period\n---\n\n## Simile Rule\n- **max_per_chapter:** 5\n')
        override = s.style_policy(self.root, argparse.Namespace(book='Book-1', simile_count=6))
        self.assertEqual(override['register_preset'], 'historical-period')
        self.assertEqual(override['simile']['max_per_chapter'], 5)
        self.assertTrue(override['chapter_simile_budget_exceeded'])
        self.assertEqual(override['clock_mode'], 'words')

    def test_prose_style_clock_mode_and_skip_dialogue(self):
        spec = importlib.util.spec_from_file_location('prose_style', SCRIPTS / 'prose_style.py')
        ps = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ps)
        sample = '“Meet me at ten thirty, whilst I pack,” she said. Then he left whilst the bell struck eight o’clock.'
        # Words mode skips clock conversion; skip_dialogue preserves spoken "whilst" while catching narrative "whilst".
        found = ps.scan(sample, True, clock_mode='words', skip_dialogue=True)
        self.assertEqual([(c['category'], c['quote']) for c in found], [('contemporary-diction', 'whilst')])
        self.assertEqual(found[0]['column'], sample.rindex('whilst') + 1)

    def test_draft_packet_enriches_psych_theme_surprise_and_lenses(self):
        self.write('Wiki/Style/style_guide.md',
                   '---\nregister_preset: comic-ironic\npov_mode: single\npov_1: Mara\n---\n\n## Style\nClose third.\n')
        self.write('Wiki/Style/voice_prompt_Mara.md',
                   '# Voice Prompt: Mara\n\n## What They Notice\nLead joints, ledger ink, and crooked hinges.\n\n'
                   '## Language Firewall\nNever use therapist labels.\n')
        self.write('Wiki/Story/theme.md',
                   '---\ncentral_question: "Can truth survive a friendly debt?"\n---\n\n## Motifs\n\n'
                   '### Brass Keys\n- **type:** Visual\n- **what_it_is:** Unclaimed harbour keys.\n')
        self.write('Wiki/Outline/Book-1/surprise-ledger.md',
                   '## Act 1 (chapters 1–3)\n- **Diverged:** ch 1 — the lock is already picked.\n'
                   '- **Surprise inventory:** Empty brass ring.\n\n'
                   '## Act 2 (chapters 4–8)\n- **Diverged:** ch 5 — ferry sinks.\n')
        self.write('Wiki/Outline/Book-1/Chapter_01_Scene.md', '## Scene 1\n- **POV:** Mara\n')
        self.write('Wiki/Psych/Book-1/Chapter_01_Psych.md',
                   '# Chapter 01: Psychological Interior Pass\n\n**POV:** Mara\n\n'
                   '## Start State\n**Surface affect:** Crisp.\n**Underneath:** Counting losses.\n'
                   '**Expression channel:** Action.\n\n'
                   '## Beat-by-Beat Interior Cost\n### The Pier\n- **Interior cost:** Old debt.\n'
                   '- **Expression channel:** Omission.\n- **What they won\u2019t say:** I lost the deed.\n\n'
                   '## End State\n**Surface affect:** Polite.\n**Underneath:** Cornered.\n\n'
                   '## Bottom Line\nProtect the manifest at all costs.\n')
        pkt = s.draft_packet(self.root, argparse.Namespace(book='Book-1', chapter='1', window=3, output=None, key=None))
        self.assertEqual(pkt['psych']['start_state']['surface_affect'], 'Crisp.')
        self.assertEqual(pkt['psych']['end_state']['underneath'], 'Cornered.')
        self.assertEqual(pkt['psych']['beat_interior_costs'][0]['interior_cost'], 'Old debt.')
        self.assertEqual(pkt['psych']['bottom_line'], 'Protect the manifest at all costs.')
        self.assertEqual(pkt['theme']['motifs'][0]['name'], 'Brass Keys')
        self.assertEqual(len(pkt['surprise_ledger']['acts']), 1)
        self.assertIn('Act 1', pkt['surprise_ledger']['acts'][0]['act'])
        self.assertEqual(pkt['style_policy']['register_preset'], 'comic-ironic')
        self.assertIn('crooked hinges', pkt['pov_lenses'][0]['what_they_notice'])

    def test_no_leaked_manuscript_prompts_in_generic_skills(self):
        for rel in (
            'skills/levelup/references/filter-word-criteria.md',
            'skills/fragment-hunter/references/fragment-criteria.md',
            'skills/reader-persona-review/references/personas.md',
        ):
            text = (ROOT / rel).read_text(encoding='utf-8')
            for leaked in ('Rowan', 'Blackwood Ridge', 'Alton Mercer', 'Sheriff Cross'):
                self.assertNotIn(leaked, text, f'{rel} still contains leaked reference {leaked}')


if __name__ == '__main__':
    unittest.main()
