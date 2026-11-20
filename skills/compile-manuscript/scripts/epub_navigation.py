#!/usr/bin/env python3
"""Follow contents, internal links, notes and returns inside a built EPUB."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sys
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[2] / 'book-status/scripts'))
from epub_publication import Publication, local, resolve, roles, words

NOTES = {'footnote','endnote','doc-footnote','doc-endnote'}
REFS = {'noteref','doc-noteref','footnote-ref'}
RETURNS = {'backlink','doc-backlink','footnote-back'}


def audit(path, expected=None, source_links=None):
    findings, observed = [], []
    def issue(kind, source, message, severity='error'):
        findings.append({'severity':severity,'kind':kind,'source':source,'message':message})
    with zipfile.ZipFile(path) as z:
        pub = Publication(z)
        docs = dict(pub.documents())
        ids = {}
        for name,doc in docs.items():
            anchored = [node for node in doc.iter() if node.get('id')]
            ids[name] = {n.get('id'):n for n in anchored}
            if len(anchored) != len(ids[name]):
                issue('fragment',name,'duplicate fragment identifier')
        def target(source,href):
            try:
                dest = resolve(source,href)
            except ValueError as error:
                issue('link',source,str(error))
                return None
            if dest is None:
                return None
            name,frag = dest
            if name not in pub.members or (frag and name in docs and frag not in ids[name]):
                issue('link',source,'missing destination ' + href)
                return None
            return dest
        if not pub.toc_sources:
            issue('contents',pub.opf,'no readable EPUB contents navigation')
        for source, links in pub.toc_sources.items():
            for label,href in links:
                dest = target(source,href)
                if dest is None:
                    if resolve(source,href) is None:
                        issue('contents',source,'external contents destination ' + href)
                    continue
                name,frag = dest
                observed.append({'kind':'contents','source':source,'label':label,'target':list(dest)})
                element = ids.get(name,{}).get(frag) if frag else docs.get(name)
                if element is None:
                    issue('contents',source,'contents entry does not land in reading text: ' + label)
                    continue
                heading = next((words(h) for h in element.iter() if local(h.tag) in
                                ('h1','h2','h3','h4','h5','h6')),None)
                if heading and heading.casefold() != label.casefold():
                    # Named navigation sections and title pages have semantic labels of their own.
                    semantic = {r for n in element.iter() for r in roles(n)}
                    special = (label.casefold() in ('title page','title') and 'titlepage' in semantic or
                               label.casefold() in ('contents','table of contents') and 'toc' in semantic)
                    candidates = {words(n).casefold() for doc in docs.values() for n in doc.iter()
                                  if re.fullmatch('h[1-6]',local(n.tag))}
                    if not special and label.casefold() in candidates:
                        issue('contents',source,f'{label} lands on {heading} at {href}')
        refs = defaultdict(set)
        backlinks = defaultdict(list)
        for source, doc in docs.items():
            parents = {c:p for p in doc.iter() for c in p}
            for a in doc.iter():
                if local(a.tag) != 'a' or not a.get('href'):
                    continue
                dest = target(source,a.get('href'))
                if dest is None:
                    continue
                decl = roles(a)
                if decl & RETURNS:
                    node = a
                    while node in parents and not roles(node) & NOTES:
                        node = parents[node]
                    backlinks[(source,node.get('id',''))].append(dest)
                    continue
                kind = 'note' if decl & REFS else 'link'
                if source == pub.nav and kind=='link':
                    continue
                label = words(a)
                observed.append({'kind':kind,'source':source,'label':label,'target':list(dest)})
                if kind == 'note':
                    refs[dest].add((source,a.get('id','')))
                    node = ids.get(dest[0],{}).get(dest[1])
                    if node is None or not roles(node) & NOTES:
                        issue('note',source,'reference does not land on a note: ' + a.get('href'))
                    num = re.fullmatch(r'fnref(\d+)',a.get('id',''))
                    if num and re.fullmatch(r'fn\d+',dest[1]) and dest[1] != 'fn'+num[1]:
                        issue('note',source,'reference lands on another numbered note')
        for dest, sources in refs.items():
            if not backlinks.get(dest):
                issue('note return',dest[0]+'#'+dest[1],'optional note return link is absent','advisory')
        for dest, returns in backlinks.items():
            for back in returns:
                if back not in refs.get(dest,set()):
                    issue('note return',dest[0]+'#'+dest[1],'return leads to a different reading location')
        if source_links:
            # Compare the reader's source Markdown destinations with the converter's emitted links.
            # This also catches converters that drop an internal fragment while splitting XHTML.
            required = Counter(tuple(v) for v in source_links)
            actual = Counter((item['label'],item['target'][1]) for item in observed if item['kind']=='link')
            for (label, fragment), count in (required-actual).items():
                issue('source link',path.name,f'{count} link(s) labelled {label!r} should reach #{fragment}')
    if expected is not None:
        if expected.get('schema_version') != 1:
            raise ValueError('unsupported EPUB navigation expectation')
        for original, new in [(expected['links'],observed)]:
            if original != new:
                for i in range(max(len(original),len(new))):
                    prior = original[i] if i<len(original) else None
                    now = new[i] if i<len(new) else None
                    if prior != now:
                        record = prior or now
                        issue(record['kind'],record['source'],f'destination changed for {record["label"]!r}: expected {prior}, found {now}')
                        if len(findings)>=100:
                            break
    return {'schema_version':1,'links':observed}, {
        'status':'FAIL' if any(f['severity']=='error' for f in findings) else 'PASS','findings':findings}


def markdown_links(pandoc, text):
    import subprocess
    proc = subprocess.run([pandoc,'-f','markdown','-t','json'],input=text,text=True,capture_output=True,check=True)
    links = []
    def inline_text(node):
        if isinstance(node,list):
            return ''.join(map(inline_text,node))
        if not isinstance(node,dict):
            return ''
        if node['t'] in ('Space','SoftBreak','LineBreak'):
            return ' '
        if node['t']=='Str':
            return node['c']
        if node['t']=='Code':
            return node['c'][-1]
        return inline_text(node.get('c',[]))
    def visit(node):
        if isinstance(node,dict):
            if node.get('t')=='Link' and node['c'][2][0].startswith('#'):
                label = inline_text(node['c'][1])
                links.append((label,node['c'][2][0][1:]))
            visit(node.get('c',[]))
        elif isinstance(node,list):
            for child in node:
                visit(child)
    visit(json.loads(proc.stdout)['blocks'])
    return links


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('epub',type=Path)
    p.add_argument('--expect',type=Path)
    args = p.parse_args()
    expected = json.loads(args.expect.read_text()) if args.expect else None
    try:
        _,report = audit(args.epub,expected)
    except (ValueError,KeyError,zipfile.BadZipFile) as e:
        report = {'status':'FAIL','findings':[{'severity':'error','kind':'package','message':str(e)}]}
    print(json.dumps(report,indent=2))
    return int(report['status']=='FAIL')


if __name__=='__main__':
    sys.exit(main())
