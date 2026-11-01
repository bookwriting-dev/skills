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


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--book', default='Book-1')
    sub = ap.add_subparsers(dest='command', required=True)
    for cmd in ('prepare', 'snapshot', 'check', 'validate', 'dashboard', 'disposition', 'memory', 'knowledge', 'reading', 'campaign', 'pipeline'):
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
