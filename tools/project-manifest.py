#!/usr/bin/env python3
"""Preview or explicitly apply the read-only legacy project manifest proposal."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_MODULE = ROOT / 'skills/book-status/scripts/project_manifest.py'
STATE_MODULE = ROOT / 'skills/book-status/scripts/project_state.py'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('action', choices=('preview', 'apply'))
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = module('project_manifest', MANIFEST_MODULE)
    state = module('project_state', STATE_MODULE)
    path = manifest.contained(root, manifest.MANIFEST_PATH)
    if path.exists():
        current = manifest.validate(json.loads(path.read_text(encoding='utf-8')), root)
        result = {'action': args.action, 'status': 'already_applied', 'manifest': current}
    else:
        proposed = manifest.propose(root)
        result = {'action': args.action, **proposed, 'status': 'preview' if args.action == 'preview' else 'not_applied'}
        if args.action == 'apply' and not proposed['unresolved']:
            with state.locked(path):
                if path.exists():
                    raise ValueError('manifest appeared during apply; inspect and retry')
                state.write(path, proposed['manifest'])
            result['status'] = 'applied'
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'error': str(exc)}))
        raise SystemExit(2)
