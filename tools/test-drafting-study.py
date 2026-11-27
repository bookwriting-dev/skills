#!/usr/bin/env python3
"""Exercise a matched drafting comparison, including resume and blind ballots."""
import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('drafting_study', HERE / 'eval-drafting.py')
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


class DraftingStudy(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / 'study'
        args = argparse.Namespace(study=self.root, baseline='HEAD', candidate='WORKTREE', model='test-model',
                                  brief=study.BRIEF, min_words=3, max_words=7, effort='low')
        study.prepare(args)
        self.manifest = study.read(self.root / 'private/manifest.json')

    def sample(self, private, label, manifest, timeout):
        self.assertTrue((private / f'{label}.zip').is_file())
        self.assertEqual(manifest['brief'], study.BRIEF.read_text().strip())
        return {part: 'Test words for the excerpt.' for part in study.PARTS}

    def test_blind_handoff_and_human_scoring(self):
        public = study.run(self.root, 5, self.sample)
        prompt = (public / 'read.md').read_text()
        self.assertEqual(prompt.count('Test words for the excerpt.'), 6)
        for secret in ['WORKTREE', 'test-model', 'baseline', 'candidate', 'manifest.json']:
            self.assertNotIn(secret, prompt)
        ballot = study.read(public / 'blank-ballot.json')
        path = public / 'my-response.json'
        with self.assertRaises(ValueError):
            study.score(self.root, [public / 'blank-ballot.json'])
        ballot.update(reader='Reader 1', keep_reading='B', reading_reason='Her next decision still mattered.',
                      character_choice='She signed before her sister arrived.', changed_detail='The empty stool.')
        study.write_json(path, ballot)
        answer = study.score(self.root, [path])['responses']['Reader 1']
        self.assertEqual(answer['version_chosen'], self.manifest['packages']['B']['version'])
        with self.assertRaisesRegex(ValueError, 'Duplicate reader'):
            study.score(self.root, [path, path])
        ballot['ballot_id'] = 'another-study'
        study.write_json(path, ballot)
        with self.assertRaisesRegex(ValueError, 'match'):
            study.score(self.root, [path])

    def test_resume_retains_valid_sample_and_rejects_altered_output(self):
        def interrupted(private, label, manifest, timeout):
            if label == 'A':
                return self.sample(private, label, manifest, timeout)
            return dict.fromkeys(study.PARTS, 'Short.')
        with self.assertRaisesRegex(ValueError, 'budget'):
            study.run(self.root, 5, interrupted)
        self.assertTrue((self.root / 'private/A.json').is_file())
        self.assertFalse((self.root / 'readers').exists())
        called = []
        def complete(private, label, manifest, timeout):
            called.append(label)
            return self.sample(private, label, manifest, timeout)
        study.run(self.root, 5, complete)
        self.assertEqual(called, ['B'])
        sample_file = self.root / 'private/A.json'
        changed = study.read(sample_file)
        changed['draft']['middle'] += ' Stowaway.'
        study.write_json(sample_file, changed)
        with self.assertRaisesRegex(ValueError, 'changed'):
            study.run(self.root, 5, complete)

    def test_altered_reader_copy_cannot_be_scored(self):
        public = study.run(self.root, 5, self.sample)
        (public / 'read.md').write_text('Changed handout')
        with self.assertRaisesRegex(ValueError, 'handout'):
            study.score(self.root, [public / 'blank-ballot.json'])

    def test_exchanging_sample_files_cannot_reverse_attribution(self):
        study.run(self.root, 5, self.sample)
        a, b = (self.root / f'private/{label}.json' for label in ('A', 'B'))
        first, second = a.read_bytes(), b.read_bytes()
        a.write_bytes(second)
        b.write_bytes(first)
        with self.assertRaisesRegex(ValueError, 'assignment'):
            study.run(self.root, 5, self.sample)
        with self.assertRaisesRegex(ValueError, 'assignment'):
            study.score(self.root, [self.root / 'readers/blank-ballot.json'])

    def test_live_entrypoint_uses_frozen_package_and_same_model_and_budget(self):
        def invoke(command, *, cwd, input, **unused):
            self.assertTrue((cwd / '.agents/skills/fiction-writechapter/SKILL.md').is_file())
            self.assertIn('FICTION', (cwd / 'AGENTS.md').read_text())
            self.assertIn('3 and 7', input)
            for skill in self.manifest['skills']:
                rules = cwd / '.agents/skills' / skill / 'SKILL.md'
                self.assertIn(rules.read_text(), input)
            self.assertIn('test-model', command)
            self.assertEqual((cwd / '_Intake/Book-1/premise.md').read_text(), self.manifest['brief'])
            output = Path(command[command.index('--output-last-message')+1])
            output.write_text(json.dumps(self.sample(self.root/'private', 'A', self.manifest, 5)))
            return argparse.Namespace(returncode=0, stderr='')
        with patch.object(study.subprocess, 'run', side_effect=invoke):
            study.run(self.root, 5)
        source = self.root / 'private/A.zip'
        source.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Frozen package changed'):
            study.generate(self.root / 'private', 'A', self.manifest, 5)


if __name__ == '__main__':
    unittest.main()
