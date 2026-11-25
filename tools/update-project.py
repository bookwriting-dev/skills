#!/usr/bin/env python3
"""Conservative library upgrade and multi-project fleet status scanner. Unknown/local files are never overwritten."""
import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
MANAGED_START = '<!-- STORYCRAFT-MANAGED:START -->'
MANAGED_END = '<!-- STORYCRAFT-MANAGED:END -->'


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


def reconstruct_base_from_git(commit: str | None) -> tuple[dict[str, str], str]:
    """Reconstruct {rel_path: sha256} for skills/ from a historical commit in ROOT."""
    if not commit or commit == 'unknown' or not re.fullmatch(r'[0-9a-fA-F]{4,40}', commit):
        return {}, 'none'
    try:
        resolved = subprocess.check_output(
            ['git', 'rev-parse', '--verify', '--end-of-options', f'{commit}^{{commit}}'],
            cwd=ROOT, stderr=subprocess.DEVNULL, text=True,
        ).strip()
        tree = subprocess.check_output(
            ['git', 'ls-tree', '-r', '-z', resolved, '--', 'skills'],
            cwd=ROOT, stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return {}, 'none'

    blobs: list[tuple[str, str]] = []
    for entry in tree.split(b'\x00'):
        if not entry:
            continue
        meta_part, path_part = entry.split(b'\t', 1)
        parts = meta_part.decode('utf-8').split()
        if len(parts) >= 3 and parts[1] == 'blob':
            rel = path_part.decode('utf-8')
            if rel.startswith('skills/'):
                blobs.append((parts[2], rel[len('skills/'):]))
    if not blobs:
        return {}, 'none'

    batch_in = ''.join(f'{oid}\n' for oid, _ in blobs).encode('ascii')
    proc = subprocess.run(
        ['git', 'cat-file', '--batch'],
        cwd=ROOT, input=batch_in, capture_output=True, check=False,
    )
    if proc.returncode != 0:
        return {}, 'none'

    raw = proc.stdout
    pos = 0
    reconstructed: dict[str, str] = {}
    for _, rel in blobs:
        nl = raw.find(b'\n', pos)
        if nl < 0:
            break
        header = raw[pos:nl].decode('utf-8', errors='replace').split()
        pos = nl + 1
        if len(header) >= 3 and header[1] == 'blob':
            size = int(header[2])
            content = raw[pos:pos + size]
            reconstructed[rel] = hashlib.sha256(content).hexdigest()
            pos += size + 1  # skip trailing LF
    return reconstructed, f'git_commit:{resolved[:7]}'


def legacy_reports(project_root: Path) -> list[str]:
    edits_dir = project_root / '_Edits'
    if not edits_dir.is_dir():
        return []
    candidates = sorted(set(edits_dir.glob('Book-*/Chapter-*_*.md')) | set(edits_dir.glob('Chapter-*_*.md')))
    return [
        str(p.relative_to(project_root))
        for p in candidates
        if p.is_file() and not p.with_suffix('.meta.json').exists()
    ]


def extract_managed_block(text: str) -> tuple[int, int, str] | None:
    start = text.find(MANAGED_START)
    end = text.find(MANAGED_END)
    if start < 0 or end < 0 or end < start:
        return None
    end_full = end + len(MANAGED_END)
    return start, end_full, text[start:end_full]


def inspect_instructions(project_root: Path) -> tuple[str, str | None]:
    template_path = ROOT / 'templates' / 'AGENTS.md'
    target_path = project_root / 'AGENTS.md'
    if not template_path.is_file() or not target_path.is_file():
        return 'missing', None
    tpl_block = extract_managed_block(template_path.read_text(encoding='utf-8'))
    cur_text = target_path.read_text(encoding='utf-8')
    cur_block = extract_managed_block(cur_text)
    if tpl_block is None or cur_block is None:
        return 'manual_reconcile_needed (no managed markers)', None
    if tpl_block[2] == cur_block[2]:
        return 'up_to_date', None
    updated_text = cur_text[:cur_block[0]] + tpl_block[2] + cur_text[cur_block[1]:]
    return 'update_available', updated_text


def inspect_project(project_dir: Path, incoming: dict[str, str], lib_version: str, lib_commit: str) -> dict:
    project_root = project_dir.resolve()
    dest = project_root / '.agents/skills'
    local = hashes(dest)
    basefile = dest / '.storycraft-base.json'
    pin = parse_source_pin(dest)
    if basefile.exists():
        base = json.loads(basefile.read_text(encoding='utf-8'))
        base_source = 'base_file'
    else:
        base, base_source = reconstruct_base_from_git(pin.get('pinned_commit'))

    changes, conflicts, removes, local_only = [], [], [], []
    for name, h in incoming.items():
        if name not in local or local[name] == base.get(name):
            if local.get(name) != h:
                changes.append(name)
        elif local[name] != h:
            conflicts.append(name)
    for name in local.keys() - incoming.keys():
        if name in base:
            if local[name] == base[name]:
                removes.append(name)
            else:
                conflicts.append(name)
        else:
            local_only.append(name)
    legacy = legacy_reports(project_root)
    sorted_changes = sorted(changes)
    sorted_conflicts = sorted(set(conflicts))
    sorted_removes = sorted(removes)
    sorted_local_only = sorted(local_only)
    if sorted_conflicts:
        status = 'CONFLICT'
    elif sorted_changes or sorted_removes or pin['pinned_version'] != lib_version:
        status = 'BEHIND'
    else:
        status = 'CURRENT'
    instr_status, _ = inspect_instructions(project_root)
    return {
        'project': project_root.name,
        'path': str(project_root),
        'status': status,
        'base_source': base_source,
        'library_version': lib_version,
        'library_commit': lib_commit,
        **pin,
        'update': sorted_changes,
        'conflict': sorted_conflicts,
        'prune': sorted_removes,
        'local_only': sorted_local_only,
        'legacy_unknown': legacy,
        'instructions': instr_status,
    }


def atomic_write_text(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=target.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('project', nargs='?', type=Path)
    ap.add_argument('--scan-dir', type=Path,
                    help='Scan a directory of book projects and report library version/migration status across all pinned repos')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--prune', action='store_true')
    ap.add_argument('--migration', action='store_true')
    ap.add_argument('--update-instructions', action='store_true',
                    help='Update only the STORYCRAFT-MANAGED block in AGENTS.md when markers are present')
    a = ap.parse_args()

    incoming = hashes(ROOT / 'skills')
    lib_version, lib_commit = library_meta()

    if a.scan_dir is not None:
        if a.apply or a.prune or a.update_instructions:
            ap.error('--scan-dir is read-only and cannot be combined with --apply, --prune, or --update-instructions')
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
    local_only = info['local_only']
    legacy = info['legacy_unknown']
    local = hashes(dest)
    basefile = dest / '.storycraft-base.json'
    if basefile.exists():
        base = json.loads(basefile.read_text(encoding='utf-8'))
    else:
        base, _ = reconstruct_base_from_git(info.get('pinned_commit'))

    instr_status, updated_agents = inspect_instructions(project_root)
    report = dict(
        base_source=info['base_source'],
        update=changes, conflict=conflicts, prune=removes,
        local_only=local_only,
        legacy_unknown=legacy,
        templates='Book instructions are preserved; reconcile new workflow sections manually.'
                  if instr_status != 'up_to_date' and not a.update_instructions
                  else instr_status,
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
        if a.update_instructions:
            if updated_agents is not None:
                atomic_write_text(project_root / 'AGENTS.md', updated_agents)
                report['templates'] = 'updated managed block in AGENTS.md'
            else:
                report['templates'] = instr_status
        # Record incoming baselines only for files actually installed/matching.
        newbase = dict(base)
        final = hashes(dest)
        for name, h in incoming.items():
            if final.get(name) == h:
                newbase[name] = h
        if a.prune:
            for name in removes:
                newbase.pop(name, None)
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
