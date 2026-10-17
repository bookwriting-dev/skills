#!/usr/bin/env python3
"""Shared helpers for the storycraft-skills toolchain (stdlib only).

Loads every skill's frontmatter once so the linter and the inventory generator
agree on what a skill is. Kept deliberately schema-light (no PyYAML): frontmatter
is `key: value` at indent 0 plus one nested `metadata:` block.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"

CATEGORY_ORDER = [
    "fiction-writing",
    "fiction-editing",
    "nonfiction-writing",
    "nonfiction-editing",
    "cross-cutting",
    "utilities",
    "meta",
]
CATEGORY_ENUM = set(CATEGORY_ORDER)


def _unquote(v: str) -> str:
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def parse_frontmatter(text: str):
    """Return (fields, body). `fields` has a nested 'metadata' dict."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None, text
    fields: dict = {}
    meta: dict = {}
    block = None
    for raw in lines[1:end]:
        if not raw.strip():
            continue
        if raw.startswith((" ", "\t")):
            m = re.match(r"^\s+([A-Za-z0-9_-]+):\s?(.*)$", raw)
            if m and block == "metadata":
                meta[m.group(1)] = _unquote(m.group(2).strip())
            continue
        m = re.match(r"^([A-Za-z0-9_-]+):\s?(.*)$", raw)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val == "":
            block = key
            if key == "metadata":
                fields["metadata"] = meta
        else:
            block = None
            fields[key] = _unquote(val)
    fields.setdefault("metadata", meta)
    body = "\n".join(lines[end + 1 :])
    return fields, body


def load_skills() -> dict:
    """Return {name: record} for every skill dir that has a SKILL.md."""
    out: dict = {}
    if not SKILLS.is_dir():
        return out
    for d in sorted(p for p in SKILLS.iterdir() if p.is_dir()):
        skill_md = d / "SKILL.md"
        if not skill_md.exists():
            continue
        text = skill_md.read_text(encoding="utf-8")
        fields, body = parse_frontmatter(text)
        if fields is None:
            continue
        meta = fields.get("metadata", {})
        out[fields.get("name", d.name)] = {
            "dir": d,
            "path": skill_md,
            "fields": fields,
            "version": meta.get("version", ""),
            "category": meta.get("category", ""),
            "description": fields.get("description", ""),
            "body": body,
        }
    return out
