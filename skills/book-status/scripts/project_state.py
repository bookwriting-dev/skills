#!/usr/bin/env python3
"""Content-addressed Storycraft records. Python standard library; see --help."""
import argparse
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import editions
from state_core import (
    VERSION, chapter_format_module, commit_ledger, continuity_module, digest,
    document, evidence, ledger_store_module, load, locked, manuscript_texts,
    now, path_at, project_manifest_module, reader_text_module, source_valid, write,
)
from state_ledgers import (
    continuity_command, continuity_dir, continuity_report, knowledge,
    knowledge_event_state, memory, relationship_state, scope_dimensions,
    scope_matches, support_findings,
)
from state_packets import (
    SOMATIC_TOKENS, STOP_WORDS, decision_applies, draft_packet,
    parse_checkpoints, parse_psych, pov_labels, prose_lines, scene_contexts,
    scene_knowledge, style_policy,
)
from state_reviews import (
    chapter_report_paths, current_inputs, dashboard, freshness, operation_profile_blockers,
    pipeline_step_reusable, readiness, record_disposition, review_begin,
    review_finish,
)
from state_workflows import (
    campaign, reading, record_pipeline_step, step_complete, step_start,
    validate_pipeline_step,
)
from rhythm_map import rhythm_map
from sync_edits import sync_edits


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--book', default='Book-1')
    sub = ap.add_subparsers(dest='command', required=True)
    for cmd in ('prepare', 'snapshot', 'check', 'readiness', 'validate', 'dashboard', 'workflow', 'style-policy',
                'register-chapters', 'disposition', 'memory', 'knowledge', 'knowledge-state',
                'relationship-state', 'reading', 'author-read', 'campaign', 'pipeline', 'draft-packet',
                'chapter-format', 'continuity', 'review-begin', 'review-finish', 'record-disposition',
                'step-start', 'step-complete', 'sync-edits', 'rhythm-map'):
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
        p.add_argument('--chapter', default=None if cmd in ('chapter-format', 'continuity', 'author-read') else '1')
        p.add_argument('--window', type=int, default=3)
        if cmd in ('continuity', 'draft-packet'):
            p.add_argument('--key', action='append')
        if cmd == 'author-read':
            p.add_argument('--edition')
            p.add_argument('--quote')
        if cmd == 'style-policy':
            p.add_argument('--simile-count', type=int)
        if cmd == 'review-begin':
            p.add_argument('--type', required=True, choices=('Gate', 'Review', 'FullEdit', 'FactCheck', 'ClarityEdit'))
            p.add_argument('--extra-path', action='append')
        if cmd == 'review-finish':
            p.add_argument('--prepared', required=True)
            p.add_argument('--verdict', required=True, choices=('PASS', 'WARN', 'FAIL'))
            p.add_argument('--report')
            p.add_argument('--finding', action='append')
            p.add_argument('--operation-id')
        if cmd == 'record-disposition':
            p.add_argument('--report', required=True)
            p.add_argument('--finding-id', required=True)
            p.add_argument('--disposition', required=True, choices=('applied', 'rejected', 'deferred', 'superseded'))
            p.add_argument('--reason', required=True)
            p.add_argument('--quote')
            p.add_argument('--before-sha')
            p.add_argument('--after-sha')
        if cmd in ('step-start', 'step-complete'):
            p.add_argument('--step-id', required=True)
            p.add_argument('--attempt-id')
            p.add_argument('--isolation-status')
            p.add_argument('--transform-path', action='append')
        if cmd == 'step-start':
            p.add_argument('--stage-role', required=True)
            p.add_argument('--write-path', action='append')
            p.add_argument('--extra-path', action='append')
            p.add_argument('--predecessor-exists', choices=('true', 'false'))
        if cmd == 'step-complete':
            p.add_argument('--output-path', action='append', required=True)
            p.add_argument('--permitted-input-manifest-sha256')
            p.add_argument('--sealed-reactions-sha256')
        if cmd == 'sync-edits':
            p.add_argument('--baseline')
        if cmd == 'rhythm-map':
            p.add_argument('--gap-threshold', type=int, default=4)
            p.add_argument('--markdown', action='store_true')
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
        if not spec.get('inputs') or current_inputs(root, spec['inputs']) != spec['inputs']:
            raise ValueError('review inputs changed or pre-review evidence missing')
        report = path_at(root, spec['report'])
        if not report.is_file() or spec['verdict'] not in ('PASS', 'WARN', 'FAIL'):
            raise ValueError('missing report or invalid verdict')
        spec.update(report_sha256=digest(report), created_at=now())
        out = path_at(root, a.output)
        with locked(out):
            write(out, spec)
        result = spec
    elif a.command == 'review-begin':
        result = review_begin(root, a.book, a.chapter, a.type, output=a.output, extra_paths=a.extra_path)
    elif a.command == 'review-finish':
        findings = [json.loads(item) for item in a.finding] if a.finding else None
        result = review_finish(root, a.prepared, a.verdict, report=a.report, output=a.output,
                               findings=findings, operation_id=a.operation_id)
    elif a.command == 'record-disposition':
        result = record_disposition(root, a.book, report=a.report, finding_id=a.finding_id,
                                    disposition=a.disposition, reason=a.reason, quote=a.quote,
                                    before_sha256=a.before_sha, after_sha256=a.after_sha)
    elif a.command == 'step-start':
        pred_flag = None if a.predecessor_exists is None else (a.predecessor_exists == 'true')
        result = step_start(root, a.book, run=a.run, step_id=a.step_id, profile=a.profile,
                            stage_role=a.stage_role, chapter_selector=a.chapter,
                            write_paths=a.write_path, transform_paths=a.transform_path,
                            extra_paths=a.extra_path, attempt_id=a.attempt_id,
                            predecessor_exists=pred_flag, isolation_status=a.isolation_status)
    elif a.command == 'step-complete':
        result = step_complete(root, a.book, run=a.run, step_id=a.step_id,
                               output_paths=a.output_path, transform_paths=a.transform_path,
                               attempt_id=a.attempt_id, isolation_status=a.isolation_status,
                               permitted_input_manifest_sha256=a.permitted_input_manifest_sha256,
                               sealed_reactions_sha256=a.sealed_reactions_sha256)
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
    elif a.command == 'author-read':
        result = editions.author_read(root, a)
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
        item = json.loads(Path(a.spec).read_text(encoding='utf-8')) if a.action == 'record' else None
        result = record_pipeline_step(root, a.book, a.run, a.action, item)
    elif a.command == 'draft-packet':
        result = draft_packet(root, a)
    elif a.command == 'sync-edits':
        result = sync_edits(root, a.book, a.chapter, baseline=a.baseline)
    elif a.command == 'rhythm-map':
        result = rhythm_map(root, a.book, gap_threshold=a.gap_threshold, markdown=a.markdown)
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
