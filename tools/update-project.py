#!/usr/bin/env python3
"""Conservative library upgrade and multi-project fleet status scanner. Unknown/local files are never overwritten."""
import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def hashes(base):
    return {str(p.relative_to(base)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in base.rglob('*') if p.is_file() and p.suffix not in ('.pyc', '.pyo')
            and not any(part.startswith('.') or part == '__pycache__' for part in p.relative_to(base).parts)}


def library_meta():
    lib_version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip() if (ROOT / 'VERSION').is_file() else 'unknown'
    try:
        lib_commit = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.SubprocessError):
        lib_commit = 'unknown'
    return lib_version, lib_commit


def parse_source_pin(dest: Path) -> dict:
    pin_path = dest / '.storycraft-source'
    raw = {}
    if pin_path.is_file():
        for line in pin_path.read_text(encoding='utf-8').splitlines():
            if ':' in line:
                k, v = line.split(':', 1)
                raw[k.strip()] = v.strip()
    return {
        'pinned_version': raw.get('version'),
        'pinned_commit': raw.get('commit'),
        'pinned_date': raw.get('pinned'),
        'pinned_skills': int(raw['skills']) if raw.get('skills', '').isdigit() else None,
    }


def inspect_project(project_dir: Path, incoming: dict[str, str], lib_version: str, lib_commit: str) -> dict:
    project_root = project_dir.resolve()
    dest = project_root / '.agents/skills'
    local = hashes(dest)
    basefile = dest / '.storycraft-base.json'
    base = json.loads(basefile.read_text(encoding='utf-8')) if basefile.exists() else {}
    changes, conflicts, removes = [], [], []
    for name, h in incoming.items():
        if name not in local or local[name] == base.get(name):
            if local.get(name) != h:
                changes.append(name)
        elif local[name] != h:
            conflicts.append(name)
    for name in local.keys() - incoming.keys():
        if local[name] == base.get(name):
            removes.append(name)
        else:
            conflicts.append(name)
    legacy = [
        str(p.relative_to(project_root))
        for p in sorted((project_root / '_Edits').rglob('Chapter-*.md'))
        if not p.with_suffix('.meta.json').exists()
    ]
    pin = parse_source_pin(dest)
    sorted_changes = sorted(changes)
    sorted_conflicts = sorted(set(conflicts))
    sorted_removes = sorted(removes)
    if sorted_conflicts:
        status = 'CONFLICT'
    elif sorted_changes or sorted_removes or pin['pinned_version'] != lib_version:
        status = 'BEHIND'
    else:
        status = 'CURRENT'
    return {
        'project': project_root.name,
        'path': str(project_root),
        'status': status,
        'library_version': lib_version,
        'library_commit': lib_commit,
        **pin,
        'update': sorted_changes,
        'conflict': sorted_conflicts,
        'prune': sorted_removes,
        'legacy_unknown': legacy,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('project', nargs='?', type=Path)
    ap.add_argument('--scan-dir', type=Path,
                    help='Scan a directory of book projects and report library version/migration status across all pinned repos')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--prune', action='store_true')
    ap.add_argument('--migration', action='store_true')
    a = ap.parse_args()

    incoming = hashes(ROOT / 'skills')
    lib_version, lib_commit = library_meta()

    if a.scan_dir is not None:
        if a.apply or a.prune:
            ap.error('--scan-dir is read-only and cannot be combined with --apply or --prune')
        scan_root = a.scan_dir.resolve()
        if not scan_root.is_dir():
            ap.error(f'scan directory does not exist: {a.scan_dir}')
        candidates = []
        if (scan_root / '.agents/skills').is_dir():
            candidates.append(scan_root)
        for child in sorted(p for p in scan_root.iterdir() if p.is_dir()):
            if (child / '.agents/skills').is_dir():
                candidates.append(child)
        projects = [inspect_project(p, incoming, lib_version, lib_commit) for p in candidates]
        print(json.dumps({
            'library_version': lib_version,
            'library_commit': lib_commit,
            'project_count': len(projects),
            'projects': projects,
        }, indent=2))
        return 0

    if a.project is None:
        ap.error('provide a project path or --scan-dir')

    project_root = a.project.resolve()
    dest = project_root / '.agents/skills'
    if not dest.is_dir():
        ap.error('project has no pinned .agents/skills')

    info = inspect_project(project_root, incoming, lib_version, lib_commit)
    changes = info['update']
    conflicts = info['conflict']
    removes = info['prune']
    legacy = info['legacy_unknown']
    local = hashes(dest)
    basefile = dest / '.storycraft-base.json'
    base = json.loads(basefile.read_text(encoding='utf-8')) if basefile.exists() else {}

    report = dict(
        update=changes, conflict=conflicts, prune=removes,
        legacy_unknown=legacy,
        templates='Book instructions are preserved; reconcile new workflow sections manually.',
        schema='Version 1 records initialize lazily; unsupported schemas are rejected, never rewritten.',
    )
    if a.apply:
        for name in changes:
            target = dest / name
            if target.is_symlink() or not target.resolve().is_relative_to(dest.resolve()):
                raise ValueError('unsafe destination: ' + name)
            if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != local.get(name):
                raise ValueError('destination changed during update: ' + name)
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(dir=target.parent)
            os.close(fd)
            try:
                shutil.copy2(ROOT / 'skills' / name, temporary)
                os.replace(temporary, target)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        if a.prune:
            for name in removes:
                target = dest / name
                if not target.resolve().is_relative_to(dest.resolve()):
                    raise ValueError('unsafe prune destination')
                target.unlink()
        # Record incoming baselines only for files actually installed/matching.
        newbase = dict(base)
        final = hashes(dest)
        for name, h in incoming.items():
            if final.get(name) == h:
                newbase[name] = h
        basefile.write_text(json.dumps(newbase, indent=2) + '\n', encoding='utf-8')
        if not conflicts:
            (dest / '.storycraft-source').write_text(
                'library: storycraft-skills\nversion: ' + lib_version + '\ncommit: ' + lib_commit
                + '\nskills: ' + str(len(list((ROOT / 'skills').glob('*/SKILL.md'))))
                + '\npinned: ' + datetime.now(timezone.utc).date().isoformat()
                + '\nsource: ' + str(ROOT) + '\n',
                encoding='utf-8',
            )
        report['pin'] = 'retained: conflicts need reconciliation' if conflicts else 'updated'
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
