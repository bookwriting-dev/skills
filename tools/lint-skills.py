#!/usr/bin/env python3
"""Lint the storycraft-skills library.

Zero dependencies (Python stdlib only), provider-neutral. This encodes the
invariants the 2026-10-11 audit checked by hand, so regressions fail CI instead
of waiting for the next manual sweep.

Errors (exit 1):
  * frontmatter contract: `name` == folder, quoted semver version, category in
    the enum, `description` present / < 1024 chars / no angle brackets.
  * broken skill-relative file paths (references/, assets/, scripts/, data/).
  * doc drift: docs/USER.md catalog versions vs frontmatter; the "N skills"
    count in README.md / docs/USER.md / docs/DEVELOPER.md vs the real count.

Warnings (exit 0 unless --strict):
  * orphaned bundled files (not named anywhere).
  * skills missing from templates/AGENTS.md's index.
  * phantom skill names (skill-shaped backticks that match no real skill and are
    not on the documented-unbuilt allowlist).
  * sync-manifest.txt duplicates / unsorted lines.

Usage:
    python3 tools/lint-skills.py            # errors fail, warnings print
    python3 tools/lint-skills.py --strict   # warnings fail too
"""

from __future__ import annotations

import argparse
import re
import sys

from skill_lib import ROOT, SKILLS, CATEGORY_ENUM, parse_frontmatter

# Documented-but-unbuilt skill names: legitimate mentions in the DEVELOPER.md
# reconciliation record / CHANGELOG-style history. Not phantoms.
DOCUMENTED_UNBUILT = {
    "nonfiction-reviewchapter",
    "nonfiction-revise",
    "nonfiction-sources",
    "nonfiction-claims",
    "nonfiction-terminology",
}

# Phrase-y backticked tokens that are skill-shaped but never skills.
EXTRA_ALLOW = {
    "fiction-writing",
    "fiction-editing",
    "nonfiction-writing",
    "nonfiction-editing",
    "cross-cutting",
    "reader-personas",
    "review-begin",
    "review-finish",
    "series-arc",  # Wiki file stem, not a skill
}

FILE_PREFIXES = ("references/", "assets/", "scripts/", "data/")
LINK_RE = re.compile(r"\]\(([^)]+)\)")
CODE_RE = re.compile(r"`([^`\n]+)`")
SKILL_SHAPED_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)+$")


class Finding:
    def __init__(self, level: str, where: str, msg: str):
        self.level = level
        self.where = where
        self.msg = msg

    def __str__(self) -> str:
        tag = "ERROR  " if self.level == "error" else "warning"
        return f"  {tag} {self.where}: {self.msg}"


def iter_paths(body: str):
    """Yield candidate skill-relative file paths found in links or backticks."""
    for m in LINK_RE.finditer(body):
        yield m.group(1)
    for m in CODE_RE.finditer(body):
        yield m.group(1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strict", action="store_true", help="warnings also fail")
    args = ap.parse_args()

    findings: list[Finding] = []
    skill_dirs = sorted(p for p in SKILLS.iterdir() if p.is_dir())
    skills: dict[str, dict] = {}  # name -> {"dir","version","category","desc"}

    all_text = []  # (label, text) for the orphan + phantom scans

    for d in skill_dirs:
        skill_md = d / "SKILL.md"
        where = f"skills/{d.name}/SKILL.md"
        if not skill_md.exists():
            findings.append(Finding("error", f"skills/{d.name}", "missing SKILL.md"))
            continue
        text = skill_md.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(text)
        if fm is None:
            findings.append(Finding("error", where, "missing or malformed frontmatter"))
            continue

        name = fm.get("name", "")
        if name != d.name:
            findings.append(Finding("error", where, f"`name: {name or '(none)'}` != folder `{d.name}`"))
        if name in skills:
            findings.append(Finding("error", where, f"duplicate skill name `{name}`"))

        desc = fm.get("description", "")
        if not desc:
            findings.append(Finding("error", where, "missing `description`"))
        else:
            if len(desc) >= 1024:
                findings.append(Finding("error", where, f"description is {len(desc)} chars (limit 1024)"))
            elif len(desc) > 450:
                findings.append(Finding("warning", where, f"description is {len(desc)} chars (target <= 450)"))
            if "<" in desc or ">" in desc:
                findings.append(Finding("error", where, "description contains `<` or `>`"))

        if name.startswith("nonfiction-"):
            if "fiction-knowledge" in text or "Wiki/Story/Book-N/knowledge.json" in text:
                findings.append(Finding("error", where, "non-fiction skill references fiction knowledge ledger"))

        meta = fm.get("metadata", {})
        version = meta.get("version", "")
        if not re.match(r"^\d+\.\d+\.\d+$", version or ""):
            findings.append(Finding("error", where, f"metadata.version not a quoted semver: {version!r}"))
        category = meta.get("category", "")
        if category not in CATEGORY_ENUM:
            findings.append(Finding("error", where, f"metadata.category {category!r} not in enum"))

        skills[name] = {
            "dir": d,
            "version": version,
            "category": category,
            "desc": desc,
        }
        all_text.append((where, text))

        # No stale __pycache__ or compiled bytecode left inside shippable skills/ tree.
        for cache_dir in sorted(d.rglob("__pycache__")):
            if cache_dir.is_dir():
                findings.append(Finding("error", str(cache_dir.relative_to(ROOT)), "stale `__pycache__` directory inside skills/"))

        # Resolvable skill-relative and cross-skill paths + bundled-dependencies for ../<skill>/scripts/ calls.
        deps_decl = [dep.strip() for dep in meta.get("bundled-dependencies", "").split(",") if dep.strip()]
        for cand in iter_paths(body):
            cand = cand.strip().rstrip(".,;:")
            cand = cand.split("#", 1)[0]
            if not cand or cand.startswith(("/", "#", "http")) or "<" in cand or "*" in cand:
                continue
            if cand.startswith("../"):
                resolved = (d / cand).resolve()
                if not resolved.is_relative_to(SKILLS.resolve()) or not resolved.exists():
                    findings.append(Finding("error", where, f"broken cross-skill path `{cand}`"))
                elif "/scripts/" in cand or cand.startswith("../") and resolved.parent.name == "scripts":
                    target_skill = resolved.relative_to(SKILLS.resolve()).parts[0]
                    if target_skill != d.name and target_skill not in deps_decl:
                        findings.append(Finding("error", where, f"uses sibling script `{cand}` without declaring `{target_skill}` in metadata.bundled-dependencies"))
                continue
            if not cand.startswith(FILE_PREFIXES) or "/" not in cand:
                continue
            if not (d / cand).exists():
                findings.append(Finding("error", where, f"broken path `{cand}`"))

        # Validate Markdown links inside references/*.md as well.
        refs_dir = d / "references"
        if refs_dir.is_dir():
            for ref_md in sorted(refs_dir.rglob("*.md")):
                ref_where = str(ref_md.relative_to(ROOT))
                ref_body = ref_md.read_text(encoding="utf-8")
                for m in LINK_RE.finditer(ref_body):
                    target = m.group(1).strip().split("#", 1)[0]
                    if not target or target.startswith(("/", "#", "http", "mailto:")) or "<" in target or "*" in target:
                        continue
                    resolved = (ref_md.parent / target).resolve()
                    if not resolved.is_relative_to(SKILLS.resolve()) or not resolved.exists():
                        findings.append(Finding("error", ref_where, f"broken reference link `{m.group(1).strip()}`"))

    KILL_SINGLE_SOURCE = {
        "kill-simile": "../kill-chapter/references/simile.md",
        "kill-person-who": "../kill-chapter/references/person-who.md",
        "kill-opinion-personification": "../kill-chapter/references/opinion-personification.md",
        "kill-the-whole": "../kill-chapter/references/the-whole.md",
        "kill-crutch": "../kill-chapter/references/crutch.md",
    }

    for name, record in skills.items():
        text = (record['dir'] / 'SKILL.md').read_text(encoding='utf-8')
        fm, body = parse_frontmatter(text)
        deps = [dep.strip() for dep in fm.get('metadata', {}).get('bundled-dependencies', '').split(',') if dep.strip()]
        for dependency in deps:
            if dependency not in skills:
                findings.append(Finding('error', name, 'missing bundled dependency: ' + dependency))
        if name in KILL_SINGLE_SOURCE:
            expected_ref = KILL_SINGLE_SOURCE[name]
            if 'kill-chapter' not in deps:
                findings.append(Finding('error', f'skills/{name}/SKILL.md', 'must declare `kill-chapter` in metadata.bundled-dependencies'))
            if expected_ref not in body:
                findings.append(Finding('error', f'skills/{name}/SKILL.md', f'must reference single-source rule file `{expected_ref}`'))

    EDITOR_LAYER_REFS = {
        "fiction-aiism-editor": "../fiction-aiism-editor/references/aiism-criteria.md",
        "fiction-prose-editor": "../fiction-prose-editor/references/prose-criteria.md",
        "fiction-line-editor": "../fiction-line-editor/references/agent-instructions.md",
    }
    full_editor = skills.get("fiction-full-editor")
    if full_editor:
        fe_text = (full_editor["dir"] / "SKILL.md").read_text(encoding="utf-8")
        fe_fm, fe_body = parse_frontmatter(fe_text)
        fe_deps = [d.strip() for d in fe_fm.get("metadata", {}).get("bundled-dependencies", "").split(",") if d.strip()]
        for dep, ref in EDITOR_LAYER_REFS.items():
            if dep not in fe_deps:
                findings.append(Finding("error", "skills/fiction-full-editor/SKILL.md", f"must declare `{dep}` in metadata.bundled-dependencies"))
            if ref not in fe_body:
                findings.append(Finding("error", "skills/fiction-full-editor/SKILL.md", f"must link layer criteria `{ref}`"))

    layer_headings: dict[str, str] = {}
    for layer_skill, rel_ref in EDITOR_LAYER_REFS.items():
        ref_path = SKILLS / rel_ref.removeprefix("../")
        if not ref_path.is_file():
            continue
        ref_rel = str(ref_path.relative_to(ROOT))
        for raw in ref_path.read_text(encoding="utf-8").splitlines():
            if not raw.startswith("### "):
                continue
            heading = re.sub(r"^###\s+(?:\d+\.\s*)?", "", raw).strip()
            heading = re.sub(r"\s*\([^)]*\)\s*$", "", heading).strip().lower()
            if layer_skill == "fiction-line-editor" and heading in {"aiisms", "narrative fragments", "telling over showing"}:
                findings.append(Finding("error", ref_rel, f"cross-layer contamination heading `{heading}` belongs to another editor layer"))
            if heading in layer_headings and layer_headings[heading] != ref_rel:
                findings.append(Finding("error", ref_rel, f"duplicate editor layer heading `{heading}` already owned by `{layer_headings[heading]}`"))
            else:
                layer_headings[heading] = ref_rel

    # Text corpus for orphan + phantom scans (references included).
    for d in skill_dirs:
        for f in sorted(d.rglob("*.md")):
            all_text.append((str(f.relative_to(ROOT)), f.read_text(encoding="utf-8")))
    corpus = "\n".join(t for _, t in all_text)

    # Orphans: bundled files (non-SKILL.md) whose basename appears nowhere.
    # `data/` corpora are addressed by glob (`data/*.txt`) and script, not by
    # name, so they are exempt.
    for d in skill_dirs:
        for sub in ("references", "assets", "scripts"):
            base = d / sub
            if not base.is_dir():
                continue
            for f in sorted(base.rglob("*")):
                if not f.is_file():
                    continue
                if f.suffix == ".pyc" or "__pycache__" in f.parts:
                    continue  # runtime-generated bytecode is not a shipped skill dependency
                if f.name == "__init__.py":
                    continue
                # search the corpus for the basename (cross-skill consumers count)
                if not re.search(re.escape(f.name), corpus):
                    findings.append(
                        Finding("warning", f"skills/{d.name}/{sub}", f"orphaned file `{f.name}` (named nowhere)")
                    )

    # Phantom skill names in docs + skills.
    families = {n.split("-")[0] for n in skills}
    real = set(skills) | DOCUMENTED_UNBUILT | EXTRA_ALLOW
    doc_files = [ROOT / "README.md", ROOT / "templates" / "AGENTS.md",
                 ROOT / "docs" / "USER.md", ROOT / "docs" / "DEVELOPER.md"]
    scan = doc_files + [ROOT / f for f, _ in all_text if f.endswith(".md")]
    seen_phantoms: set[str] = set()
    for f in scan:
        if not f.exists():
            continue
        for m in CODE_RE.finditer(f.read_text(encoding="utf-8")):
            tok = m.group(1).strip()
            if not SKILL_SHAPED_RE.match(tok) or tok in real or tok in seen_phantoms:
                continue
            if tok.split("-")[0] in families:
                seen_phantoms.add(tok)
                findings.append(
                    Finding("warning", str(f.relative_to(ROOT)), f"skill-shaped name `{tok}` matches no skill")
                )

    # USER.md catalog version drift.
    user_md = ROOT / "docs" / "USER.md"
    if user_md.exists():
        catalog_re = re.compile(r"`([a-z0-9-]+)`\s+(\d+\.\d+\.\d+)")
        cited: set[str] = set()
        for name, ver in catalog_re.findall(user_md.read_text(encoding="utf-8")):
            cited.add(name)
            if name in skills and skills[name]["version"] != ver:
                findings.append(
                    Finding("error", "docs/USER.md", f"`{name}` catalog says {ver}, frontmatter says {skills[name]['version']}")
                )
        for name in sorted(set(skills) - cited):
            findings.append(Finding("warning", "docs/USER.md", f"skill `{name}` not in the catalog"))

    # Count drift. Only total claims ("all N skills" / "**N skills**") are
    # checked — a phrase like "upstream's 42 skills" is a subset, not the total.
    total = len(skills)
    count_re = re.compile(r"(?:all\b|\*\*)\s*(\d+)\s+skills\b", re.IGNORECASE)
    for rel in ("README.md", "docs/USER.md", "docs/DEVELOPER.md"):
        p = ROOT / rel
        if not p.exists():
            continue
        for n in count_re.findall(p.read_text(encoding="utf-8")):
            if int(n) != total:
                findings.append(Finding("error", rel, f"says '{n} skills', library has {total}"))

    # templates/AGENTS.md index coverage.
    agents = ROOT / "templates" / "AGENTS.md"
    if agents.exists():
        atext = agents.read_text(encoding="utf-8")
        for name in sorted(skills):
            if not re.search(r"`" + re.escape(name) + r"`", atext):
                findings.append(Finding("warning", "templates/AGENTS.md", f"skill `{name}` not in the index"))

    # sync-manifest hygiene.
    manifest = ROOT / "sync-manifest.txt"
    if manifest.exists():
        entries = [l.strip() for l in manifest.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
        dupes = {e for e in entries if entries.count(e) > 1}
        for e in sorted(dupes):
            findings.append(Finding("error", "sync-manifest.txt", f"duplicate entry `{e}`"))
        if entries != sorted(entries):
            findings.append(Finding("warning", "sync-manifest.txt", "entries are not sorted"))

    # Report.
    total_desc_chars = sum(len(r["desc"]) for r in skills.values())
    errors = [f for f in findings if f.level == "error"]
    warnings = [f for f in findings if f.level == "warning"]
    print(f"lint-skills: {total} skills, {total_desc_chars} desc chars (~{total_desc_chars // 4} tokens), {len(errors)} error(s), {len(warnings)} warning(s)")
    if findings:
        print()
        for f in errors + warnings:
            print(f)
    if errors or (args.strict and warnings):
        return 1
    print("\nOK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
