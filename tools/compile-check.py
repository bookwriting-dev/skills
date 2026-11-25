#!/usr/bin/env python3
"""Syntax- and contract-check every script in the repo without writing bytecode.

Python: `python -m compileall` would write __pycache__ directories into skills/,
which sync-check.sh (a filesystem diff) then reports as fork additions. This
compiles in memory instead, so the check is side-effect free.

Shell: the repo's bash scripts are the highest-risk code in it — they scaffold
projects and update them in place — and they were previously unchecked by
anything. Each one is run through `bash -n`, which parses without executing.

Ledger contract: fiction-promises and promise-tracker are copied into projects
individually, so their duplicate parsers/assets cannot share a file — instead
this check imports both copies of chapter_number() and asserts they agree on a
fixed vector, and asserts the two assets/promises.yaml are byte-identical with
the full entry schema. The parsers once disagreed ('sec2.1' read as 21 by one
and 2 by the other), which made the same ledger overdue in one skill's report
and current in the other's.

Usage:
    python3 tools/compile-check.py
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Shell scripts live at the repo root and under tools/.
SHELL_SCRIPTS = ("new-book.sh", "sync-check.sh", "tools/update-project.sh")

LEDGER_SKILLS = ("skills/fiction-promises", "skills/promise-tracker")

# chapter_number() must return exactly these — a wrong value in BOTH copies is
# still a failure, so the expectations are pinned here, not just cross-compared.
CHAPTER_NUMBER_VECTOR = [
    ("ch12", 12),
    ("Chapter 12", 12),
    (12, 12),
    ("sec2.1", 2),
    ("ch3.5", 3),
    ("3.2", 3),
    ("", None),
    (None, None),
    ("epilogue", None),
]

LEDGER_ENTRY_KEYS = (
    "id", "promise", "introduced_ch", "kind", "weight", "payoff_by_ch",
    "project_type", "paid_in_ch", "paid_how", "deferred_to_series", "notes",
)


def check_python() -> tuple[int, int]:
    bad = count = 0
    for base in ("tools", "skills", "mcp"):
        base_dir = ROOT / base
        if not base_dir.is_dir():
            continue
        for f in sorted(base_dir.rglob("*.py")):
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


def _load_chapter_number(script: Path):
    # Never leave __pycache__ behind: sync-check.sh (filesystem diff) would
    # report it as a fork addition, and lint-skills flags it as orphaned.
    # The Makefile exports PYTHONDONTWRITEBYTECODE, but this tool must stay
    # side-effect free even when invoked directly.
    saved = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location(f"promises_{script.parents[1].name}", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module.chapter_number


def check_ledger_contract() -> tuple[int, int]:
    bad = count = 0
    parsers = {}
    assets = {}
    for rel in LEDGER_SKILLS:
        name = rel.split("/")[-1]
        script = ROOT / rel / "scripts" / "promises.py"
        asset = ROOT / rel / "assets" / "promises.yaml"
        if not script.is_file() or not asset.is_file():
            print(f"  LEDGER MISSING {rel}: scripts/promises.py or assets/promises.yaml", file=sys.stderr)
            bad += 1
            continue
        count += 1
        try:
            parsers[name] = _load_chapter_number(script)
        except Exception as e:
            print(f"  LEDGER IMPORT {rel}/scripts/promises.py: {e}", file=sys.stderr)
            bad += 1
            continue
        assets[name] = asset.read_text(encoding="utf-8")

    for name, fn in parsers.items():
        for raw, expected in CHAPTER_NUMBER_VECTOR:
            got = None
            try:
                got = fn(raw)
            except Exception as e:
                print(f"  LEDGER PARSER {name}.chapter_number({raw!r}) raised: {e}", file=sys.stderr)
                bad += 1
                continue
            if got != expected:
                print(f"  LEDGER PARSER {name}.chapter_number({raw!r}) = {got!r}, expected {expected!r}", file=sys.stderr)
                bad += 1

    values = list(parsers.values())
    if len(values) == 2:
        for raw, expected in CHAPTER_NUMBER_VECTOR:
            if values[0](raw) != values[1](raw):
                print(f"  LEDGER DISAGREE chapter_number({raw!r}): {LEDGER_SKILLS[0]} says {values[0](raw)!r}, {LEDGER_SKILLS[1]} says {values[1](raw)!r}", file=sys.stderr)
                bad += 1

    asset_texts = list(assets.values())
    if len(asset_texts) == 2 and asset_texts[0] != asset_texts[1]:
        print(f"  LEDGER ASSETS differ: {LEDGER_SKILLS[0]} and {LEDGER_SKILLS[1]} must ship byte-identical assets/promises.yaml", file=sys.stderr)
        bad += 1
    for name, text in assets.items():
        for key in LEDGER_ENTRY_KEYS:
            if not re.search(rf"^\s*-?\s*{key}:", text, re.MULTILINE):
                print(f"  LEDGER ASSET {name}/assets/promises.yaml: missing key '{key}'", file=sys.stderr)
                bad += 1
    return bad, count


def main() -> int:
    py_bad, py_count = check_python()
    sh_bad, sh_count = check_shell()
    led_bad, led_count = check_ledger_contract()

    if py_bad:
        print(f"compile-check: {py_bad} of {py_count} Python files failed", file=sys.stderr)
    if sh_bad:
        print(f"compile-check: {sh_bad} of {sh_count} shell scripts failed", file=sys.stderr)
    if led_bad:
        print(f"compile-check: {led_bad} ledger-contract failure(s)", file=sys.stderr)
    if py_bad or sh_bad or led_bad:
        return 1

    print(f"compile-check: {py_count} Python files, {sh_count} shell scripts, {led_count} ledger contracts OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
