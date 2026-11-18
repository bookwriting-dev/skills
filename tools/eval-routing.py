#!/usr/bin/env python3
"""Exercise Storycraft routing in fresh Codex sessions and verify actual project writes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parent.parent
CHAPTER = 'Chapters/Book-1/Chapter-005.md'
REPORT = '_Edits/Book-1/Chapter-005_Review.md'
TRIAL = '_Intake/Book-1/opening-scene.md'
CHAPTER_TEXT = (
    '# Chapter 5 — The Empty Rack\n\n'
    'Mara quietly put the key in the drawer. She simply took a seat beside the window.\n\n'
    'The copper kettle sat on the stove. It was just a little warm.\n\n'
    'At dusk, three starlings landed on the railing.\n'
)
FIXES = (
    ('Mara quietly put the key in the drawer.', 'Mara put the key in the drawer.'),
    ('The copper kettle sat on the stove.', 'The kettle sat on the stove.'),
    ('It was just a little warm.', 'It was warm.'),
)
CASES = (
    ('review', 'fiction-reviewchapter', 'Review chapter 5.'),
    ('review-only', 'fiction-reviewchapter', 'What would you change in chapter 5? Show me the review first.'),
    ('cleanup', 'kill-chapter', 'Clean this chapter in place. In chapter 5, strip out the recurring prose crutches.'),
    ('approved', 'fiction-revise', 'Apply fixes 1 and 3 to chapter 5.'),
    ('opening', 'fiction-writechapter',
     'Try my opening scene. A ferry keeper named Inez has one berth left. She promised it to her brother, but '
     'a traveler arrives with a feverish child. Write from Inez’s viewpoint through her choice.'),
    ('beta', 'beta-feedback', "I put Sam's beta-reader comments in beta-notes.json for the current edition. "
     "Import the beta feedback and group it by passage."),
)


def put(root, name, content):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')


def run_json(command, workdir):
    return json.loads(subprocess.check_output(command, cwd=workdir, text=True))


def make_fixture(root, case):
    subprocess.run([str(ROOT / 'new-book.sh'), root.name, 'The Empty Rack'], check=True,
                   env={**os.environ, 'BOOKS_DIR': str(root.parent)}, capture_output=True)
    if case == 'opening':
        return
    put(root, CHAPTER, CHAPTER_TEXT)
    put(root, 'Wiki/Characters/Mara.md', '# Mara\n\nMara keeps the keys to the ferry storehouse.\n')
    put(root, 'Wiki/Style/style_guide.md', '# Style\n\nThird person past. The closing image of the birds is deliberate.\n')
    put(root, 'Wiki/Outline/Book-1/Chapter_05_Scene.md',
        '# Chapter 5\n\n## Scene 1\n- **POV:** Mara\n- Mara waits for the ferry to return.\n')
    if case == 'approved':
        entries = [f'{i}. [R{i}] Local edit\n   - Original: "{before}"\n   - Replace with: "{after}"'
                   for i, (before, after) in enumerate(FIXES, 1)]
        put(root, REPORT, '# Review\n\n## Proposed Edits\n\n' + '\n\n'.join(entries) + '\n')
    if case == 'beta':
        exporter = root / '.agents/skills/compile-manuscript/scripts/compile_manuscript.py'
        run_json([sys.executable, str(exporter), '--root', str(root)], root)
        notes = {'schema_version': 1, 'reader': 'Sam',
                 'notes': [{'chapter': 'Chapter 5', 'quote': 'At dusk, three starlings landed on the railing.',
                            'comment': 'This image made the wait feel final.'}]}
        put(root, 'beta-notes.json', json.dumps(notes))


def snapshot(root):
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob('*') if path.is_file() and '.git' not in path.relative_to(root).parts}


def trace_skills(stdout):
    observed = set()
    model = None
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get('type') == 'session.meta':
            model = event.get('model')
        if event.get('type') != 'item.completed':
            continue
        item = event.get('item', {})
        if item.get('type') != 'command_execution' or item.get('exit_code') not in (None, 0):
            continue
        command = item.get('command', '')
        observed.update(re.findall(r'(?<![\w-])skills/([a-z0-9-]+)/SKILL\.md\b', command))
        if re.search(r'skills/beta-feedback/scripts/beta_feedback\.py\b', command):
            observed.add('beta-feedback')
    return sorted(observed), model


def outcomes(root, case, before):
    after = snapshot(root)
    changed = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
    draft = root / CHAPTER
    body = draft.read_text(encoding='utf-8') if draft.is_file() else ''
    values = {'changed': changed, 'chapter_unchanged': body == CHAPTER_TEXT}
    if case == 'approved':
        exact = CHAPTER_TEXT
        for index in (0, 2):
            exact = exact.replace(*FIXES[index])
        values['only_selected_fixes'] = body == exact
    elif case == 'cleanup':
        values['cleanup_preserved_closing'] = body.endswith(CHAPTER_TEXT.split('\n\n')[-1])
        values['cleaned_crutch'] = any(word not in body for word in ('simply', 'just a little'))
    elif case == 'opening':
        trial = root / TRIAL
        values['intake_prose'] = trial.is_file() and len(trial.read_text(encoding='utf-8').split()) >= 50
    elif case == 'beta':
        records = sorted((root / '_Edits/Book-1/beta-feedback').glob('*.json'))
        values['beta_anchor'] = any(
            note.get('reader') == 'Sam' and note['location']['status'] == 'ANCHORED'
            for file in records for note in json.loads(file.read_text())['feedback'])
    return values


def score(record, expected):
    name, skill, _ = expected
    if record.get('status') != 'complete':
        return [record.get('error') or 'Codex execution did not complete']
    output = record['observed']
    failures = []
    if skill not in record['observed_skills']:
        failures.append(f'no tool evidence that {skill} ran')
    changed = set(output['changed'])
    if name in ('review', 'review-only'):
        if not output['chapter_unchanged'] or any(not path.startswith('_Edits/Book-1/') for path in changed):
            failures.append('review touched content outside its report directory')
        if name == 'review' and REPORT not in changed:
            failures.append('expected a durable Chapter 5 review')
    elif name in ('cleanup', 'approved'):
        unexpected = [path for path in changed if path != CHAPTER and not path.startswith('_Edits/Book-1/')]
        if unexpected or CHAPTER not in changed:
            failures.append('edits should target Chapter 5 and its edit receipts')
        if name == 'cleanup' and not (output['cleanup_preserved_closing'] and output['cleaned_crutch']):
            failures.append('cleanup did not preserve the closing and remove a fixture crutch')
        if name == 'approved' and not output['only_selected_fixes']:
            failures.append('chapter differs from applying exactly fixes 1 and 3')
    elif name == 'opening':
        if changed != {TRIAL} or not output['intake_prose']:
            failures.append('trial must produce only the opening scene sample')
    elif name == 'beta':
        if not output['beta_anchor'] or not changed or any(
                not path.startswith('_Edits/Book-1/beta-feedback/') for path in changed):
            failures.append('beta intake must anchor Sam’s note and write only feedback records')
    return failures


def live_case(binary, case, model, timeout):
    name, _, prompt = case
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='storycraft-routing-') as tmp:
        project = Path(tmp) / 'book'
        make_fixture(project, name)
        before = snapshot(project)
        command = [binary, '-a', 'never', '-s', 'workspace-write', '-C', str(project), 'exec',
                   '--json', '--ephemeral', '--ignore-user-config']
        if model:
            command.extend(('--model', model))
        command.append(prompt)
        try:
            result = subprocess.run(command, text=True, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or b'').decode(errors='replace')
            skills, reported = trace_skills(output)
            last_error = run_error(output, (exc.stderr or b'').decode(errors='replace'))
            return {'case': name, 'status': 'failed', 'error': f'Codex timed out after {timeout} seconds. {last_error}',
                    'observed': outcomes(project, name, before), 'observed_skills': skills, 'model': reported or model}
        skills, reported = trace_skills(result.stdout)
        record = {'case': name, 'status': 'complete' if result.returncode == 0 else 'failed',
                  'observed': outcomes(project, name, before), 'observed_skills': skills,
                  'model': reported or model, 'seconds': round(time.monotonic() - start, 2)}
        if result.returncode:
            record['error'] = run_error(result.stdout, result.stderr) or 'Codex exited unsuccessfully'
        return record


def run_error(stdout, stderr):
    messages = [line for line in stdout.splitlines()
                if re.match(r'^\{"type":"(?:error|turn\.failed)"', line)]
    return ' '.join(messages[-2:])[-800:] or (stderr.strip().splitlines()[-1][:800] if stderr.strip() else '')


def check_fixtures():
    assert len({item[0] for item in CASES}) == len(CASES)
    for _, skill, _ in CASES:
        assert (ROOT / 'skills' / skill / 'SKILL.md').is_file(), skill
    for source, _ in FIXES:
        assert CHAPTER_TEXT.count(source) == 1
    example = json.dumps({'type': 'item.completed', 'item': {'type': 'command_execution', 'exit_code': 0,
                          'command': 'cat .agents/skills/fiction-revise/SKILL.md'}})
    assert trace_skills(example)[0] == ['fiction-revise']
    assert not trace_skills('The agent says it used fiction-revise.')[0]
    case = next(case for case in CASES if case[0] == 'approved')
    result = {'status': 'complete', 'observed_skills': ['fiction-revise'],
              'observed': {'changed': [CHAPTER], 'only_selected_fixes': True}}
    assert not score(result, case)
    result['observed']['only_selected_fixes'] = False
    assert score(result, case)
    print('Routing fixtures and scorer verified')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--case', choices=[item[0] for item in CASES], action='append')
    parser.add_argument('--check-fixtures', action='store_true')
    parser.add_argument('--score', type=Path, help='score recorded observations from a compatible host')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--model')
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    if args.check_fixtures:
        check_fixtures()
        return 0
    cases = [item for item in CASES if not args.case or item[0] in args.case]
    if args.score:
        run = json.loads(args.score.read_text(encoding='utf-8'))
    elif args.live:
        binary = shutil.which('codex')
        if not binary:
            parser.error('Codex CLI is required for --live')
        run = {'host': subprocess.check_output([binary, '--version'], text=True).strip(), 'results': []}
        for case in cases:
            result = live_case(binary, case, args.model, args.timeout)
            run['results'].append(result)
            print(f'{case[0]}: {result["status"]}', file=sys.stderr, flush=True)
    else:
        parser.error('choose --live, --check-fixtures, or --score')
    by_name = {item['case']: item for item in run['results']}
    report = {**run, 'checks': {case[0]: score(by_name.get(case[0], {'observed': {}}), case) for case in cases}}
    summary = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        args.output.write_text(summary, encoding='utf-8')
    print(summary, end='')
    return int(any(report['checks'].values()))


if __name__ == '__main__':
    raise SystemExit(main())
