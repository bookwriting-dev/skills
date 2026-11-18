"""Build the archived passage map and Word bookmarks for a Storycraft beta export."""
import hashlib
import json
import re
import secrets
import subprocess
from xml.etree import ElementTree as ET
import zipfile


WORD = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def normal(text):
    return ' '.join(text.split())


def bookmark_name(node):
    # Pandoc prepends an underscore to document bookmark names.
    return node.get(WORD + 'name', '').lstrip('_')


def paragraph_text(paragraph):
    pieces = []
    for node in paragraph.iter():
        if node.tag == WORD + 't' and node.text:
            pieces.append(node.text)
        elif node.tag in (WORD + 'tab', WORD + 'br', WORD + 'cr'):
            pieces.append(' ')
    return normal(''.join(pieces))


def build_map(parts, chapter_records, source_hashes):
    sections = []
    passages = {}
    for path, text in parts:
        chapter = chapter_records.get(path, {})
        identifier = 'scu' + sha256(path.encode())[:18]
        sections.append({'bookmark': identifier, 'chapter_id': chapter.get('id'),
                         'label': chapter.get('display_label', path), 'path': path,
                         'source_sha256': source_hashes[path], 'reader_text': text})
        for index, paragraph in enumerate(re.split(r'\n[ \t]*\n', text)):
            if paragraph.strip():
                anchor = 'scm' + sha256(f'{identifier}:{index}'.encode())[:20]
                passages[anchor] = {'section': identifier, 'text': normal(paragraph)}
    return {'schema_version': 1, 'export_id': secrets.token_hex(12), 'sections': sections,
            'word_passages': {}, 'text_passages': passages}


def docx_input(pandoc, stage, exchange):
    """Use Pandoc's native Div and Span bookmarks, keeping reader text and style intact."""
    sections = exchange['sections']
    colon_width = max((len(run) for section in sections for run in
                       re.findall(r'^ {0,3}(:{3,})', section['reader_text'], re.M)), default=2) + 1
    inner = ':' * colon_width
    outer = ':' * (colon_width + 1)
    source = f'{outer} {{#sc_export_{exchange["export_id"]}}}\n\n'
    source += '\n'.join(f'{inner} {{#{section["bookmark"]}}}\n\n{section["reader_text"]}\n{inner}\n'
                        for section in sections)
    source += f'\n{outer}\n'
    result = subprocess.run([pandoc, '--from=markdown', '--to=json'], input=source,
                            text=True, capture_output=True, check=True)
    document = json.loads(result.stdout)
    section_ids = {section['bookmark'] for section in sections}
    visited = set()
    passages = exchange['word_passages']

    def visit(node, section_id=None):
        if isinstance(node, list):
            for child in node:
                visit(child, section_id)
        elif isinstance(node, dict) and 'c' in node:
            content = node['c']
            tag = node.get('t')
            if tag == 'Div' and content[0][0] in section_ids:
                section_id = content[0][0]
                visited.add(section_id)
            if section_id and tag in ('Para', 'Plain', 'Header'):
                inlines = content[2] if tag == 'Header' else content
                anchor = 'scp' + sha256(f'{section_id}:{len(passages)}'.encode())[:20]
                inlines.insert(0, {'t': 'Span', 'c': [[anchor, [], []], []]})
                passages[anchor] = {'section': section_id}
            visit(content, section_id)

    visit(document['blocks'])
    if visited != section_ids:
        raise ValueError('some beta manuscript sections could not be mapped to Word bookmarks')
    path = stage / 'beta-pandoc.json'
    path.write_text(json.dumps(document, ensure_ascii=False), encoding='utf-8')
    return path


def bind_word_passages(path, exchange):
    with zipfile.ZipFile(path) as archive:
        document = ET.fromstring(archive.read('word/document.xml'))
    found = {bookmark_name(node) for node in document.iter(WORD + 'bookmarkStart')}
    if 'sc_export_' + exchange['export_id'] not in found:
        raise ValueError('beta DOCX is missing its export bookmark')
    passages = exchange['word_passages']
    rendered = {}
    for paragraph in document.iter(WORD + 'p'):
        text = paragraph_text(paragraph)
        for node in paragraph.iter(WORD + 'bookmarkStart'):
            name = bookmark_name(node)
            if name in passages:
                rendered[name] = {**passages[name], 'text': text}
    if passages and not rendered:
        raise ValueError('beta DOCX is missing its passage bookmarks')
    # Pandoc can omit empty spans belonging to structural table/list positions.
    exchange['word_passages'] = rendered
