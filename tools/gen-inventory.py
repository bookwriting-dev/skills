#!/usr/bin/env python3
"""Generate docs/SKILL-INVENTORY.md from every skill's frontmatter.

The frontmatter is the single source of truth; this renders it so the inventory
can never drift from the library. `--check` fails when the committed file is
stale, which is what CI runs.

Usage:
    python3 tools/gen-inventory.py            # rewrite docs/SKILL-INVENTORY.md
    python3 tools/gen-inventory.py --check     # exit 1 if the file is out of date
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from skill_lib import CATEGORY_ORDER, ROOT, load_skills

OUT = ROOT / "docs" / "SKILL-INVENTORY.md"

CATEGORY_TITLES = {
    "fiction-writing": "Fiction — writing",
    "fiction-editing": "Fiction — editing",
    "nonfiction-writing": "Non-fiction — writing",
    "nonfiction-editing": "Non-fiction — editing",
    "cross-cutting": "Cross-cutting",
    "utilities": "Utilities",
    "meta": "Meta",
}


def render() -> str:
    skills = load_skills()
    by_cat: dict[str, list[str]] = {c: [] for c in CATEGORY_ORDER}
    unknown: list[str] = []
    for name, rec in skills.items():
        cat = rec["category"]
        (by_cat[cat] if cat in by_cat else unknown).append(name)

    lines: list[str] = []
    lines.append("# Skill Inventory")
    lines.append("")
    lines.append(
        "Generated from each skill's `SKILL.md` frontmatter by "
        "`tools/gen-inventory.py` (`make inventory`). **Do not edit by hand** — "
        "`make check` fails if this file is out of date."
    )
    lines.append("")
    lines.append(f"Total: **{len(skills)} skills**. The hand-written workflow guide "
                 "is [USER.md](USER.md); this file is the machine-checked roster.")
    lines.append("")

    for cat in CATEGORY_ORDER:
        names = sorted(by_cat[cat])
        if not names:
            continue
        lines.append(f"## {CATEGORY_TITLES.get(cat, cat)} ({len(names)})")
        lines.append("")
        lines.append("| Skill | Version | Summary |")
        lines.append("|---|---|---|")
        for name in names:
            rec = skills[name]
            desc = " ".join(rec["description"].split())
            lines.append(f"| `{name}` | {rec['version']} | {desc} |")
        lines.append("")

    if unknown:
        lines.append("## Uncategorized")
        lines.append("")
        for name in sorted(unknown):
            lines.append(f"- `{name}` ({skills[name]['version']})")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="fail if the file is stale")
    args = ap.parse_args()

    content = render()
    if args.check:
        existing = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if existing != content:
            print(f"tools/gen-inventory.py: {OUT.relative_to(ROOT)} is out of date — run `make inventory`", file=sys.stderr)
            return 1
        print(f"{OUT.relative_to(ROOT)} is up to date")
        return 0

    OUT.write_text(content, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
