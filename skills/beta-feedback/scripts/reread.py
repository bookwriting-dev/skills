"""Make a reader-specific packet from two archived beta editions."""
from collections import defaultdict
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import beta_exchange
import editions
import epub_navigation
import feedback_scope
import project_state as state


def quote_block(text):
    width = max([3] + [len(r)+1 for r in re.findall(r'(?m)^~+',text)])
    return '~'*width + '\n' + text + '\n' + '~'*width


def note_scene(note, sections):
    place = note.get('location',{})
    if place.get('status') != 'ANCHORED':
        return None
    evidence = note.get('quote') or place.get('anchor_text','')
    if not evidence.strip():
        return None
    found = []
    for s in sections:
        if s['path'] != place.get('path'):
            continue
        for i,sc in enumerate(s['scenes']):
            sample = s['reader_text'][sc['start']:sc['end']]
            if beta_exchange.normal(evidence) in beta_exchange.normal(sample):
                found.append((editions.section_id(s),i))
    return found[0] if len(found)==1 else None


def pandoc_document(pandoc, text):
    result = subprocess.run([pandoc,'-f','markdown','-t','json'],input=text,text=True,
                            capture_output=True,check=True)
    return json.loads(result.stdout)


def ast_nodes(value):
    if isinstance(value,dict):
        if 't' in value:
            yield value
        yield from ast_nodes(value.get('c',[]))
    elif isinstance(value,list):
        for child in value:
            yield from ast_nodes(child)


def anchors(document):
    ids = set()
    for node in ast_nodes(document['blocks']):
        content = node.get('c')
        if node['t']=='Header':
            attrs = content[1]
        elif node['t'] in {'Span','Div','Table','Code','CodeBlock','Figure','Image','Link'}:
            attrs = content[0]
        else:
            continue
        if isinstance(attrs,list) and attrs and isinstance(attrs[0],str) and attrs[0]:
            ids.add(attrs[0])
    return ids


def omitted_destinations(pandoc, excerpt, target):
    requested = {fragment for _,fragment in epub_navigation.source_links(excerpt)}
    missing = requested - anchors(excerpt)
    if not missing:
        return {}
    # Check the frozen full book before telling a reader that an omitted target exists.
    full = pandoc_document(pandoc,'\n\n'.join(s['reader_text'] for s in target['sections']))
    missing &= anchors(full)
    labels = defaultdict(list)
    for section in target['sections']:
        if not missing:
            break
        for fragment in missing & anchors(pandoc_document(pandoc,section['reader_text'])):
            labels[fragment].append(section['label'])
    return {fragment: (places[0] if len(places)==1 else '') for fragment in sorted(missing)
            for places in [labels[fragment]]}


def label_omitted_links(document, destinations):
    for node in ast_nodes(document['blocks']):
        if node['t']!='Link':
            continue
        attrs,label,(href,_) = node['c']
        if not href.startswith('#') or href[1:] not in destinations:
            continue
        location = destinations[href[1:]]
        message = f'(see {location} in the full beta)' if location else '(see the full beta)'
        node.update(t='Span',c=[attrs,[*label,{'t':'Space'},{'t':'Str','c':message}]])


def build(root, book, old, target_id, reader):
    reader = reader.strip()
    if not reader or old['export_id']==target_id or old.get('target_edition'):
        raise ValueError('choose a named reader and two distinct full beta editions')
    target, archive = editions.open_beta(root,book,target_id,with_directory=True)
    if target.get('target_edition'):
        raise ValueError('choose the revised full beta edition')
    feedback = state.path_at(root,f'_Edits/{book}/beta-feedback/{old["export_id"]}.json')
    notes = [n for n in state.document(feedback,'feedback')['feedback'] if n['reader']==reader]
    by_scene = defaultdict(list)
    broader = []
    for n in notes:
        if n['location']['status'] == 'GENERAL' or n['location'].get('scope'):
            broader.append(n)
        else:
            by_scene[note_scene(n,old['sections'])].append(n)
    comparison = editions.compare(old,target)
    parts, attrs, hashes, origins = [], {}, {}, {}
    sections = {editions.section_id(s):s for s in target['sections']}
    old_sections = {editions.section_id(s):s for s in old['sections']}
    counts = defaultdict(int)

    def append(text, label, origin=None):
        name = f'packet/part-{len(parts)+1}.md'
        parts.append((name,text.strip()+'\n'))
        attrs[name] = {'id':origin['chapter_id'] if origin else None,'display_label':label}
        hashes[name] = origin['source_sha256'] if origin else editions.digest(text)
        if origin:
            origins[name] = origin

    def prior(rows):
        for n in rows:
            block = 'Your previous comment\n\n' + quote_block(n['comment'])
            if n.get('kind') == 'strength':
                block = 'What you wanted to keep\n\n' + quote_block(n['comment'])
            if n.get('quote'):
                block += '\n\nPrevious selection\n\n' + quote_block(n['quote'])
            append(block,'Previous comment')

    append('# Changes since your last beta\n\n' + reader,'Reread packet')
    for change in comparison:
        a,b,status = change['before'],change['after'],change['status']
        if status=='unchanged':
            continue
        counts[status] += 1
        sec = sections[b[0]] if b else old_sections[a[0]]
        loc = f'{sec["label"]}, scene {(b or a)[1]+1}'
        labels = {'edited':'Revised','moved-edited':'Moved and revised','added':'New','deleted':'Removed',
                  'unresolved':'Scene correspondence unresolved','moved':'Moved'}
        append('## ' + loc + '\n\n' + labels[status],loc)
        if b and status not in ('moved',):
            scene = sec['scenes'][b[1]]
            origin = {k:sec[k] for k in ('path','chapter_id','source_sha256','label','bookmark')}
            origin.update(start=scene['start'],end=scene['end'],scene=b[1])
            append(sec['reader_text'][scene['start']:scene['end']],loc,origin)
        if a and status in ('deleted','moved'):
            original = old_sections[a[0]]['scenes'][a[1]]
            line = next((p['text'] for p in original['paragraphs'] if not p['text'].startswith('#')), '')
            if line:
                append('Earlier passage opened with\n\n'+quote_block(line[:180]),'Earlier passage')
        if a and status.startswith('moved'):
            append(f'Previously {old_sections[a[0]]["label"]}, scene {a[1]+1}.','Previous position')
        if a:
            prior(by_scene.pop(a,[]))
    for key, rows in by_scene.items():
        if key:
            sec = old_sections[key[0]]
            append(f'## Earlier comment on an unchanged passage\n\n{sec["label"]}, scene {key[1]+1}.','Previous comment')
        else:
            append('## Earlier comments without a unique scene match','Unmatched comments')
        prior(rows)
    for note in broader:
        scope = note['location'].get('scope')
        if not scope:
            try:
                scope, _ = feedback_scope.resolve(note, old)
            except ValueError:
                scope = {'label': note.get('chapter') or 'Unlocated'}
        append('## Earlier feedback on ' + scope['label'], 'Earlier feedback')
        prior([note])
    if not counts:
        append('The two editions have the same reader scenes.','Comparison')
    # A note definition can live in an unchanged scene at the end of the chapter.
    full_text = '\n\n'.join(section['reader_text'] for section in target['sections'])
    definitions = {m[1]:m[0] for m in re.finditer(r'(?m)^\[\^([^]\n]+)\]:[^\n]*(?:\n(?:    |\t)[^\n]*)*',full_text)}
    used, included = set(), set()
    for name,content in parts:
        if name in origins:
            used.update(re.findall(r'\[\^([^]\n]+)\](?!:)',content))
            included.update(re.findall(r'(?m)^\[\^([^]\n]+)\]:',content))
    for key in sorted(used-included):
        if key in definitions:
            # Keep the definition in the same Pandoc input as its reference.
            append(definitions[key],'Notes')
    for i,(path,content) in enumerate(parts):
        if path in origins:
            for href,dest in sorted(target.get('resource_links',{}).items(),key=lambda v:-len(v[0])):
                if href != dest:
                    content = re.sub(r'(?P<prefix>\]\(\s*<?|src=["\']|\]:\s*<?)' + re.escape(href)
                                     + r'(?=[\s)>"\']|$)',lambda m:m['prefix']+dest,content)
            parts[i] = (path,content)
    packet = beta_exchange.build_map(parts,attrs,hashes)
    packet.update(reader=reader, baseline_edition=old['export_id'],target_edition=target_id)
    for section in packet['sections']:
        section['origin'] = origins.get(section['path'])
    base = state.path_at(root,f'_Edits/{book}/beta-rereads')
    base.mkdir(parents=True,exist_ok=True)
    out = base / packet['export_id']
    pandoc = shutil.which('pandoc')
    if not pandoc:
        raise ValueError('Pandoc is required to build reread EPUB and Word packets')
    with tempfile.TemporaryDirectory(dir=base) as temp:
        stage = Path(temp)
        images = archive / 'beta-resources'
        for name, digest in target.get('resources',{}).items():
            if Path(name).name != name or state.digest(state.path_at(root,images/name)) != digest:
                raise ValueError('archived beta illustration changed: '+name)
        switches = ['--standalone','--metadata','lang='+target.get('language','und'),'--metadata','title=Changes since your last beta','--resource-path='+str(images)]
        docx = stage/'reread.docx'
        text = '\n\n'.join(v for _,v in parts)
        epub_source = pandoc_document(pandoc,text)
        omitted = omitted_destinations(pandoc,epub_source,target)
        label_omitted_links(epub_source,omitted)
        source = beta_exchange.docx_input(pandoc,stage,packet)
        if omitted:
            word_source = json.loads(source.read_text())
            label_omitted_links(word_source,omitted)
            source.write_text(json.dumps(word_source,ensure_ascii=False))
        subprocess.run([pandoc,str(source),'-f','json',*switches,'-o',str(docx)],check=True,capture_output=True)
        source.unlink()
        beta_exchange.bind_word_passages(docx,packet)
        epub = stage/'reread.epub'
        subprocess.run([pandoc,'-f','json',*switches,'-o',str(epub)],input=json.dumps(epub_source),text=True,check=True,capture_output=True)
        expected, report = epub_navigation.audit(epub,source_links=epub_navigation.source_links(epub_source))
        state.write(stage/'epub-navigation.json',expected)
        path = stage/'beta-passages.json'
        state.write(path,packet)
        meta = {'schema_version':1,'reader':reader,'baseline_edition':old['export_id'],'target_edition':target_id,
                'packet_id':packet['export_id'],'changes':dict(counts),'omitted_link_destinations':omitted,'epub_navigation':report,
                'beta_feedback':{'export_id':packet['export_id'],'map':path.name,'sha256':state.digest(path)}}
        state.write(stage/'export-manifest.json',meta)
        stage.rename(out)
    return {'output':str(out),**meta}


def remap(note, packet, target, locate):
    """Translate only anchored packet manuscript passages to the archived target."""
    if not note.get('anchors') and not note.get('quote'):
        return locate(note, target)
    explicit = any(key in note for key in ('scope', 'chapter_range', 'chapter'))
    scoped_note = {k: v for k, v in note.items() if k not in ('scope', 'chapter_range', 'chapter')}
    if explicit:
        origins = [s for s in packet['sections'] if s.get('origin')]
        selected = [s for s in origins if note.get('chapter') and feedback_scope.matches(s, note['chapter'])]
        if not selected:
            try:
                scope, _ = feedback_scope.resolve(note, target)
            except ValueError as exc:
                return {'status': 'UNRESOLVED', 'reason': str(exc)}
            selected = [s for s in origins if s['origin']['chapter_id'] in scope['chapter_ids']]
        packet = dict(packet, sections=selected)
    binding = locate(scoped_note, packet)
    if binding['status']!='ANCHORED':
        return binding
    section = next(s for s in packet['sections'] if s['path']==binding['path'])
    origin = section.get('origin')
    if not origin:
        return {'status':'UNRESOLVED','reason':'comment is on reread context outside the target manuscript'}
    source = next(s for s in target['sections'] if s['bookmark']==origin['bookmark'])
    pool = target['word_passages'] or target.get('text_passages',{})
    target_passages = {k:v for k,v in pool.items() if v['section']==source['bookmark']}
    packet_pool = packet['word_passages'] or packet['text_passages']
    if any(a in packet['text_passages'] for a in binding['passages']):
        packet_pool = packet['text_passages']
    anchors = []
    for key in binding['passages']:
        passage = packet_pool[key]['text']
        hits = [k for k,v in target_passages.items() if v['text']==passage]
        if len(hits)==1:
            anchors.append(hits[0])
        elif hits:
            sc = source['scenes'][origin['scene']]
            positions = [p for scene in source['scenes'] for p in scene['paragraphs']
                         if beta_exchange.normal(p['text'])==passage]
            within = [i for i,p in enumerate(positions) if sc['start']<=p['start']<sc['end']]
            if len(hits)==len(positions) and len(within)==1:
                anchors.append(hits[within[0]])
    if anchors and len(anchors)==len(binding['passages']):
        result = locate(dict(scoped_note, anchors=anchors, chapter=source['chapter_id'] or source['path']), target)
        if result['status'] == 'ANCHORED' and ('scope' in note or 'chapter_range' in note):
            result['scope'] = scope
        return result
    quote = note.get('quote') or binding.get('anchor_text','')
    if quote and quote in beta_exchange.normal(source['reader_text'][origin['start']:origin['end']]):
        if 'scope' in note or 'chapter_range' in note:
            binding['scope'] = scope
        return dict(binding,chapter_id=source['chapter_id'],chapter=source['label'],path=source['path'],
                    source_sha256=source['source_sha256'],passages=[],scene=origin['scene']+1)
    return {'status':'UNRESOLVED','reason':'returned selection cannot be matched to the archived target scene'}
