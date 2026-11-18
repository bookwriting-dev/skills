#!/usr/bin/env python3
"""Content-addressed Storycraft records. Python standard library; see --help."""
import argparse
import contextlib
import hashlib
import importlib.util
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


def reader_text_module():
    p = Path(__file__).with_name('reader_text.py')
    spec = importlib.util.spec_from_file_location('storycraft_reader_text', p)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ledger_store_module():
    p = Path(__file__).with_name('ledger_store.py')
    spec = importlib.util.spec_from_file_location('storycraft_ledger_store', p)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def project_manifest_module():
    p = Path(__file__).with_name('project_manifest.py')
    spec = importlib.util.spec_from_file_location('storycraft_project_manifest', p)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def chapter_format_module():
    p = Path(__file__).with_name('chapter_format.py')
    spec = importlib.util.spec_from_file_location('storycraft_chapter_format', p)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def continuity_module():
    p = Path(__file__).with_name('continuity.py')
    spec = importlib.util.spec_from_file_location('storycraft_continuity', p)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manuscript_texts(root, book):
    return {chapter['path']: path_at(root, chapter['path']).read_bytes().decode('utf-8')
            for chapter in book['chapters'] if path_at(root, chapter['path']).is_file()}


def chapter_report_paths(root, book, chapter, check=None):
    resolver = project_manifest_module()
    folder = path_at(root, f'_Edits/{book}')
    stem = resolver.report_stem(chapter)
    legacy = resolver.legacy_report_stem(chapter)
    suffix = f'_{check}.meta.json' if check else '_*.meta.json'
    primary = sorted(folder.glob(stem + suffix))
    if check and primary:
        return primary
    if legacy != stem:
        for path in sorted(folder.glob(legacy + suffix)):
            if any(item.get('path') == chapter['path'] for item in load(path).get('inputs', [])):
                primary.append(path)
    return primary or ([folder / (stem + suffix)] if check else [])


def continuity_dir(book):
    label = book.get('display_label', book['id'])
    if not isinstance(label, str) or not re.fullmatch(r'[\w-]+', label):
        label = book['id']
    if not isinstance(label, str) or not re.fullmatch(r'[\w-]+', label):
        raise ValueError('continuity requires a path-safe book ID or display label')
    return f'_Edits/{label}/continuity'


def support_findings(root, texts, claims):
    runtime = continuity_module()
    dependencies, source_texts, research_checks, findings = {}, {}, {}, []
    research_runtime = None

    def remember(name, checksum):
        if dependencies.setdefault(name, checksum) != checksum:
            raise ValueError(f'evidence changed during continuity review: {name}')

    for claim in claims:
        if claim['kind'] != 'support':
            continue
        sources = [claim]
        issues = []
        subject = path_at(root, claim['path'])
        for ref in claim['references']:
            path = path_at(root, ref['path'])
            name = path.relative_to(root).as_posix()
            if name not in source_texts:
                text = texts.get(ref['path'])
                if text is None and path.is_file():
                    text = path.read_bytes().decode('utf-8')
                source_texts[name] = text.splitlines() if text is not None else []
                remember(name, runtime.source_hash(text) if text is not None else None)
            lines = source_texts[name]
            line, quote = ref['line'], ref['quote']
            if dependencies[name] != ref['source_sha256'] or line > len(lines) or quote not in lines[line - 1]:
                issues.append(f'{name}:{line} is missing, changed, or lacks the quoted passage')
            elif path == subject and line == claim['line'] and (quote in claim['quote'] or claim['quote'] in quote):
                issues.append(f'{name}:{line} repeats the assertion itself as support')
            else:
                sources.append(dict(ref, path=name, chapter_id=None))

        research = claim.get('research')
        if research:
            path = path_at(root, research['path'])
            name = path.relative_to(root).as_posix()
            if name not in research_checks:
                result = None
                if path.is_file():
                    if research_runtime is None:
                        script = Path(__file__).resolve().parents[2] / 'nonfiction-research/scripts/evidence.py'
                        spec = importlib.util.spec_from_file_location('storycraft_research_evidence', script)
                        research_runtime = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(research_runtime)
                    result = research_runtime.audit(root, path)
                    for source, checksum in result['source_inputs'].items():
                        remember(source, checksum)
                else:
                    remember(name, None)
                research_checks[name] = result
            result = research_checks[name]
            if dependencies[name] != research['sha256'] or not result:
                issues.append(f'{name} is missing or its reviewed research record has changed')
            elif result['readiness'] != 'ELIGIBLE':
                issues.extend(result['blocking_reasons'])
            else:
                anchor = result['verified_anchors'].get(research['assertion_id'])
                lines = texts[claim['path']].splitlines(keepends=True)
                start = sum(len(line) for line in lines[:claim['line'] - 1])
                end = start + len(lines[claim['line'] - 1])
                if (path_at(root, result['subject_path']) != subject
                        or result['subject_sha256'] != claim['source_sha256']
                        or not anchor or anchor['quote'] != claim['quote']
                        or not start <= anchor['start'] < anchor['end'] <= end):
                    issues.append(f"{name} does not verify this exact chapter assertion and source span")

        category = None
        if issues:
            category = 'support-evidence-invalid'
            message = f"{claim['key']}: " + ' | '.join(issues)
        elif claim['assessment'] != 'supported':
            category = 'support-' + claim['assessment']
            message = f"{claim['key']}: {claim['rationale']}"
        if category:
            finding = runtime.finding(category, message, sources)
            if research:
                finding['research'] = research
            findings.append(finding)
    return findings, dependencies


def continuity_report(root, book, texts, *, chapter=None, keys=None):
    runtime = continuity_module()
    base = continuity_dir(book)
    required = book.get('continuity_required', False)
    if type(required) is not bool:
        raise ValueError('continuity_required must be a boolean')
    active = required or path_at(root, base).is_dir()
    chapters = sorted(book['chapters'], key=lambda item: item['reading_order'])
    if chapter:
        chapters = [item for item in chapters
                    if item['reading_order'] < chapter['reading_order']
                    or (keys is None and item['id'] == chapter['id'])]
    paths = {item['id']: f"{base}/{runtime.filename(item['id'])}" for item in chapters}
    sources = list(paths.values()) + [item['path'] for item in chapters]
    records = {}
    for chapter_id, name in paths.items():
        p = path_at(root, name)
        if p.exists():
            records[chapter_id] = load(p)
    coverage, claims = runtime.current_claims(chapters, texts, records)
    if keys is not None:
        context = runtime.context(coverage, claims, set(keys))
        findings, _ = support_findings(root, texts, context['claims'])
        return {'active': active, **context, 'support_findings': findings}
    support, support_inputs = support_findings(root, texts, claims)
    findings = runtime.reconcile(claims) + support
    if chapter:
        findings = [finding for finding in findings
                    if any(source['chapter_id'] == chapter['id'] for source in finding['sources'])]
    if not active:
        status = 'NOT_CONFIGURED'
    elif any(finding['blocking'] for finding in findings):
        status = 'FAIL'
    elif any(item['status'] != 'CURRENT' for item in coverage):
        status = 'UNKNOWN'
    else:
        status = 'WARN' if findings else 'PASS'
    return {'schema_version': VERSION, 'active': active, 'status': status,
            'coverage': coverage, 'findings': findings,
            'source_inputs': support_inputs,
            'inputs': sorted({project_manifest_module().MANIFEST_PATH, *sources, *support_inputs})}


def continuity_command(root, args):
    resolver = project_manifest_module()
    chapter = None
    if args.chapter:
        book, chapter = resolver.resolve_chapter(root, args.book, args.chapter)
    else:
        book = resolver.resolve_book(root, args.book)
    if args.action == 'record':
        if not chapter or not args.spec:
            raise ValueError('continuity record requires --chapter and --spec')
        spec = load(Path(args.spec))
        path = path_at(root, chapter['path'])
        runtime = continuity_module()
        output = path_at(root, f"{continuity_dir(book)}/{runtime.filename(chapter['id'])}")
        text = path.read_bytes().decode('utf-8')
        if spec.get('source_sha256') != runtime.source_hash(text):
            raise ValueError('continuity review source changed or source_sha256 is missing')
        if 'record_sha256' not in spec:
            raise ValueError('continuity review requires record_sha256 from the source command')
        runtime.validate_claims(spec.get('claims'), text)
        record = {'schema_version': VERSION, 'chapter_id': chapter['id'],
                  'path': chapter['path'], 'source_sha256': spec['source_sha256'],
                  'claims': spec['claims']}
        with locked(output):
            if (digest(path) != spec['source_sha256']
                    or resolver.resolve_chapter(root, args.book, args.chapter) != (book, chapter)):
                raise ValueError('continuity review inputs changed before recording')
            if not output.exists() or load(output) != record:
                if digest(output) != spec['record_sha256']:
                    raise ValueError('another review updated this continuity record; inspect its claims before retrying')
                write(output, record)
        return {'record': str(output.relative_to(root)), **record}
    if args.action not in ('list', 'audit', 'context', 'source'):
        raise ValueError('continuity action must be audit, context, source, or record')
    if args.action == 'source':
        if not chapter:
            raise ValueError('continuity source requires --chapter')
        record = f"{continuity_dir(book)}/{continuity_module().filename(chapter['id'])}"
        return {'chapter_id': chapter['id'], 'path': chapter['path'],
                'source_sha256': digest(path_at(root, chapter['path'])),
                'record_sha256': digest(path_at(root, record))}
    return continuity_report(root, book, manuscript_texts(root, book), chapter=chapter,
                             keys=(args.key or []) if args.action == 'context' else None)


def commit_ledger(root, logical_path, data, transaction_id, source_paths, expected_generation):
    store = ledger_store_module()
    return store.commit(root, {
        'transaction_id': transaction_id,
        'expected_generation': expected_generation,
        'source_evidence': evidence(root, source_paths) if source_paths else [],
        'updates': {logical_path: data},
    })


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


def readiness(root, meta_path, subject_paths=None, profile='draft_verified'):
    """Shared readiness predicate; execution, verdict, freshness and decision stay distinct."""
    root = root.resolve()
    meta_path = path_at(root, str(meta_path))
    if not meta_path.exists():
        return {'profile': profile, 'execution': 'PENDING', 'verdict': 'UNKNOWN',
                'freshness': 'UNKNOWN', 'readiness': 'UNKNOWN',
                'blocking_reasons': ['required review evidence is missing'], 'conditions': []}
    meta = load(meta_path)
    fresh = freshness(root, meta_path)
    required_subjects = list(subject_paths or meta.get('subject_paths', []))
    inputs = {item.get('path'): item for item in meta.get('inputs', [])}
    missing_subjects = []
    for name in required_subjects:
        current = evidence(root, [name])[0]
        captured = inputs.get(current['path'])
        if captured != current:
            missing_subjects.append(name)

    dispositions = {}
    report_sha = meta.get('report_sha256')
    for ledger in (root / '_Edits').glob('*/decisions.jsonl'):
        for line in ledger.read_text(encoding='utf-8').splitlines() if ledger.exists() else []:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if item.get('report_sha256') == report_sha and item.get('report') == meta.get('report'):
                dispositions[item.get('finding_id')] = item.get('disposition')

    blockers = []
    for finding in meta.get('findings', []):
        if finding.get('blocking') and dispositions.get(finding.get('id')) not in ('applied', 'rejected', 'superseded'):
            blockers.append(finding.get('id', 'unknown finding'))
    reasons = []
    if not required_subjects:
        reasons.append('review has no provable subject coverage')
    if fresh['freshness'] != 'CURRENT':
        reasons.extend(fresh.get('reasons', ['review evidence is not current']))
    if missing_subjects:
        reasons.append('review does not cover exact current subject(s): ' + ', '.join(missing_subjects))
    if fresh.get('verdict') != 'PASS':
        reasons.append('review verdict is not PASS')
    if blockers:
        reasons.append('unresolved blocking findings: ' + ', '.join(blockers))
    allowed_profiles = ('draft_verified', 'full_editorial_candidate', 'independent_editorial_gate', 'campaign_task')
    if profile not in allowed_profiles:
        reasons.append('unknown readiness profile: ' + str(profile))
    elif profile in ('full_editorial_candidate', 'independent_editorial_gate'):
        reasons.extend(operation_profile_blockers(root, meta, profile, required_subjects))
    eligible = not reasons
    return {
        'profile': profile, 'subject': required_subjects,
        'execution': 'COMPLETE', 'verdict': fresh.get('verdict', 'UNKNOWN'),
        'freshness': fresh['freshness'], 'readiness': 'ELIGIBLE' if eligible else 'INELIGIBLE',
        'blocking_reasons': reasons, 'blocking_findings': blockers, 'conditions': [],
        'evidence': [str(meta_path.relative_to(root))],
    }


def operation_profile_blockers(root, meta, profile, subject_paths):
    operation_id = meta.get('operation_id')
    if not isinstance(operation_id, str) or not re.fullmatch(r'[\w-]+', operation_id):
        return ['required profile lacks a linked operation journal']
    book_id = meta.get('book_id')
    if not book_id:
        parts = Path(subject_paths[0]).parts if subject_paths else ()
        book_id = parts[1] if len(parts) > 1 and parts[0] == 'Chapters' else 'Book-1'
    journal_path = path_at(root, f"_Edits/{book_id}/pipeline/{operation_id}.json")
    if not journal_path.is_file():
        return ['required operation journal is missing']
    journal = load(journal_path)
    if journal.get('record_type') != 'operation_journal' or journal.get('completion_profile') != profile:
        return ['operation journal profile does not match requested profile']
    steps = journal.get('steps', [])
    completed = [step for step in steps if step.get('status') == 'complete' and pipeline_step_reusable(root, step)]
    roles = {step.get('stage_role') for step in completed}
    required = {'developmental_assessment', 'developmental_checkpoint', 'line_edit',
                'integration_read', 'ledger_reconciliation', 'final_gate'}
    if 'developmental_repair' not in roles and 'developmental_no_change' not in roles:
        required.add('developmental_repair')
    constraints = journal.get('constraints', {})
    if constraints.get('predecessor_exists') is not False:
        required.add('seam_read')
    if profile == 'independent_editorial_gate':
        required.add('independent_reader')
        independent = next((step for step in completed if step.get('stage_role') == 'independent_reader'), None)
        if not independent or independent.get('isolation_status') != 'VERIFIED':
            return ['independent reader isolation is not verified']
        if not independent.get('permitted_input_manifest_sha256') or not independent.get('sealed_reactions_sha256'):
            return ['independent reader input manifest or sealed reactions are missing']
        first = next((step for step in steps if step.get('status') == 'complete'), None)
        if first is not independent:
            return ['independent reader reactions were not sealed before informed stages']
    missing = sorted(required - roles)
    if missing:
        return ['required profile stages are missing or stale: ' + ', '.join(missing)]
    role_order = [step.get('stage_role') for step in steps if step.get('status') == 'complete']
    sequence = (['independent_reader'] if profile == 'independent_editorial_gate' else []) + [
        'developmental_assessment', 'developmental_repair' if 'developmental_repair' in roles else 'developmental_no_change',
        'developmental_checkpoint', 'line_edit', 'integration_read', 'seam_read',
        'ledger_reconciliation', 'final_gate']
    positions = []
    cursor = -1
    for role in sequence:
        if role == 'seam_read' and role not in required:
            continue
        try:
            cursor = role_order.index(role, cursor + 1)
        except ValueError:
            return ['required profile stages are out of order: ' + role]
        positions.append(cursor)
    if positions != sorted(positions):
        return ['required profile stages are out of order']
    if role_order and role_order[-1] != 'final_gate':
        return ['final gate is not the last completed profile stage']
    current_subjects = {path for step in completed for subject in step.get('subjects', [])
                        for path in [subject.get('path')]}
    if not set(subject_paths).issubset(current_subjects):
        return ['operation journal does not cover the exact requested subject paths']
    final_gate = next((step for step in reversed(completed) if step.get('stage_role') == 'final_gate'), None)
    final_subject_hashes = {subject.get('path'): subject.get('sha256')
                            for subject in final_gate.get('subjects', [])} if final_gate else {}
    if not final_gate or any(final_subject_hashes.get(path) != digest(path_at(root, path))
                             for path in subject_paths):
        return ['final gate is not bound to the exact final subject revision']
    return []


def source_valid(root, item):
    return (isinstance(item.get('source'), str) and bool(item.get('quote')) and
            digest(path_at(root, item['source'])) == item.get('source_sha256') and
            item['quote'] in path_at(root, item['source']).read_text())


def document(path, key):
    return load(path) if path.exists() else {'schema_version': VERSION, key: []}


def scope_dimensions(scope):
    if isinstance(scope, dict):
        dimensions = {
            'book_id': scope.get('book_id') or scope.get('book'),
            'chapter_id': scope.get('chapter_id') or scope.get('chapter'),
            'pov_id': scope.get('pov_id') or scope.get('pov'),
            'passage_id': scope.get('passage_id') or scope.get('passage'),
        }
        return {key: value for key, value in dimensions.items() if value is not None}
    if not isinstance(scope, str):
        return None
    if scope == 'series':
        return {}
    parts = scope.split('/')
    dimensions = {}
    index = 0
    while index < len(parts):
        part = parts[index]
        if re.fullmatch(r'Book-[\w-]+', part):
            dimensions['book_id'] = part
        elif part == 'POV' and index + 1 < len(parts):
            index += 1
            dimensions['pov_id'] = parts[index]
        elif re.fullmatch(r'Chapter-\d+', part):
            dimensions['chapter_id'] = part
        elif part == 'Passage' and index + 1 < len(parts):
            index += 1
            dimensions['passage_id'] = parts[index]
        elif len(parts) == 1:
            # Legacy bare POV labels remain supported.
            dimensions['pov_id'] = part
        else:
            return None
        index += 1
    return {key: value for key, value in dimensions.items() if value is not None}


def scope_matches(decision, query_scope):
    required = scope_dimensions(decision.get('scope'))
    context = scope_dimensions(query_scope)
    if required is None or context is None:
        return False
    return all(context.get(key) == value for key, value in required.items())


def memory(root, args):
    p = path_at(root, 'Wiki/Style/editorial-decisions.json')
    if args.action == 'list':
        d = document(p, 'decisions')
        return [x for x in d['decisions'] if x.get('status') == 'active' and
                (not args.scope or scope_matches(x, args.scope))]
    item = load(Path(args.spec))
    for key in ('id', 'scope', 'rule_category', 'reason', 'status', 'reusable'):
        if key not in item:
            raise ValueError('decision missing ' + key)
    if item['rule_category'] in ('canon', 'fact', 'knowledge', 'numeric') and item['reusable']:
        raise ValueError('preferences cannot waive correctness')
    if item['status'] not in ('active', 'retired', 'superseded'):
        raise ValueError('invalid decision status')
    supersedes = item.get('supersedes', [])
    if not isinstance(supersedes, list) or not all(isinstance(value, str) for value in supersedes) or len(set(supersedes)) != len(supersedes):
        raise ValueError('supersedes must be a unique list of decision IDs')
    with locked(p):
        d = document(p, 'decisions')
        existing = next((x for x in d['decisions'] if x['id'] == item['id']), None)
        if existing:
            if {k: v for k, v in existing.items() if k != 'created_at'} == item:
                return existing
            raise ValueError('decision ID exists with different content; use a new superseding record')
        known = {x['id'] for x in d['decisions']}
        if not set(supersedes).issubset(known):
            raise ValueError('supersedes references unknown decision IDs')
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
    visible = [event for event in events if event['current'] and event['confirmed']
               and event['observer'] == args.observer and event[field] <= pos]
    superseded = {item for event in visible for item in event.get('supersedes', [])}
    for e in sorted(visible, key=lambda x: x[field]):
        if e['id'] not in superseded:
            state[e['fact_id']] = e
    return state


def relationship_state(root, args):
    logical_path = 'Wiki/Story/relationship-events.json'
    path = path_at(root, logical_path)
    store = ledger_store_module()
    if args.action == 'record':
        event = load(Path(args.spec))
        required = ('id', 'relationship_id', 'observer', 'other', 'stance', 'status',
                    'book_id', 'scene_id', 'story_order', 'source', 'source_sha256', 'quote')
        missing = [key for key in required if key not in event]
        if missing:
            raise ValueError('relationship event missing: ' + ', '.join(missing))
        if event['status'] not in ('planned', 'confirmed') or type(event['story_order']) is not int or event['story_order'] < 0:
            raise ValueError('relationship event needs planned/confirmed status and nonnegative integer story_order')
        if not event['quote'] or not source_valid(root, event):
            raise ValueError('relationship event requires current exact source evidence')
        pointer = store.current_pointer(root)
        d = store.load_ledger(root, logical_path, {'schema_version': VERSION, 'events': []})
        existing = next((old for old in d['events'] if old.get('id') == event['id']), None)
        if existing:
            if {k: v for k, v in existing.items() if k != 'created_at'} == event:
                return existing
            raise ValueError('relationship event ID exists with different content')
        known = {old.get('id') for old in d['events']}
        if not set(event.get('supersedes', [])).issubset(known):
            raise ValueError('relationship event supersedes an unknown event')
        event['created_at'] = now()
        d['events'].append(event)
        commit_ledger(root, logical_path, d, 'relationship-' + event['id'], [event['source']],
                      pointer.get('generation_id') if pointer else None)
        return event

    d = store.load_ledger(root, logical_path, {'schema_version': VERSION, 'events': []})
    if type(args.position) is not int or args.position < 0:
        raise ValueError('relationship query requires nonnegative integer --position story order')
    events = [dict(event, current=source_valid(root, event)) for event in d['events']]
    superseded = {event_id for event in events if event['current'] and event['status'] == 'confirmed'
                  for event_id in event.get('supersedes', [])}
    applicable = [event for event in events if event['current'] and event['status'] == 'confirmed'
                  and event['id'] not in superseded and event['observer'] == args.observer
                  and (not args.other or event['other'] == args.other)
                  and event['story_order'] < args.position]
    state = {}
    conflicts = []
    for event in sorted(applicable, key=lambda item: item['story_order']):
        key = (event['relationship_id'], event['observer'], event['other'])
        previous = state.get(key)
        if previous and previous['story_order'] == event['story_order'] and previous['stance'] != event['stance']:
            conflicts.append({'relationship_id': event['relationship_id'], 'story_order': event['story_order'],
                              'events': [previous['id'], event['id']]})
        else:
            state[key] = event
    planned = [event for event in events if event['current'] and event['status'] == 'planned'
               and event['observer'] == args.observer and event['story_order'] == args.position
               and (not args.other or event['other'] == args.other)
               and (not getattr(args, 'scene_id', None) or event['scene_id'] == args.scene_id)]
    return {'status': 'CHRONOLOGY_UNRESOLVED' if conflicts else 'RESOLVED',
            'observer': args.observer, 'story_order': args.position,
            'established': list(state.values()) if not conflicts else [],
            'planned_transitions': planned, 'conflicts': conflicts,
            'stale_events': [event['id'] for event in events if not event['current']]}


def knowledge_event_state(root, args):
    logical_path = 'Wiki/Story/knowledge-events.json'
    path = path_at(root, logical_path)
    store = ledger_store_module()
    if args.action == 'record':
        event = load(Path(args.spec))
        required = ('id', 'fact_id', 'observer', 'state', 'truth_status', 'event_kind',
                    'story_order', 'reader_order', 'confirmed', 'source', 'source_sha256', 'quote')
        missing = [key for key in required if key not in event]
        if missing:
            raise ValueError('knowledge event missing: ' + ', '.join(missing))
        allowed_states = ('knows', 'suspects', 'believes', 'disbelieves', 'forgets', 'exposed')
        if event['state'] not in allowed_states or event['truth_status'] not in ('true', 'false', 'unknown'):
            raise ValueError('invalid epistemic state or objective truth status')
        if (type(event['story_order']) is not int or event['story_order'] < 0 or
                type(event['reader_order']) is not int or event['reader_order'] < 0 or
                type(event['confirmed']) is not bool):
            raise ValueError('knowledge positions must be nonnegative integers and confirmed must be boolean')
        if not event['quote'] or not source_valid(root, event):
            raise ValueError('knowledge event requires current exact source evidence')
        pointer = store.current_pointer(root)
        d = store.load_ledger(root, logical_path, {'schema_version': VERSION, 'events': []})
        existing = next((old for old in d['events'] if old.get('id') == event['id']), None)
        if existing:
            if {k: v for k, v in existing.items() if k != 'created_at'} == event:
                return existing
            raise ValueError('knowledge event ID exists with different content')
        known = {old.get('id') for old in d['events']}
        if not set(event.get('supersedes', [])).issubset(known):
            raise ValueError('knowledge event supersedes an unknown event')
        event['created_at'] = now()
        d['events'].append(event)
        commit_ledger(root, logical_path, d, 'knowledge-' + event['id'], [event['source']],
                      pointer.get('generation_id') if pointer else None)
        return event

    d = store.load_ledger(root, logical_path, {'schema_version': VERSION, 'events': []})
    observer = args.observer
    position = args.reader_order if observer == 'reader' else args.story_order
    if type(position) is not int or position < 0:
        axis = '--reader-order' if observer == 'reader' else '--story-order'
        raise ValueError('knowledge-state query requires nonnegative integer ' + axis)
    axis = 'reader_order' if observer == 'reader' else 'story_order'
    events = [dict(event, current=source_valid(root, event)) for event in d['events']]
    visible = [event for event in events if event['current'] and event['confirmed']
               and event['observer'] == observer and event[axis] <= position]
    visible.sort(key=lambda event: (event[axis], event.get('created_at', ''), event['id']))
    state = {}
    conflicts = []
    applied_ids = set()
    for event in visible:
        prior = state.get(event['fact_id'])
        if prior and prior[axis] == event[axis] and prior['state'] != event['state']:
            conflicts.append({'fact_id': event['fact_id'], 'position': event[axis],
                              'events': [prior['id'], event['id']]})
            state.pop(event['fact_id'], None)
            continue
        for superseded_id in event.get('supersedes', []):
            if superseded_id in applied_ids:
                for fact_id, applied in list(state.items()):
                    if applied['id'] == superseded_id:
                        state.pop(fact_id, None)
        state[event['fact_id']] = event
        applied_ids.add(event['id'])
    return {'status': 'CHRONOLOGY_UNRESOLVED' if conflicts else 'RESOLVED',
            'observer': observer, 'axis': axis, 'position': position,
            'state': state if not conflicts else {}, 'conflicts': conflicts,
            'coverage': 'partial; missing events do not establish ignorance',
            'stale_events': [event['id'] for event in events if not event['current']]}


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
            # Source paths, raw hashes, and apparatus mappings remain coordinator-side.
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


def dashboard(root, book):
    resolver = project_manifest_module()
    book_record = resolver.resolve_book(root, book)
    workflow = resolver.workflow(root, book_record)
    chapters = []
    for chapter in sorted(book_record['chapters'], key=lambda item: item['reading_order']):
        draft = path_at(root, chapter['path'])
        reports = chapter_report_paths(root, book, chapter)
        required = [chapter_report_paths(root, book, chapter, check)[0]
                    for check in workflow['required_checks']]
        checks = []
        for meta in sorted(set(reports + required)):
            result = readiness(root, meta, [chapter['path']])
            status = freshness(root, meta) if meta.is_file() else {
                'freshness': 'UNKNOWN', 'verdict': 'UNKNOWN', 'reasons': result['blocking_reasons']}
            checks.append(dict(path=str(meta.relative_to(root)), blocking=result.get('blocking_findings', []),
                               required=meta in required, readiness=result['readiness'], **status))
        chapters.append(dict(chapter=chapter['path'], chapter_id=chapter['id'],
                             display_label=chapter.get('display_label', chapter['id']),
                             report_stem=resolver.report_stem(chapter), draft_exists=draft.is_file(),
                             ready=draft.is_file() and all(item['readiness'] == 'ELIGIBLE'
                                                           for item in checks if item['required'])
                             and not any(item['blocking'] for item in checks), checks=checks))
    campaigns = []
    for p in (root / '_Edits' / book / 'campaigns').glob('*/campaign.json'):
        d = load(p)
        expected = {}
        for task in sorted(d['tasks'], key=lambda x: x.get('completed_at', '')):
            expected.update({e['path']: e for e in task.get('after', [])})
        checks_ready = True
        for task in d['tasks']:
            for check in task.get('checks', []):
                result = readiness(root, check, task.get('files', []), profile='campaign_task')
                checks_ready = checks_ready and result['readiness'] == 'ELIGIBLE'
        current = (evidence(root, list(expected)) == sorted(expected.values(), key=lambda e: e['path']) and
                   all(t['status'] == 'complete' for t in d['tasks']) and checks_ready)
        campaigns.append(dict(path=str(p.relative_to(root)), current=current, tasks=d['tasks']))
    return dict(chapters=chapters, campaigns=campaigns, **workflow,
                missing_chapters=resolver.missing_chapters(root, book_record))


def pipeline_step_reusable(root, step):
    if step.get('status') != 'complete' or not step.get('inputs') or not step.get('outputs'):
        return False
    if (step.get('completion_profile') not in ('draft_verified', 'full_editorial_candidate', 'independent_editorial_gate') or
            not step.get('operation_id') or not step.get('idempotency_key') or
            not step.get('stage_role') or not step.get('subjects')):
        return False
    outputs = {item.get('path'): item for item in step['outputs']}
    if any(path not in step.get('authorized_writes', outputs) for path in outputs):
        return False
    # Inputs transformed in-place remain historical evidence; all other inputs
    # must still match their captured revision.
    transformed = {item.get('path') for item in step.get('transformations', [])}
    unchanged = [item for item in step['inputs']
                 if item.get('path') not in outputs and item.get('path') not in transformed]
    if unchanged and evidence(root, [item['path'] for item in unchanged]) != unchanged:
        return False
    return evidence(root, list(outputs)) == sorted(outputs.values(), key=lambda item: item['path'])


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


def decision_applies(decision, book_ids, chapter_ids, pov):
    """Resolve documented legacy scopes and explicit intersection scopes."""
    required = scope_dimensions(decision.get('scope'))
    if required is None:
        return False
    context = {'book_id': book_ids, 'chapter_id': chapter_ids, 'pov_id': (pov,)}
    return all(value in context.get(key, ()) for key, value in required.items())


def style_policy(root, args):
    resolver = project_manifest_module()
    book = resolver.find_book(resolver.load(root), args.book) or {}
    names = ('Wiki/Style/review_guide.md', 'Wiki/Style/Review Guide.md')
    if book.get('review_authority'):
        names = (book['review_authority'],)
    choices = [name for name in names if path_at(root, name).is_file()]
    hashes = {name: digest(path_at(root, name)) for name in choices}
    if len(set(hashes.values())) > 1:
        raise ValueError('conflicting review guides: ' + ', '.join(choices))
    if not choices and book.get('review_authority'):
        raise ValueError('declared review guide is missing: ' + names[0])
    guide = path_at(root, choices[0]).read_text(encoding='utf-8') if choices else ''
    sections = re.split(r'^##[ \t]+([^\n]+)\n', guide, flags=re.M)
    sections = dict(zip((name.strip().lower() for name in sections[1::2]), sections[2::2]))

    def fields(section, name):
        return [match.strip() for match in re.findall(
            rf'^[ \t]*[-*][ \t]+(?:\*\*)?{name}(?:\*\*)?:(?:\*\*)?[ \t]*(.+)$',
            sections.get(section, ''), re.M | re.I)]

    def limit(name, default):
        values = fields('simile rule', name)
        if not values:
            return default
        if len(values) == 1:
            value = values[0].strip('"')
            if value.lower() == 'unlimited':
                return None
            if re.fullmatch(r'[0-9]+', value):
                return int(value)
        raise ValueError(f'{name} in the review guide must be one nonnegative integer or unlimited')

    chapter_limit = limit('max_per_chapter', 3)
    policy = {
        'review_guide': choices[0] if choices else None,
        'inputs': list(names),
        'simile': {'max_per_chapter': chapter_limit, 'max_per_paragraph': limit('max_per_paragraph', 1),
                   'keep_examples': [value for value in fields('simile rule', 'keep_example')
                                     if not value.startswith('[')]},
        'punctuation': {key: value[-1] for key in ('em_dash', 'fragments')
                        if (value := fields('punctuation', key)) and not value[-1].startswith('[')},
    }
    if args.simile_count is not None:
        if args.simile_count < 0:
            raise ValueError('simile count must be nonnegative')
        policy['chapter_simile_budget_exceeded'] = chapter_limit is not None and args.simile_count > chapter_limit
    return policy


def pov_labels(text):
    values = re.findall(r'^[ \t]*(?:[-*][ \t]+)?(?:\*\*)?POV(?:\*\*)?:(?:\*\*)?[ \t]*(.+)$',
                        text, re.M | re.I)
    names = (name.strip(' *').split('(')[0].strip()
             for value in values for name in re.split(r'[,/|]| and ', value, flags=re.I))
    return list(dict.fromkeys(name for name in names if name and name.lower() != 'none'))


def scene_contexts(text, psych_povs, roster, multi):
    sections = list(re.finditer(r'^#{2,4}[ \t]+Scene[ \t]+(\d+)\b[^\n]*', text, re.M | re.I))
    chapter_povs = pov_labels(text[:sections[0].start()]) if sections else pov_labels(text)
    scopes = [(sec[1], text[sec.end():sections[index + 1].start() if index + 1 < len(sections) else len(text)])
              for index, sec in enumerate(sections)] or [('1', '')]
    named = {pov for _, body in scopes for pov in pov_labels(body)}
    # An opening label in a mixed-POV chapter cannot assign every later scene.
    fallback = chapter_povs or psych_povs
    if named - set(fallback) and fallback:
        fallback = []
    if not fallback and len(roster) == 1 and not multi:
        fallback = roster
    result = []
    ids = set()
    for number, body in scopes:
        scene_id = f'scene-{int(number)}'
        if scene_id in ids:
            raise ValueError(f'duplicate scene number in plan: {number}')
        ids.add(scene_id)
        labels = pov_labels(body) or fallback
        pov = labels[0] if len(labels) == 1 else None
        scope = {'id': scene_id, 'pov': pov,
                 'pov_status': 'RESOLVED' if pov else 'UNRESOLVED' if multi or labels or named else 'UNSPECIFIED'}
        for field in ('story_order', 'reader_order'):
            label = field.replace('_', ' ')
            match = re.search(rf'^[ \t]*(?:-[ \t]+)?(?:\*\*)?{label}:(?:\*\*)?[ \t]*(\d+)[ \t]*$',
                              body, re.M | re.I)
            if match:
                scope[field] = int(match[1])
        result.append(scope)
    return result


def scene_knowledge(root, book, chapter_num, scene, args, *, global_ledger, legacy_ledger, first):
    pov = scene['pov']
    observers = [pov, 'reader'] if pov else ['reader']
    if global_ledger:
        data = {'_coverage': {'status': 'PARTIAL', 'note': 'missing events do not establish ignorance'}}
        for field, observer in zip(('story_order', 'reader_order'), (pov, 'reader')):
            if not observer:
                continue
            position = scene.get(field, getattr(args, field, None) if first else None)
            if position is None:
                data[observer] = {'status': 'CHRONOLOGY_UNRESOLVED', 'reason': f'scene has no explicit {field}'}
            else:
                data[observer] = knowledge_event_state(root, argparse.Namespace(
                    action='as-of', observer=observer, story_order=position, reader_order=position, spec=None))
        return data
    if not legacy_ledger:
        return {}
    if chapter_num is None:
        return {'_coverage': {'status': 'PARTIAL'}, '_story_time': {'status': 'CHRONOLOGY_UNRESOLVED'}}
    result = {}
    for observer in observers:
        # Legacy records use chapter/scene/beat coordinates. Character knowledge stays
        # at chapter entry when the plan has no explicit chronology for later scenes.
        position = f'{chapter_num}.0'
        if observer == 'reader' and not first:
            position = f'{chapter_num}.{scene["id"].removeprefix("scene-")}.0'
        known = knowledge(root, argparse.Namespace(
            book=book, action='as-of', observer=observer, position=position))
        if known:
            result[observer] = known
    return result


def draft_packet(root, args):
    resolver = project_manifest_module()
    book_record, chapter_record = resolver.resolve_chapter(root, args.book, args.chapter or 'Chapter 1', allow_new=True)
    texts = manuscript_texts(root, book_record)
    if chapter_record not in book_record['chapters']:
        book_record = {**book_record, 'chapters': [*book_record['chapters'], chapter_record]}
    book = book_record.get('display_label', book_record['id'])
    book_chapters = sorted(book_record['chapters'], key=lambda chapter: chapter['reading_order'])
    chapter_index = book_chapters.index(chapter_record)
    label = chapter_record.get('display_label') or chapter_record['id']
    ch_match = re.fullmatch(r'(?:Chapter[- ]?)?(\d+)', str(label), re.I)
    ch_num = int(ch_match.group(1)) if ch_match else None
    chapter_scope_id = f'Chapter-{ch_num:03d}' if ch_num is not None else chapter_record['id']
    window = max(1, int(args.window))

    # 1. Scene plan
    scene_info = None
    stext = ''
    scene_candidates = ([path_at(root, chapter_record['scene_plan_path'])]
                        if chapter_record.get('scene_plan_path') else [])
    if ch_num is not None:
        scene_candidates.extend((root / 'Wiki' / 'Outline' / book_record.get('display_label', book) / f'Chapter_{ch_num:02d}_Scene.md',
                                 root / 'Wiki' / 'Outline' / book_record.get('display_label', book) / f'Chapter_{ch_num:03d}_Scene.md'))
    for cand in scene_candidates:
        if cand.is_file():
            stext = cand.read_text(encoding='utf-8')
            key_line = re.search(r'^\s*(?:\*\*)?Continuity keys:(?:\*\*)?\s*([^\n]+)', stext, re.M)
            scene_info = {
                'path': str(cand.relative_to(root)),
                'sha256': digest(cand),
                'continuity_keys': [key.strip() for key in key_line[1].split(',') if key.strip()] if key_line else [],
            }
            break

    # 2. Psych pass
    psych_info = None
    psych_povs = []
    psych_candidates = ([path_at(root, chapter_record['psych_path'])]
                        if chapter_record.get('psych_path') else [])
    if ch_num is not None:
        psych_candidates.extend((root / 'Wiki' / 'Psych' / book_record.get('display_label', book) / f'Chapter_{ch_num:02d}_Psych.md',
                                 root / 'Wiki' / 'Psych' / book_record.get('display_label', book) / f'Chapter_{ch_num:03d}_Psych.md'))
    for cand in psych_candidates:
        if cand.is_file():
            # Psych notes often put the POV character's age after the name.
            psych_povs = [name for name in pov_labels(cand.read_text(encoding='utf-8'))
                          if not re.fullmatch(r'(?:age[ \t]+)?\d+(?:[ \t]+years?[ \t]+old)?', name, re.I)]
            psych_info = {
                'path': str(cand.relative_to(root)),
                'sha256': digest(cand),
                **parse_psych(cand),
            }
            break

    # 3. Style guide & multi-POV voice prompts
    style_authority = project_manifest_module().resolve_style_guide(root, book)
    style_path = path_at(root, style_authority['path']) if style_authority.get('status') == 'RESOLVED' else None
    roster = []
    multi = False
    if style_path and style_path.is_file():
        sg_text = style_path.read_text(encoding='utf-8')
        names = re.findall(r'^pov_\d+:[ \t]*["\']?([^"\'\n]+)', sg_text, re.M)
        roster = list(dict.fromkeys(name.strip() for name in names if name.strip().lower() not in ('', 'none')))
        multi = len(roster) > 1 or bool(re.search(r'^pov_mode:[ \t]*["\']?(?:dual|multi)\b', sg_text, re.M | re.I))
    scenes = scene_contexts(stext, psych_povs, roster, multi)
    pov_names = list(dict.fromkeys(scene['pov'] for scene in scenes if scene['pov']))
    multi = multi or len(pov_names) > 1
    if scene_info:
        scene_info.update(scene_count=len(scenes), pov_characters=pov_names)
    voice_prompts = []
    seen_vp = set()
    style_dir = root / 'Wiki' / 'Style'
    for pov in pov_names:
        slug_full = re.sub(r'\s+', '_', pov.strip())
        slug_first = slug_full.split('_')[0]
        for cand_name in (f'voice_prompt_{slug_full}.md', f'voice_prompt_{slug_first}.md',
                          f'voice_prompt_{slug_full.lower()}.md', f'voice_prompt_{slug_first.lower()}.md'):
            vp = path_at(root, style_dir / cand_name)
            if vp.is_file() and vp not in seen_vp:
                seen_vp.add(vp)
                voice_prompts.append({'pov': pov, 'path': str(vp.relative_to(root)), 'sha256': digest(vp)})
                break
    default_vp = style_dir / 'voice_prompt.md'
    if not multi and default_vp.is_file() and default_vp not in seen_vp:
        voice_prompts.append({'pov': 'default', 'path': str(default_vp.relative_to(root)), 'sha256': digest(default_vp)})

    # 4. Active relationship checkpoints for Chapter N
    checkpoints = []
    char_dir = root / 'Wiki' / 'Characters'
    if char_dir.is_dir() and ch_num is not None:
        for cf in sorted(char_dir.glob('*.md')):
            if cf.stem.endswith('_sheet'):
                continue
            for cp in parse_checkpoints(cf, ch_num):
                cp['source'] = str(cf.relative_to(root))
                cp['source_sha256'] = digest(cf)
                checkpoints.append(cp)

    # 5. Immediate continuity tail from Chapter-(N-1)
    continuity_tail = None
    predecessor_id = resolver.predecessor(book_record, chapter_record)
    predecessor = next((item for item in book_chapters if item.get('id') == predecessor_id), None)
    if predecessor is None and ch_num is not None and ch_num > 1:
        predecessor_path = f'Chapters/{book}/Chapter-{ch_num - 1:03d}.md'
    else:
        predecessor_path = predecessor.get('path') if predecessor else None
    if predecessor_path:
        prev_ch = path_at(root, predecessor_path)
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
    trail_chapters = book_chapters[max(0, chapter_index-window):chapter_index]
    for trail in trail_chapters:
        t_path = path_at(root, trail['path'])
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
            recent_openers.append({'chapter': trail.get('display_label', trail['id']), 'chapter_id': trail['id'],
                                   'opener': ' '.join(first_w)})
        last_s = ''
        for l in reversed(t_lines):
            sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', l) if len(s.split()) >= 3]
            if sents:
                last_s = sents[-1]
                break
        if last_s:
            recent_closers.append({'chapter': trail.get('display_label', trail['id']), 'chapter_id': trail['id'],
                                   'closer': last_s})

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

    # 7. Apply only the narrator's knowledge and author preferences to each scene.
    ledger_store = ledger_store_module()
    global_knowledge = ledger_store.load_ledger(root, 'Wiki/Story/knowledge-events.json') is not None
    legacy_knowledge = path_at(root, f'Wiki/Story/{book}/knowledge.json').is_file()
    ed_path = path_at(root, 'Wiki/Style/editorial-decisions.json')
    decisions = [item for item in document(ed_path, 'decisions')['decisions'] if item.get('status') == 'active']
    book_ids = (book, book_record['id'])
    chapter_ids = (chapter_scope_id, chapter_record['id'])
    for index, scene in enumerate(scenes):
        scene['voice_prompts'] = [item for item in voice_prompts if item['pov'] in (scene['pov'], 'default')]
        scene['knowledge_as_of'] = scene_knowledge(root, book, ch_num, scene, args,
                                                  global_ledger=global_knowledge,
                                                  legacy_ledger=legacy_knowledge, first=index == 0)
        scene['editorial_decisions'] = [item for item in decisions
                                        if decision_applies(item, book_ids, chapter_ids, scene['pov'])]

    # 8. Optional series-wide relationship state requires explicit story order.
    relationship_as_of = []
    relationship_events = ledger_store.load_ledger(root, 'Wiki/Story/relationship-events.json')
    if relationship_events is not None:
        if getattr(args, 'story_order', None) is None:
            relationship_as_of = [{'status': 'CHRONOLOGY_UNRESOLVED', 'reason':
                                   'relationship event records exist but this packet has no explicit story order'}]
        else:
            for pov in pov_names:
                query = argparse.Namespace(action='as-of', observer=pov, other=None,
                                           position=args.story_order, scene_id=getattr(args, 'scene_id', None))
                relationship_as_of.append(relationship_state(root, query))

    formatting = chapter_format_module().audit(book_record, texts, selected=chapter_record['id'])
    keys = (scene_info or {}).get('continuity_keys', []) + (getattr(args, 'key', None) or [])
    packet = {
        'schema_version': VERSION,
        'book': book,
        'book_id': book_record['id'],
        'chapter_number': label,
        'chapter_id': chapter_record['id'],
        'chapter_path': chapter_record['path'],
        'report_stem': resolver.report_stem(chapter_record),
        'reading_order': chapter_record['reading_order'],
        'predecessor_id': predecessor_id,
        'scene_plan': scene_info,
        'scenes': scenes,
        'psych': psych_info,
        'style_authority': style_authority,
        'voice_prompts': voice_prompts,
        'relationship_checkpoints': checkpoints,
        'relationship_state_as_of': relationship_as_of,
        'continuity_tail': continuity_tail,
        'chapter_format': formatting['contract'],
        'continuity': continuity_report(root, book_record, texts, chapter=chapter_record, keys=keys),
        'knowledge_as_of': scenes[0]['knowledge_as_of'],
        'editorial_decisions': list({item['id']: item for scene in scenes
                                     for item in scene['editorial_decisions']}.values()),
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
    for cmd in ('prepare', 'snapshot', 'check', 'readiness', 'validate', 'dashboard', 'workflow', 'style-policy',
                'register-chapters', 'disposition', 'memory', 'knowledge', 'knowledge-state',
                'relationship-state', 'reading', 'campaign', 'pipeline', 'draft-packet', 'chapter-format', 'continuity'):
        p = sub.add_parser(cmd)
        p.add_argument('--spec')
        p.add_argument('--output')
        p.add_argument('--meta')
        p.add_argument('--action', default='list')
        p.add_argument('--scope')
        p.add_argument('--subject', action='append')
        p.add_argument('--profile', default='draft_verified')
        p.add_argument('--observer', default='reader')
        p.add_argument('--position', default='999999')
        p.add_argument('--story-order', type=int)
        p.add_argument('--reader-order', type=int)
        p.add_argument('--scene-id')
        p.add_argument('--run', default='default')
        p.add_argument('--task')
        p.add_argument('--chapter', default=None if cmd in ('chapter-format', 'continuity') else '1')
        p.add_argument('--window', type=int, default=3)
        if cmd in ('continuity', 'draft-packet'):
            p.add_argument('--key', action='append')
        if cmd == 'style-policy':
            p.add_argument('--simile-count', type=int)
    a = ap.parse_args()
    root = a.root.resolve()
    if not re.fullmatch(r'[\w-]+', a.book) or not re.fullmatch(r'[\w-]+', a.run):
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
    elif a.command == 'chapter-format':
        resolver = project_manifest_module()
        if a.chapter:
            book, chapter = resolver.resolve_chapter(root, a.book, a.chapter)
        else:
            book = resolver.resolve_book(root, a.book)
            chapter = None
        result = chapter_format_module().audit(book, manuscript_texts(root, book),
                                               selected=chapter['id'] if chapter else None)
        result['inputs'].append(resolver.MANIFEST_PATH)
        if chapter:
            result.update(chapter_id=chapter['id'], chapter_path=chapter['path'],
                          report_stem=resolver.report_stem(chapter))
    elif a.command == 'continuity':
        result = continuity_command(root, a)
    elif a.command == 'workflow':
        resolver = project_manifest_module()
        result = resolver.workflow(root, resolver.resolve_book(root, a.book))
        result['inputs'] = ['AGENTS.md', resolver.MANIFEST_PATH]
    elif a.command == 'style-policy':
        result = style_policy(root, a)
    elif a.command == 'register-chapters':
        if not a.spec:
            raise ValueError('register-chapters requires --spec')
        resolver = project_manifest_module()
        path = path_at(root, resolver.MANIFEST_PATH)
        with locked(path):
            current = resolver.load(root)
            old = json.dumps(current, sort_keys=True)
            result = resolver.register(root, a.book, load(Path(a.spec)), current)
            if not path.is_file() or json.dumps(result, sort_keys=True) != old:
                write(path, result)
    elif a.command == 'check':
        result = freshness(root, path_at(root, a.meta))
    elif a.command == 'readiness':
        result = readiness(root, a.meta, a.subject, profile=a.profile)
    elif a.command == 'relationship-state':
        if a.action != 'record' and a.story_order is None:
            raise ValueError('relationship-state query requires --story-order')
        result = relationship_state(root, argparse.Namespace(action=a.action, spec=a.spec,
            observer=a.observer, other=a.scope, position=a.story_order, scene_id=a.scene_id))
    elif a.command == 'knowledge-state':
        if a.action != 'record' and (a.observer == 'reader' and a.reader_order is None or
                                     a.observer != 'reader' and a.story_order is None):
            raise ValueError('knowledge-state query requires the position for the selected observer axis')
        result = knowledge_event_state(root, argparse.Namespace(action=a.action, spec=a.spec,
            observer=a.observer, story_order=a.story_order, reader_order=a.reader_order))
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
                item = json.loads(Path(a.spec).read_text(encoding='utf-8'))
                validate_pipeline_step(item, a.run)
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
                            result = [dict(step, reusable=pipeline_step_reusable(root, step)) for step in d['steps']]
                            print(json.dumps(result, indent=2, ensure_ascii=False))
                            return 0
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
                    input_map = {e.get('path'): e for e in existing['inputs']}
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
            result = [dict(step, reusable=pipeline_step_reusable(root, step)) for step in d['steps']]
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
