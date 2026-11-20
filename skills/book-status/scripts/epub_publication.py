"""Read EPUB package order, navigation and local resources without extracting the ZIP."""
from collections import defaultdict
from pathlib import PurePosixPath
import posixpath
import re
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET
import zipfile

EPUB = '{http://www.idpf.org/2007/ops}'
XHTML = '{http://www.w3.org/1999/xhtml}'


def local(tag):
    return tag.rsplit('}', 1)[-1]


def words(element):
    return ' '.join(''.join(element.itertext()).split())


def roles(element):
    return set((element.get(EPUB + 'type', '') + ' ' + element.get('role', '') +
                ' ' + element.get('class', '')).split())


def resolve(source, href):
    uri = urlsplit(href)
    if uri.scheme or uri.netloc:
        return None
    name = unquote(uri.path)
    if '\\' in name or name.startswith('/') or '\x00' in name:
        raise ValueError(f'invalid EPUB member reference in {source}: {href}')
    path = posixpath.normpath(posixpath.join(posixpath.dirname(source), name)) if name else source
    if path == '..' or path.startswith('../'):
        raise ValueError(f'EPUB reference leaves package: {href}')
    return path, unquote(uri.fragment)


class Publication:
    def __init__(self, archive):
        self.archive = archive
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('duplicate ZIP member in EPUB')
        self.members = set(names)
        self.cache = {}
        if archive.read('mimetype') != b'application/epub+zip':
            raise ValueError('invalid EPUB mimetype')
        container = self.xml('META-INF/container.xml')
        root = container.find('.//{*}rootfile')
        if root is None:
            raise ValueError('missing EPUB rootfile')
        self.opf = root.attrib['full-path']
        self.package = self.xml(self.opf)
        self.items = {}
        for item in self.package.findall('./{*}manifest/{*}item'):
            target = resolve(self.opf, item.attrib['href'])
            if target:
                self.items[item.attrib['id']] = (target[0], item.get('media-type', ''), item.get('properties','').split())
        spine = self.package.find('{*}spine')
        if spine is None:
            raise ValueError('missing EPUB spine')
        self.spine = [(self.items[i.attrib['idref']][0], i) for i in spine.findall('{*}itemref')]
        self.nav = next((path for path, _, props in self.items.values() if 'nav' in props), None)
        self.ncx = self.items.get(spine.get('toc'), (None,))[0] or next(
            (path for path, media, _ in self.items.values() if media == 'application/x-dtbncx+xml'), None)
        self.toc_sources = {}
        if self.nav:
            toc = next((n for n in self.xml(self.nav).iter() if local(n.tag) == 'nav' and
                        roles(n) & {'toc', 'doc-toc'}), None)
            if toc is not None:
                self.toc_sources[self.nav] = [(words(n), n.get('href')) for n in toc.iter()
                                               if local(n.tag) == 'a' and n.get('href')]
        if self.ncx:
            toc = self.xml(self.ncx).find('.//{*}navMap')
            if toc is not None:
                self.toc_sources[self.ncx] = [(words(n.find('{*}navLabel')), n.find('{*}content').attrib['src'])
                                              for n in toc.iterfind('.//{*}navPoint')]
        self.nav_entries = defaultdict(list)
        for source, links in list(self.toc_sources.items())[:1]:
            for label, href in links:
                target = resolve(source, href)
                if target:
                    self.nav_entries[target[0]].append((target[1], label))

    def xml(self, path):
        if path not in self.cache:
            if path not in self.members:
                raise ValueError('missing EPUB member: ' + path)
            try:
                self.cache[path] = ET.fromstring(self.archive.read(path))
            except ET.ParseError as exc:
                raise ValueError(f'cannot parse EPUB member {path}: {exc}') from exc
        return self.cache[path]

    def documents(self):
        for path, media, _ in self.items.values():
            if media in ('application/xhtml+xml', 'text/html'):
                yield path, self.xml(path)
