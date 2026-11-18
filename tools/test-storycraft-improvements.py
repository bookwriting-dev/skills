#!/usr/bin/env python3
"""Regression cases for manuscript safety, scoped editing, beta feedback and matched studies."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / 'skills/book-status/scripts/project_state.py'
EXPORT = ROOT / 'skills/compile-manuscript/scripts/compile_manuscript.py'
IMPORT = ROOT / 'skills/book-reverse-engineer/scripts/manuscriptkit.py'
BETA = ROOT / 'skills/beta-feedback/scripts/beta_feedback.py'
EVAL = ROOT / 'tools/eval-editorial.py'
AUDIT = ROOT / 'skills/litrpg-audit/scripts/stat_audit.py'
WORD = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def load_module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StorycraftImprovements(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def put(self, name, obj):
        return self.write(name, json.dumps({'schema_version': 1, **obj}, ensure_ascii=False))

    def cli(self, script, *args, fail=False):
        result = subprocess.run([sys.executable, str(script), *map(str, args)],
                                text=True, capture_output=True)
        if fail:
            self.assertNotEqual(result.returncode, 0, result.stdout)
            return result.stderr.strip() or result.stdout.strip()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return json.loads(result.stdout)

    def state(self, *args):
        return self.cli(STATE, '--root', self.root, *args)

    def chapter(self, n, body):
        return self.write(f'Chapters/Book-1/Chapter-{n:03}.md', f'# Chapter {n}\n\n{body}\n')

    def review(self, chapter, stem, checks):
        relative = chapter.relative_to(self.root).as_posix()
        for check in checks:
            report = f'_Edits/Book-1/{stem}_{check}.md'
            self.write(report, 'PASS\nSynthetic review evidence for this regression.\n')
            spec = self.put('check-spec.json', {'paths': [relative], 'report': report, 'verdict': 'PASS'})
            self.state('prepare', '--spec', spec, '--output', 'prepared.json')
            self.state('snapshot', '--spec', self.root / 'prepared.json',
                       '--output', report.replace('.md', '.meta.json'))

    def test_plaintext_import_preserves_front_matter_and_author_edits(self):
        manuscript = self.write('manuscript.txt', 'For my sister.\n\nChapter 1\nFirst.\n\nChapter 2\nSecond.\n')
        target = self.root / 'Chapters/Book-1'
        args = manuscript, '--export-chapters', target
        first = self.cli(IMPORT, *args, '--preview')
        self.assertEqual(first['unit_count'], 2)
        self.assertFalse(target.exists())
        self.assertEqual(first['import']['files']['FrontMatter.md']['action'], 'create')
        self.cli(IMPORT, *args)
        self.assertEqual((target / 'FrontMatter.md').read_text(), 'For my sister.\n')
        self.assertEqual(self.cli(IMPORT, *args)['written'], [])
        edited = self.chapter(1, 'Author revision.')
        self.cli(IMPORT, *args)
        self.assertIn('Author revision.', edited.read_text())
        manuscript.write_text('For my sister.\n\nChapter 1\nAn incoming edit.\n\nChapter 2\nAn incoming ending.\n')
        preview = self.cli(IMPORT, *args, '--preview')['import']['files']['Chapter-001.md']
        self.assertEqual(preview['action'], 'conflict')
        self.assertIn('-Author revision.', preview['diff'])
        self.assertIn('import conflict', self.cli(IMPORT, *args, fail=True))
        self.assertIn('Second.', (target / 'Chapter-002.md').read_text())
        self.cli(IMPORT, *args, '--keep', 'Chapter-001.md')
        self.assertIn('Author revision.', edited.read_text())
        self.assertIn('An incoming ending.', (target / 'Chapter-002.md').read_text())
        self.cli(EXPORT, '--root', self.root)
        combined = target / 'export/beta/manuscript-combined.md'
        self.assertTrue(combined.read_text().startswith('For my sister.'))

    def test_interrupted_import_resumes_remaining_work(self):
        module = load_module(IMPORT)
        manuscript = self.write('draft.md', '# Chapter 1\n\nFirst.\n\n# Chapter 2\n\nSecond.\n')
        destination = self.root / 'output'
        replace = module.replace_file

        def interrupt(path, data):
            if path == destination / 'Chapter-002.md':
                raise OSError('fixture interruption')
            replace(path, data)

        module.replace_file = interrupt
        with self.assertRaisesRegex(OSError, 'fixture interruption'):
            module.export_chapters(module.analyze(manuscript), destination)
        self.assertTrue((destination / 'Chapter-001.md').is_file())
        self.assertFalse((destination / 'Chapter-002.md').exists())
        self.assertEqual(self.cli(IMPORT, '--export-chapters', destination, '--recover')['recovered'],
                         ['Chapter-002.md'])
        self.assertEqual(self.cli(IMPORT, manuscript, '--export-chapters', destination)['written'], [])

    def test_manifest_registers_new_chapters_and_enforces_completeness(self):
        first = self.chapter(1, 'She waited.')
        third = self.chapter(3, 'The ferry came back.')
        for n, chapter in ((1, first), (3, third)):
            self.review(chapter, f'Chapter-{n:03}', ['Gate'])
        self.write('Wiki/Outline/Book-1/outline.md', '## Chapter 04: The ending\n')
        args = '--root', self.root, '--check'
        errors = self.cli(EXPORT, *args, '--profile', 'publication', fail=True)
        self.assertIn('missing expected chapter: Chapter 2', errors)
        self.assertIn('missing expected chapter: Chapter 4', errors)
        recorded = self.cli(ROOT/'tools/project-manifest.py', self.root, 'apply')
        self.assertEqual(recorded['status'], 'applied')
        packet = self.state('draft-packet', '--chapter', 2)
        self.assertEqual(packet['chapter_path'], 'Chapters/Book-1/Chapter-002.md')
        spec = self.put('interlude-registration.json', {'chapter_order': 'declared', 'chapters': [
            {'id': 'starlings', 'display_label': 'Interlude', 'path': 'Chapters/Book-1/starlings.md', 'reading_order': 2},
            {'number': 4},
        ]})
        self.state('register-chapters', '--spec', spec)
        saved = (self.root / '.storycraft/project.json').read_bytes()
        self.state('register-chapters', '--spec', spec)
        self.assertEqual((self.root / '.storycraft/project.json').read_bytes(), saved)
        self.assertEqual(self.state('draft-packet', '--chapter', 'Interlude')['continuity_tail']['path'],
                         'Chapters/Book-1/Chapter-001.md')
        beta = self.cli(EXPORT, *args)
        self.assertEqual([entry['label'] for entry in beta['missing_chapters']], ['Interlude', 'Chapter 4'])
        interlude = self.write('Chapters/Book-1/starlings.md', '# Interlude\n\nThe birds returned at dusk.\n')
        fourth = self.chapter(4, 'The water grew still.')
        self.review(interlude, 'starlings', ['Gate'])
        self.review(fourth, 'Chapter-004', ['Gate'])
        publication = self.cli(EXPORT, '--root', self.root, '--profile', 'publication')
        self.assertEqual(publication['missing_chapters'], [])
        output = (self.root / 'Chapters/Book-1/export/publication/manuscript-combined.md').read_text()
        self.assertLess(output.index('Interlude'), output.index('Chapter 3'))

    def test_nonneutral_project_types_share_required_reviews(self):
        chapter = self.chapter(1, 'Here is the premise.')
        self.write('AGENTS.md', 'This project is: **NONFICTION**\n')
        self.review(chapter, 'Chapter-001', ['FactCheck', 'ClarityEdit'])
        dashboard = self.state('dashboard')
        self.assertEqual(dashboard['required_checks'], ['FactCheck', 'ClarityEdit'])
        self.assertTrue(dashboard['chapters'][0]['ready'])
        args = '--root', self.root, '--check', '--profile', 'publication'
        publication = self.cli(EXPORT, *args)
        self.assertEqual(publication['required_checks'], dashboard['required_checks'])
        self.write('AGENTS.md', 'This project is: **HYBRID**\n')
        self.assertIn('Gate', self.cli(EXPORT, *args, fail=True))
        config = self.put('export-config.json', {'required_checks': ['FactCheck', 'ClarityEdit']})
        self.cli(EXPORT, *args, '--config', config)
        self.review(chapter, 'Chapter-001', ['Gate'])
        self.assertEqual(self.state('workflow')['required_checks'], ['Gate', 'FactCheck', 'ClarityEdit'])
        self.cli(EXPORT, *args)

    def test_draft_context_filters_two_narrators(self):
        original = self.chapter(1, 'Mara took the key. Jo remembered the letter.')
        original_rel = original.relative_to(self.root).as_posix()
        digest = hashlib.sha256(original.read_bytes()).hexdigest()
        self.write('Wiki/Style/style_guide.md', '---\npov_mode: dual\npov_1: Mara\npov_2: Jo\n---\n')
        self.write('Wiki/Style/voice_prompt_Mara.md', 'Mara’s rules.')
        self.write('Wiki/Style/voice_prompt_Jo.md', 'Jo’s rules.')
        self.write('Wiki/Style/voice_prompt.md', 'Book roster index.')
        self.put('Wiki/Style/editorial-decisions.json', {'decisions': [
            dict(id='letter-cadence', status='active', scope='Book-1/POV/Jo'),
            dict(id='key-cadence', status='active', scope={'pov_id': 'Mara'}),
        ]})
        self.put('Wiki/Story/Book-1/knowledge.json', {'events': [
            dict(id=name.lower(), observer=name, fact_id=f'{name}-fact', confirmed=True,
                 story_position=[1, 1, 1], reader_position=[1, 1, 1], source=original_rel,
                 source_sha256=digest, state='knows', quote=quote)
            for name, quote in (('Mara', 'Mara took the key.'), ('Jo', 'Jo remembered the letter.'))
        ]})
        plan = 'Wiki/Outline/Book-1/Chapter_02_Scene.md'
        self.write(plan, '## Scene 1\n- **POV:** Mara\n')
        solo = self.state('draft-packet', '--chapter', 2)
        self.assertEqual(solo['scene_plan']['pov_characters'], ['Mara'])
        self.assertEqual([item['pov'] for item in solo['voice_prompts']], ['Mara'])
        self.assertNotIn('letter-cadence', json.dumps(solo))
        self.assertNotIn('Jo-fact', json.dumps(solo))
        self.write(plan, '## Scene 1\n- **POV:** Mara\n\n## Scene 2\n- **POV:** Jo\n\n## Scene 3\n')
        mara, jo, unresolved = self.state('draft-packet', '--chapter', 2)['scenes']
        self.assertEqual([item['id'] for item in mara['editorial_decisions']], ['key-cadence'])
        self.assertEqual([item['id'] for item in jo['editorial_decisions']], ['letter-cadence'])
        self.assertEqual(list(jo['knowledge_as_of']), ['Jo'])
        self.assertEqual(unresolved['pov_status'], 'UNRESOLVED')
        self.assertEqual(unresolved['voice_prompts'], [])

    def test_two_review_guides_apply_different_simile_budgets(self):
        self.chapter(1, 'The dog shook like a kettle. The plank flew like a shingle.')
        guide = 'Wiki/Style/review_guide.md'
        policy = '## Simile Rule\n- **max_per_chapter:** {}\n- **keep_example:** The plank flew like a shingle.\n'
        self.write(guide, policy.format(1) + '\n## Punctuation\n- **em_dash:** Use for interruptions.\n')
        stricter = self.state('style-policy', '--simile-count', 2)
        self.assertTrue(stricter['chapter_simile_budget_exceeded'])
        self.assertEqual(stricter['punctuation']['em_dash'], 'Use for interruptions.')
        self.assertEqual(stricter['simile']['keep_examples'], ['The plank flew like a shingle.'])
        self.write(guide, policy.format('unlimited'))
        self.assertFalse(self.state('style-policy', '--simile-count', 2)['chapter_simile_budget_exceeded'])

    @unittest.skipUnless(importlib.util.find_spec('yaml'), 'PyYAML is required for ledger behavior')
    def test_litrpg_each_advertised_rule_and_character_chronology(self):
        import yaml
        entry = {'level': 1, 'xp': 100, 'unspent_stats': 5, 'attributes': {'CON': 10},
                 'resources': {'MP': 10}, 'inventory': {'key': 1}, 'incapacitated': False}
        rules = {'xp_model': 'quadratic', 'xp_base': 100, 'stat_points_per_level': 5,
                 'pool_formulas': {'HP': {'CON': 10, 'level': 5, 'base': 50}}}
        ledger = {'system_rules': rules, 'characters': {
            'Zachary_Cross': {'skills': [{'name': 'Mana Dart', 'unlocked_chapter': 1},
                                         {'name': 'Frost Nova', 'unlocked_chapter': 2}]},
            'Mara': {'skills': [{'name': 'Frost Nova', 'unlocked_chapter': 1}]}
        }, 'chapters': {'Chapter-002': {'character': 'Zachary_Cross', 'state_in': entry}}}

        def run(body, events=(), *, fail=False):
            chapter = self.chapter(2, body)
            ledger['chapters']['Chapter-002']['events'] = list(events)
            path = self.write('Wiki/World/Systems/ledger.yaml', yaml.safe_dump(ledger))
            command = subprocess.run([sys.executable, str(AUDIT), str(chapter), '--ledger', str(path), '--json'],
                                     text=True, capture_output=True)
            self.assertEqual(command.returncode, int(fail), command.stderr + command.stdout)
            return json.loads(command.stdout)

        good_unlock = '> [!SYSTEM]\n> **Skill Unlocked:** Frost Nova\n\nZachary cast Frost Nova.'
        bad_unlock = 'Zachary cast Frost Nova.\n\n> [!SYSTEM]\n> **Skill Unlocked:** Frost Nova'
        self.assertEqual(run(good_unlock)['rule_results']['skill_unlock'], 'PASS')
        self.assertEqual(run(bad_unlock, fail=True)['rule_results']['skill_unlock'], 'FAIL')
        self.assertEqual(run('Zachary cast Mana Dart.')['rule_results']['skill_unlock'], 'PASS')
        bundled = ROOT / 'skills/litrpg-system/assets/ledger-template.yaml'
        chapter = self.chapter(2, 'Zachary cast Frost Nova.')
        report = self.cli(AUDIT, chapter, '--ledger', bundled, '--json', fail=True)
        self.assertEqual(json.loads(report)['status'], 'FAIL')
        trials = [
            ('stat_points', {'type': 'allocate', 'amount': 5}, {'type': 'allocate', 'amount': 6}, 'FAIL'),
            ('xp', {'type': 'level_up', 'level': 2}, {'type': 'level_up', 'level': 3}, 'WARN'),
            ('derived_pools', {'type': 'status', 'pools': {'HP': 155}}, {'type': 'status', 'pools': {'HP': 200}}, 'FAIL'),
            ('resources', {'type': 'spend', 'resource': 'MP', 'amount': 9}, {'type': 'spend', 'resource': 'MP', 'amount': 11}, 'WARN'),
            ('inventory', {'type': 'lose_item', 'item': 'key', 'amount': 1}, {'type': 'lose_item', 'item': 'key', 'amount': 2}, 'WARN'),
        ]
        for rule, good, bad, verdict in trials:
            with self.subTest(rule=rule):
                self.assertEqual(run('She waited.', [good])['rule_results'][rule], 'PASS')
                self.assertEqual(run('She waited.', [bad], fail=verdict == 'FAIL')['rule_results'][rule], verdict)
        self.assertEqual(run('She waited.', [{'type': 'act'}])['rule_results']['incapacitation'], 'PASS')
        self.assertEqual(run('She waited.', [{'type': 'incapacitate'}, {'type': 'act'}],
                             fail=True)['rule_results']['incapacitation'], 'FAIL')
        self.assertEqual(run('> [!SYSTEM]\n> Completed')['rule_results']['status_length'], 'PASS')
        self.assertEqual(run('> [!SYSTEM]\n' + '> Detail\n' * 25)['rule_results']['status_length'], 'WARN')
        self.assertEqual(run('She waited.', [{'type': 'spend', 'resource': 'SP', 'amount': 2}])
                         ['rule_results']['resources'], 'UNVERIFIED')
        ending = ledger['chapters']['Chapter-002']
        ending['events'] = []
        ending['state_out'] = {'inventory': {}}
        chapter = self.chapter(2, 'Zachary waited.')
        logical = 'Wiki/World/Systems/ledger.yaml'
        # The committed ledger may exist only in its transaction generation.
        (self.root / logical).unlink()
        store = load_module(ROOT / 'skills/book-status/scripts/ledger_store.py')
        store.commit(self.root, {'transaction_id': 'litrpg-fixture',
                                'source_evidence': store.capture(self.root, [chapter.relative_to(self.root).as_posix()]),
                                'updates': {logical: ledger}})
        committed = self.cli(AUDIT, chapter, '--json')
        self.assertTrue(committed['ledger_found'])
        self.assertEqual(committed['rule_results']['inventory'], 'WARN')

    def test_pasted_notes_ambiguity_and_revision_campaign(self):
        chapter = self.chapter(1, 'The door was closed.\n\nMara kept the key.')
        self.chapter(2, 'The door was closed.')
        exported = self.cli(EXPORT, '--root', self.root)
        edition = exported['beta_feedback']['export_id']
        notes = self.put('notes.json', {'reader': 'Inez', 'notes': [
            {'quote': 'The door was closed.', 'comment': 'Where is she?'},
            {'quote': 'Mara kept the key.', 'comment': 'I missed the reason.'},
        ]})
        args = '--root', self.root, '--export', edition
        report = self.cli(BETA, *args, '--notes', notes)
        ambiguous, selected = report['feedback']
        self.assertEqual(ambiguous['location']['status'], 'UNRESOLVED')
        self.assertEqual(selected['location']['status'], 'ANCHORED')
        self.assertEqual(self.cli(BETA, *args, '--notes', notes)['added'], 0)
        chapter.write_text(chapter.read_text() + '\nDarkness fell.\n')
        # Re-export moves the first map into the previous-edition archive.
        self.cli(EXPORT, '--root', self.root)
        campaign = self.cli(BETA, *args, '--campaign', 'selected', '--select', selected['id'])
        task = campaign['tasks'][0]
        self.assertEqual(task['status'], 'pending')
        self.assertEqual(task['feedback'][0], selected)
        chapter.write_text(chapter.read_text().replace('Mara kept the key.', 'Mara gave the key away.'))
        self.assertIn('passage changed', self.cli(BETA, *args, '--campaign', 'stale', '--select', selected['id'], fail=True))

    @unittest.skipUnless(shutil.which('pandoc'), 'Pandoc is required for the Word round trip')
    def test_returned_word_comments_match_anchored_edition(self):
        self.chapter(1, 'The lantern went out.\n\nMara kept the key.')
        self.chapter(2, 'Mara kept the key.')
        exported = self.cli(EXPORT, '--root', self.root, '--format', 'docx')
        edition = exported['beta_feedback']['export_id']
        source = self.root / 'Chapters/Book-1/export/beta/manuscript-combined.docx'
        returned = self.root / 'returned.docx'
        # A returned native Word comment has a range in document.xml and its text in comments.xml.
        with zipfile.ZipFile(source) as original, zipfile.ZipFile(returned, 'w') as file:
            doc = ET.fromstring(original.read('word/document.xml'))
            target = next(p for p in doc.iter(WORD + 'p')
                          if ''.join(n.text or '' for n in p.iter(WORD + 't')) == 'Mara kept the key.')
            target.insert(0, ET.Element(WORD + 'commentRangeStart', {WORD+'id': '2'}))
            ET.SubElement(target, WORD + 'commentRangeEnd', {WORD+'id': '2'})
            comments = ET.Element(WORD + 'comments')
            node = ET.SubElement(comments, WORD + 'comment', {WORD+'id': '2', WORD+'author': 'Sam'})
            ET.SubElement(ET.SubElement(ET.SubElement(node, WORD + 'p'), WORD + 'r'), WORD + 't').text = 'Why keep it?'
            for entry in original.infolist():
                if entry.filename == 'word/comments.xml':
                    continue
                data = (ET.tostring(doc) if entry.filename == 'word/document.xml' else original.read(entry))
                file.writestr(entry, data)
            file.writestr('word/comments.xml', ET.tostring(comments))
        args = '--root', self.root, '--docx', returned
        feedback = self.cli(BETA, *args)
        self.assertEqual(feedback['export_id'], edition)
        note, = feedback['feedback']
        self.assertEqual((note['reader'], note['quote'], note['comment']), ('Sam', 'Mara kept the key.', 'Why keep it?'))
        self.assertEqual(note['location']['chapter'], 'Chapter 1')
        self.assertEqual(self.cli(BETA, *args)['added'], 0)
        next_edition = self.cli(EXPORT, '--root', self.root)['beta_feedback']['export_id']
        self.assertIn('different beta export',
                      self.cli(BETA, '--root', self.root, '--export', next_edition, '--docx', returned, fail=True))

    def test_private_study_freezes_matched_packets_and_blinds_author(self):
        source = 'The ink wept.\n\nThe pen was just a little dry.\n'
        chapter = self.write('private/chapter.md', source)
        corpus = self.put('private/corpus.json', {'cases': [
            {'id': 'private-chapter', 'category': 'voice', 'source_file': chapter.name, 'rules': 'Retain metaphor.',
             'defect_spans': ['just a little'], 'protected_spans': ['The ink wept.']}
        ]})
        config = self.put('private/configuration.json', {'model': 'fixture', 'host': 'fixture'})
        run = self.cli(EVAL, '--corpus', corpus, '--packets', self.root/'private/packets',
                       '--baseline-ref', 'HEAD', '--candidate-ref', 'HEAD', '--configuration', config)
        self.assertEqual(run['packets'], 2)
        manifest = json.loads(Path(run['study_manifest']).read_text())
        private = json.loads(Path(run['private_manifest']).read_text())
        opaque, = manifest['expected_case_ids']
        results = []
        for variant in manifest['variants']:
            packet_path = self.root/'private/packets'/variant/(opaque+'.json')
            data = json.loads(packet_path.read_text())
            self.assertNotIn('defect_spans', data)
            self.assertNotIn('private-chapter', data)
            is_candidate = private['variants'][variant] == 'candidate'
            position = source.index('just a little')
            findings = ([dict(start=position, end=position+13, quote='just a little',
                              replacement='slightly', reason='Remove filler.')] if is_candidate else [])
            for repeat in range(1, 3):
                results.append(dict(case_id=opaque, variant=variant, repeat_index=repeat, status='complete',
                                    attempt_id=f'{variant}-{repeat}', source_sha256=manifest['source_hashes'][opaque],
                                    configuration_sha256=manifest['configuration_sha256'], findings=findings,
                                    packet_sha256=hashlib.sha256(packet_path.read_bytes()).hexdigest()))
        result = self.put('private/results.json', {'manifest': manifest, 'results': results})
        args = '--corpus', corpus, '--results', result, '--mapping', run['private_manifest']
        blind = self.root/'private/blind.json'
        self.cli(EVAL, *args, '--blind-review', blind)
        authored = json.loads(blind.read_text())
        self.assertEqual(len(authored['outputs']), 4)
        self.assertNotIn('variant', authored['outputs'][0])
        scored = self.cli(EVAL, *args)
        self.assertEqual(scored['by_variant']['candidate']['defects_caught'], 2)
        self.assertEqual(scored['by_variant']['baseline']['defects_caught'], 0)
        self.assertEqual(scored['author_evaluation'], 'pending')
        ratings = [
            {'review_id': output['review_id'], 'dimension': 'useful_repair', 'accepted': True,
             'reason': 'Synthetic scoring fixture.', 'kept_findings': [1] if output['findings'] else []}
            for output in authored['outputs']
        ]
        ratings_path = self.put('private/ratings.json', {'evaluator_id': 'author-fixture', 'ratings': ratings})
        reviewed = self.cli(EVAL, *args, '--author-scores', ratings_path)
        self.assertEqual(reviewed['by_variant']['candidate']['fixes_kept'], 2)
        self.assertFalse(reviewed['release_eligible'])


if __name__ == '__main__':
    unittest.main()
