#!/usr/bin/env python3
"""Conservative library upgrade. Unknown/local files are never overwritten."""
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
            for p in base.rglob('*') if p.is_file() and not any(part.startswith('.') for part in p.relative_to(base).parts)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('project', type=Path)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--prune', action='store_true')
    ap.add_argument('--migration', action='store_true')
    a = ap.parse_args()
    dest = a.project.resolve() / '.agents/skills'
    if not dest.is_dir():
        ap.error('project has no pinned .agents/skills')
    incoming = hashes(ROOT / 'skills')
    local = hashes(dest)
    basefile = dest / '.storycraft-base.json'
    base = json.loads(basefile.read_text()) if basefile.exists() else {}
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
    legacy = [str(p.relative_to(a.project.resolve())) for p in (a.project.resolve() / '_Edits').rglob('Chapter-*.md')
              if not p.with_suffix('.meta.json').exists()]
    report = dict(update=sorted(changes), conflict=sorted(set(conflicts)), prune=sorted(removes),
                  legacy_unknown=legacy, templates='Book instructions are preserved; reconcile new workflow sections manually.',
                  schema='Version 1 records initialize lazily; unsupported schemas are rejected, never rewritten.')
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
                if os.path.exists(temporary): os.unlink(temporary)
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
        basefile.write_text(json.dumps(newbase, indent=2) + '\n')
        if not conflicts:
            commit = subprocess.check_output(['git','rev-parse','--short','HEAD'],cwd=ROOT,text=True).strip()
            (dest / '.storycraft-source').write_text('library: storycraft-skills\nversion: ' + (ROOT/'VERSION').read_text().strip() + '\ncommit: ' + commit + '\nskills: ' + str(len(list((ROOT/'skills').glob('*/SKILL.md')))) + '\npinned: ' + datetime.now(timezone.utc).date().isoformat() + '\nsource: ' + str(ROOT) + '\n')
        report['pin'] = 'retained: conflicts need reconciliation' if conflicts else 'updated'
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
