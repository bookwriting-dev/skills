#!/usr/bin/env python3
"""Inspect or commit an immutable, multi-ledger generation."""
import argparse
import json
from pathlib import Path
import ledger_store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--spec', type=Path)
    group.add_argument('--status', action='store_true')
    args = parser.parse_args()
    result = (ledger_store.status(args.root) if args.status else
              ledger_store.commit(args.root, json.loads(args.spec.read_text(encoding='utf-8'))))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({'error': str(exc)}))
        raise SystemExit(2)
