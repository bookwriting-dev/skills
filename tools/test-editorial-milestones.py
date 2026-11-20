#!/usr/bin/env python3
"""Forward checks for editorial commands using paired, disposable Storycraft projects."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / 'skills/book-status/scripts/editorial_tools.py'
CASES = json.loads((ROOT / 'tools/eval-fixtures/editorial-milestones/cases.json').read_text(encoding='utf-8'))
COMMENT_SECRET = 'AUTHOR-COMMENT-ONLY'
FENCE_SECRET = 'AUTHOR-FENCE-ONLY'
OTHER_BOOK = 'COMPANION-VOLUME-ONLY'
PLAN = 'PLAN-COORDINATOR-ONLY'
POCKET_KEY = 'The archive assigns slip 1 to the paper pocket and slip 2 to the brass pocket.'
TARGET = 'Ruth caught June at the foot of the stairs.'
PAYOFF = 'June reached under the blue teapot without looking'
ALTERNATE = 'June watched her aunt put the parcel token beneath the blue teapot.'


def write(root, relative, content):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    return path


def materialize(root, kind, variant):
    """Only the materialized project is visible to the tool under test."""
    group = CASES[kind]
    files = {
        'Chapters/Book-2/Chapter-001.md': f'# Chapter 1\n\n{OTHER_BOOK}. A second account of the journey.\n',
        'Wiki/Outline/Book-1/outline.md': f'# Notes to the author\n\n{PLAN}. The second account is false.\n',
        **group['common'], **group['variants'][variant],
    }
    for relative, source in files.items():
        if relative.startswith('Chapters/Book-1/'):
            source += (f'\n<!-- STORYCRAFT: {COMMENT_SECRET} -->\n'
                       f'\n```storycraft-internal\n{FENCE_SECRET}\n```\n')
        write(root, relative, source)
    return root


def invoke(root, *args, book='Book-1'):
    return subprocess.run([sys.executable, '-B', str(TOOL), '--root', str(root), '--book', book, *args],
                          text=True, capture_output=True)


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


class EditorialMilestones(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def project(self, kind, variant):
        return materialize(Path(self.temp.name) / variant, kind, variant)

    def run_tool(self, root, *args, book='Book-1'):
        def files():
            return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        original = files()
        result = invoke(root, *args, book=book)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        current = files()
        if '--approve' in args:
            original.pop('Wiki/Style/pronunciations.json', None)
            current.pop('Wiki/Style/pronunciations.json', None)
        self.assertEqual(current, original, 'an editorial command changed unrelated project files')
        packet = json.loads(result.stdout)
        delivered = '\n'.join(strings(packet))
        for secret in (COMMENT_SECRET, FENCE_SECRET, OTHER_BOOK, PLAN):
            self.assertNotIn(secret, delivered)
        return packet

    def assert_evidence(self, needle, packet):
        self.assertTrue(any(needle in item for item in strings(packet)), f'{needle!r} missing from {packet!r}')

    def test_cast_collision_cites_both_people_and_excludes_same_person_aliases(self):
        separate = self.run_tool(self.project('cast', 'two_people'), 'cast')
        self.assertEqual(len(separate['collisions']), 1)
        collision = separate['collisions'][0]
        self.assertEqual(set(collision['names']), {'Mara Holt', 'Mira Holt'})
        self.assert_evidence('Mara Holt, the shuttle driver', collision['evidence'])
        self.assert_evidence('Mira Holt, the clerk', collision['evidence'])
        alias = self.run_tool(self.project('cast', 'one_person'), 'cast')
        self.assertEqual(alias['collisions'], [])

    def test_missing_phonetic_codes_do_not_match_unrelated_names(self):
        root = Path(self.temp.name) / 'names'
        for name in ('如歌', '子安'):
            write(root, f'Wiki/Characters/{name}.md', f'---\nname: {name}\nrole: supporting\n---\n')
        write(root, 'Chapters/Book-1/Chapter-001.md',
              '# Chapter 1\n\n如歌 brought in the shawl. 子安 went for the doctor.\n')
        self.assertEqual(self.run_tool(root, 'cast')['collisions'], [])

    def test_cast_citation_finds_the_physical_source_line_after_private_material(self):
        root = self.project('cast', 'two_people')
        path = root / 'Chapters/Book-1/Chapter-001.md'
        private = f'<!-- STORYCRAFT: {COMMENT_SECRET}\nsecond private line -->\n\n'
        source = path.read_text(encoding='utf-8').replace('Mara Holt,', private + 'Mara Holt,')
        path.write_text(source, encoding='utf-8')
        evidence = self.run_tool(root, 'cast')['collisions'][0]['evidence']
        row = next(item for item in evidence if item['path'] == path.relative_to(root).as_posix())
        self.assertEqual(source.splitlines()[row['line'] - 1], row['quote'])

    def test_alias_return_includes_prior_anchor_and_the_paragraph_after_the_return(self):
        cues = {'bare': 'She chose the chair farthest from the window.',
                'cued': 'The ferry pilot held out her hand for the spare key'}
        for variant, cue in cues.items():
            with self.subTest(variant=variant):
                root = self.project('return', variant)
                packet = self.run_tool(root, 'cast', '--gap', '3')
                self.assertEqual([row['name'] for row in packet['returns']], ['Eska Fen'])
                row = packet['returns'][0]
                self.assertEqual(row['gap'], 4)
                self.assert_evidence('the ferry pilot', row['previous'])
                self.assert_evidence('Rook drew the meeting room door shut.', row['return_line'])
                self.assert_evidence(cue, row['context'])
                self.assertNotIn('She wrote the letter under the pier.', '\n'.join(strings(row)))
                self.assertEqual(self.run_tool(root, 'cast', '--gap', '20')['returns'], [])

    def test_scene_removal_exposes_the_earlier_witness_and_later_payoff(self):
        for variant, earlier in [('sole_setup', 'The shop notice had turned to pulp'),
                                 ('alternate_setup', ALTERNATE)]:
            with self.subTest(variant=variant):
                root = self.project('scene', variant)
                packet = self.run_tool(root, 'scene', '--chapter', '2', '--scene', '2')
                self.assert_evidence(TARGET, packet['text'])
                self.assertNotIn('June took down the shutters', packet['text'])
                self.assertNotIn('At closing time', packet['text'])
                self.assert_evidence(earlier, packet['before'])
                self.assert_evidence('June took down the shutters', packet['before'])
                self.assert_evidence('At closing time June stacked the saucers', packet['after'])
                self.assert_evidence(PAYOFF, packet['later'])
                for scene in [packet, *packet['before'], *packet['after'], *packet['later']]:
                    source = (root / scene['path']).read_text(encoding='utf-8').splitlines()
                    self.assertEqual(scene['text'].splitlines()[0], source[scene['start_line'] - 1])

    def test_geography_delivers_the_sourced_constraint_or_its_actual_omission(self):
        variants = {'explicit_bank': 'The only ferry landing at Wren Lock stands on the west bank.',
                    'unspecified_bank': 'Wren Lock has a ferry landing with a canvas shelter.'}
        for variant, canon in variants.items():
            with self.subTest(variant=variant):
                packet = self.run_tool(self.project('geography', variant), 'scene', '--chapter', '1', '--scene', '1')
                self.assert_evidence('the ferry landing on the east bank at Wren Lock', packet['text'])
                self.assert_evidence('Wiki/Locations/Wren_Lock.md', packet['places'])
                self.assert_evidence(canon, packet['places'])
                if variant == 'unspecified_bank':
                    self.assertNotIn('west bank', '\n'.join(strings(packet['places'])))

    def test_pronunciation_reuses_only_approved_readings_and_keeps_first_appearance(self):
        for variant in ('pending', 'approved'):
            with self.subTest(variant=variant):
                root = self.project('pronunciation', variant)
                pending = self.run_tool(root, 'pronunciation')
                entries = {row['term']: row for row in pending['entries']}
                self.assertEqual(list(entries), ['Sélin Orre', 'Xoë Quell', 'Lio Pier', 'nárin'])
                for term, chapter, category in [('Sélin Orre', 1, 'character'), ('Xoë Quell', 2, 'character'),
                                                ('Lio Pier', 2, 'place'), ('nárin', 2, 'term')]:
                    self.assertEqual(entries[term]['status'].lower(), 'pending')
                    self.assertEqual(entries[term]['category'], category)
                    self.assertFalse(entries[term].get('reading'))
                    self.assert_evidence(f'Chapter-{chapter:03}.md', entries[term]['first_appearance'])
                if variant == 'approved':
                    reading = 'SAY-lin OR'
                    self.run_tool(root, 'pronunciation', '--approve', 'Sélin Orre', '--reading', reading)
                    again = self.run_tool(root, 'pronunciation')
                    rows = {row['term']: row for row in again['entries']}
                    self.assertEqual(rows['Sélin Orre']['reading'], reading)
                    self.assertEqual(rows['Sélin Orre']['status'].lower(), 'approved')
                    self.assertEqual(rows['Sélin Orre']['first_appearance'], entries['Sélin Orre']['first_appearance'])
                    self.assertEqual(rows['Xoë Quell']['status'].lower(), 'pending')
                    self.assertFalse(rows['Xoë Quell'].get('reading'))
                    write(root, 'Chapters/Book-2/Chapter-001.md',
                          '# Chapter 1\n\nXoë Quell passed the ledger back to Sélin Orre.\n')
                    sequel = self.run_tool(root, 'pronunciation', book='Book-2')
                    reused = {row['term']: row for row in sequel['entries']}
                    self.assertEqual(reused['Sélin Orre']['reading'], reading)
                    self.assertEqual(reused['Sélin Orre']['status'].lower(), 'approved')
                    self.assertEqual(reused['Xoë Quell']['status'].lower(), 'pending')
                    self.assertFalse(reused['Xoë Quell'].get('reading'))

    def test_walkthrough_delivers_only_the_unaltered_reader_chapter(self):
        for variant in ('missing_key', 'printed_key'):
            with self.subTest(variant=variant):
                root = self.project('walkthrough', variant)
                packet = self.run_tool(root, 'walkthrough', '--chapter', '2')
                original = CASES['walkthrough']['variants'][variant]['Chapters/Book-1/Chapter-002.md']
                self.assertEqual(packet['text'].strip(), original.strip())
                self.assertEqual(POCKET_KEY in packet['text'], variant == 'printed_key')
                delivered = '\n'.join(strings(packet))
                for other in ('POCKET-PREFACE-ONLY', 'POCKET-AFTERWORD-ONLY', 'The missing archive rule'):
                    self.assertNotIn(other, delivered)

    def test_walkthrough_resolves_a_registered_interlude_without_reading_its_neighbor(self):
        root = self.project('walkthrough', 'printed_key')
        path = 'Essays/Filing at the counter.md'
        chapter = root / 'Chapters/Book-1/Chapter-002.md'
        write(root, path, chapter.read_text(encoding='utf-8'))
        neighbor = 'Chapters/Book-1/Chapter-003.md'
        write(root, neighbor, '# Chapter 3\n\n<!-- Unclassified private material in a separate chapter -->\n')
        manifest = {'schema_version': 1, 'record_type': 'project_manifest', 'project_id': 'fixture',
                    'books': [{'id': 'book-1', 'display_label': 'Book-1', 'chapter_order': 'declared',
                               'chapters': [{'id': 'filing', 'display_label': 'Interlude',
                                             'path': path, 'reading_order': 1},
                                            {'id': 'following', 'display_label': 'Afterword',
                                             'path': neighbor, 'reading_order': 2}]}]}
        write(root, '.storycraft/project.json', json.dumps(manifest))
        packet = self.run_tool(root, 'walkthrough', '--chapter', 'Interlude')
        self.assert_evidence(POCKET_KEY, packet['text'])
        self.assertNotIn('Unclassified', '\n'.join(strings(packet)))

    def test_act_boundary_limits_cast_and_unlisted_narrator_term_carries_approval(self):
        root = self.project('cast','two_people')
        self.assertFalse(self.run_tool(root,'cast','--through','1')['collisions'])
        term = 'Daëmir'
        for n in (1,2):
            write(root,f'Chapters/Book-{n}/Chapter-003.md',f'# Chapter 3\n\nShe took the {term} from its case.\n')
        pending = self.run_tool(root,'pronunciation','--term',term)['entries']
        self.assertEqual(next(e['status'] for e in pending if e['term']==term),'pending')
        self.run_tool(root,'pronunciation','--approve',term,'--reading','DAY-meer')
        later = subprocess.run([sys.executable,'-B',str(TOOL),'--root',str(root),'--book','Book-2','pronunciation'],
                               check=True,capture_output=True,text=True)
        entry = next(e for e in json.loads(later.stdout)['entries'] if e['term']==term)
        self.assertEqual(entry['reading'],'DAY-meer')
        self.assertIn('Book-2',entry['first_appearance']['path'])

    def test_unknown_private_apparatus_and_out_of_range_scene_fail_closed(self):
        root = self.project('scene', 'sole_setup')
        invalid = invoke(root, 'scene', '--chapter', '2', '--scene', '9')
        self.assertNotEqual(invalid.returncode, 0)
        self.assertNotIn(TARGET, invalid.stdout)
        path = root / 'Chapters/Book-1/Chapter-002.md'
        source = path.read_text(encoding='utf-8') + '\n<!-- PRIVATE-UNKNOWN -->\n'
        path.write_text(source, encoding='utf-8')
        invalid = invoke(root, 'walkthrough', '--chapter', '2')
        self.assertNotEqual(invalid.returncode, 0)
        self.assertNotIn('PRIVATE-UNKNOWN', invalid.stdout)
        self.assertEqual(path.read_text(encoding='utf-8'), source)


if __name__ == '__main__':
    unittest.main()
