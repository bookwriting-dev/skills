#!/usr/bin/env python3
"""Inspect or commit an immutable, multi-ledger generation."""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULE = ROOT / 'skills/book-status/scripts/ledger_store.py'
spec = importlib.util.spec_from_file_location('ledger_store', MODULE)
ledger_store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ledger_store)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--spec', type=Path)
    group.add_argument('--status', action='store_true')
    args = parser.parse_args()
    if args.status:
        result = ledger_store.status(args.root)
    else:
        result = ledger_store.commit(args.root, json.loads(args.spec.read_text(encoding='utf-8')))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({'error': str(exc)}))
        raise SystemExit(2)
