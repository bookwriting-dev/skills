"""Record the author's decisions on an editor's changes and write the accepted ones to chapters."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'beta-feedback/scripts'))
import beta_feedback as beta
import editor_preview
import feedback_scope

state = beta.state
TEXT_CHANGES = ('insert', 'delete', 'replace')


def grouped(changes):
    """Map each change ID to the changes that edit the same word, which are decided together."""
    result = {change['id']: [change] for change in changes}
    paragraphs = {}
    for change in changes:
        if change['type'] in TEXT_CHANGES and change.get('location'):
            key = editor_preview.paragraph_key(change)
            paragraphs.setdefault(key, []).append(change)
    for members in paragraphs.values():
        group, end = [], 0
        for change in sorted(members, key=lambda c: c['offset']):
            if group and re.search(r'\s', change['paragraph_before'][end:change['offset']]):
                group = []
            group.append(change)
            end = max(end, change['offset'] + len(change['before']))
            for member in group:
                result[member['id']] = group
    return result


def punctuation_only(change):
    words = [re.sub(r'[\W_]', '', change[key]) for key in ('before', 'after')]
    return change['type'] in TEXT_CHANGES and words[0] == words[1]


def decide(report, status, *, ids=(), chapter=None, author=None, punctuation=False, confirm=None):
    """Set a status by change ID, or by filter once its matches have been shown and confirmed."""
    filtered = bool(chapter or author or punctuation)
    if bool(ids) == filtered:
        raise ValueError('choose changes with --change, or with filters, not both')
    changes = report['changes']
    groups = grouped(changes)

    def blocked(change):
        if any(c['status'] == 'applied' for c in groups[change['id']]):
            return 'already applied'
        if status == 'accepted':
            return next((c['reason'] for c in groups[change['id']] if not c['supported']), None)
        return None

    def matches(change):
        location = change.get('location') or {}
        section = {'chapter_id': location.get('chapter_id'), 'label': location.get('chapter'),
                   'path': location.get('path') or ''}
        return ((not chapter or feedback_scope.matches(section, chapter))
                and (not author or author in change['authors'])
                and (not punctuation or punctuation_only(change)))

    skipped = []
    if ids:
        known = {change['id']: change for change in changes}
        if unknown := [identifier for identifier in ids if identifier not in known]:
            raise ValueError('unknown change: ' + ', '.join(unknown))
        for identifier in ids:
            if reason := blocked(known[identifier]):
                raise ValueError(f'{identifier} cannot be marked {status}: {reason}')
        wanted = {member['id'] for identifier in ids for member in groups[identifier]}
    else:
        wanted = set()
        for change in changes:
            if not all(map(matches, groups[change['id']])):
                continue
            if reason := blocked(change):
                skipped.append({'id': change['id'], 'reason': reason})
            else:
                wanted.add(change['id'])
    selected = [change for change in changes if change['id'] in wanted]
    shown = json.dumps([status, [(c['id'], c['status']) for c in selected]])
    token = hashlib.sha256(shown.encode()).hexdigest()[:12]
    if confirm and confirm != token:
        raise ValueError('the matching changes differ from the ones shown; run the filter again')
    recorded = bool(selected) and (bool(ids) or confirm == token)
    if recorded:
        for change in selected:
            change['status'] = status
    return {'status': status, 'recorded': recorded, 'skipped': skipped,
            **({} if ids or recorded or not selected else {'confirm': token}),
            'changes': [{key: c.get(key) for key in ('id', 'before', 'after', 'status', 'paragraph_before')}
                        | {'chapter': (c.get('location') or {}).get('chapter')} for c in selected]}


def replace_file(path, data):
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix='.editor-return-')
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        shutil.copymode(path, temporary)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def confirmed(path, item):
    """Read the written chapter back and compare what a reader would now see."""
    written = path.read_bytes()
    if written != item['after']:
        return False
    chapter = item['chapter']
    return editor_preview.render(chapter.read(written.decode('utf-8'))) == item['expected']


def apply(root, book, report, ledger, token):
    """Write the previewed accepted changes. The caller holds the ledger lock."""
    proposal = editor_preview.propose(root, book, report, accepted=True)
    if not proposal['files'] or token != proposal['token']:
        raise ValueError('the accepted changes and chapters do not match that token; preview them again')
    written, failed = [], []
    for item in proposal['files']:
        path = state.path_at(root, item['path'])
        backup = state.path_at(root, ledger.parent / f'{ledger.stem}-backups'
                               / hashlib.sha256(item['before']).hexdigest()[:16] / (item['path'] + '.bak'))
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(item['before'])
        if path.read_bytes() != item['before']:
            failed.append({'path': item['path'], 'reason': 'the chapter changed while applying; nothing written'})
            continue
        replace_file(path, item['after'])
        try:
            good = confirmed(path, item)
        except (ValueError, OSError):
            good = False
        if not good:
            replace_file(path, item['before'])
            failed.append({'path': item['path'], 'reason': 'the written text could not be confirmed; restored'})
            continue
        saved = backup.relative_to(root).as_posix()
        for change in report['changes']:
            if change['id'] in item['changes']:
                change.update(status='applied', backup=saved)
        state.write(ledger, report)
        written.append({'path': item['path'], 'changes': item['changes'], 'backup': saved})
    return {'written': written, 'failed': failed, 'held': proposal['manual']}
