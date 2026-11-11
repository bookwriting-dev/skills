#!/usr/bin/env python3
"""Content-addressed Storycraft records. Python standard library; see --help."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from datetime import datetime, timezone

VERSION = 1


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def path_at(root, name):
    p = (root / name).resolve()
    if not p.is_relative_to(root.resolve()):
        raise ValueError('path escapes project: ' + str(name))
    return p


def load(path):
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or value.get('schema_version') != VERSION:
        raise ValueError('unsupported or missing schema_version: ' + str(path))
    return value


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextlib.contextmanager
def locked(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + '.lock')
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        lock.unlink()


def evidence(root, paths):
    root = root.resolve()
    out = []
    for name in sorted(set(paths)):
        p = path_at(root, name)
        item = {'path': str(p.relative_to(root)), 'kind': 'directory' if p.is_dir() else 'file'}
        if p.is_dir():
            item['files'] = {str(f.relative_to(p)): digest(f) for f in sorted(p.rglob('*')) if f.is_file()}
        else:
            item['sha256'] = digest(p)
        out.append(item)
    return out


def freshness(root, meta):
    if not meta.exists():
        return {'freshness': 'UNKNOWN', 'reasons': ['no review metadata']}
    m = load(meta)
    if not m.get('inputs') or not m.get('report'):
        raise ValueError('review metadata requires inputs and report')
    reasons = []
    for item in m['inputs']:
        current = evidence(root, [item['path']])[0]
        if current != item:
            reasons.append('changed input: ' + item['path'])
    if digest(path_at(root, m['report'])) != m.get('report_sha256'):
        reasons.append('report body changed')
    return {'freshness': 'STALE' if reasons else 'CURRENT', 'reasons': reasons,
            'verdict': m.get('verdict', 'UNKNOWN')}


def source_valid(root, item):
    return (isinstance(item.get('source'), str) and bool(item.get('quote')) and
            digest(path_at(root, item['source'])) == item.get('source_sha256') and
            item['quote'] in path_at(root, item['source']).read_text())


def document(path, key):
    return load(path) if path.exists() else {'schema_version': VERSION, key: []}


def memory(root, args):
    p = path_at(root, 'Wiki/Style/editorial-decisions.json')
    if args.action == 'list':
        d = document(p, 'decisions')
        return [x for x in d['decisions'] if x.get('status') == 'active' and
                (not args.scope or x.get('scope') in ('series', args.scope))]
    item = load(Path(args.spec))
    for key in ('id', 'scope', 'rule_category', 'reason', 'status', 'reusable'):
        if key not in item:
            raise ValueError('decision missing ' + key)
    if item['rule_category'] in ('canon', 'fact', 'knowledge', 'numeric') and item['reusable']:
        raise ValueError('preferences cannot waive correctness')
    if item['status'] not in ('active', 'retired', 'superseded'):
        raise ValueError('invalid decision status')
    with locked(p):
        d = document(p, 'decisions')
        if any(x['id'] == item['id'] for x in d['decisions']):
            raise ValueError('decision ID exists; use a new superseding record')
        for old in d['decisions']:
            if old['id'] in item.get('supersedes', []):
                old['status'] = 'superseded'
        item['created_at'] = now()
        d['decisions'].append(item)
        write(p, d)
    return item


def knowledge(root, args):
    p = path_at(root, f'Wiki/Story/{args.book}/knowledge.json')
    if args.action == 'record':
        event = load(Path(args.spec))
        for key in ('id', 'fact_id', 'observer', 'state', 'story_position', 'reader_position', 'confirmed'):
            if key not in event:
                raise ValueError('event missing ' + key)
        if event['state'] not in ('knows', 'suspects', 'believes', 'disbelieves', 'forgets', 'exposed'):
            raise ValueError('invalid epistemic state')
        if not source_valid(root, event):
            raise ValueError('event requires current exact source evidence')
        for key in ('story_position', 'reader_position'):
            if not isinstance(event[key], list) or not all(isinstance(v, int) for v in event[key]):
                raise ValueError('positions must be integer arrays')
        with locked(p):
            d = document(p, 'events')
            if any(x['id'] == event['id'] for x in d['events']):
                raise ValueError('duplicate knowledge event')
            d['events'].append(event)
            write(p, d)
        return event
    d = document(p, 'events')
    events = [dict(e, current=source_valid(root, e)) for e in d['events']]
    if args.action == 'audit':
        return {'events': events, 'coverage': 'partial; missing events do not establish ignorance'}
    pos = [int(x) for x in args.position.split('.')]
    field = 'reader_position' if args.observer == 'reader' else 'story_position'
    state = {}
    superseded = {i for e in events if e['current'] and e['confirmed'] for i in e.get('supersedes', [])}
    for e in sorted(events, key=lambda x: x[field]):
        if e['current'] and e['confirmed'] and e['id'] not in superseded and e['observer'] == args.observer and e[field] <= pos:
            state[e['fact_id']] = e
    return state


def campaign(root, args):
    base = path_at(root, f'_Edits/{args.book}/campaigns/{args.run}')
    p = base / 'campaign.json'
    if args.action == 'init':
        with locked(p):
            if p.exists():
                raise ValueError('campaign already exists')
            d = load(Path(args.spec))
            tasks = {t['id']: t for t in d['tasks']}
            if any(not re.fullmatch(r'[\w-]+', i) for i in tasks):
                raise ValueError('invalid task ID')
            if len(tasks) != len(d['tasks']):
                raise ValueError('duplicate task IDs')
            def visit(i, chain):
                if i in chain or i not in tasks:
                    raise ValueError('cyclic or missing dependency: ' + i)
                for dep in tasks[i].get('depends_on', []):
                    visit(dep, chain + [i])
            for i in tasks:
                visit(i, [])
            for t in tasks.values():
                t['status'] = 'pending'
                t['before'] = evidence(root, t['files'])
                for e in t['before']:
                    if e['kind'] != 'file':
                        raise ValueError('task files must be explicit files')
                    f = path_at(root, e['path'])
                    if f.exists():
                        dest = base / 'snapshots' / t['id'] / e['path']
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(f.read_bytes())
            if any(evidence(root, t['files']) != t['before'] for t in d['tasks']):
                raise ValueError('source changed during campaign initialization')
            write(p, d)
            return d
    with locked(p):
        d = load(p)
        if args.action == 'status':
            return d
        t = next(t for t in d['tasks'] if t['id'] == args.task)
        if args.action == 'start':
            if t['status'] != 'pending' or any(x['status'] != 'complete' for x in d['tasks'] if x['id'] in t.get('depends_on', [])):
                raise ValueError('task is not ready')
            # Prior campaign tasks can legitimately change shared files.
            expected = {e['path']: e for e in t['before']}
            for prior in sorted(d['tasks'], key=lambda x: x.get('completed_at', '')):
                if prior['status'] == 'complete':
                    expected.update({e['path']: e for e in prior['after'] if e['path'] in expected})
            if evidence(root, list(expected)) != sorted(expected.values(), key=lambda e: e['path']):
                raise ValueError('author changes detected; reconcile before starting')
            t['before'] = evidence(root, t['files'])
            for e in t['before']:
                f = path_at(root, e['path'])
                if f.is_file():
                    snapshot = base / 'snapshots' / t['id'] / e['path']
                    snapshot.parent.mkdir(parents=True, exist_ok=True)
                    snapshot.write_bytes(f.read_bytes())
            if evidence(root, t['files']) != t['before']:
                raise ValueError('source changed during task snapshot')
            t['status'] = 'running'
        elif args.action == 'complete':
            if t['status'] != 'running':
                raise ValueError('task must be running')
            checks = load(Path(args.spec))
            if not checks.get('checks') or any((freshness(root, path_at(root, m))['freshness'] != 'CURRENT' or freshness(root, path_at(root, m)).get('verdict') != 'PASS') for m in checks['checks']):
                raise ValueError('completion requires current check metadata')
            checked = {e['path'] for meta in checks['checks'] for e in load(path_at(root, meta))['inputs']}
            if not set(t['files']).issubset(checked):
                raise ValueError('checks must cover all task source files')
            t['checks'] = checks['checks']
            t['completed_at'] = now()
            t['after'] = evidence(root, t['files'])
            t['status'] = 'complete'
        elif args.action == 'recover':
            if any(t['id'] in x.get('depends_on', []) and x['status'] in ('running', 'complete') for x in d['tasks']) or t['status'] != 'complete' or evidence(root, t['files']) != t['after']:
                raise ValueError('recovery conflicts with subsequent changes')
            for e in t['before']:
                f = path_at(root, e['path'])
                snapshot = base / 'snapshots' / t['id'] / e['path']
                if e['sha256'] is None:
                    f.unlink(missing_ok=True)
                else:
                    f.write_bytes(snapshot.read_bytes())
            t['status'] = 'restored'
        write(p, d)
        return d


def reading(root, args):
    base = path_at(root, f'_Edits/{args.book}/reading/{args.run}')
    p = base / 'run.json'
    with locked(p):
        if args.action == 'init':
            if p.exists():
                raise ValueError('reading run exists')
            d = load(Path(args.spec))
            if not d.get('chapters') or len(set(d['chapters'])) != len(d['chapters']) or not all(path_at(root, name).is_file() for name in d['chapters']) or not isinstance(d.get('reader_brief', ''), str):
                raise ValueError('reading run needs ordered chapters and spoiler-free reader_brief')
            d.update(checkpoints=[], simulated=True)
            d['inputs'] = evidence(root, d['chapters'])
            write(p, d)
            return d
        d = load(p)
        n = len(d['checkpoints'])
        if any(evidence(root, [c['source']])[0] != c['input'] for c in d['checkpoints']):
            raise ValueError('earlier chapter changed: fork a run from last valid checkpoint')
        if n >= len(d['chapters']):
            return {'status': 'sealed', 'simulated': True, 'checkpoints': n}
        chapter = d['chapters'][n]
        packet = {'schema_version': 1, 'chapter': chapter, 'input': evidence(root, [chapter])[0],
                  'reader_brief': d.get('reader_brief', ''), 'text': path_at(root, chapter).read_text(),
                  'memory': d['checkpoints'][-1]['reaction'] if n else None}
        if args.action == 'packet':
            write(base / f'packet-{n+1:03}.json', packet)
            return packet
        reaction = load(Path(args.spec))
        packet_path = base / f'packet-{n+1:03}.json'
        saved = load(packet_path)
        if saved != packet:
            raise ValueError('packet inputs changed')
        for key in ('remembered_facts', 'predictions', 'questions', 'emotional_response', 'continue_reading', 'confusion', 'relationship_changes', 'isolation_evidence'):
            if key not in reaction:
                raise ValueError('reaction missing ' + key)
        isolation = reaction['isolation_evidence']
        if not isinstance(isolation, dict) or not isolation.get('verified_by_coordinator') or not isolation.get('transcript_reference'):
            raise ValueError('sealing requires inspected isolated input transcript')
        if len(json.dumps(reaction)) > 16000:
            raise ValueError('memory exceeds 16000 characters; explicitly summarize and disclose truncation')
        checkpoint = {'source': chapter, 'input': packet['input'], 'reaction': reaction}
        d['checkpoints'].append(checkpoint)
        write(base / f'Chapter-{n+1:03}.json', dict(schema_version=1, **checkpoint))
        write(p, d)
        return {'accepted': chapter, 'remaining': len(d['chapters']) - n - 1}


def dashboard(root, book):
    chapters = []
    decisions_path = root / '_Edits' / book / 'decisions.jsonl'
    dispositions = {}
    if decisions_path.exists():
        for line in decisions_path.read_text().splitlines():
            entry = json.loads(line)
            dispositions[(entry.get('report_sha256'), entry['finding_id'])] = entry['disposition']
    for draft in sorted((root / 'Chapters' / book).glob('Chapter-*.md')):
        checks = []
        for meta in sorted((root / '_Edits' / book).glob(draft.stem + '_*.meta.json')):
            m = load(meta)
            status = freshness(root, meta)
            blocking = [f['id'] for f in m.get('findings', []) if f.get('blocking') and
                        dispositions.get((m.get('report_sha256'), f['id'])) not in ('applied', 'rejected', 'superseded')]
            checks.append(dict(path=str(meta.relative_to(root)), blocking=blocking, **status))
        chapters.append(dict(chapter=str(draft.relative_to(root)), checks=checks))
    campaigns = []
    for p in (root / '_Edits' / book / 'campaigns').glob('*/campaign.json'):
        d = load(p)
        expected = {}
        for task in sorted(d['tasks'], key=lambda x: x.get('completed_at', '')):
            expected.update({e['path']: e for e in task.get('after', [])})
        current = evidence(root, list(expected)) == sorted(expected.values(), key=lambda e: e['path']) and all(t['status'] == 'complete' and
                      all(freshness(root, path_at(root, c))['freshness'] == 'CURRENT' and
                          freshness(root, path_at(root, c)).get('verdict') == 'PASS' for c in t.get('checks', [])) for t in d['tasks'])
        campaigns.append(dict(path=str(p.relative_to(root)), current=current, tasks=d['tasks']))
    return dict(chapters=chapters, campaigns=campaigns)


SOMATIC_TOKENS = {
    'jaw', 'breath', 'throat', 'pulse', 'ribs', 'chest', 'knuckles', 'stomach',
    'silence', 'stillness', 'ozone', 'copper', 'bile', 'sternum', 'temples',
    'collarbone', 'exhale', 'inhale', 'swallowed', 'clenched', 'unclenched',
    'tightened', 'shiver', 'tremor', 'heartbeat',
}

STOP_WORDS = {
    'a', 'an', 'and', 'the', 'this', 'that', 'these', 'those', 'there', 'here',
    'it', 'its', 'he', 'she', 'they', 'them', 'his', 'her', 'their', 'him',
    'of', 'to', 'in', 'on', 'at', 'by', 'for', 'with', 'from', 'as', 'is',
    'are', 'was', 'were', 'be', 'been', 'being', 'am', 'do', 'does', 'did',
    'have', 'has', 'had', 'will', 'would', 'could', 'should', 'can', 'may',
    'might', 'must', 'not', 'no', 'nor', 'so', 'if', 'but', 'or', 'then',
    'than', 'when', 'while', 'where', 'what', 'which', 'who', 'whom', 'whose',
    'how', 'why', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other',
    'some', 'such', 'only', 'own', 'same', 'too', 'very', 'just', 'now', 'i',
    'you', 'we', 'us', 'our', 'your', 'my', 'me', 'up', 'out', 'off', 'over',
    'under', 'again', 'once', 'about', 'into', 'through', 'during', 'before',
    'after', 'above', 'below', 'between', 'because', 'until', 'against',
}


def prose_lines(path):
    """Extract clean prose lines, stripping headings, fences, > callouts, rules, and checkboxes."""
    lines = []
    in_fence = False
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith('```'):
            in_fence = not in_fence
            continue
        if in_fence or line.startswith('#') or line.startswith('>') or line in ('---', '***'):
            continue
        if re.match(r'^[-*] \[', line):
            continue
        lines.append(line)
    return lines


def parse_checkpoints(path, chapter_num):
    """Return active relationship_checkpoints for chapter_num from a character Markdown file."""
    text = path.read_text(encoding='utf-8')
    m = re.search(r'^##\s+relationship_checkpoints\b(.*?)(?=^##\s+|\Z)', text, re.M | re.S)
    if not m:
        return []
    char_name = path.stem.replace('_', ' ')
    fm_name = re.search(r'^name:\s*["\']?([^"\'\n]+)["\']?', text, re.M)
    if fm_name:
        char_name = fm_name.group(1).strip()
    active = []
    block = m.group(1)
    for sub in re.finditer(r'^###\s+([^\n]+)\n(.*?)(?=^###\s+|\Z)', block, re.M | re.S):
        other = sub.group(1).strip()
        entries = []
        current = {}
        for line in sub.group(2).splitlines():
            kv = re.match(r'^\s*-\s*\*\*([a-z_]+):\*\*\s*(.+)$', line.strip())
            if kv:
                k, v = kv.group(1), kv.group(2).strip()
                if k == 'link_type' and current:
                    entries.append(current)
                    current = {}
                current[k] = v
        if current:
            entries.append(current)
        for entry in entries:
            start_m = re.search(r'\d+', str(entry.get('chapter_start', '1')))
            start = int(start_m.group(0)) if start_m else 1
            end_raw = str(entry.get('chapter_end', '(open)')).strip().lower()
            end_m = re.search(r'\d+', end_raw)
            end = None if ('open' in end_raw or not end_m) else int(end_m.group(0))
            if start <= chapter_num and (end is None or chapter_num <= end):
                active.append({
                    'character': char_name,
                    'other_character': other,
                    'link_type': entry.get('link_type', ''),
                    'chapter_start': start,
                    'chapter_end': 'open' if end is None else end,
                    'notes': entry.get('notes', ''),
                    'source': path,
                })
    return active


def parse_psych(path):
    """Extract What they won't say lines and Show-Don't-Tell Gaps rows from a Psych file."""
    text = path.read_text(encoding='utf-8')
    unsaid = [m.group(1).strip() for m in re.finditer(
        r'^\s*-\s*\*\*What they won\'t say:\*\*\s*(.+)$', text, re.M | re.I
    )]
    gaps = []
    gap_sec = re.search(r'^##\s+Show-Don\'t-Tell Gaps\b(.*?)(?=^##\s+|^---\s*$|\Z)', text, re.M | re.S | re.I)
    if gap_sec:
        for line in gap_sec.group(1).splitlines():
            line = line.strip()
            if not line.startswith('|') or re.match(r'^\|\s*[-:]+\s*\|', line):
                continue
            cells = [c.strip() for c in line.strip('|').split('|')]
            if len(cells) >= 3 and cells[0].lower() != 'beat':
                gaps.append({'beat': cells[0], 'reporting_draft': cells[1], 'instead': cells[2]})
    return {'what_they_wont_say': unsaid, 'show_dont_tell_gaps': gaps}


def draft_packet(root, args):
    ch_m = re.search(r'\d+', str(args.chapter or '1'))
    if not ch_m:
        raise ValueError('invalid --chapter value')
    ch_num = int(ch_m.group(0))
    window = max(1, int(args.window))
    book = args.book

    # 1. Scene plan
    scene_info = None
    pov_names = []
    for cand in (
        root / 'Wiki' / 'Outline' / book / f'Chapter_{ch_num:02d}_Scene.md',
        root / 'Wiki' / 'Outline' / book / f'Chapter_{ch_num:03d}_Scene.md',
    ):
        if cand.is_file():
            stext = cand.read_text(encoding='utf-8')
            for pm in re.finditer(r'(?:\*\*POV:\*\*|^POV:)\s*([^\n|]+)', stext, re.M | re.I):
                for raw_p in re.split(r'[,/]| and ', pm.group(1)):
                    clean_p = raw_p.strip().split('(')[0].strip()
                    if clean_p and clean_p not in pov_names:
                        pov_names.append(clean_p)
            scenes_count = len(re.findall(r'^##\s+Scene\s+\d+\b', stext, re.M | re.I))
            scene_info = {
                'path': str(cand.relative_to(root)),
                'sha256': digest(cand),
                'scene_count': scenes_count or 1,
                'pov_characters': pov_names,
            }
            break

    # 2. Psych pass
    psych_info = None
    for cand in (
        root / 'Wiki' / 'Psych' / book / f'Chapter_{ch_num:02d}_Psych.md',
        root / 'Wiki' / 'Psych' / book / f'Chapter_{ch_num:03d}_Psych.md',
    ):
        if cand.is_file():
            ptext = cand.read_text(encoding='utf-8')
            for pm in re.finditer(r'\*\*POV:\*\*\s*([^\n,]+)', ptext):
                clean_p = pm.group(1).strip()
                if clean_p and clean_p not in pov_names:
                    pov_names.append(clean_p)
            psych_info = {
                'path': str(cand.relative_to(root)),
                'sha256': digest(cand),
                **parse_psych(cand),
            }
            break

    # 3. Style guide & multi-POV voice prompts
    style_path = root / 'Wiki' / 'Style' / 'style_guide.md'
    if style_path.is_file():
        sg_text = style_path.read_text(encoding='utf-8')
        for key in ('pov_1', 'pov_2', 'pov_3', 'pov_4'):
            km = re.search(rf'^{key}:\s*["\']?([^"\'\n]+)["\']?', sg_text, re.M)
            if km:
                val = km.group(1).strip()
                if val and val.lower() != 'none' and val not in pov_names:
                    pov_names.append(val)
    voice_prompts = []
    seen_vp = set()
    style_dir = root / 'Wiki' / 'Style'
    for pov in pov_names:
        slug_full = re.sub(r'\s+', '_', pov.strip())
        slug_first = slug_full.split('_')[0]
        for cand_name in (f'voice_prompt_{slug_full}.md', f'voice_prompt_{slug_first}.md',
                          f'voice_prompt_{slug_full.lower()}.md', f'voice_prompt_{slug_first.lower()}.md'):
            vp = style_dir / cand_name
            if vp.is_file() and vp not in seen_vp:
                seen_vp.add(vp)
                voice_prompts.append({'pov': pov, 'path': str(vp.relative_to(root)), 'sha256': digest(vp)})
                break
    default_vp = style_dir / 'voice_prompt.md'
    if default_vp.is_file() and default_vp not in seen_vp:
        voice_prompts.append({'pov': 'default', 'path': str(default_vp.relative_to(root)), 'sha256': digest(default_vp)})

    # 4. Active relationship checkpoints for Chapter N
    checkpoints = []
    char_dir = root / 'Wiki' / 'Characters'
    if char_dir.is_dir():
        for cf in sorted(char_dir.glob('*.md')):
            if cf.stem.endswith('_sheet'):
                continue
            for cp in parse_checkpoints(cf, ch_num):
                cp['source'] = str(cf.relative_to(root))
                cp['source_sha256'] = digest(cf)
                checkpoints.append(cp)

    # 5. Immediate continuity tail from Chapter-(N-1)
    continuity_tail = None
    if ch_num > 1:
        prev_ch = root / 'Chapters' / book / f'Chapter-{ch_num - 1:03d}.md'
        if prev_ch.is_file():
            plines = prose_lines(prev_ch)
            all_words = ' '.join(plines).split()
            tail_words = ' '.join(all_words[-400:]) if all_words else ''
            closing_sentence = ''
            for line in reversed(plines):
                sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', line) if len(s.split()) >= 3]
                if sents:
                    closing_sentence = sents[-1]
                    break
            continuity_tail = {
                'path': str(prev_ch.relative_to(root)),
                'sha256': digest(prev_ch),
                'tail_excerpt': tail_words,
                'closing_sentence': closing_sentence,
            }

    # 6. Rolling N-chapter Cooling List
    somatic_counts = {}
    ngram_counts = {}
    simile_counts = {}
    recent_openers = []
    recent_closers = []
    start_trail = max(1, ch_num - window)
    for t_num in range(start_trail, ch_num):
        t_path = root / 'Chapters' / book / f'Chapter-{t_num:03d}.md'
        if not t_path.is_file():
            continue
        t_lines = prose_lines(t_path)
        if not t_lines:
            continue
        first_w = []
        for l in t_lines:
            w = re.findall(r"[A-Za-z][A-Za-z']+", l)
            if len(w) >= 3:
                first_w = w[:6]
                break
        if first_w:
            recent_openers.append({'chapter': f'Chapter-{t_num:03d}', 'opener': ' '.join(first_w)})
        last_s = ''
        for l in reversed(t_lines):
            sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', l) if len(s.split()) >= 3]
            if sents:
                last_s = sents[-1]
                break
        if last_s:
            recent_closers.append({'chapter': f'Chapter-{t_num:03d}', 'closer': last_s})

        prose_blob = ' '.join(t_lines)
        tokens = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z']+", prose_blob)]
        ch_somatic = {}
        for tok in tokens:
            if tok in SOMATIC_TOKENS:
                ch_somatic[tok] = ch_somatic.get(tok, 0) + 1
                somatic_counts[tok] = somatic_counts.get(tok, 0) + 1
        # Flag any somatic token used >= 2 times in a single trailing chapter as at least 3 in aggregate
        for tok, c in ch_somatic.items():
            if c >= 2 and somatic_counts[tok] < 3:
                somatic_counts[tok] = 3

        for i in range(len(tokens) - 2):
            tri = tokens[i:i + 3]
            if sum(1 for w in tri if w not in STOP_WORDS) >= 2:
                key = ' '.join(tri)
                ngram_counts[key] = ngram_counts.get(key, 0) + 1

        for sm in re.finditer(r'\b(?:like\s+(?:a|an|the)\s+[a-z]+\s+[a-z]+|as\s+if\s+[a-z]+\s+[a-z]+\s+[a-z]+)', prose_blob.lower()):
            phrase = re.sub(r'\s+', ' ', sm.group(0).strip())
            simile_counts[phrase] = simile_counts.get(phrase, 0) + 1

    cooling_list = {
        'window_chapters': window,
        'somatic_hotspots': [
            {'word': k, 'count': v}
            for k, v in sorted(somatic_counts.items(), key=lambda x: (-x[1], x[0]))
            if v >= 3
        ],
        'repeated_ngrams': [
            {'ngram': k, 'count': v}
            for k, v in sorted(ngram_counts.items(), key=lambda x: (-x[1], x[0]))
            if v >= 2
        ][:20],
        'repeated_similes': [
            {'phrase': k, 'count': v}
            for k, v in sorted(simile_counts.items(), key=lambda x: (-x[1], x[0]))
        ][:15],
        'recent_openers': recent_openers,
        'recent_closers': recent_closers,
    }

    # 7. Knowledge state as of start of Chapter N
    k_path = root / 'Wiki' / 'Story' / book / 'knowledge.json'
    knowledge_as_of = {}
    if k_path.is_file():
        kd = document(k_path, 'events')
        events = [dict(e, current=source_valid(root, e)) for e in kd['events']]
        superseded = {i for e in events if e['current'] and e['confirmed'] for i in e.get('supersedes', [])}
        observers = sorted({e.get('observer') for e in events if e.get('observer')})
        for obs in observers:
            field = 'reader_position' if obs == 'reader' else 'story_position'
            obs_state = {}
            for e in sorted(events, key=lambda x: x[field]):
                if e['current'] and e['confirmed'] and e['id'] not in superseded and e['observer'] == obs and e[field] <= [ch_num, 0]:
                    obs_state[e['fact_id']] = e
            if obs_state:
                knowledge_as_of[obs] = obs_state

    # 8. Applicable active editorial decisions
    ed_path = root / 'Wiki' / 'Style' / 'editorial-decisions.json'
    allowed_scopes = {'series', book, f'Chapter-{ch_num:03d}'} | set(pov_names)
    active_decisions = []
    if ed_path.is_file():
        ed = document(ed_path, 'decisions')
        active_decisions = [
            x for x in ed['decisions']
            if x.get('status') == 'active' and x.get('scope') in allowed_scopes
        ]

    packet = {
        'schema_version': VERSION,
        'book': book,
        'chapter_number': ch_num,
        'chapter_id': f'Chapter-{ch_num:03d}',
        'scene_plan': scene_info,
        'psych': psych_info,
        'voice_prompts': voice_prompts,
        'relationship_checkpoints': checkpoints,
        'continuity_tail': continuity_tail,
        'knowledge_as_of': knowledge_as_of,
        'editorial_decisions': active_decisions,
        'cooling_list': cooling_list,
    }
    if getattr(args, 'output', None):
        out = path_at(root, args.output)
        with locked(out):
            write(out, packet)
    return packet


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--book', default='Book-1')
    sub = ap.add_subparsers(dest='command', required=True)
    for cmd in ('prepare', 'snapshot', 'check', 'validate', 'dashboard', 'disposition', 'memory', 'knowledge', 'reading', 'campaign', 'pipeline', 'draft-packet'):
        p = sub.add_parser(cmd)
        p.add_argument('--spec')
        p.add_argument('--output')
        p.add_argument('--meta')
        p.add_argument('--action', default='list')
        p.add_argument('--scope')
        p.add_argument('--observer', default='reader')
        p.add_argument('--position', default='999999')
        p.add_argument('--run', default='default')
        p.add_argument('--task')
        p.add_argument('--chapter', default='1')
        p.add_argument('--window', type=int, default=3)
    a = ap.parse_args()
    root = a.root.resolve()
    if not re.fullmatch(r'Book-\d+', a.book) or not re.fullmatch(r'[\w-]+', a.run):
        raise ValueError('invalid book or run ID')
    if a.command == 'prepare':
        spec = load(Path(a.spec))
        if not spec.get('paths'):
            raise ValueError('prepare requires paths including all consumed references')
        spec['inputs'] = evidence(root, spec.pop('paths'))
        write(path_at(root, a.output), spec)
        result = spec
    elif a.command == 'snapshot':
        spec = load(Path(a.spec))
        # Spec is captured BEFORE the review; it contains the expected input hashes.
        if not spec.get('inputs') or evidence(root, [e['path'] for e in spec['inputs']]) != spec['inputs']:
            raise ValueError('review inputs changed or pre-review evidence missing')
        report = path_at(root, spec['report'])
        if not report.is_file() or spec['verdict'] not in ('PASS', 'WARN', 'FAIL'):
            raise ValueError('missing report or invalid verdict')
        spec.update(report_sha256=digest(report), created_at=now())
        out = path_at(root, a.output)
        with locked(out):
            write(out, spec)
        result = spec
    elif a.command == 'check':
        result = freshness(root, path_at(root, a.meta))
    elif a.command == 'dashboard':
        result = dashboard(root, a.book)
    elif a.command == 'validate':
        result = []
        for m in sorted((root / '_Edits' / a.book).rglob('*.meta.json')):
            result.append(dict(path=str(m.relative_to(root)), **freshness(root, m)))
    elif a.command == 'disposition':
        item = load(Path(a.spec))
        if item.get('disposition') not in ('applied', 'rejected', 'deferred', 'superseded') or not item.get('finding_id') or not item.get('report') or not item.get('report_sha256'):
            raise ValueError('invalid finding disposition')
        p = path_at(root, f'_Edits/{a.book}/decisions.jsonl')
        with locked(p):
            with p.open('a') as f:
                f.write(json.dumps(dict(item, created_at=now())) + '\n')
        result = item
    elif a.command == 'pipeline':
        p = path_at(root, f'_Edits/{a.book}/pipeline/{a.run}.json')
        with locked(p):
            d = document(p, 'steps')
            if a.action == 'record':
                item = load(Path(a.spec))
                if item.get('status') not in ('running', 'complete') or not item.get('id') or not item.get('inputs'):
                    raise ValueError('invalid pipeline step')
                if evidence(root, [e['path'] for e in item['inputs']]) != item['inputs']:
                    raise ValueError('stale pipeline inputs')
                if item['status'] == 'complete' and (not item.get('outputs') or evidence(root, [e['path'] for e in item['outputs']]) != item['outputs']):
                    raise ValueError('completion requires current output evidence')
                d['steps'].append(item)
                write(p, d)
            result = [dict(s, reusable=s['status'] == 'complete' and evidence(root, [e['path'] for e in s['inputs']]) == s['inputs'] and evidence(root, [e['path'] for e in s.get('outputs', [])]) == s.get('outputs')) for s in d['steps']]
    elif a.command == 'draft-packet':
        result = draft_packet(root, a)
    else:
        result = globals()[a.command](root, a)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, StopIteration, TypeError) as e:
        print(json.dumps({'error': str(e)}))
        raise SystemExit(2)
