"""Review freshness, readiness, operation-profile validation, and dashboard views."""
import json
from pathlib import Path
import re
from uuid import uuid4

import editions
from chapter_format import DEFAULT_SCENE_BREAK, metadata as chapter_metadata
from state_packets import pov_labels, voice_roster, voice_sources
import state_projections as projections
from state_core import (
    PLUGIN_SKILL_INPUT, PLUGIN_VERSION, VERSION, digest, evidence, load, locked, manuscript_texts, now,
    path_at, plugin_skill_input, project_manifest_module, write,
)


def current_inputs(root, items):
    """Re-evaluate recorded review inputs (plain evidence records and chapter projections)."""
    return projections.current_inputs(root, items)


def subject_lineage(steps, initial=()):
    """Every subject/output hash a journal has legitimately recorded, per path."""
    lineage = {}

    def add(entry):
        if isinstance(entry, dict) and entry.get('path') and entry.get('sha256'):
            lineage.setdefault(entry['path'], set()).add(entry['sha256'])

    for entry in initial:
        add(entry)
    for step in steps:
        if step.get('status') != 'complete':
            continue
        for entry in [*step.get('subjects', []), *step.get('outputs', [])]:
            add(entry)
        for transform in step.get('transformations', []):
            add(transform.get('before'))
            add(transform.get('after'))
    return lineage


def campaign_expected(campaign_record):
    expected = {}
    for task in sorted(campaign_record['tasks'], key=lambda x: x.get('completed_at', '')):
        expected.update({e['path']: e for e in task.get('after', [])})
    return expected


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


def freshness(root, meta):
    if not meta.exists():
        return {'freshness': 'UNKNOWN', 'reasons': ['no review metadata']}
    m = load(meta)
    if not m.get('inputs') or not m.get('report'):
        raise ValueError('review metadata requires inputs and report')
    reasons = review_input_changes(root, m)
    if digest(path_at(root, m['report'])) != m.get('report_sha256'):
        reasons.append('report body changed')
    return {'freshness': 'STALE' if reasons else 'CURRENT', 'reasons': reasons,
            'verdict': m.get('verdict', 'UNKNOWN')}


def pipeline_step_reusable(root, step, lineage=None):
    """A completed step is reusable while its evidence matches, or has advanced along the journal's lineage.

    `lineage` maps a path to the hashes the journal recorded for it. A later step that legitimately
    transformed the chapter does not make an earlier step's historical evidence stale; an edit that
    no recorded step produced still does.
    """
    if step.get('status') != 'complete' or not step.get('inputs') or not step.get('outputs'):
        return False
    lineage = lineage or {}

    def advanced(item):
        hashes = lineage.get(item.get('path'), set())
        return bool(hashes) and item.get('sha256') in hashes and digest(path_at(root, item['path'])) in hashes

    if (step.get('completion_profile') not in ('draft_verified', 'full_editorial_candidate', 'independent_editorial_gate') or
            not step.get('operation_id') or not step.get('idempotency_key') or
            not step.get('stage_role') or not step.get('subjects')):
        return False
    outputs = {item.get('path'): item for item in step['outputs']}
    if any(path not in step.get('authorized_writes', outputs) for path in outputs):
        return False
    transformed = {item.get('path') for item in step.get('transformations', [])}
    unchanged = [item for item in step['inputs']
                 if item.get('path') not in outputs and item.get('path') not in transformed]
    current = {entry['path']: entry for entry in evidence(root, [item['path'] for item in unchanged])} if unchanged else {}
    if any(current[item['path']] != item and not advanced(item) for item in unchanged):
        return False
    now_outputs = {entry['path']: entry for entry in evidence(root, list(outputs))}
    return all(now_outputs[path] == item or advanced(item) for path, item in outputs.items())


def operation_profile_blockers(root, meta, profile, subject_paths):
    operation_id = meta.get('operation_id')
    if not isinstance(operation_id, str) or not re.fullmatch(r'[\w-]+', operation_id):
        return ['required profile lacks a linked operation journal']
    book_id = meta.get('book_id')
    if not book_id:
        parts = Path(subject_paths[0]).parts if subject_paths else ()
        book_id = parts[1] if len(parts) > 1 and parts[0] == 'Chapters' else 'Book-1'
    journal_path = project_manifest_module().edit_artifact(root, book_id, f'pipeline/{operation_id}.json')
    if not journal_path.is_file():
        return ['required operation journal is missing']
    journal = load(journal_path)
    if journal.get('record_type') != 'operation_journal' or journal.get('completion_profile') != profile:
        return ['operation journal profile does not match requested profile']
    steps = journal.get('steps', [])
    lineage = subject_lineage(steps, journal.get('initial_subjects', journal.get('subjects', [])))
    completed = [step for step in steps
                 if step.get('status') == 'complete' and pipeline_step_reusable(root, step, lineage)]
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
        'freshness_reasons': fresh['reasons'],
        'freshness': fresh['freshness'], 'readiness': 'ELIGIBLE' if eligible else 'INELIGIBLE',
        'blocking_reasons': reasons, 'blocking_findings': blockers, 'conditions': [],
        'evidence': [str(meta_path.relative_to(root))],
    }


def dashboard(root, book, *, view='full', chapter=None):
    if view not in ('full', 'compact'):
        raise ValueError('dashboard view must be full or compact')
    resolver = project_manifest_module()
    if chapter is None:
        book_record, selected = resolver.resolve_book(root, book), None
    else:
        book_record, selected = resolver.resolve_chapter(root, book, chapter)
    book_label = book_record.get('display_label', book_record['id'])
    workflow = resolver.workflow(root, book_record)
    chapters = []
    roster = [selected] if selected and view == 'full' else book_record['chapters']
    for chapter in sorted(roster, key=lambda item: item['reading_order']):
        draft = path_at(root, chapter['path'])
        reports = chapter_report_paths(root, book_label, chapter)
        ch_workflow = resolver.workflow(root, book_record, chapter=chapter)
        required = [chapter_report_paths(root, book_label, chapter, check)[0]
                    for check in ch_workflow['required_checks']]
        checks = []
        for meta in sorted(set(reports + required)):
            result = readiness(root, meta, [chapter['path']])
            checks.append(dict(path=str(meta.relative_to(root)), blocking=result.get('blocking_findings', []),
                               required=meta in required, readiness=result['readiness'], verdict=result['verdict'],
                               freshness=result['freshness'], blocking_reasons=result['blocking_reasons'],
                               reasons=result.get('freshness_reasons', result['blocking_reasons'])))
        chapters.append(dict(chapter=chapter['path'], chapter_id=chapter['id'],
                             display_label=chapter.get('display_label', chapter['id']),
                             report_stem=resolver.report_stem(chapter), draft_exists=draft.is_file(),
                             ready=draft.is_file() and all(item['readiness'] == 'ELIGIBLE'
                                                           for item in checks if item['required'])
                             and not any(item['blocking'] for item in checks), checks=checks))
    campaigns = []
    for p in resolver.edit_files(root, book_record, 'campaigns/*/campaign.json'):
        d = load(p)
        sealed, cancelled = bool(d.get('sealed')), bool(d.get('cancelled'))
        if sealed or cancelled:
            # Authoring after a sealed (or abandoned) campaign is governed by the chapters' own reviews.
            campaigns.append(dict(path=str(p.relative_to(root)), current=True, sealed=sealed,
                                  cancelled=cancelled, tasks=d['tasks']))
            continue
        expected = campaign_expected(d)
        checks_ready = True
        for task in d['tasks']:
            for check in task.get('checks', []):
                result = readiness(root, check, task.get('files', []), profile='campaign_task')
                checks_ready = checks_ready and result['readiness'] == 'ELIGIBLE'
        current = (evidence(root, list(expected)) == sorted(expected.values(), key=lambda e: e['path']) and
                   all(t['status'] == 'complete' for t in d['tasks']) and checks_ready)
        campaigns.append(dict(path=str(p.relative_to(root)), current=current, sealed=False,
                              cancelled=False, tasks=d['tasks']))
    progress = resolver.edit_artifact(root, book_record, 'author-read/progress.json')
    base = progress.parent
    author = {'personally_read': 0, 'reported_complete': 0}
    if progress.is_file():
        log = load(progress)
        if log.get('marks'):
            report = editions.reading_status(root, book, log, base, editions.current(root, book, allow_empty=True))
            author = {key: report[key] for key in ('personally_read', 'reported_complete', 'bookmark')}
    missing = resolver.missing_chapters(root, book_record)
    if view == 'full':
        return dict(chapters=chapters, campaigns=campaigns, author_read=author, **workflow, missing_chapters=missing)
    return compact_dashboard(book_record, workflow, chapters, missing, campaigns, author, selected)


def compact_dashboard(book, workflow, chapters, missing, campaigns, author, selected):
    drafted = sum(row['draft_exists'] for row in chapters)
    ready = sum(row['ready'] for row in chapters)
    missing_count = sum(group.get('count', 1) for group in missing)
    counts = dict(expected=drafted + missing_count, drafted=drafted, ready=ready,
                  needs_review=drafted - ready, missing_drafts=missing_count)

    first = None
    first_missing = min(missing, key=lambda group: group['reading_order'], default=None)
    rows = {row['chapter_id']: row for row in chapters}
    for record in sorted(book['chapters'], key=lambda item: item['reading_order']):
        if first_missing and first_missing['reading_order'] <= record['reading_order']:
            break
        row = rows[record['id']]
        if row['ready']:
            continue
        check = next(check for check in row['checks']
                     if check['blocking'] or (check['required'] and check['readiness'] != 'ELIGIBLE'))
        first = dict(chapter_id=row['chapter_id'], label=row['display_label'], path=row['chapter'],
                     check=check['path'], reason=check['blocking_reasons'][0])
        break
    if first is None and first_missing:
        first = dict(first_missing, reason='expected draft is missing')
    outstanding = [item for item in campaigns if not item['current']]
    summary = dict(view='compact', book=book.get('display_label', book['id']), book_id=book['id'],
                   counts=counts, first_blocker=first, **workflow,
                   campaigns={'count': len(campaigns), 'needs_attention': len(outstanding),
                              'first_blocker': outstanding[0]['path'] if outstanding else None},
                   author_read={key: author[key] for key in ('personally_read', 'reported_complete')})
    if selected:
        summary['chapter'] = rows[selected['id']]
    return summary


REVIEW_TYPE_SKILLS = {
    'Gate': 'gate-check',
    'Review': 'fiction-reviewchapter',
    'DevEdit': 'fiction-dev-editor',
    'NonfictionDevEdit': 'nonfiction-dev-editor',
    'LineEdit': 'fiction-line-editor',
    'Prose': 'fiction-prose-editor',
    'AIisms': 'fiction-aiism-editor',
    'FullEdit': 'fiction-full-editor',
    'LevelUp': 'levelup',
    'FragmentHunt': 'fragment-hunter',
    'StatAudit': 'litrpg-audit',
    'Knowledge': 'fiction-knowledge',
    'FactCheck': 'nonfiction-factcheck',
    'ClarityEdit': 'nonfiction-clarity-edit',
}


def _review_inputs(root, book_record, chapter_record, review_type, extra_paths):
    resolver = project_manifest_module()
    book_label = book_record.get('display_label', book_record['id'])
    stem = resolver.report_stem(chapter_record)
    chapter_text = path_at(root, chapter_record['path']).read_text(encoding='utf-8', errors='replace')
    paths = [chapter_record['path'], 'AGENTS.md']
    ordered = sorted(book_record['chapters'], key=lambda c: c['reading_order'])
    through = [c['path'] for c in ordered if c['reading_order'] <= chapter_record['reading_order']]
    label_number = re.search(r'\d+', str(chapter_record.get('display_label', '')))
    chapter_number = int(label_number.group(0)) if label_number else chapter_record['reading_order']
    projected = [
        projections.make(root, 'promises', f'Wiki/Story/{book_label}/promises.yaml', chapter_number=chapter_number),
        projections.make(root, 'events', 'Wiki/Story/knowledge-events.json', sources=through),
        projections.make(root, 'events', 'Wiki/Story/relationship-events.json', sources=through),
        projections.make(root, 'decisions', 'Wiki/Style/editorial-decisions.json',
                         book_ids=sorted({book_label, book_record['id']}),
                         chapter_ids=sorted({chapter_record['id'], f'Chapter-{chapter_number:03d}'}),
                         chapter_path=chapter_record['path']),
    ]
    legacy_knowledge = f'Wiki/Story/{book_label}/knowledge.json'
    legacy_events = projections.selected_events(root, legacy_knowledge, through)
    if legacy_events:
        projected.append(legacy_events)
    paths.extend(projections.canon_files(root, chapter_text))

    predecessor_id = resolver.predecessor(book_record, chapter_record)
    predecessor = next((c for c in book_record['chapters'] if c.get('id') == predecessor_id), None)
    if predecessor and path_at(root, predecessor['path']).is_file():
        paths.append(predecessor['path'])

    ch_match = re.fullmatch(r'Chapter-(\d+)', stem)
    ch_num = int(ch_match.group(1)) if ch_match else None
    plan_candidates = ([chapter_record['scene_plan_path']] if chapter_record.get('scene_plan_path') else [])
    if ch_num is not None:
        plan_candidates.extend([
            f'Wiki/Outline/{book_label}/Chapter_{ch_num:02d}_Scene.md',
            f'Wiki/Outline/{book_label}/Chapter_{ch_num:03d}_Scene.md',
        ])
    plan_candidates.append(f'Wiki/Outline/{book_label}/plan.md')
    plan_path = plan_candidates[-1]
    chapter_plan = None
    for cand in plan_candidates:
        if path_at(root, cand).is_file():
            if cand == plan_path:
                shared_plan = projections.selected_plan(root, cand, chapter_number)
                if shared_plan:
                    projected.append(shared_plan)
            else:
                paths.append(cand)
                chapter_plan = path_at(root, cand)
            break

    psych_candidates = ([chapter_record['psych_path']] if chapter_record.get('psych_path') else [])
    if ch_num is not None:
        psych_candidates.extend([
            f'Wiki/Psych/{book_label}/Chapter_{ch_num:02d}_Psych.md',
            f'Wiki/Psych/{book_label}/Chapter_{ch_num:03d}_Psych.md',
        ])
    for cand in psych_candidates:
        if path_at(root, cand).is_file():
            paths.append(cand)
            break

    style_auth = resolver.resolve_style_guide(root, book_label)
    if style_auth.get('status') == 'CONFLICT':
        raise ValueError('conflicting style guides: ' + ', '.join(style_auth['paths']))
    if style_auth.get('status') == 'RESOLVED':
        paths.append(style_auth['path'])
    if review_type in ('FullEdit', 'LineEdit'):
        style_path = path_at(root, style_auth['path']) if style_auth.get('status') == 'RESOLVED' else None
        roster, multi = voice_roster(style_path)
        scene_break = book_record.get('chapter_format', {}).get('scene_break', DEFAULT_SCENE_BREAK)
        _, slots = chapter_metadata(chapter_text, scene_break)
        names = [marker[3] for _, marker in slots if marker and marker[3]]
        if chapter_plan:
            names.extend(pov_labels(chapter_plan.read_text(encoding='utf-8')))
        if not names and len(roster) == 1:
            names = roster
        names = list(dict.fromkeys(names))
        _, _, voice_paths = voice_sources(root, names, multi or len(names) > 1, roster)
        paths.extend(voice_paths)
    for rg in ('Wiki/Style/review_guide.md', 'Wiki/Style/Review Guide.md'):
        if path_at(root, rg).is_file():
            paths.append(rg)

    if review_type in ('FactCheck', 'ClarityEdit'):
        ev_file = f'_Edits/{book_label}/evidence/{stem}.json'
        if path_at(root, 'Wiki/Concept').is_dir():
            paths.append('Wiki/Concept')
        research_plan = chapter_plan.relative_to(root).as_posix() if chapter_plan else plan_path
        research = projections.selected_research(root, ev_file, research_plan, chapter_number)
        if research:
            projected.append(research)
        if path_at(root, ev_file).is_file():
            paths.append(ev_file)

    skill_name = REVIEW_TYPE_SKILLS.get(review_type)
    if review_type == 'DevEdit' and resolver.workflow(root, book_record, chapter=chapter_record)['project_type'] == 'NONFICTION':
        skill_name = REVIEW_TYPE_SKILLS['NonfictionDevEdit']
    plugin_input = plugin_skill_input(skill_name) if skill_name else None
    if skill_name and plugin_input is None and path_at(root, f'.agents/skills/{skill_name}').is_dir():
        paths.append(f'.agents/skills/{skill_name}')

    paths.extend(extra_paths)

    inputs = evidence(root, paths) + sorted(projected, key=lambda i: (i['path'], i['projection']))
    if plugin_input is not None:
        inputs.append(plugin_input)
    return inputs


def _legacy_review_selection(spec):
    subjects = spec.get('subject_paths', [])
    if len(subjects) != 1 or not spec.get('book_id'):
        return None
    inputs = spec['inputs']
    # The scoped decisions projection identifies an ergonomic chapter capture even when the
    # author supplied a custom report name. Raw prepare/snapshot records use explicit paths.
    if not any(item.get('projection') == 'decisions' and item.get('chapter_path') == subjects[0]
               for item in inputs):
        return None
    skills = {item['path'] for item in inputs if item.get('kind') == PLUGIN_SKILL_INPUT}
    if not skills:
        skills = {Path(item['path']).name for item in inputs if item.get('kind') == 'directory'
                  and Path(item['path']).parent == Path('.agents/skills')}
    matches = [name for name, skill in REVIEW_TYPE_SKILLS.items() if skill in skills]
    suffix = Path(spec.get('report', '')).stem.rsplit('_', 1)[-1]
    review_type = suffix if suffix in REVIEW_TYPE_SKILLS else None
    if len(matches) == 1:
        review_type = matches[0]
    # An unknown check still consumed the rules, guides, plans, and canon shared by chapter reviews.
    return {'book': spec['book_id'], 'chapter': subjects[0], 'review_type': review_type}


def review_input_changes(root, spec):
    """Resolve the chapter's applicable evidence again, including sources introduced after capture."""
    previous = spec['inputs']
    selection = spec.get('review_selection') or _legacy_review_selection(spec)

    def key(item):
        return item['path'], item.get('projection', ''), item.get('kind') == PLUGIN_SKILL_INPUT

    before = {key(item): item for item in previous}
    current = {}
    if selection is not None:
        try:
            book, chapter = project_manifest_module().resolve_chapter(root, selection['book'], selection['chapter'])
            selected = _review_inputs(root, book, chapter, selection['review_type'], selection.get('extra_paths', []))
            current = {key(item): item for item in selected}
        except (OSError, ValueError) as exc:
            return ['cannot resolve review inputs: ' + str(exc)]
    if 'review_selection' not in spec:
        # Raw snapshots use explicit paths. Old chapter reviews may also have included manual extra paths.
        for name, item in before.items():
            if name not in current:
                # An old shared-plan projection was selected automatically. If its applicable
                # section still exists but another plan supersedes it, preserving the old file
                # as an extra input would hide the change in authority.
                if (selection and item.get('projection') == 'plan' and path_at(root, item['path']).is_file()
                        and projections.selected_plan(root, item['path'], item['chapter_number'])):
                    continue
                current[name] = projections.current_input(root, item)

    changes = []
    for name in sorted(before.keys() | current.keys()):
        old, new = before.get(name), current.get(name)
        if old == new:
            continue
        item = old or new
        if item.get('kind') == PLUGIN_SKILL_INPUT:
            changes.append('changed plugin review skill: ' + item['path'])
        else:
            label = f" ({item['projection']} as of chapter)" if item.get('kind') == projections.PROJECTION else ''
            changes.append('changed input: ' + item['path'] + label)
    return changes


def review_begin(root, book_id, chapter_selector, review_type, *, output=None, extra_paths=None):
    resolver = project_manifest_module()
    book_record, chapter_record = resolver.resolve_chapter(root, book_id, chapter_selector)
    book_label = book_record.get('display_label', book_record['id'])
    stem = resolver.report_stem(chapter_record)
    report_rel = f'_Edits/{book_label}/{stem}_{review_type}.md'
    extras = sorted({path_at(root, path).relative_to(root.resolve()).as_posix() for path in extra_paths or []})
    inputs = _review_inputs(root, book_record, chapter_record, review_type, extras)
    spec = {
        'schema_version': VERSION,
        'book_id': book_label,
        'review_selection': {'book': book_record['id'], 'chapter': chapter_record['id'],
                             'review_type': review_type, 'extra_paths': extras},
        'report': report_rel,
        'verdict': 'WARN',
        'subject_paths': [chapter_record['path']],
        'inputs': inputs,
    }
    if any(item.get('kind') == PLUGIN_SKILL_INPUT for item in inputs):
        spec['storycraft_version'] = PLUGIN_VERSION
    capture_id = uuid4().hex
    spec['capture_id'] = capture_id
    out_rel = output or f'_Edits/{book_label}/review-captures/{stem}_{review_type}.{capture_id}.prepared.json'
    out_path = path_at(root, out_rel)
    with locked(out_path):
        if out_path.exists():
            raise ValueError(f'review capture already exists: {out_rel}; choose a new output path')
        write(out_path, spec)
    return {'prepared': str(out_path.relative_to(root)), **spec}


def review_finish(root, prepared_path, verdict, *, report=None, output=None, findings=None, operation_id=None):
    prep_p = Path(prepared_path)
    if not prep_p.is_absolute():
        prep_p = path_at(root, prepared_path)
    spec = load(prep_p)
    changes = review_input_changes(root, spec) if spec.get('inputs') else ['missing pre-review evidence']
    if changes:
        raise ValueError('review inputs changed or pre-review evidence missing: ' + ', '.join(changes))
    report_rel = report or spec.get('report')
    if not report_rel:
        raise ValueError('missing report path')
    report_path = path_at(root, report_rel)
    if not report_path.is_file() or verdict not in ('PASS', 'WARN', 'FAIL'):
        raise ValueError('missing report or invalid verdict')
    spec['report'] = str(report_path.relative_to(root))
    spec['verdict'] = verdict
    if findings is not None:
        spec['findings'] = findings
    if operation_id:
        spec['operation_id'] = operation_id
    spec.update(report_sha256=digest(report_path), created_at=now())
    out_rel = output or str(Path(spec['report']).with_suffix('.meta.json'))
    out_path = path_at(root, out_rel)
    if out_path == prep_p.resolve():
        raise ValueError('review metadata and prepared capture must have different paths')
    with locked(out_path):
        write(out_path, spec)
    return {'meta': str(out_path.relative_to(root)), **spec}


def record_dispositions_batch(root, book_id, *, report, items):
    """Append a list of finding dispositions under a single lock."""
    if not isinstance(items, list) or not items:
        raise ValueError('batch disposition requires a nonempty JSON list')
    report_path = path_at(root, report)
    if not report_path.is_file():
        raise ValueError('report file does not exist: ' + str(report))
    report_rel = str(report_path.relative_to(root))
    report_sha = digest(report_path)
    records = []
    for raw in items:
        disp = raw.get('disposition')
        fid = raw.get('finding_id')
        reason = raw.get('reason')
        if disp not in ('applied', 'rejected', 'deferred', 'superseded'):
            raise ValueError('invalid finding disposition')
        if not fid or not reason:
            raise ValueError('each disposition requires finding_id and reason')
        entry = {
            'schema_version': VERSION,
            'finding_id': fid,
            'report': report_rel,
            'report_sha256': report_sha,
            'disposition': disp,
            'reason': reason,
            'created_at': now(),
        }
        for opt, src_key in (('quote', 'quote'), ('before_sha256', 'before_sha256'),
                             ('after_sha256', 'after_sha256')):
            if raw.get(src_key) is not None:
                entry[opt] = raw[src_key]
            elif opt == 'before_sha256' and raw.get('before_sha') is not None:
                entry[opt] = raw['before_sha']
            elif opt == 'after_sha256' and raw.get('after_sha') is not None:
                entry[opt] = raw['after_sha']
        records.append(entry)
    p = project_manifest_module().edit_artifact(root, book_id, 'decisions.jsonl')
    with locked(p):
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open('a', encoding='utf-8') as f:
            for entry in records:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    return {'recorded': len(records), 'dispositions': records}


def record_disposition(root, book_id, *, report, finding_id, disposition, reason,
                       quote=None, before_sha256=None, after_sha256=None):
    if disposition not in ('applied', 'rejected', 'deferred', 'superseded'):
        raise ValueError('invalid finding disposition')
    if not finding_id or not reason:
        raise ValueError('record-disposition requires finding_id and reason')
    report_path = path_at(root, report)
    if not report_path.is_file():
        raise ValueError('report file does not exist: ' + str(report))
    item = {
        'schema_version': VERSION,
        'finding_id': finding_id,
        'report': str(report_path.relative_to(root)),
        'report_sha256': digest(report_path),
        'disposition': disposition,
        'reason': reason,
        'created_at': now(),
    }
    if quote is not None:
        item['quote'] = quote
    if before_sha256 is not None:
        item['before_sha256'] = before_sha256
    if after_sha256 is not None:
        item['after_sha256'] = after_sha256
    p = project_manifest_module().edit_artifact(root, book_id, 'decisions.jsonl')
    with locked(p):
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open('a', encoding='utf-8') as f:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    return item
