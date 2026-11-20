#!/usr/bin/env python3
"""Forward acceptance tests for EPUB intake, exported links, and returning beta readers."""
import base64
import hashlib
import json
import os
from pathlib import Path
import posixpath
import shutil
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parent.parent
IMPORT = ROOT / 'skills/book-reverse-engineer/scripts/manuscriptkit.py'
STATE = ROOT / 'skills/book-status/scripts/project_state.py'
EXPORT = ROOT / 'skills/compile-manuscript/scripts/compile_manuscript.py'
BETA = ROOT / 'skills/beta-feedback/scripts/beta_feedback.py'
NAVIGATION = EXPORT.with_name('epub_navigation.py')
HTML = '{http://www.w3.org/1999/xhtml}'
EPUB = '{http://www.idpf.org/2007/ops}'
WORD = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
RELS = '{http://schemas.openxmlformats.org/package/2006/relationships}'
TYPES = '{http://schemas.openxmlformats.org/package/2006/content-types}'
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAgAAAAFCAIAAAD38zoCAAAAJklEQVR4nGN48+ru1ok+'
                       'EARkwxEDEHOETIcgOBtdAlkOrw6sdgAAwYpJM3cTm9MAAAAASUVORK5CYII=')
PANDOC = shutil.which('pandoc')
UNITS = {
    'Prologue': 'Salt dried on the clock face.',
    'Chapter 1': 'The sounder rose from the channel.',
    'Chapter 2': 'The shutter caught the last light.',
    'Interlude': 'Three gulls watched the empty pier.',
    'Epilogue': 'The lightship sailed at noon.',
}
CAPTION = 'Sounding line at slack water'
ALT = 'A blue sounding line on a brass spool'
NOTE = 'The mark was cut before the flood.'


def write_epub(path, package, members):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        archive.writestr('META-INF/container.xml',
                         '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                         '<rootfiles><rootfile full-path="Book/package.opf" '
                         'media-type="application/oebps-package+xml"/></rootfiles></container>')
        archive.writestr('Book/package.opf', package)
        for name, data in members.items():
            archive.writestr('Book/' + name, data)


def source_epub(path):
    """Write one original EPUB whose archive order differs from its reading order."""
    def xhtml(title, body):
        return (f'<html xmlns="{HTML[1:-1]}" xmlns:epub="{EPUB[1:-1]}" xml:lang="en">'
                f'<head><title>{title}</title></head><body>{body}</body></html>')

    def unit(label, anchor, role, extra=''):
        return (f'<section id="{anchor}" epub:type="{role}"><h1>{label}</h1>'
                f'<p>{UNITS[label]}</p>{extra}</section>')

    destinations = [
        ('Prologue', 'fore.xhtml#fore'), ('Chapter 1', 'channel.xhtml#ebb'),
        ('Chapter 2', 'channel.xhtml#flood'), ('Interlude', 'birds.xhtml#tide'),
        ('Epilogue', 'light.xhtml#sailing'), ('Notes', 'notes.xhtml#notes'),
    ]
    toc = ''.join(f'<li><a href="{href}">{label}</a></li>' for label, href in destinations)
    content = {
        'notes': xhtml('Notes', '<section epub:type="endnotes" id="notes"><h1>Notes</h1>'
                       f'<aside epub:type="endnote" id="survey"><p>{NOTE} '
                       '<a href="channel.xhtml#reader-mark" role="doc-backlink">Return to the mark</a>'
                       '</p></aside></section>'),
        'light': xhtml('Epilogue', unit('Epilogue', 'sailing', 'epilogue')),
        'birds': xhtml('Interlude', unit('Interlude', 'tide', 'interlude')),
        'channel': xhtml('Channel', unit('Chapter 1', 'ebb', 'chapter',
                         '<table><thead><tr><th>Station</th><th>Depth</th></tr></thead>'
                         '<tbody><tr><td>Cormorant</td><td>Seven fathoms</td></tr></tbody></table>'
                         f'<figure><img src="../images/spool.png" alt="{ALT}"/>'
                         f'<figcaption>{CAPTION}</figcaption></figure>'
                         '<p>They would <a href="#flood">visit the shutter</a> across the bay.</p>')
                         + unit('Chapter 2', 'flood', 'chapter',
                                '<p>She found the mark.<a epub:type="noteref" role="doc-noteref" '
                                'id="reader-mark" href="notes.xhtml#survey">1</a></p>')),
        'fore': xhtml('Prologue', unit('Prologue', 'fore', 'prologue')),
    }
    items = ''.join(f'<item id="{key}" href="text/{key}.xhtml" media-type="application/xhtml+xml"/>'
                    for key in content)
    spine = ''.join(f'<itemref idref="{key}"/>' for key in ('fore', 'channel', 'birds', 'light', 'notes'))
    package = ('<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="edition">'
               '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
               '<dc:identifier id="edition">urn:uuid:312de966-a8d9-463b-b0b5-43d03b0b4050</dc:identifier>'
               '<dc:title>The Sounding Line</dc:title><dc:language>en</dc:language>'
               '<meta property="dcterms:modified">2026-11-01T00:00:00Z</meta></metadata>'
               f'<manifest>{items}<item id="nav" href="text/nav.xhtml" media-type="application/xhtml+xml" '
               'properties="nav"/><item id="image" href="images/spool.png" media-type="image/png"/>'
               f'</manifest><spine>{spine}</spine></package>')
    members = {f'text/{key}.xhtml': text for key, text in content.items()}
    members['text/nav.xhtml'] = xhtml('Contents', f'<nav epub:type="toc"><ol>{toc}</ol></nav>')
    members['images/spool.png'] = PNG
    write_epub(path, package, members)


def ncx_epub(path):
    """Make an EPUB 2 whose NCX alone identifies two named units inside one XHTML."""
    uid = 'urn:uuid:55bcc637-0dc4-477f-ada7-92beda537a0b'
    package = ('<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="edition">'
               '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
               f'<dc:identifier id="edition">{uid}</dc:identifier><dc:title>Old Signals</dc:title>'
               '<dc:language>en</dc:language></metadata><manifest><item id="text" href="old.xhtml" '
               'media-type="application/xhtml+xml"/><item id="contents" href="toc.ncx" '
               'media-type="application/x-dtbncx+xml"/></manifest><spine toc="contents">'
               '<itemref idref="text"/></spine></package>')
    labels = ('Prologue', 'Epilogue')
    points = ''.join(f'<navPoint id="n{i}" playOrder="{i}"><navLabel><text>{label}</text></navLabel>'
                     f'<content src="old.xhtml#s{i}"/></navPoint>' for i, label in enumerate(labels, 1))
    ncx = ('<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
           f'<head><meta name="dtb:uid" content="{uid}"/></head><docTitle><text>Old Signals</text></docTitle>'
           f'<navMap>{points}</navMap></ncx>')
    body = ''.join(f'<p id="s{i}">{UNITS[label]}</p>' for i, label in enumerate(labels, 1))
    document = f'<html xmlns="{HTML[1:-1]}"><head><title>Signals</title></head><body>{body}</body></html>'
    write_epub(path, package, {'toc.ncx': ncx, 'old.xhtml': document})


def rewrite_archive(source, destination, replacements):
    """Preserve unrelated parts and their ZIP metadata in a reader's returned book."""
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(destination, 'w') as changed:
        for entry in original.infolist():
            changed.writestr(entry, replacements.get(entry.filename, original.read(entry)))
        for name, data in replacements.items():
            if name not in original.namelist():
                changed.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)


def selection_comment(source, destination, quote, reader, comment):
    """Make the same comment selection as Word, with its relationship and content type."""
    with zipfile.ZipFile(source) as original:
        document = ET.fromstring(original.read('word/document.xml'))
        relationships = ET.fromstring(original.read('word/_rels/document.xml.rels'))
        types = ET.fromstring(original.read('[Content_Types].xml'))
        comments = (ET.fromstring(original.read('word/comments.xml'))
                    if 'word/comments.xml' in original.namelist() else ET.Element(WORD + 'comments'))
    paragraph, = (p for p in document.iter(WORD + 'p')
                  if ''.join(n.text or '' for n in p.iter(WORD + 't')) == quote)
    next_id = max((int(n.get(WORD + 'id')) for n in comments.iter(WORD + 'comment')), default=0) + 1
    identifier = {WORD + 'id': str(next_id)}
    start = 1 if paragraph.find(WORD + 'pPr') is not None else 0
    paragraph.insert(start, ET.Element(WORD + 'commentRangeStart', identifier))
    ET.SubElement(paragraph, WORD + 'commentRangeEnd', identifier)
    ET.SubElement(ET.SubElement(paragraph, WORD + 'r'), WORD + 'commentReference', identifier)
    entry = ET.SubElement(comments, WORD + 'comment', {**identifier, WORD + 'author': reader})
    run = ET.SubElement(ET.SubElement(entry, WORD + 'p'), WORD + 'r')
    ET.SubElement(run, WORD + 't').text = comment
    if not any(rel.get('Target') == 'comments.xml' for rel in relationships):
        ET.SubElement(relationships, RELS + 'Relationship', {
            'Id': 'storycraftReturnComments', 'Target': 'comments.xml',
            'Type': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments'})
    if not any(part.get('PartName') == '/word/comments.xml' for part in types):
        ET.SubElement(types, TYPES + 'Override', {
            'PartName': '/word/comments.xml',
            'ContentType': 'application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml'})
    parts = {'word/document.xml': document, 'word/comments.xml': comments,
             'word/_rels/document.xml.rels': relationships, '[Content_Types].xml': types}
    rewrite_archive(source, destination, {name: ET.tostring(root) for name, root in parts.items()})


def visible_text(element):
    return ' '.join(' '.join(element.itertext()).split())


def package_text(path):
    with zipfile.ZipFile(path) as archive:
        text = []
        for name in archive.namelist():
            data = archive.read(name)
            if name.endswith(('.xhtml', '.html', '.xml', '.opf', '.ncx')):
                text.append(visible_text(ET.fromstring(data)))
            if name.endswith(('.xhtml', '.html', '.xml', '.rels', '.opf', '.ncx', '.json', '.txt', '.md')):
                text.append(data.decode('utf-8'))
        return '\n'.join(text)


def epub_documents(path):
    with zipfile.ZipFile(path) as archive:
        return {name: ET.fromstring(archive.read(name)) for name in archive.namelist()
                if name.endswith(('.html', '.xhtml'))}


def href_target(document_name, href):
    url = urlsplit(href)
    target = (posixpath.normpath(posixpath.join(posixpath.dirname(document_name), unquote(url.path)))
              if url.path else document_name)
    return target, unquote(url.fragment)


def note_ref(element):
    return ('noteref' in element.get(EPUB + 'type', '').split() or
            element.get('role') == 'doc-noteref')


def backlink(element):
    return (element.get('role') == 'doc-backlink' or
            'backlink' in element.get(EPUB + 'type', '').split() or
            'footnote-back' in element.get('class', '').split())


class EditionExchange(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.chapters = self.root / 'Chapters/Book-1'

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def cli(self, script, *args, code=0, json_output=True):
        command = [sys.executable, str(script), *map(str, args)]
        # A minimal install may expose C as its locale. EPUB metadata still needs a language tag.
        environment = {**os.environ, 'LC_ALL': 'C', 'PYTHONDONTWRITEBYTECODE': '1'}
        result = subprocess.run(command, cwd=self.root, env=environment, text=True, capture_output=True)
        self.assertEqual(result.returncode, code,
                         f'{script.name} {args!r}\n{result.stderr}\n{result.stdout}')
        return json.loads(result.stdout) if json_output else result.stderr + result.stdout

    def state(self, *args):
        return self.cli(STATE, '--root', self.root, *args)

    def export(self, *formats):
        flags = [item for fmt in formats for item in ('--format', fmt)]
        return self.cli(EXPORT, '--root', self.root, '--profile', 'beta', *flags)

    def check_epub_metadata(self, path, *, title=None, language=None):
        dc = '{http://purl.org/dc/elements/1.1/}'
        with zipfile.ZipFile(path) as archive:
            container = ET.fromstring(archive.read('META-INF/container.xml'))
            package_name = container.find('.//{*}rootfile').get('full-path')
            package = ET.fromstring(archive.read(package_name))
        metadata = package.find('{*}metadata')
        titles = [(n.text or '').strip() for n in metadata.findall(dc + 'title')]
        self.assertTrue(any(titles), 'missing EPUB title')
        languages = [n.text for n in metadata.findall(dc + 'language')]
        self.assertTrue(languages, 'missing EPUB language')
        if title:
            self.assertIn(title, titles)
        if language:
            self.assertIn(language, languages)
        if lang := package.get('{http://www.w3.org/XML/1998/namespace}lang'):
            languages.append(lang)
        for lang in languages:
            self.assertRegex(lang or '', r'^(?:[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*|[ix](?:-[A-Za-z0-9]{1,8})+)$')

    def intake(self):
        source = self.root / 'source.epub'
        source_epub(source)
        original = source.read_bytes()
        args = source, '--export-chapters', self.chapters
        preview = self.cli(IMPORT, *args, '--preview')
        self.assertEqual(sorted(self.root.iterdir()), [source], 'preview wrote to the project')
        titles = [unit['title'] for unit in preview['units']]
        self.assertEqual([name for name in titles if name in UNITS], list(UNITS))
        self.cli(IMPORT, *args)
        self.assertEqual(source.read_bytes(), original, 'intake changed the source EPUB')
        return source

    @unittest.skipUnless(PANDOC, 'Pandoc is required to convert EPUB reader content')
    def test_imported_units_enter_normal_workflow_in_spine_order(self):
        source = self.intake()
        self.assertIn('Gate', self.state('workflow')['required_checks'])
        dashboard = self.state('dashboard')
        units = [row for row in dashboard['chapters'] if row['display_label'] in UNITS]
        self.assertEqual([row['display_label'] for row in units], list(UNITS))
        previous = None
        for unit in units:
            label = unit['display_label']
            packet = self.state('draft-packet', '--chapter', label)
            self.assertEqual(packet['chapter_path'], unit['chapter'])
            self.assertEqual(packet['predecessor_id'], previous)
            previous = unit['chapter_id']
            body = (self.root / packet['chapter_path']).read_text()
            self.assertIn(UNITS[label], body)
            for other_label, other_body in UNITS.items():
                if other_label != label:
                    self.assertNotIn(other_body, body, f'{label} absorbed {other_label}')
        files = [self.root / unit['chapter'] for unit in units]
        local_edit = files[1].read_text() + '\nA locally revised line.\n'
        files[1].write_text(local_edit)
        before = {path: path.read_bytes() for path in files}
        self.cli(IMPORT, source, '--export-chapters', self.chapters)
        self.assertEqual({path: path.read_bytes() for path in files}, before)

    @unittest.skipUnless(PANDOC, 'Pandoc is required to convert EPUB reader content')
    def test_reviewed_unit_selection_controls_roster_and_is_bound_to_source(self):
        source = self.root / 'source.epub'
        source_epub(source)
        args = source, '--export-chapters', self.chapters
        preview = self.cli(IMPORT, *args, '--preview')
        units = {row['title']: row['id'] for row in preview['units']}
        corrected = {'source_sha256': preview['source_sha256'], 'units': [
            {'id': units['Prologue'], 'role': 'front'},
            {'id': units['Chapter 1'], 'title': 'The sounder'},
            {'id': units['Interlude']},
            {'id': units['Chapter 2']},
            {'id': units['Epilogue'], 'merge_into': units['Chapter 2']},
            {'id': units['Notes'], 'role': 'omit'},
        ]}
        selection = self.write('corrections.json', json.dumps(corrected))
        reviewed = self.cli(IMPORT, *args, '--selection', selection, '--preview')
        self.assertFalse(self.chapters.exists(), 'corrected preview wrote manuscript files')
        self.assertEqual([u['title'] for u in reviewed['units'] if u['role'] == 'narrative'],
                         ['The sounder', 'Interlude', 'Chapter 2'])
        self.cli(IMPORT, *args, '--selection', selection)
        self.assertEqual([row['display_label'] for row in self.state('dashboard')['chapters']],
                         ['The sounder', 'Interlude', 'Chapter 2'])
        last = self.root / self.state('draft-packet', '--chapter', 'Chapter 2')['chapter_path']
        self.assertLess(last.read_text().index(UNITS['Chapter 2']), last.read_text().index(UNITS['Epilogue']))
        combined = Path(self.export('md')['output']) / 'manuscript-combined.md'
        order = ['Prologue', 'Chapter 1', 'Interlude', 'Chapter 2', 'Epilogue']
        positions = [combined.read_text().index(UNITS[label]) for label in order]
        self.assertEqual(positions, sorted(positions))
        with zipfile.ZipFile(source) as archive:
            xml = archive.read('Book/text/birds.xhtml').replace(b'Three gulls', b'Four gulls')
        changed = self.root / 'revised-source.epub'
        rewrite_archive(source, changed, {'Book/text/birds.xhtml': xml})
        fresh = self.root / 'unapproved'
        error = self.cli(IMPORT, changed, '--selection', selection, '--export-chapters', fresh,
                         code=1, json_output=False)
        self.assertIn('source', error.lower())
        self.assertFalse(fresh.exists(), 'stale approval created manuscript files')

    def test_fixed_layout_and_encrypted_inputs_explain_unsupported_preview(self):
        source = self.root / 'source.epub'
        source_epub(source)
        with zipfile.ZipFile(source) as archive:
            package = archive.read('Book/package.opf')
        fixed = package.replace(b'</metadata>', b'<meta property="rendition:layout">pre-paginated</meta></metadata>')
        encrypted = ('<encryption xmlns="urn:oasis:names:tc:opendocument:xmlns:container" '
                     'xmlns:e="http://www.w3.org/2001/04/xmlenc#"><e:EncryptedData>'
                     '<e:EncryptionMethod Algorithm="http://www.w3.org/2001/04/xmlenc#aes128-cbc"/>'
                     '<e:CipherData><e:CipherReference URI="Book/text/channel.xhtml"/></e:CipherData>'
                     '</e:EncryptedData></encryption>')
        for reason, changes in [('fixed-layout', {'Book/package.opf': fixed}),
                                ('encrypted', {'META-INF/encryption.xml': encrypted,
                                               'Book/text/channel.xhtml': b'opaque content'})]:
            with self.subTest(reason=reason):
                variant = self.root / (reason + '.epub')
                rewrite_archive(source, variant, changes)
                original = variant.read_bytes()
                args = variant, '--export-chapters', self.chapters
                report = self.cli(IMPORT, *args, '--preview')
                self.assertTrue(report['unsupported'])
                self.assertIn(reason, ' '.join(report['warnings']).lower())
                self.assertEqual(report['import']['files'], {})
                self.assertIn(reason, self.cli(IMPORT, *args, code=1, json_output=False).lower())
                self.assertFalse(self.chapters.exists())
                self.assertEqual(variant.read_bytes(), original)

    @unittest.skipUnless(PANDOC, 'Pandoc is required to convert EPUB reader content')
    def test_epub2_ncx_fragments_supply_boundaries_without_xhtml_headings(self):
        source = self.root / 'signals.epub'
        ncx_epub(source)
        args = source, '--export-chapters', self.chapters
        preview = self.cli(IMPORT, *args, '--preview')
        self.assertEqual([unit['title'] for unit in preview['units']], ['Prologue', 'Epilogue'])
        self.cli(IMPORT, *args)
        for label, other in [('Prologue', 'Epilogue'), ('Epilogue', 'Prologue')]:
            path = self.root / self.state('draft-packet', '--chapter', label)['chapter_path']
            self.assertIn(UNITS[label], path.read_text())
            self.assertNotIn(UNITS[other], path.read_text())

    @unittest.skipUnless(PANDOC, 'Pandoc is required to create real EPUB and Word files')
    def test_epub_round_trip_preserves_content_and_accessible_figure(self):
        self.intake()
        built = self.export('epub', 'docx')
        output = Path(built['output'])
        epub = output / 'manuscript-combined.epub'
        self.check_epub_metadata(epub, title='The Sounding Line', language='en')
        docs = epub_documents(epub)
        images = [(name, image) for name, doc in docs.items() for image in doc.iter(HTML + 'img')
                  if image.get('alt') == ALT]
        self.assertEqual(len(images), 1, 'figure alt text was lost or duplicated')
        name, picture = images[0]
        image_name, _ = href_target(name, picture.get('src'))
        with zipfile.ZipFile(epub) as archive:
            self.assertEqual(archive.read(image_name), PNG)
        self.assertIn(CAPTION, visible_text(docs[name]))
        tables = [t for doc in docs.values() for t in doc.iter(HTML + 'table')]
        self.assertTrue(any([visible_text(c) for c in t.iter(HTML + 'th')] == ['Station', 'Depth'] and
                            [visible_text(c) for c in t.iter(HTML + 'td')] == ['Cormorant', 'Seven fathoms']
                            for t in tables), 'table headers, cells or column order changed')
        text = '\n'.join(map(visible_text, docs.values()))
        for sentence in (*UNITS.values(), NOTE):
            self.assertEqual(text.count(sentence), 1, sentence)
        name, jump = next((name, el) for name, doc in docs.items() for el in doc.iter(HTML + 'a')
                          if visible_text(el) == 'visit the shutter')
        target, anchor = href_target(name, jump.get('href'))
        self.assertIn(UNITS['Chapter 2'], visible_text(docs[target]))
        if anchor:
            self.assertIn(anchor, {el.get('id') for el in docs[target].iter()})
        ref_name, ref = next((name, el) for name, doc in docs.items() for el in doc.iter(HTML + 'a')
                             if note_ref(el))
        target, anchor = href_target(ref_name, ref.get('href'))
        note, = (el for el in docs[target].iter() if el.get('id') == anchor)
        self.assertIn(NOTE, visible_text(note))
        with zipfile.ZipFile(output / 'manuscript-combined.docx') as archive:
            word = ET.fromstring(archive.read('word/document.xml'))
            self.assertTrue(any('Seven fathoms' in visible_text(table) for table in word.iter(WORD + 'tbl')))
            self.assertIn(PNG, [archive.read(name) for name in archive.namelist() if name.startswith('word/media/')])
        self.assertFalse(any(item['severity'] == 'error' for item in
                             self.cli(NAVIGATION, epub, '--expect', output / 'epub-navigation.json')['findings']))

    @unittest.skipUnless(PANDOC, 'Pandoc is required to build both EPUB profiles')
    def test_beta_and_publication_record_navigation_only_after_build(self):
        chapter = 'Chapters/Book-1/Chapter-001.md'
        source = self.write(chapter, '# Chapter 1\n\nThe lightship sounded a single bell.\n')
        gate = '_Edits/Book-1/Chapter-001_Gate.md'
        self.write(gate, 'PASS\nSynthetic gate for the publication converter fixture.\n')
        spec = self.write('gate.json', json.dumps({'schema_version': 1, 'paths': [chapter],
                                                  'report': gate, 'verdict': 'PASS'}))
        def record_gate():
            self.state('prepare', '--spec', spec, '--output', 'prepared.json')
            self.state('snapshot', '--spec', self.root / 'prepared.json', '--output', gate.replace('.md', '.meta.json'))

        record_gate()
        for profile in ('beta', 'publication'):
            with self.subTest(profile=profile):
                args = '--root', self.root, '--profile', profile, '--format', 'epub'
                before = self.cli(EXPORT, *args, '--check')
                self.assertEqual(before['structural_checks']['epub'], 'NOT_BUILT')
                self.assertEqual(before['epub_navigation']['status'], 'PENDING')
                out = self.chapters / 'export' / profile
                self.assertFalse(out.exists(), 'preflight published an artifact')
                built = self.cli(EXPORT, *args)
                saved = json.loads((out / 'export-manifest.json').read_text())
                self.assertEqual(saved['epub_navigation'], built['epub_navigation'])
                verified = self.cli(NAVIGATION, out / 'manuscript-combined.epub',
                                    '--expect', out / 'epub-navigation.json')
                self.assertEqual(built['epub_navigation']['status'], verified['status'])
                self.assertFalse(any(f['severity'] == 'error' for f in verified['findings']))
        published = self.chapters / 'export/publication/manuscript-combined.epub'
        last_good = published.read_bytes()
        source.write_text(source.read_text() + '\nSee [the missing berth](#vanished-berth).\n')
        record_gate()
        beta = self.export('epub')
        self.assertEqual(beta['epub_navigation']['status'], 'FAIL')
        self.assertTrue(any('vanished-berth' in warning for warning in beta['warnings']))
        failure = self.cli(EXPORT, '--root', self.root, '--profile', 'publication', '--format', 'epub',
                           code=1, json_output=False)
        self.assertIn('navigation', failure.lower())
        self.assertIn('vanished-berth', failure)
        self.assertEqual(published.read_bytes(), last_good)

    @unittest.skipUnless(PANDOC, 'Pandoc is required for the navigation acceptance test')
    def test_navigation_checks_destinations_and_optional_note_returns(self):
        self.write('Chapters/Book-1/Chapter-001.md',
                   '# Chapter 1\n\nShe rang the [bronze bell](#listening-post). '
                   'A low tone.[^first]\n\n[^first]: Notes about the first tone.\n')
        self.write('Chapters/Book-1/Chapter-002.md',
                   '# Chapter 2\n\n## Listening post {#listening-post}\n\n'
                   'Another tone.[^second]\n\n[^second]: Notes about the second tone.\n')
        output = Path(self.export('epub')['output'])
        epub = output / 'manuscript-combined.epub'
        expected = output / 'epub-navigation.json'
        clean = self.cli(NAVIGATION, epub, '--expect', expected)
        self.assertFalse(any(f['severity'] == 'error' for f in clean['findings']), clean)

        def verify_mutation(label, doc_name, doc, *, advisory=False):
            copy = self.root / (label + '.epub')
            rewrite_archive(epub, copy, {doc_name: ET.tostring(doc)})
            report = self.cli(NAVIGATION, copy, '--expect', expected, code=0 if advisory else 1)
            if advisory:
                self.assertTrue(any(f['severity'] == 'advisory' and
                                    any(word in str(f).lower() for word in ('return', 'backlink', 'back-link'))
                                    for f in report['findings']), report)
            else:
                self.assertTrue(any(f['severity'] == 'error' for f in report['findings']), report)

        docs = epub_documents(epub)
        name, toc = next((name, el) for name, doc in docs.items() for el in doc.iter(HTML + 'nav')
                         if 'toc' in el.get(EPUB + 'type', '').split())
        chapters = {visible_text(a): a for a in toc.iter(HTML + 'a')}
        chapters['Chapter 1'].set('href', chapters['Chapter 2'].get('href'))
        verify_mutation('wrong-existing-toc', name, docs[name])

        docs = epub_documents(epub)
        name, bell = next((name, a) for name, doc in docs.items() for a in doc.iter(HTML + 'a')
                          if visible_text(a) == 'bronze bell')
        ref = next(a for a in docs[name].iter(HTML + 'a') if note_ref(a))
        bell.set('href', ref.get('href'))
        verify_mutation('wrong-existing-link', name, docs[name])

        docs = epub_documents(epub)
        refs = [(name, a) for name, doc in docs.items() for a in doc.iter(HTML + 'a') if note_ref(a)]
        self.assertEqual(len(refs), 2)
        (name, first), (other_name, second) = refs
        note_name, note_anchor = href_target(name, first.get('href'))
        other_note, other_anchor = href_target(other_name, second.get('href'))
        first.set('href', posixpath.relpath(other_note, posixpath.dirname(name)) + '#' + other_anchor)
        verify_mutation('wrong-existing-note', name, docs[name])
        first.set('href', '#missing-note-fragment')
        verify_mutation('missing-fragment', name, docs[name])
        first.set('href', 'no-such-book-section.xhtml#missing')
        verify_mutation('missing-file', name, docs[name])

        docs = epub_documents(epub)
        note = next(el for el in docs[note_name].iter() if el.get('id') == note_anchor)
        for parent in note.iter():
            for child in list(parent):
                if child.tag == HTML + 'a' and backlink(child):
                    parent.remove(child)
        verify_mutation('absent-optional-return', note_name, docs[note_name], advisory=True)
        return_href = posixpath.relpath(other_name, posixpath.dirname(note_name)) + '#' + second.get('id')
        ET.SubElement(note, HTML + 'a', {'href': return_href, 'role': 'doc-backlink'}).text = 'Return'
        verify_mutation('wrong-existing-return', note_name, docs[note_name])

    @unittest.skipUnless(PANDOC, 'Pandoc is required for the two-edition reader exchange')
    def test_two_reader_reread_and_native_word_comment_target_saved_revision(self):
        first = self.write('Chapters/Book-1/Chapter-001.md',
                           '# Chapter 1\n\nThe watchman lifted the red flag.\n\nA brass dial spun.\n\n'
                           '<!-- STORYCRAFT: Coordinators know the watchman secretly owns the dial. -->\n\n'
                           '* * *\n\nThe cartographer unfolded the map.\n\nThe copper coast was missing.\n\n'
                           '* * *\n\nThe sleepy gull settled on the crane.\n')
        second = self.write('Chapters/Book-1/Chapter-002.md',
                            '# Chapter 2\n\nThe inspector unlocked the boathouse.\n\n'
                            'She laid the chart on a rowboat.\n')
        old = self.export('epub', 'docx')['beta_feedback']['export_id']
        readers = [('Inez', 'The watchman lifted the red flag.', 'Why would the watchman signal alone?'),
                   ('Pavel', 'The cartographer unfolded the map.', 'Who surveyed the copper coast?')]
        for reader, quote, comment in readers:
            notes = self.write(reader + '.json', json.dumps({'schema_version': 1, 'reader': reader,
                               'notes': [{'quote': quote, 'comment': comment}]}))
            feedback = self.cli(BETA, '--root', self.root, '--export', old, '--notes', notes)
            self.assertEqual(feedback['feedback'][-1]['location']['status'], 'ANCHORED')
        revised = 'Two watchmen raised the yellow flag.'
        survey = 'The cartographer unfolded a damp survey.'
        boat = 'The inspector opened the chart room.'
        first.write_text(first.read_text().replace(readers[0][1], revised).replace(readers[1][1], survey))
        second.write_text(second.read_text().replace('The inspector unlocked the boathouse.', boat))
        target_hash = hashlib.sha256(first.read_bytes()).hexdigest()
        config = self.write('revision.json', json.dumps({'schema_version': 1, 'language': 'en-GB',
                                                        'title': 'The Watchmen'}))
        target = self.cli(EXPORT, '--root', self.root, '--profile', 'beta', '--config', config,
                          '--format', 'epub', '--format', 'docx')
        new = target['beta_feedback']['export_id']
        self.assertNotEqual(old, new)
        live = 'On the next draft the watchmen struck the flag.'
        first.write_text(first.read_text().replace(revised, live))
        self.write('_Edits/Book-1/private-memo.md', 'Coordinator-only note about the tide book.')

        packets = {}
        for reader, _, comment in readers:
            outcome = self.cli(BETA, '--root', self.root, '--export', old, '--reread-to', new,
                               '--reader', reader)
            self.assertEqual(outcome['target_edition'], new)
            folder = Path(outcome['output'])
            packets[reader] = folder
            for name in ('reread.docx', 'reread.epub'):
                with self.subTest(reader=reader, format=name):
                    if name == 'reread.epub':
                        self.check_epub_metadata(folder / name, language='en-GB')
                    body = package_text(folder / name)
                    for required in (comment, revised, survey, boat):
                        self.assertIn(required, body, name)
                    for other_reader, _, other_note in readers:
                        if other_reader != reader:
                            self.assertNotIn(other_reader, body, name)
                            self.assertNotIn(other_note, body, name)
                    for excluded in ('The sleepy gull settled on the crane.', live,
                                     'Coordinators know the watchman secretly owns the dial.',
                                     'Coordinator-only note about the tide book.'):
                        self.assertNotIn(excluded, body, name)
        self.assertNotEqual(packets['Inez'], packets['Pavel'])
        returned = self.root / 'returned.docx'
        reaction = 'The second watchman makes the signal clear.'
        selection_comment(packets['Inez'] / 'reread.docx', returned, revised, 'Inez', reaction)
        result = self.cli(BETA, '--root', self.root, '--docx', returned)
        self.assertEqual(result['export_id'], new)
        note, = (item for item in result['feedback'] if item['comment'] == reaction)
        self.assertEqual((note['export_id'], note['reader'], note['quote']), (new, 'Inez', revised))
        self.assertEqual(note['location']['status'], 'ANCHORED')
        self.assertEqual(note['location']['path'], 'Chapters/Book-1/Chapter-001.md')
        self.assertEqual(note['location']['source_sha256'], target_hash)
        self.assertEqual(self.cli(BETA, '--root', self.root, '--docx', returned)['added'], 0)
        saved = self.cli(BETA, '--root', self.root, '--export', new)['feedback']
        self.assertIn(note, saved)
        archived = self.cli(BETA, '--root', self.root, '--export', old)['feedback']
        self.assertEqual([item['comment'] for item in archived], [row[2] for row in readers])


if __name__ == '__main__':
    unittest.main(verbosity=2)
