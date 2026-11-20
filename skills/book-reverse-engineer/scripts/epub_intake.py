"""Preview reflowable EPUB reading units and convert their reader content to Markdown."""
from collections import defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
from xml.etree import ElementTree as ET
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'book-status/scripts'))
from epub_publication import Publication, local, resolve, roles, words


def anchor(path, fragment):
    return 'sc-' + hashlib.sha256((path + '#' + fragment).encode()).hexdigest()[:18]


def markdown(element):
    if not shutil.which('pandoc'):
        raise ValueError('Pandoc is required to convert reflowable EPUB content to Markdown')
    result = subprocess.run(['pandoc', '-f', 'html', '-t', 'markdown', '--wrap=none'],
                            input=ET.tostring(element, encoding='unicode'), capture_output=True, text=True)
    if result.returncode:
        raise ValueError('EPUB conversion failed: ' + result.stderr.strip())
    return result.stdout.strip()


def limitations(z):
    reasons = []
    if any(item.flag_bits & 1 for item in z.infolist()):
        return ['encrypted EPUB archive requires a readable source']
    if 'META-INF/encryption.xml' in z.namelist():
        xml = ET.fromstring(z.read('META-INF/encryption.xml'))
        for data in xml.findall('.//{*}EncryptedData'):
            method = data.find('.//{*}EncryptionMethod')
            if method is None or method.get('Algorithm') not in {
                    'http://www.idpf.org/2008/embedding', 'http://ns.adobe.com/pdf/enc#RC'}:
                reasons.append('encrypted publication content requires a readable source')
                break
    return reasons


def fragments(body, boundaries):
    """Clone ancestor wrappers for each range, including mixed text and tails."""
    parts = defaultdict(lambda: ET.Element('div'))
    active = [0]
    def append_text(parent, value):
        if value:
            if len(parent):
                parent[-1].tail = (parent[-1].tail or '') + value
            else:
                parent.text = (parent.text or '') + value
    def visit(node, parent_for):
        if node in boundaries:
            active[0] = boundaries[node]
        copies = {}
        def copy_for(number):
            if number not in copies:
                attrs = dict(node.attrib)
                if copies:
                    attrs.pop('id', None)
                copies[number] = ET.SubElement(parent_for(number), node.tag, attrs)
            return copies[number]
        opening = active[0]
        append_text(copy_for(opening), node.text)
        for child in node:
            visit(child, copy_for)
        append_text(parent_for(active[0]), node.tail)
    for child in body:
        visit(child, lambda n: parts[n])
    if body.text and body.text.strip():
        parts[0].text = body.text
    return parts


def classify(title, types):
    if types & {'toc','page-list','landmarks'}:
        return 'navigation'
    if types & {'endnotes','footnotes','backmatter','bibliography','index','acknowledgments','colophon'} or re.fullmatch(
            r'(?:end ?notes|notes|bibliography|acknowledg[e]?ments|index|colophon)', title, re.I):
        return 'back'
    if types & {'prologue','epilogue','chapter','bodymatter','interlude','part'} or re.match(
            r'^(prologue|epilogue|chapter|interlude|part)\b', title, re.I):
        return 'narrative'
    if types & {'frontmatter','titlepage','cover','dedication','copyright-page','preface','foreword','halftitlepage'} or re.fullmatch(
            r'(?:cover|title page|copyright|dedication|preface|foreword)', title, re.I):
        return 'front'
    return 'narrative'


def convert(pub):
    resources = {}
    notes = {}
    docs = dict(pub.documents())
    for path, doc in docs.items():
        for node in doc.iter():
            if node.get('id') and roles(node) & {'footnote','endnote','doc-footnote','doc-endnote'}:
                notes[(path, node.get('id'))] = node
    used_notes = set()
    for path, doc in docs.items():
        for node in doc.iter():
            if local(node.tag) == 'a' and node.get('href') and roles(node) & {'noteref','doc-noteref'}:
                target = resolve(path, node.get('href'))
                if target in notes:
                    used_notes.add(target)

    def prepare(node, path, definitions, inside_note=False):
        decl = roles(node)
        node.tag = local(node.tag)
        original = node.get('id')
        attrs = {local(k): v for k, v in node.attrib.items() if local(k) in
                 ('href','src','alt','title','colspan','rowspan','start','lang','id','class')}
        node.attrib = attrs
        if original:
            node.set('id', anchor(path, original))
        if (path, original) in used_notes and not inside_note or inside_note and decl & {'backlink','doc-backlink'}:
            node.clear()
            node.tag = 'span'
            return
        if decl & {'scene-break','scenebreak'}:
            node.clear()
            node.tag = 'hr'
            return
        if node.tag in ('script','style'):
            node.clear()
            node.tag = 'span'
            return
        if node.tag == 'a' and attrs.get('href'):
            target = resolve(path, attrs['href'])
            if target in used_notes and decl & {'noteref','doc-noteref'}:
                key = anchor(*target)
                body = deepcopy(notes[target])
                prepare(body, target[0], {}, True)
                body.tag = 'div'
                body.attrib.clear()
                definitions[key] = markdown(body)
                node.tag = 'span'
                node.attrib.clear()
                node[:] = []
                node.text = 'SCNOTE' + key[3:].upper() + 'END'
            elif target and target[0] in docs:
                node.set('href', '#' + anchor(*target))
        if node.tag == 'img' and attrs.get('src'):
            target = resolve(path, attrs['src'])
            if target is None or target[0] not in pub.members:
                raise ValueError(f'illustration is unavailable in EPUB: {attrs["src"]}')
            data = pub.archive.read(target[0])
            ext = PurePosixPath(target[0]).suffix.lower()
            if not re.fullmatch(r'\.[a-z0-9]{1,8}', ext):
                raise ValueError(f'unsupported illustration filename: {target[0]}')
            name = 'epub-' + hashlib.sha256(data).hexdigest() + ext
            resources[name] = data
            node.set('src', name)
        for child in node:
            tail = child.tail
            prepare(child, path, definitions, inside_note)
            child.tail = tail

    records = []
    for path, item in pub.spine:
        if path not in docs:
            raise ValueError('unsupported non-XHTML spine item: ' + path)
        body = docs[path].find('.//{*}body')
        if body is None:
            raise ValueError('missing XHTML body: ' + path)
        entries = dict(pub.nav_entries.get(path, []))
        nodes = list(body.iter())
        starts = {n: (n.get('id'), entries[n.get('id')]) for n in nodes if n.get('id') in entries}
        if not starts:
            for idx, node in enumerate(n for n in nodes if local(n.tag) == 'h1'):
                starts[node] = (node.get('id', 'heading-' + str(idx + 1)), words(node))
        title_node = docs[path].find('.//{*}title')
        fallback = entries.get('') or (words(title_node) if title_node is not None else PurePosixPath(path).stem)
        body_entry = starts.pop(body, None)
        if body_entry:
            fallback = body_entry[1]
        boundaries = {node: i for i, node in enumerate(starts, 1)}
        sections = fragments(body, boundaries)
        names = {index: (frag, title, roles(node)) for node,(frag,title) in starts.items()
                 for index in [boundaries[node]]}
        visible = [i for i,v in sections.items() if words(v) or any(local(n.tag) in ('img','image','hr') for n in v.iter())]
        for index, segment in sorted(sections.items()):
            if not words(segment) and not any(local(n.tag) in ('img','image','hr') for n in segment.iter()):
                continue
            frag, title, kind = names.get(index, (body_entry[0] if body_entry else '', fallback, roles(body)))
            tags = kind or roles(body) or next((roles(n) for n in segment.iter() if roles(n)),set())
            role = 'navigation' if path == pub.nav else classify(title, tags)
            if item.get('linear') == 'no' and role == 'narrative':
                role = 'back'
            definitions = {}
            prepare(segment, path, definitions)
            # Put the unit heading first. Keep source anchors at this landing point.
            ids = []
            first = next((n for n in segment.iter() if n.tag in ('h1','h2','h3')),None)
            if first is not None and words(first).casefold() == title.casefold():
                if first.get('id'):
                    ids.append(first.get('id'))
                first.clear()
                first.tag = 'span'
            for node in segment.iter():
                if node.tag in ('body','section','article','div'):
                    node.tag = 'div'
                    if node.get('id') == anchor(path, frag):
                        ids.append(node.attrib.pop('id'))
            if index == min(visible):
                ids.append(anchor(path, ''))
            ids.append(anchor(path, frag))
            content = re.sub(r'(?m)^-{5,}$', '* * *', markdown(segment))
            for key, value in definitions.items():
                content = content.replace('SCNOTE' + key[3:].upper() + 'END', '[^' + key + ']')
                content += '\n\n[^' + key + ']: ' + value.replace('\n', '\n    ')
            marks = ''.join('[]{#' + name + '}' for name in dict.fromkeys(ids))
            records.append({'id':anchor(path,frag), 'source':path,'fragment':frag,'title':title,
                            'role':role,'content':marks + '\n\n' + content})
    return records, resources


ROLES = {'front', 'narrative', 'back', 'navigation', 'omit'}


def split_reviewed(record, cuts):
    """Split only at a uniquely quoted reader paragraph in the reviewed unit."""
    content = record['content']
    pieces = []
    start = 0
    part = record
    for cut in cuts:
        quote = cut.get('quote', '').strip()
        title = cut.get('title', '').strip()
        role = cut.get('role', record['role'])
        index = content.find(quote)
        if not title or role not in ROLES or not quote or index < 0 or index != content.rfind(quote):
            raise ValueError('each EPUB split needs a title, a valid role and a unique source quote')
        # Split at the start of the quoted paragraph, keeping any preceding text on the correct side.
        separator = content.rfind('\n\n', 0, index)
        boundary = separator + 2 if separator >= 0 else 0
        earlier = content[start:boundary].strip()
        if boundary <= start or not re.sub(r'\[\]\{#[^}]+\}', '', earlier).strip():
            raise ValueError('EPUB split would create an empty or out-of-order reading unit')
        pieces.append(dict(part, content=earlier))
        fragment = record['fragment'] + ':split:' + quote
        part = dict(record, id=anchor(record['source'], fragment), title=title, role=role,
                    fragment=record['fragment'], split_quote=quote)
        start = boundary
    pieces.append(dict(part,content=content[start:].strip()))
    return pieces


def analyze(path, selection=None):
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    metadata = {}
    with zipfile.ZipFile(path) as z:
        issues = limitations(z)
        if not issues:
            pub = Publication(z)
            for field in ('title','language'):
                node = pub.package.find('{*}metadata/{*}' + field)
                if node is not None and words(node):
                    metadata[field] = words(node)
            if any((n.get('property') == 'rendition:layout' and words(n) == 'pre-paginated') or
                   (n.get('name') == 'fixed-layout' and n.get('content','').lower()=='true')
                   for n in pub.package.iter()) or any('rendition:layout-pre-paginated' in
                   item.get('properties','').split() for _, item in pub.spine):
                issues.append('fixed-layout EPUB requires an author-reviewed text source')
        records, resources = ([], {}) if issues else convert(pub)
    if selection:
        selected = json.loads(Path(selection).read_text())
        if selected.get('source_sha256') != sha:
            raise ValueError('EPUB selection refers to a different source revision')
        changes = selected['units']
        if len(changes) != len(records) or {c['id'] for c in changes} != {r['id'] for r in records}:
            raise ValueError('selection must list each preview unit exactly once')
        by_id = {r['id']: r for r in records}
        edited = []
        for choice in changes:
            record = dict(by_id[choice['id']])
            record.update({k:choice[k] for k in ('title','role') if k in choice})
            if record['role'] not in ROLES or not record['title'].strip():
                raise ValueError('invalid reading unit title or role')
            join = choice.get('merge_into')
            if join:
                if choice.get('split_before'):
                    raise ValueError('use either merge_into or split_before on a reviewed unit')
                if not edited or edited[-1]['id'] != join:
                    raise ValueError('merge_into must name the preceding retained unit')
                edited[-1]['content'] += '\n\n' + record['content']
            else:
                edited.extend(split_reviewed(record,choice.get('split_before',[])))
        records = edited
    files, units = {}, []
    for r in records:
        filename = 'Unit-' + r['id'][3:] + '.md'
        content = '# ' + r['title'] + '\n\n' + r['content'].strip() + '\n'
        units.append({k:v for k,v in r.items() if k != 'content'} | {'filename':filename,'word_count':len(content.split())})
        if r['role'] not in ('omit','navigation'):
            files[filename] = content
    for name, data in resources.items():
        if any(name in value for value in files.values() if isinstance(value, str)):
            files[name] = data
    return {'source':str(path), 'source_sha256':sha,'mode':'epub','units':units,'unit_count':len(units),
            'total_words':sum(u['word_count'] for u in units),'warnings':issues,'unsupported':bool(issues),
            '_files':files,'metadata':metadata, '_registration':{'units':units, 'source_sha256':sha, **metadata}}
