#!/usr/bin/env python3
"""Compare two Storycraft packages on three connected excerpts and collect blind reader choices."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import hashlib
import json
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import zipfile

from editorial_study import document_hash, write_json
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/book-status/scripts'))
from state_core import write as write_atomic

BRIEF = ROOT / 'tools/eval-fixtures/drafting/brief.md'
PARTS = ('opening', 'middle', 'payoff')
LABELS = ('A', 'B')
QUESTIONS = {
    'reading_reason': 'Which version would you keep reading, and what on the page made you choose?',
    'character_choice': 'Which choice felt specific to its character? Point to the action or line.',
    'changed_detail': 'Which earlier detail changed meaning at the end? Describe its effect, or where the payoff fell short.',
}
SCHEMA = {'type': 'object', 'properties': {key: {'type': 'string'} for key in PARTS},
          'required': list(PARTS), 'additionalProperties': False}


def assignment(min_words, max_words):
    return (
        'Write three connected sample excerpts from the same novel, each between '
        f'{min_words} and {max_words} whitespace-delimited words inclusive. '
        'Read the brief in _Intake/Book-1/premise.md. Use this project’s bundled fiction-outline, '
        'fiction-voiceprompt, and fiction-writechapter guidance. You may create the local planning '
        'or canon notes you need and decide provisional details for this synthetic sample. '
        'Use one continuous interpretation of the brief across the opening, a consequential middle '
        'choice, and the payoff. Intervening chapters are off-page. Return only the prose in the '
        'three schema fields, without headings, planning notes, commentary or author identification.'
    )


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def freeze(ref, dest):
    if ref != 'WORKTREE':
        commit = subprocess.check_output(['git', 'rev-parse', '--verify', '--end-of-options',
                                          ref + '^{commit}'], cwd=ROOT, text=True).strip()
        subprocess.run(['git', 'archive', '--format=zip', '-o', str(dest), commit, '--',
                        'skills', 'templates/AGENTS.md'], cwd=ROOT, check=True)
        return commit
    files = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others',
                                     '--exclude-standard', '--', 'skills', 'templates/AGENTS.md'], cwd=ROOT)
    with zipfile.ZipFile(dest, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(set(files.decode().strip('\0').split('\0'))):
            path = ROOT / name
            if path.is_file():
                archive.write(path, name)
    return 'WORKTREE'


def prepare(args):
    destination = args.study.resolve()
    if destination.exists():
        raise ValueError('Choose a new study directory.')
    if not (0 < args.min_words <= args.max_words) or not args.model.strip() or args.model == 'default':
        raise ValueError('Select a specific model and a positive per-excerpt word range.')
    brief = args.brief.read_text(encoding='utf-8').strip()
    if not brief:
        raise ValueError('Supply a nonempty story brief.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as stage:
        study = Path(stage) / 'study'
        private = study / 'private'
        private.mkdir(parents=True)
        labels = list(LABELS)
        secrets.SystemRandom().shuffle(labels)
        manifest = {'run_id': secrets.token_hex(12), 'brief': brief, 'model': args.model,
                    'reasoning_effort': args.effort, 'min_words': args.min_words,
                    'max_words': args.max_words, 'packages': {}, 'host': 'codex',
                    'assignment': assignment(args.min_words, args.max_words), 'schema': SCHEMA,
                    'rubric': QUESTIONS, 'skills': ['fiction-outline', 'fiction-voiceprompt', 'fiction-writechapter']}
        for label, (version, ref) in zip(labels, [('baseline', args.baseline), ('candidate', args.candidate)]):
            archive = private / f'{label}.zip'
            revision = freeze(ref, archive)
            manifest['packages'][label] = {'version': version, 'revision': revision, 'sha256': checksum(archive)}
        write_json(private / 'manifest.json', manifest)
        study.rename(destination)
    return destination


def generate(private, label, manifest, timeout):
    package = manifest['packages'][label]
    archive = private / f'{label}.zip'
    if checksum(archive) != package['sha256']:
        raise ValueError('Frozen package changed. Prepare a new study.')
    with tempfile.TemporaryDirectory(prefix='storycraft-drafting-') as temp:
        workspace = Path(temp)
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.namelist():
                if member.endswith('/'):
                    continue
                path = Path(member)
                if path.is_absolute() or '..' in path.parts:
                    raise ValueError('Invalid package path.')
                if member == 'templates/AGENTS.md':
                    guidance = bundle.read(member).decode().replace('__SERIES_TITLE__', 'Study Novel')
                    (workspace / 'AGENTS.md').write_text(guidance.replace('__PROJECT_TYPE__', 'FICTION'))
                elif path.parts[0] == 'skills':
                    target = workspace / '.agents' / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(bundle.read(member))
        brief_path = workspace / '_Intake/Book-1/premise.md'
        brief_path.parent.mkdir(parents=True)
        brief_path.write_text(manifest['brief'], encoding='utf-8')
        schema = workspace / 'output-schema.json'
        output = workspace / 'output.json'
        write_json(schema, manifest['schema'])
        guidance = []
        for skill in manifest['skills']:
            content = (workspace / '.agents/skills' / skill / 'SKILL.md').read_text(encoding='utf-8')
            guidance.append(f'## Bundled instructions for {skill}\n{content}')
        prompt = manifest['assignment'] + '\n\n' + '\n\n'.join(guidance)
        command = ['codex', '-a', 'never', '-s', 'workspace-write', '-C', temp, 'exec',
                   '--skip-git-repo-check', '--ephemeral', '--ignore-user-config', '--model', manifest['model'],
                   '-c', 'model_reasoning_effort=' + json.dumps(manifest['reasoning_effort']),
                   '--output-schema', str(schema), '--output-last-message', str(output), '-']
        result = subprocess.run(command, cwd=workspace, input=prompt, capture_output=True,
                                text=True, timeout=timeout)
        if result.returncode or not output.is_file():
            raise ValueError(f'Generation for sample {label} failed: {result.stderr[-1200:]}')
        return read(output)


def validate_draft(draft, manifest):
    if not isinstance(draft, dict) or set(draft) != set(PARTS):
        raise ValueError('Each sample requires an opening, middle, and payoff.')
    for part in PARTS:
        count = len(draft[part].split()) if isinstance(draft[part], str) else 0
        if not manifest['min_words'] <= count <= manifest['max_words']:
            raise ValueError(f'{part} used {count} words, outside the frozen budget.')


def saved_draft(private, manifest, label):
    sample = read(private / f'{label}.json')
    package_hash = manifest['packages'][label]['sha256']
    if (sample.get('label') != label or sample.get('package') != package_hash
            or sample.get('study') != document_hash(manifest)
            or sample.get('sha256') != document_hash(sample['draft'])):
        raise ValueError('Saved sample changed or belongs to another assignment.')
    validate_draft(sample['draft'], manifest)
    return sample['draft']


def reader_handout(drafts, manifest):
    lines = ['# Blind novel comparison', '', 'Read both samples in order before recording your response.']
    for label, draft in drafts.items():
        lines += ['', f'## Sample {label}']
        for part in PARTS:
            lines += ['', f'### {part.title()}', '', draft[part]]
    lines += ['', '## Reader response', '', *['- ' + q for q in manifest['rubric'].values()]]
    return '\n'.join(lines) + '\n'


def handout_id(manifest, handout):
    return document_hash({'run': manifest['run_id'], 'handout': handout})


def run(study, timeout, generator=generate):
    private = study / 'private'
    manifest = read(private / 'manifest.json')
    fingerprint = document_hash(manifest)

    def sample(label):
        path = private / f'{label}.json'
        with (private / f'{label}.lock').open('a') as lockfile:
            fcntl.flock(lockfile, fcntl.LOCK_EX)
            if path.exists():
                return saved_draft(private, manifest, label)
            draft = generator(private, label, manifest, timeout)
            validate_draft(draft, manifest)
            write_atomic(path, {'study': fingerprint, 'label': label, 'package': manifest['packages'][label]['sha256'],
                                'sha256': document_hash(draft), 'draft': draft})
            return draft

    with ThreadPoolExecutor(max_workers=2) as pool:
        drafts = dict(zip(LABELS, pool.map(sample, LABELS)))
    review = study / 'readers'
    review.mkdir(exist_ok=True)
    handout = reader_handout(drafts, manifest)
    ballot_id = handout_id(manifest, handout)
    handout_path = review / 'read.md'
    if handout_path.exists() and handout_path.read_text(encoding='utf-8') != handout:
        raise ValueError('Reader handout changed. Reconcile it before collecting ballots.')
    if not handout_path.exists():
        handout_path.write_text(handout, encoding='utf-8')
    write_atomic(review / 'blank-ballot.json', {'ballot_id': ballot_id, 'reader': '',
                 'keep_reading': '', **dict.fromkeys(manifest['rubric'], '')})
    return review


def score(study, ballots):
    manifest = read(study / 'private/manifest.json')
    drafts = {label: saved_draft(study / 'private', manifest, label) for label in LABELS}
    handout = reader_handout(drafts, manifest)
    if (study / 'readers/read.md').read_text(encoding='utf-8') != handout:
        raise ValueError('Reader handout differs from the frozen samples and questions.')
    ballot_id = handout_id(manifest, handout)
    responses = {}
    for filename in ballots:
        ballot = read(filename)
        if ballot.get('ballot_id') != ballot_id or ballot.get('keep_reading') not in (*LABELS, 'both', 'neither'):
            raise ValueError('A ballot must match these samples and choose A, B, both, or neither.')
        if any(not isinstance(ballot.get(k), str) or not ballot[k].strip() for k in ('reader', *manifest['rubric'])):
            raise ValueError('Enter the reader identity and a response to each question.')
        reader = ballot['reader'].strip()
        if reader in responses:
            raise ValueError(f'Duplicate reader: {reader}')
        choice = ballot['keep_reading']
        responses[reader] = {**ballot, 'version_chosen': manifest['packages'].get(choice, {}).get('version', choice)}
    return {'study': manifest['run_id'], 'responses': responses}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    prepare_cmd = sub.add_parser('prepare', help='freeze packages, brief and generation budget')
    prepare_cmd.add_argument('study', type=Path)
    prepare_cmd.add_argument('--baseline', required=True, help='Git revision')
    prepare_cmd.add_argument('--candidate', default='WORKTREE', help='Git revision or WORKTREE')
    prepare_cmd.add_argument('--brief', type=Path, default=BRIEF)
    prepare_cmd.add_argument('--model', required=True)
    prepare_cmd.add_argument('--effort', choices=('low','medium','high','xhigh','max'), default='medium')
    prepare_cmd.add_argument('--min-words', type=int, default=180)
    prepare_cmd.add_argument('--max-words', type=int, default=350)
    run_cmd = sub.add_parser('run', help='generate both samples and write reader copies')
    run_cmd.add_argument('study', type=Path)
    run_cmd.add_argument('--timeout', type=int, default=600, help='seconds per sample')
    score_cmd = sub.add_parser('score', help='unblind completed, attributable reader ballots')
    score_cmd.add_argument('study', type=Path)
    score_cmd.add_argument('ballots', type=Path, nargs='+')
    args = parser.parse_args()
    try:
        if args.action == 'prepare':
            print(prepare(args))
        elif args.action == 'run':
            print(run(args.study, args.timeout))
        else:
            print(json.dumps(score(args.study, args.ballots), indent=2, ensure_ascii=False))
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
