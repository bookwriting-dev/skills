#!/usr/bin/env python3
"""Payoff context reaches the ordinary draft and preflight commands."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/book-status/scripts'
sys.path.insert(0, str(SCRIPTS))
from state_core import evidence, ledger_store_module


class DraftPromises(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.first = 'Chapters/Book-1/Chapter-001.md'
        self.ledger = 'Wiki/Story/Book-1/promises.yaml'
        self.quote = 'Her brother whistled twice.'
        self.write(self.first, '# Chapter 1\n\n' + self.quote + '\n<!-- STORYCRAFT: Hidden setup. -->\n')
        for number in (2, 3, 4):
            self.write(f'Chapters/Book-1/Chapter-{number:03}.md', f'# Chapter {number}\n\nLow tide.')
        self.write(self.ledger, json.dumps({'promises': [
            self.promise('due', 2, setup_quote=self.quote), self.promise('soon', 'ch3'),
            self.promise('later', 4), self.promise('deferred', 2, deferred_to_series=True),
            self.promise('previously-paid', 2, paid_in_ch=1, paid_how='Returned'),
            self.promise('future-setup', 3, introduced_ch=3),
            self.promise('later-paid', 2, paid_in_ch=4, paid_how='A future confession'),
        ]}))

    def write(self, name, contents):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding='utf-8')

    def promise(self, identifier, due, **fields):
        return dict({'id': identifier, 'promise': f'Pay off {identifier}', 'introduced_ch': 'ch1',
                     'payoff_by_ch': due, 'kind': 'relationship', 'weight': 'plain'}, **fields)

    def packet(self, command='chapter-preflight', number=2):
        result = subprocess.run([sys.executable, '-B', str(SCRIPTS/'project_state.py'), '--root',
                                 str(self.root), '--book', 'Book-1', command, '--chapter', str(number)],
                                check=True, capture_output=True, text=True)
        payload = json.loads(result.stdout)
        return payload.get('draft_packet', payload)['promises']

    def test_due_promise_in_standard_preflight_with_verified_setup(self):
        context = self.packet()
        items = {item['id']: item for item in context['items']}
        self.assertEqual(set(items), {'due', 'soon', 'later-paid'})
        self.assertEqual(items['due']['status'], 'due')
        self.assertEqual(items['soon']['status'], 'due_next')
        self.assertEqual(items['due']['setup']['path'], self.first)
        self.assertEqual(items['due']['setup']['quote'], self.quote)
        self.assertNotIn('future confession', json.dumps(items))
        self.assertEqual(self.packet('draft-packet'), context)

    def test_committed_generation_overrides_mirror_and_stale_quote_is_omitted(self):
        managed = self.promise('managed', 1, setup_quote='An obsolete version.')
        ledger_store_module().commit(self.root, {
            'schema_version': 1, 'transaction_id':'managed', 'expected_generation': None,
            'source_evidence': evidence(self.root, [self.first]),
            'updates': {self.ledger: json.dumps({'promises':[managed]})}})
        items = self.packet()['items']
        self.assertEqual([(i['id'], i['status']) for i in items], [('managed', 'overdue')])
        self.assertEqual(items[0]['setup']['path'], self.first)
        self.assertNotIn('quote', items[0]['setup'])
        self.assertEqual(items[0]['setup']['quote_status'], 'unverified')

    def test_private_setup_note_and_cash_already_on_page(self):
        self.write(self.ledger, json.dumps({'promises': [
            self.promise('old', 2, setup_quote='Hidden setup.'),
            self.promise('keep', 10, paid_in_ch=2, paid_how='The whistle returns.'),
        ]}))
        old, keep = self.packet()['items']
        self.assertNotIn('quote', old['setup'])
        self.assertEqual(keep['status'], 'paid_here')
        self.assertNotIn('keep', {item['id'] for item in self.packet(number=3)['items']})

    def test_missing_and_unreadable_ledger_are_distinct(self):
        (self.root/self.ledger).unlink()
        self.assertEqual(self.packet()['status'], 'missing')
        self.write(self.ledger, 'promises: [')
        self.assertEqual(self.packet()['status'], 'unreadable')

    def test_declared_order_next_ids_numbered_aliases_and_paths(self):
        chapters = [
            dict(id='intro-7', display_label='Prologue', reading_order=10, path=self.first),
            dict(id='unit-83', display_label='Chapter 1', reading_order=20, path='Chapters/Book-1/Chapter-002.md'),
            dict(id='unit-14', display_label='Chapter 2', reading_order=30, path='Chapters/Book-1/Chapter-003.md'),
            dict(id='unit-19', display_label='Interlude', reading_order=40, path='Chapters/Book-1/Chapter-004.md'),
        ]
        self.write('.storycraft/project.json', json.dumps({
            'schema_version': 1, 'record_type': 'project_manifest', 'project_id': 'test-project',
            'books': [{'id': 'book-1', 'display_label': 'Book-1', 'chapter_order': 'declared', 'chapters': chapters}]}))
        self.write(self.ledger, json.dumps({'promises': [
            self.promise('known-id', 'unit-14', introduced_ch='intro-7', setup_quote=self.quote),
            self.promise('known-path', chapters[2]['path'], introduced_ch='sec1.2', setup_quote='Low tide.'),
            self.promise('numbered', 'ch2', introduced_ch='Chapter 1'),
            self.promise('opaque', 'retired-13'), self.promise('lost-paid', 'ch1', paid_in_ch='old-unit-8'),
            self.promise('unknown-start', 'ch1', introduced_ch='discarded-9'),
            self.promise('paid-here', 'unit-14', paid_in_ch='unit-83'),
        ]}))
        context = self.packet('draft-packet', number='unit-83')
        items = {item['id']: item for item in context['items']}
        self.assertEqual({key: item['status'] for key, item in items.items()}, {
            'known-id': 'due_next', 'known-path': 'due_next', 'numbered': 'due_next', 'paid-here': 'paid_here'})
        self.assertEqual(items['known-path']['setup'], {'path': chapters[1]['path'], 'quote': 'Low tide.'})
        self.assertEqual(items['known-id']['setup']['quote'], self.quote)
        self.assertEqual({(row['id'], row['field']) for row in context['unresolved']},
                         {('opaque', 'payoff_by_ch'), ('lost-paid', 'paid_in_ch'), ('unknown-start', 'introduced_ch')})

    def test_conventional_future_target_before_chapter_registration(self):
        (self.root/'Chapters/Book-1/Chapter-003.md').unlink()
        (self.root/'Chapters/Book-1/Chapter-004.md').unlink()
        self.write(self.ledger, json.dumps({'promises': [self.promise('unregistered', 'ch3')]}))
        self.assertEqual(self.packet()['items'][0]['status'], 'due_next')

    def test_legacy_manifest_with_repeated_labels_needs_a_unique_id(self):
        chapters = [dict(id=key, display_label=label, reading_order=order,
                         path=f'Chapters/Book-1/Chapter-{index:03}.md')
                    for index, (key, label, order) in enumerate(
                        [('open', 'Opening', 10), ('left', 'Interlude', 20), ('right', 'Interlude', 30)], 1)]
        self.write('.storycraft/project.json', json.dumps({
            'schema_version': 1, 'record_type': 'project_manifest', 'project_id': 'older',
            'books': [{'id': 'book-1', 'display_label': 'Book-1', 'chapters': chapters}]}))
        self.write(self.ledger, json.dumps({'promises': [
            self.promise('valid', 'left', introduced_ch='open'),
            self.promise('ambiguous', 'Interlude', introduced_ch='open')]}))
        context = self.packet('draft-packet', number='open')
        self.assertEqual([(item['id'], item['status']) for item in context['items']], [('valid', 'due_next')])
        self.assertEqual(context['unresolved'][0]['id'], 'ambiguous')

    def test_wrong_yaml_shape_is_unreadable_but_empty_ledger_is_available(self):
        for raw in ('[]', 'false', '{}', '""', 'null'):
            with self.subTest(raw=raw):
                self.write(self.ledger, raw)
                self.assertEqual(self.packet()['status'], 'unreadable')
        for raw in ('', '# intentionally blank\n', 'promises: []\n'):
            with self.subTest(raw=raw):
                self.write(self.ledger, raw)
                self.assertEqual(self.packet()['status'], 'available')


if __name__ == '__main__':
    unittest.main()
