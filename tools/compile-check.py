#!/usr/bin/env python3
"""Syntax-check every Python file in tools/ and skills/ without writing bytecode.

`python -m compileall` would write __pycache__ directories into skills/, which
sync-check.sh (a filesystem diff) then reports as fork additions. This compiles in
memory instead, so the check is side-effect free.

Usage:
    python3 tools/compile-check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    bad = 0
    count = 0
    for base in ("tools", "skills"):
        for f in sorted((ROOT / base).rglob("*.py")):
            count += 1
            try:
                compile(f.read_text(encoding="utf-8"), str(f.relative_to(ROOT)), "exec")
            except SyntaxError as e:
                bad += 1
                print(f"  SYNTAX ERROR {f.relative_to(ROOT)}:{e.lineno}: {e.msg}", file=sys.stderr)
    if bad:
        print(f"compile-check: {bad} of {count} files failed", file=sys.stderr)
        return 1
    print(f"compile-check: {count} files OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
