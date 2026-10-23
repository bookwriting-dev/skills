#!/usr/bin/env python3
"""Syntax-check every script in the repo without writing bytecode.

Python: `python -m compileall` would write __pycache__ directories into skills/,
which sync-check.sh (a filesystem diff) then reports as fork additions. This
compiles in memory instead, so the check is side-effect free.

Shell: the repo's bash scripts are the highest-risk code in it — they scaffold
projects and update them in place — and they were previously unchecked by
anything. Each one is run through `bash -n`, which parses without executing.

Usage:
    python3 tools/compile-check.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Shell scripts live at the repo root and under tools/.
SHELL_SCRIPTS = ("new-book.sh", "sync-check.sh", "tools/update-project.sh")


def check_python() -> tuple[int, int]:
    bad = count = 0
    for base in ("tools", "skills"):
        for f in sorted((ROOT / base).rglob("*.py")):
            count += 1
            try:
                compile(f.read_text(encoding="utf-8"), str(f.relative_to(ROOT)), "exec")
            except SyntaxError as e:
                bad += 1
                print(f"  SYNTAX ERROR {f.relative_to(ROOT)}:{e.lineno}: {e.msg}", file=sys.stderr)
            except UnicodeDecodeError as e:
                bad += 1
                print(f"  NOT UTF-8 {f.relative_to(ROOT)}: {e}", file=sys.stderr)
    return bad, count


def check_shell() -> tuple[int, int]:
    bad = count = 0
    for rel in SHELL_SCRIPTS:
        f = ROOT / rel
        if not f.is_file():
            print(f"  MISSING {rel} (declared in SHELL_SCRIPTS but not on disk)", file=sys.stderr)
            bad += 1
            continue
        count += 1
        proc = subprocess.run(
            ["bash", "-n", str(f)], capture_output=True, text=True, check=False
        )
        if proc.returncode != 0:
            bad += 1
            detail = (proc.stderr or proc.stdout).strip().splitlines()
            print(f"  SYNTAX ERROR {rel}: {detail[0] if detail else 'bash -n failed'}", file=sys.stderr)
    return bad, count


def main() -> int:
    py_bad, py_count = check_python()
    sh_bad, sh_count = check_shell()

    if py_bad:
        print(f"compile-check: {py_bad} of {py_count} Python files failed", file=sys.stderr)
    if sh_bad:
        print(f"compile-check: {sh_bad} of {sh_count} shell scripts failed", file=sys.stderr)
    if py_bad or sh_bad:
        return 1

    print(f"compile-check: {py_count} Python files, {sh_count} shell scripts OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
