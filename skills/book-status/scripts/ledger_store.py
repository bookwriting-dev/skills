#!/usr/bin/env python3
"""Immutable multi-ledger generations committed through one atomic pointer."""
import hashlib
import json
import os
import fcntl
from pathlib import Path
import tempfile

POINTER = '.storycraft/ledger-current.json'
GENERATIONS = '_Edits/_ledger-generations'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def contained(root: Path, relative: str) -> Path:
    root = root.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f'path escapes project root: {relative}')
    return path


def capture(root: Path, paths: list[str]) -> list[dict]:
    root = root.resolve()
    records = []
    for name in sorted(set(paths)):
        path = contained(root, name)
        record = {'path': path.relative_to(root).as_posix(),
                  'kind': 'directory' if path.is_dir() else 'file'}
        if path.is_dir():
            record['files'] = {
                item.relative_to(path).as_posix(): digest(item.read_bytes())
                for item in sorted(path.rglob('*')) if item.is_file()
            }
        else:
            record['sha256'] = digest(path.read_bytes()) if path.is_file() else None
        records.append(record)
    return records


def current_pointer(root: Path) -> dict | None:
    path = contained(root, POINTER)
    if not path.is_file():
        return None
    pointer = json.loads(path.read_text(encoding='utf-8'))
    if pointer.get('record_type') != 'committed_ledger_pointer' or pointer.get('schema_version') != 1:
        raise ValueError('unsupported committed ledger pointer')
    return pointer


def load_ledger(root: Path, relative: str, default=None):
    content = load_ledger_bytes(root, relative)
    return json.loads(content.decode('utf-8')) if content is not None else default


def load_ledger_bytes(root: Path, relative: str) -> bytes | None:
    root = root.resolve()
    pointer = current_pointer(root)
    if pointer and relative in pointer.get('ledgers', {}):
        ref = pointer['ledgers'][relative]
        path = contained(root, ref['generation_path'])
        content = path.read_bytes()
        if digest(content) != ref.get('sha256'):
            raise ValueError(f'committed ledger digest mismatch: {relative}')
        return content
    path = contained(root, relative)
    if path.is_file():
        return path.read_bytes()
    return None


def _write_file(path: Path, content: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('wb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _atomic_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix='.ledger-pointer-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + '.lock')
    fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode())
        os.fsync(fd)
        return lock, fd
    except BlockingIOError:
        os.close(fd)
        raise ValueError('CONCURRENT_CHANGE: another ledger transaction holds the commit lock') from None
    except Exception:
        os.close(fd)
        raise


def commit(root: Path, transaction: dict) -> dict:
    root = root.resolve()
    txid = transaction.get('transaction_id')
    updates = transaction.get('updates')
    if not isinstance(txid, str) or not txid or not isinstance(updates, dict) or not updates:
        raise ValueError('ledger transaction requires transaction_id and nonempty updates')
    sources = transaction.get('source_evidence')
    if (not isinstance(sources, list) or not sources or
            any(not isinstance(item, dict) or not isinstance(item.get('path'), str) for item in sources) or
            len({item['path'] for item in sources}) != len(sources)):
        raise ValueError('ledger transaction requires unique, exact source_evidence records')
    if any(not isinstance(path, str) or path.startswith('/') for path in updates):
        raise ValueError('ledger update paths must be project-relative')
    update_bytes = {}
    for logical, value in updates.items():
        contained(root, logical)
        update_bytes[logical] = (value.encode('utf-8') if isinstance(value, str) else
                                 (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8'))
    payload_sha = digest(json.dumps({k: digest(v) for k, v in sorted(update_bytes.items())}, sort_keys=True).encode())
    pointer_path = contained(root, POINTER)
    lock, lock_fd = _lock(pointer_path)
    try:
        pointer = current_pointer(root)
        current_generation = pointer.get('generation_id') if pointer else None
        history = pointer.get('history', []) if pointer else []
        previous_tx = next((item for item in history if item.get('transaction_id') == txid), None)
        if previous_tx:
            if previous_tx.get('payload_sha256') != payload_sha:
                raise ValueError('transaction_id reused with different ledger updates')
            return {'status': 'ALREADY_COMMITTED', 'generation_id': previous_tx['generation_id'],
                    'transaction_id': txid}
        expected = transaction.get('expected_generation')
        if expected != current_generation:
            raise ValueError(f'CONCURRENT_CHANGE: expected generation {expected!r}, current is {current_generation!r}')
        if capture(root, [item['path'] for item in sources]) != sources:
            raise ValueError('CONCURRENT_CHANGE: transaction source evidence changed before prepare')

        contents = {}
        if pointer:
            for logical, ref in pointer.get('ledgers', {}).items():
                path = contained(root, ref['generation_path'])
                content = path.read_bytes()
                if digest(content) != ref.get('sha256'):
                    raise ValueError(f'committed ledger digest mismatch: {logical}')
                contents[logical] = content
        else:
            # Bootstrap only explicitly updated legacy authorities; originals remain untouched.
            for logical in update_bytes:
                legacy = contained(root, logical)
                if legacy.is_file():
                    contents[logical] = legacy.read_bytes()
        contents.update(update_bytes)
        refs_digest = {key: digest(value) for key, value in sorted(contents.items())}
        generation_seed = json.dumps({'parent': current_generation, 'transaction': txid,
                                      'payload': payload_sha, 'ledgers': refs_digest}, sort_keys=True)
        generation_id = digest(generation_seed.encode())[:24]
        generation_relative = f'{GENERATIONS}/{generation_id}'
        generation_path = contained(root, generation_relative)
        stage_root = contained(root, GENERATIONS)
        stage_root.mkdir(parents=True, exist_ok=True)
        if not generation_path.exists():
            temp = Path(tempfile.mkdtemp(prefix='.prepared-', dir=stage_root))
            try:
                refs = {}
                for logical, content in contents.items():
                    staged = temp / 'ledgers' / logical
                    _write_file(staged, content)
                    refs[logical] = {'generation_path': f'{generation_relative}/ledgers/{logical}',
                                     'sha256': digest(content)}
                metadata = {'record_type': 'ledger_generation', 'schema_version': 1,
                            'generation_id': generation_id, 'transaction_id': txid,
                            'parent_generation': current_generation, 'ledgers': refs,
                            'source_evidence': sources, 'payload_sha256': payload_sha,
                            'commit_state': 'prepared'}
                _write_file(temp / 'generation.json', (json.dumps(metadata, indent=2, sort_keys=True) + '\n').encode())
                os.replace(temp, generation_path)
            finally:
                if temp.exists():
                    import shutil
                    shutil.rmtree(temp)
        else:
            metadata = json.loads((generation_path / 'generation.json').read_text(encoding='utf-8'))
            if metadata.get('generation_id') != generation_id or metadata.get('transaction_id') != txid:
                raise ValueError('prepared generation ID collision; inspect recovery state')

        if capture(root, [item['path'] for item in sources]) != sources:
            raise ValueError('CONCURRENT_CHANGE: transaction source evidence changed before commit')
        generation_meta = json.loads((generation_path / 'generation.json').read_text(encoding='utf-8'))
        new_history = history + [{'transaction_id': txid, 'payload_sha256': payload_sha,
                                  'generation_id': generation_id}]
        new_pointer = {'record_type': 'committed_ledger_pointer', 'schema_version': 1,
                       'generation_id': generation_id, 'previous_generation_id': current_generation,
                       'ledgers': generation_meta['ledgers'], 'history': new_history,
                       'transaction_id': txid, 'payload_sha256': payload_sha}
        _atomic_json(pointer_path, new_pointer)
        return {'status': 'COMMITTED', 'generation_id': generation_id, 'transaction_id': txid,
                'ledger_paths': sorted(contents)}
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def status(root: Path) -> dict:
    root = root.resolve()
    pointer = current_pointer(root)
    base = contained(root, GENERATIONS)
    current = pointer.get('generation_id') if pointer else None
    history_ids = {entry.get('generation_id') for entry in pointer.get('history', [])} if pointer else set()
    committed_history = []
    uncommitted = []
    if base.is_dir():
        for path in sorted(base.iterdir()):
            if path.name == current:
                continue
            if path.is_dir() and path.name in history_ids:
                committed_history.append(path.name)
            else:
                uncommitted.append(path.name)
    return {'current_generation': current, 'ledger_paths': sorted(pointer.get('ledgers', {})) if pointer else [],
            'committed_history': committed_history,
            'abandoned_or_uncommitted_generations': uncommitted}
