"""Core storage, locking, hashing, and module helpers for Storycraft state."""
import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import chapter_format
import continuity
import editions
import ledger_store
import project_manifest
import reader_text

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
    return reader_text


def ledger_store_module():
    return ledger_store


def project_manifest_module():
    return project_manifest


def chapter_format_module():
    return chapter_format


def continuity_module():
    return continuity


def manuscript_texts(root, book):
    return {chapter['path']: path_at(root, chapter['path']).read_bytes().decode('utf-8')
            for chapter in book['chapters'] if path_at(root, chapter['path']).is_file()}


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


def source_valid(root, item):
    return (isinstance(item.get('source'), str) and bool(item.get('quote')) and
            digest(path_at(root, item['source'])) == item.get('source_sha256') and
            item['quote'] in path_at(root, item['source']).read_text())


def document(path, key):
    return load(path) if path.exists() else {'schema_version': VERSION, key: []}


def commit_ledger(root, logical_path, data, transaction_id, source_paths, expected_generation):
    store = ledger_store_module()
    return store.commit(root, {
        'transaction_id': transaction_id,
        'expected_generation': expected_generation,
        'source_evidence': evidence(root, source_paths) if source_paths else [],
        'updates': {logical_path: data},
    })
