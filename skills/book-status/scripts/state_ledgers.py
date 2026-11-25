"""Editorial memory, knowledge events, relationship state, and continuity ledgers."""
import importlib.util
import json
from pathlib import Path
import re

from state_core import (
    VERSION, commit_ledger, continuity_module, digest, document, ledger_store_module,
    load, locked, manuscript_texts, now, path_at, project_manifest_module, source_valid, write,
)


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


def _parse_event_batch(spec_path, batch_path=None):
    raw = json.loads(Path(batch_path or spec_path).read_text(encoding='utf-8'))
    if isinstance(raw, list):
        return raw, True
    if isinstance(raw, dict) and isinstance(raw.get('events'), list):
        return raw['events'], True
    return [raw], False


def relationship_state(root, args):
    logical_path = 'Wiki/Story/relationship-events.json'
    store = ledger_store_module()
    if args.action == 'record':
        items, is_batch = _parse_event_batch(getattr(args, 'spec', None), getattr(args, 'events', None))
        if not items:
            raise ValueError('relationship record requires at least one event')
        required = ('id', 'relationship_id', 'observer', 'other', 'stance', 'status',
                    'book_id', 'scene_id', 'story_order', 'source', 'source_sha256', 'quote')
        pointer = store.current_pointer(root)
        d = store.load_ledger(root, logical_path, {'schema_version': VERSION, 'events': []})
        by_id = {old.get('id'): old for old in d['events'] if old.get('id')}
        known = set(by_id) | {item.get('id') for item in items if isinstance(item, dict) and item.get('id')}
        added, source_paths = [], []
        for raw_event in items:
            event = dict(raw_event)
            missing = [key for key in required if key not in event]
            if missing:
                raise ValueError('relationship event missing: ' + ', '.join(missing))
            if event['status'] not in ('planned', 'confirmed') or type(event['story_order']) is not int or event['story_order'] < 0:
                raise ValueError('relationship event needs planned/confirmed status and nonnegative integer story_order')
            if not event['quote'] or not source_valid(root, event):
                raise ValueError('relationship event requires current exact source evidence')
            existing = by_id.get(event['id'])
            if existing:
                if {k: v for k, v in existing.items() if k != 'created_at'} == event:
                    added.append(existing)
                    continue
                raise ValueError('relationship event ID exists with different content')
            if not set(event.get('supersedes', [])).issubset(known):
                raise ValueError('relationship event supersedes an unknown event')
            event['created_at'] = now()
            d['events'].append(event)
            by_id[event['id']] = event
            added.append(event)
            source_paths.append(event['source'])
        if source_paths:
            tx_id = 'relationship-' + (added[0]['id'] if len(added) == 1 else f'batch-{len(added)}-{digest(path_at(root, source_paths[0]))[:8]}')
            commit_ledger(root, logical_path, d, tx_id, sorted(set(source_paths)),
                          pointer.get('generation_id') if pointer else None)
        return {'recorded': len(added), 'events': added} if is_batch else added[0]

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
    store = ledger_store_module()
    if args.action == 'record':
        items, is_batch = _parse_event_batch(getattr(args, 'spec', None), getattr(args, 'events', None))
        if not items:
            raise ValueError('knowledge-state record requires at least one event')
        required = ('id', 'fact_id', 'observer', 'state', 'truth_status', 'event_kind',
                    'story_order', 'reader_order', 'confirmed', 'source', 'source_sha256', 'quote')
        allowed_states = ('knows', 'suspects', 'believes', 'disbelieves', 'forgets', 'exposed')
        pointer = store.current_pointer(root)
        d = store.load_ledger(root, logical_path, {'schema_version': VERSION, 'events': []})
        by_id = {old.get('id'): old for old in d['events'] if old.get('id')}
        known = set(by_id) | {item.get('id') for item in items if isinstance(item, dict) and item.get('id')}
        added, source_paths = [], []
        for raw_event in items:
            event = dict(raw_event)
            missing = [key for key in required if key not in event]
            if missing:
                raise ValueError('knowledge event missing: ' + ', '.join(missing))
            if event['state'] not in allowed_states or event['truth_status'] not in ('true', 'false', 'unknown'):
                raise ValueError('invalid epistemic state or objective truth status')
            if (type(event['story_order']) is not int or event['story_order'] < 0 or
                    type(event['reader_order']) is not int or event['reader_order'] < 0 or
                    type(event['confirmed']) is not bool):
                raise ValueError('knowledge positions must be nonnegative integers and confirmed must be boolean')
            if not event['quote'] or not source_valid(root, event):
                raise ValueError('knowledge event requires current exact source evidence')
            existing = by_id.get(event['id'])
            if existing:
                if {k: v for k, v in existing.items() if k != 'created_at'} == event:
                    added.append(existing)
                    continue
                raise ValueError('knowledge event ID exists with different content')
            if not set(event.get('supersedes', [])).issubset(known):
                raise ValueError('knowledge event supersedes an unknown event')
            event['created_at'] = now()
            d['events'].append(event)
            by_id[event['id']] = event
            added.append(event)
            source_paths.append(event['source'])
        if source_paths:
            tx_id = 'knowledge-' + (added[0]['id'] if len(added) == 1 else f'batch-{len(added)}-{digest(path_at(root, source_paths[0]))[:8]}')
            commit_ledger(root, logical_path, d, tx_id, sorted(set(source_paths)),
                          pointer.get('generation_id') if pointer else None)
        return {'recorded': len(added), 'events': added} if is_batch else added[0]

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


def reanchor_chapter(root, book_id, chapter_selector):
    """Re-anchor continuity claims, knowledge events, and relationship events whose exact quote survives a polish edit."""
    resolver = project_manifest_module()
    book, chapter = resolver.resolve_chapter(root, book_id, chapter_selector)
    ch_path = chapter['path']
    p = path_at(root, ch_path)
    if not p.is_file():
        raise ValueError('chapter file missing: ' + ch_path)
    text = p.read_bytes().decode('utf-8')
    new_sha = digest(p)
    lines = text.splitlines()

    def unique_line(quote):
        hits = [idx for idx, line in enumerate(lines, 1) if quote in line]
        return hits[0] if len(hits) == 1 else None

    runtime = continuity_module()
    cont_rel = f"{continuity_dir(book)}/{runtime.filename(chapter['id'])}"
    cont_p = path_at(root, cont_rel)
    continuity_result = {'path': cont_rel, 'status': 'MISSING', 'reanchored': 0, 'unresolved': []}
    if cont_p.is_file():
        with locked(cont_p):
            rec = load(cont_p)
            claims = rec.get('claims', [])
            unresolved = []
            updated_claims = []
            for idx, raw_claim in enumerate(claims):
                claim = dict(raw_claim)
                quote = claim.get('quote', '')
                ln = unique_line(quote) if quote else None
                if ln is None:
                    unresolved.append({'claim_index': idx, 'kind': claim.get('kind'), 'quote': quote,
                                       'reason': 'quote missing or non-unique in updated chapter'})
                else:
                    claim['line'] = ln
                if claim.get('kind') == 'support':
                    new_refs = []
                    for ref in claim.get('references', []):
                        if ref.get('path') == ch_path:
                            ref_line = unique_line(ref.get('quote', '')) if ref.get('quote') else None
                            if ref_line is None:
                                unresolved.append({'claim_index': idx, 'kind': 'support_ref', 'quote': ref.get('quote', ''),
                                                   'reason': 'reference quote missing or non-unique'})
                                new_refs.append(ref)
                            else:
                                new_refs.append({**ref, 'line': ref_line, 'source_sha256': new_sha})
                        else:
                            new_refs.append(ref)
                    claim['references'] = new_refs
                updated_claims.append(claim)
            if not unresolved and rec.get('source_sha256') != new_sha:
                runtime.validate_claims(updated_claims, text)
                rec['claims'] = updated_claims
                rec['source_sha256'] = new_sha
                write(cont_p, rec)
                continuity_result = {'path': cont_rel, 'status': 'REANCHORED',
                                     'reanchored': len(updated_claims), 'unresolved': []}
            elif unresolved:
                continuity_result = {'path': cont_rel, 'status': 'UNRESOLVED',
                                     'reanchored': 0, 'unresolved': unresolved}
            else:
                continuity_result = {'path': cont_rel, 'status': 'CURRENT',
                                     'reanchored': 0, 'unresolved': []}

    store = ledger_store_module()
    ledger_results = {}
    for key, logical_path in (('knowledge', 'Wiki/Story/knowledge-events.json'),
                              ('relationship', 'Wiki/Story/relationship-events.json')):
        pointer = store.current_pointer(root)
        d = store.load_ledger(root, logical_path)
        if not d:
            ledger_results[key] = {'status': 'MISSING', 'reanchored': 0, 'unresolved': []}
            continue
        reanchored_ids, unresolved_ids = [], []
        for event in d.get('events', []):
            if event.get('source') != ch_path or event.get('source_sha256') == new_sha:
                continue
            quote = event.get('quote', '')
            if quote and quote in text:
                event['source_sha256'] = new_sha
                reanchored_ids.append(event.get('id'))
            else:
                unresolved_ids.append({'id': event.get('id'), 'quote': quote,
                                       'reason': 'quote absent after edit'})
        if reanchored_ids:
            commit_ledger(root, logical_path, d, f'{key}-reanchor-{new_sha[:10]}', [ch_path],
                          pointer.get('generation_id') if pointer else None)
        ledger_results[key] = {
            'status': 'REANCHORED' if reanchored_ids else ('UNRESOLVED' if unresolved_ids else 'CURRENT'),
            'reanchored': len(reanchored_ids),
            'event_ids': reanchored_ids,
            'unresolved': unresolved_ids,
        }

    return {
        'chapter': chapter['path'],
        'chapter_id': chapter['id'],
        'source_sha256': new_sha,
        'continuity': continuity_result,
        'ledgers': ledger_results,
    }
