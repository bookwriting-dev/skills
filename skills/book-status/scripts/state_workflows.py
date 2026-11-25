"""Revision campaigns, sequential blind reading, and pipeline step journals."""
import json
from pathlib import Path
import re

from state_core import (
    VERSION, chapter_format_module, digest, document, evidence, load, locked, now,
    path_at, project_manifest_module, reader_text_module, write,
)
from state_reviews import pipeline_step_reusable, readiness


def validate_pipeline_step(item, run):
    if item.get('record_type') != 'pipeline_step' or item.get('schema_version') != 2:
        raise ValueError('pipeline step requires record_type pipeline_step and schema_version 2')
    if item.get('status') not in ('running', 'complete') or not item.get('id') or not item.get('inputs'):
        raise ValueError('invalid pipeline step')
    if item.get('operation_id') != run:
        raise ValueError('pipeline step operation_id must match --run')
    if item.get('completion_profile') not in ('draft_verified', 'full_editorial_candidate', 'independent_editorial_gate'):
        raise ValueError('pipeline step requires a supported completion_profile')
    if not item.get('idempotency_key') or not item.get('stage_role'):
        raise ValueError('pipeline step requires idempotency_key and stage_role')
    subjects = item.get('subjects')
    if (not isinstance(subjects, list) or not subjects or
            any(not isinstance(subject, dict) or not subject.get('id') or not subject.get('path') or
                not subject.get('sha256')
                for subject in subjects)):
        raise ValueError('pipeline step requires identified subject paths')
    input_by_path = {entry.get('path'): entry for entry in item['inputs']}
    if any(subject.get('path') not in input_by_path or
           input_by_path[subject['path']].get('sha256') != subject.get('sha256')
           for subject in subjects):
        raise ValueError('pipeline subject identity/hash must be captured in step inputs')
    if not isinstance(item.get('constraints'), dict):
        raise ValueError('pipeline step requires a constraints object')
    if not isinstance(item.get('authorized_writes'), list):
        raise ValueError('pipeline step requires an authorized_writes list')
    if not isinstance(item.get('transform_paths', []), list):
        raise ValueError('pipeline step transform_paths must be a list')


def record_pipeline_step(root, book, run, action, item=None):
    p = path_at(root, f'_Edits/{book}/pipeline/{run}.json')
    with locked(p):
        d = document(p, 'steps')
        if action == 'record':
            validate_pipeline_step(item, run)
            if d.get('operation_schema_version', 2) != 2:
                raise ValueError('unsupported operation journal schema; preserve and migrate before mutation')
            d['record_type'] = 'operation_journal'
            d['operation_schema_version'] = 2
            envelope = {'operation_id': item['operation_id'],
                        'completion_profile': item['completion_profile'],
                        'subjects': item['subjects'], 'constraints': item['constraints']}
            for key, value in envelope.items():
                if key in d and d[key] != value:
                    raise ValueError(f'pipeline run {key} differs from the established run manifest')
                d[key] = value
            existing = next((step for step in d['steps'] if step.get('id') == item['id']), None)
            if existing and item.get('completion_profile') != existing.get('completion_profile'):
                raise ValueError('pipeline step completion profile changed during operation')
            if item['status'] == 'running':
                if existing:
                    raise ValueError('operation ID already exists; resume or use a new operation ID')
                if evidence(root, [e['path'] for e in item['inputs']]) != item['inputs']:
                    raise ValueError('stale pipeline inputs')
                item.setdefault('attempt_id', item.get('id') + '-attempt-1')
                d['steps'].append(item)
            else:
                if existing and existing.get('status') == 'complete':
                    same_manifest = all(item.get(key) == existing.get(key) for key in
                        ('operation_id', 'idempotency_key', 'completion_profile', 'stage_role',
                         'subjects', 'constraints', 'authorized_writes', 'transform_paths'))
                    if (same_manifest and item.get('outputs') == existing.get('outputs') and
                            item.get('attempt_id', existing.get('attempt_id')) == existing.get('attempt_id')):
                        return [dict(step, reusable=pipeline_step_reusable(root, step)) for step in d['steps']]
                    raise ValueError('operation ID already completed with different output; use a new operation ID')
                if not existing or existing.get('status') != 'running':
                    raise ValueError('completion must reference an existing running operation')
                if item.get('attempt_id', existing.get('attempt_id')) != existing.get('attempt_id'):
                    raise ValueError('completion attempt does not match running operation')
                for key in ('operation_id', 'idempotency_key', 'completion_profile', 'stage_role',
                            'subjects', 'constraints', 'authorized_writes', 'transform_paths'):
                    if item.get(key) != existing.get(key):
                        raise ValueError(f'pipeline completion changed its authorized {key}')
                if not item.get('outputs'):
                    raise ValueError('completion requires output evidence')
                output_paths = {e.get('path') for e in item['outputs']}
                allowed = set(existing.get('authorized_writes', []))
                item['authorized_writes'] = existing['authorized_writes']
                if allowed and not output_paths.issubset(allowed):
                    raise ValueError('pipeline output exceeds authorized write paths')
                input_map = {e.get('path'): e for e in existing['inputs']}
                output_map = {e.get('path'): e for e in item['outputs']}
                if not output_paths.issubset(set(input_map) | allowed):
                    raise ValueError('pipeline output path was not captured or authorized')
                transform_paths = set(existing.get('transform_paths', []))
                unchanged = [e for name, e in input_map.items()
                             if name not in output_paths and name not in transform_paths]
                if unchanged and evidence(root, [e['path'] for e in unchanged]) != unchanged:
                    raise ValueError('untouched pipeline dependency changed')
                if evidence(root, list(output_map)) != sorted(output_map.values(), key=lambda e: e['path']):
                    raise ValueError('completion requires current output evidence')
                transforms = item.get('transformations', [])
                if not isinstance(transforms, list):
                    raise ValueError('transformations must be a list')
                transformed_paths = set()
                for transform in transforms:
                    path = transform.get('path')
                    before = transform.get('before')
                    after = transform.get('after')
                    if (not path or path in transformed_paths or path not in existing.get('transform_paths', []) or
                            path not in existing.get('authorized_writes', []) or before != input_map.get(path) or
                            not isinstance(after, dict) or after.get('path') != path or
                            path in output_paths or
                            evidence(root, [path]) != [after]):
                        raise ValueError(f'invalid or stale transformation lineage for {path}')
                    transformed_paths.add(path)
                if transformed_paths != set(existing.get('transform_paths', [])):
                    raise ValueError('completion must record every authorized in-place transformation')
                item['inputs'] = existing['inputs']
                if not pipeline_step_reusable(root, dict(item, status='complete')):
                    raise ValueError('pipeline completion failed current lineage validation')
                d['steps'][d['steps'].index(existing)] = item
            write(p, d)
        return [dict(step, reusable=pipeline_step_reusable(root, step)) for step in d['steps']]


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
                if 'expected_inputs' in t and t['before'] != t['expected_inputs']:
                    raise ValueError('campaign source differs from the approved input: ' + t['id'])
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
            if not checks.get('checks') or any(
                readiness(root, m, t['files'], profile='campaign_task')['readiness'] != 'ELIGIBLE'
                for m in checks['checks']
            ):
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
            d.update(checkpoints=[], execution='PENDING', isolation_status='PENDING')
            d['inputs'] = evidence(root, d['chapters'])
            write(p, d)
            return d
        d = load(p)
        n = len(d['checkpoints'])
        if any(evidence(root, [c['source']])[0] != c['input'] for c in d['checkpoints']):
            raise ValueError('earlier chapter changed: fork a run from last valid checkpoint')
        if n >= len(d['chapters']):
            return {'status': 'sealed', 'execution': d.get('execution', 'PENDING'),
                    'isolation_status': d.get('isolation_status', 'PENDING'), 'checkpoints': n}
        chapter = d['chapters'][n]
        source = path_at(root, chapter).read_text(encoding='utf-8')
        scene_break = d.get('scene_break', '* * *')
        extracted = reader_text_module().extract(
            source, source=chapter, scene_break=scene_break,
            pov_comment_lines=chapter_format_module().comment_lines(source, scene_break))
        packet = {'schema_version': 1, 'chapter_id': f'reading-unit-{n + 1:03}',
                  'reader_brief': d.get('reader_brief', ''), 'text': extracted['text'],
                  'reader_text_sha256': extracted['reader_text_sha256'],
                  'extractor_version': extracted['extractor_version'],
                  'memory': d['checkpoints'][-1]['reaction'] if n else None}
        if args.action == 'packet':
            write(base / f'coordinator-{n+1:03}.json', {
                'schema_version': VERSION, 'source': chapter,
                'input': evidence(root, [chapter])[0], 'raw_sha256': extracted['raw_sha256'],
                'reader_text_sha256': extracted['reader_text_sha256'],
                'extractor_version': extracted['extractor_version'], 'removed': extracted['removed'],
            })
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
        coordinator = load(base / f'coordinator-{n+1:03}.json')
        if coordinator.get('reader_text_sha256') != packet['reader_text_sha256']:
            raise ValueError('reader text changed; prepare a newly validated packet')
        checkpoint = {'source': chapter, 'input': evidence(root, [chapter])[0],
                      'reader_text_sha256': packet['reader_text_sha256'],
                      'extractor_version': packet['extractor_version'], 'reaction': reaction}
        d['checkpoints'].append(checkpoint)
        d['execution'] = 'COMPLETE'
        d['isolation_status'] = 'VERIFIED'
        write(base / f'Chapter-{n+1:03}.json', dict(schema_version=1, **checkpoint))
        write(p, d)
        return {'accepted': chapter, 'remaining': len(d['chapters']) - n - 1}


def step_start(root, book_id, *, run, step_id, profile, stage_role, chapter_selector,
               write_paths=None, transform_paths=None, extra_paths=None,
               attempt_id=None, predecessor_exists=None, isolation_status=None):
    resolver = project_manifest_module()
    book_record, chapter_record = resolver.resolve_chapter(root, book_id, chapter_selector)
    book_label = book_record.get('display_label', book_record['id'])
    ch_path = chapter_record['path']
    ch_sha = digest(path_at(root, ch_path))
    if not ch_sha:
        raise ValueError('chapter file missing: ' + ch_path)
    t_paths = list(dict.fromkeys(transform_paths or []))
    w_paths = list(dict.fromkeys([*(write_paths or []), *t_paths]))
    in_paths = [ch_path, *t_paths, *(extra_paths or [])]
    pred_id = resolver.predecessor(book_record, chapter_record)
    constraints = {'predecessor_exists': pred_id is not None if predecessor_exists is None else predecessor_exists}
    item = {
        'record_type': 'pipeline_step',
        'schema_version': 2,
        'id': step_id,
        'operation_id': run,
        'idempotency_key': f'{run}:{step_id}',
        'completion_profile': profile,
        'stage_role': stage_role,
        'subjects': [{'id': chapter_record['id'], 'path': ch_path, 'sha256': ch_sha}],
        'constraints': constraints,
        'authorized_writes': w_paths,
        'transform_paths': t_paths,
        'status': 'running',
        'inputs': evidence(root, in_paths),
    }
    if attempt_id:
        item['attempt_id'] = attempt_id
    if isolation_status:
        item['isolation_status'] = isolation_status
    return record_pipeline_step(root, book_label, run, 'record', item)


def step_complete(root, book_id, *, run, step_id, output_paths, transform_paths=None,
                  attempt_id=None, isolation_status=None,
                  permitted_input_manifest_sha256=None, sealed_reactions_sha256=None):
    resolver = project_manifest_module()
    book_record = resolver.resolve_book(root, book_id)
    book_label = book_record.get('display_label', book_record['id'])
    p = path_at(root, f'_Edits/{book_label}/pipeline/{run}.json')
    d = load_journal_raw(p)
    existing = next((step for step in d['steps'] if step.get('id') == step_id), None)
    if not existing or existing.get('status') != 'running':
        raise ValueError(f'running step not found: {step_id}')
    t_paths = list(existing.get('transform_paths', [])) if transform_paths is None else list(transform_paths)
    input_map = {e['path']: e for e in existing['inputs']}
    transformations = []
    for tpath in t_paths:
        before = input_map.get(tpath)
        if not before:
            raise ValueError(f'transform path missing from step inputs: {tpath}')
        transformations.append({'path': tpath, 'before': before, 'after': evidence(root, [tpath])[0]})
    item = {
        'record_type': 'pipeline_step',
        'schema_version': 2,
        'id': step_id,
        'operation_id': existing['operation_id'],
        'idempotency_key': existing['idempotency_key'],
        'completion_profile': existing['completion_profile'],
        'stage_role': existing['stage_role'],
        'subjects': existing['subjects'],
        'constraints': existing['constraints'],
        'authorized_writes': existing['authorized_writes'],
        'transform_paths': existing.get('transform_paths', []),
        'status': 'complete',
        'attempt_id': attempt_id or existing.get('attempt_id', step_id + '-attempt-1'),
        'inputs': existing['inputs'],
        'outputs': evidence(root, output_paths),
        'transformations': transformations,
    }
    iso = isolation_status or existing.get('isolation_status')
    if iso:
        item['isolation_status'] = iso
    if permitted_input_manifest_sha256:
        item['permitted_input_manifest_sha256'] = permitted_input_manifest_sha256
    if sealed_reactions_sha256:
        item['sealed_reactions_sha256'] = sealed_reactions_sha256
    return record_pipeline_step(root, book_label, run, 'record', item)


def load_journal_raw(path):
    if not path.is_file():
        raise ValueError('pipeline journal does not exist: ' + str(path))
    return json.loads(path.read_text(encoding='utf-8'))
