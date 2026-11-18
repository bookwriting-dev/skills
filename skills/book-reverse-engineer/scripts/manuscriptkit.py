#!/usr/bin/env python3
"""Locate a finished or raw manuscript and split it into chapter units.

Two input shapes are supported:
  - a single file (.md, .txt) containing the whole manuscript, split by
    heading detection (Chapter N / Part N / Section N / numbered headings)
  - a directory of one file per chapter, ordered by natural sort

Word counts use standard whitespace tokenization.

Usable as a library or standalone CLI:
    python3 manuscriptkit.py <path>
    python3 manuscriptkit.py <path> --export-chapters <target_chapters_dir>
"""
from __future__ import annotations

import argparse
import difflib
import fcntl
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

HEADING_PATTERNS = [
    re.compile(r"^#{1,3}[ \t]*Chapter[ \t]+[A-Za-z0-9]+\b.*$", re.IGNORECASE),
    re.compile(r"^Chapter[ \t]+(?:\d+|[IVXLCDM]+)(?:[ \t]*[:.–—-][ \t]*\S.*)?[ \t]*$", re.IGNORECASE),
    re.compile(r"^#{1,3}[ \t]*Part[ \t]+[A-Za-z0-9]+\b.*$", re.IGNORECASE),
    re.compile(r"^#{1,3}[ \t]*Section[ \t]+[A-Za-z0-9]+\b.*$", re.IGNORECASE),
    re.compile(r"^#{1,3}[ \t]*\d+[\.:]?[ \t]+\S.*$"),
]

UNIT_FILENAME = re.compile(
    r"^(?:ch(?:apter)?|sec(?:tion)?)?[\s_\-]*0*(\d+)", re.IGNORECASE
)
RECEIPT = '.storycraft-import.json'
PENDING = '.storycraft-import-pending'


def count_words(text: str) -> int:
    return len([w for w in re.split(r"\s+", text) if w.strip()])


def _natural_key(name: str) -> tuple:
    return tuple(int(p) if i % 2 else p.casefold() for i, p in enumerate(re.split(r"(\d+)", name)))


def locate(path: str) -> Path:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"No such file or directory: {path}")
    return p


def split_file(text: str) -> tuple[list[dict], list[str]]:
    """Split single-file manuscript text into units by heading detection.

    Returns (units, warnings). Each unit is:
    {"n", "title", "start_line", "end_line", "word_count", "body"}
    Line numbers are 1-indexed and inclusive.
    """
    lines = text.splitlines()
    warnings: list[str] = []

    candidates = [[] for _ in range(4)]
    fence = None
    for index, line in enumerate(lines):
        marker = re.match(r"^\s*(\x60{3,}|~{3,})", line)
        if marker:
            run = marker[1]
            if fence is None:
                fence = run
            elif run.startswith(fence) and not line.strip()[len(run):].strip():
                fence = None
            continue
        if fence is None:
            for kind, pattern in enumerate(HEADING_PATTERNS):
                if pattern.fullmatch(line):
                    candidates[max(0, kind - 1)].append(index)
                    break
    starts = next((group for group in candidates if group), [])
    if not starts:
        warnings.append(
            "Could not identify chapter headings in this file. "
            "Treating the whole file as a single unit."
        )
        return (
            [{
                "n": 1,
                "title": "Untitled",
                "start_line": 1,
                "end_line": len(lines),
                "word_count": count_words(text),
                "body": text,
            }],
            warnings,
        )

    units: list[dict] = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(lines)
        body = "\n".join(lines[start:end]).strip("\n")
        units.append({
            "n": i + 1,
            "title": lines[start].lstrip("#").strip(),
            "start_line": start + 1,
            "end_line": end,
            "word_count": count_words(body),
            "body": body,
            "has_heading": True,
        })

    return units, warnings


def list_dir_units(directory: Path) -> tuple[list[dict], list[str]]:
    """Enumerate a directory of per-chapter files in natural order."""
    all_files = sorted(
        (f for f in directory.iterdir() if f.is_file() and not f.name.startswith(".")),
        key=lambda f: _natural_key(f.name),
    )
    warnings: list[str] = []
    files = [f for f in all_files if f.suffix.casefold() in ('.md', '.txt')]
    ignored = [f.name for f in all_files if f not in files]
    if ignored:
        warnings.append("Unsupported files left in the source directory: " + ", ".join(ignored))
    if any(f.stem.casefold().replace('-', '').replace('_', '') == 'frontmatter' for f in files):
        files = [f for f in files if f.stem.casefold().replace('-', '').replace('_', '') != 'frontmatter']
    unordered = [f for f in files if not UNIT_FILENAME.match(f.name)]
    if unordered:
        warnings.append(
            "Files with no recognizable chapter number in the name: "
            + ", ".join(f.name for f in unordered)
            + " — confirm reading order manually."
        )

    units = []
    for i, f in enumerate(files):
        text = f.read_text(encoding="utf-8-sig").strip("\n")
        units.append({
            "n": i + 1,
            "title": f.stem,
            "source": f.name,
            "word_count": count_words(text),
            "body": text,
            "has_heading": bool(re.match(r"^#{1,3}[ \t]+\S", text)),
        })
    return units, warnings


def analyze(path: str) -> dict:
    target = locate(path)
    front_matter = ''
    if target.is_dir():
        units, warnings = list_dir_units(target)
        front_files = [p for p in target.iterdir() if p.is_file() and p.suffix.casefold() in ('.md', '.txt')
                       and p.stem.casefold().replace('-', '').replace('_', '') == 'frontmatter']
        if len(front_files) > 1:
            raise ValueError("multiple front matter files in the source directory")
        if front_files:
            front_matter = front_files[0].read_text(encoding="utf-8-sig").strip("\n")
        mode = "directory"
    else:
        if target.suffix.casefold() not in ('.md', '.txt'):
            raise ValueError("manuscript must be Markdown (.md), plain text (.txt), or a chapter directory")
        text = target.read_text(encoding="utf-8-sig")
        units, warnings = split_file(text)
        if units[0].get("has_heading"):
            front_matter = "\n".join(text.splitlines()[:units[0]["start_line"] - 1]).strip("\n")
        mode = "single-file"
    if not units:
        raise ValueError("no manuscript chapters found")

    # Omit bodies from the summary dict output
    summary_units = [
        {k: v for k, v in u.items() if k != "body"}
        for u in units
    ]

    return {
        "source": str(target),
        "mode": mode,
        "unit_count": len(units),
        "total_words": sum(u["word_count"] for u in units),
        "units": summary_units,
        "warnings": warnings,
        "front_matter_words": count_words(front_matter),
        "_raw_units": units,
        "_front_matter": front_matter,
    }


def incoming_files(analysis_result):
    files = {}
    if analysis_result["_front_matter"].strip():
        files['FrontMatter.md'] = analysis_result["_front_matter"] + "\n"
    for u in analysis_result["_raw_units"]:
        n = u["n"]
        filename = f"Chapter-{n:03d}.md"
        body = u["body"]
        if u["has_heading"]:
            title, _, body = body.partition("\n")
            title = title.lstrip("#").strip()
        else:
            title = u["title"]
            body = "\n" + body
        if not re.match(rf"^Chapter {n}(?:$|: | [—–-] )", title):
            short_title = re.sub(r"^(?:chapter|part|section)\s+[A-Za-z0-9]+\b[\s:–—.-]*",
                                 "", title, flags=re.IGNORECASE)
            title = f"Chapter {n}" + (f" — {short_title}" if short_title else "")
        files[filename] = f"# {title}\n{body.rstrip(chr(10))}\n"
    return files


def sha256(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


def local_bytes(path):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError(f"import expects a regular file: {path}")
    return path.read_bytes() if path.is_file() else None


def metadata(path, fallback=None):
    data = local_bytes(path)
    if data is None and fallback is not None:
        return fallback
    if data is None:
        raise ValueError(f"import operation is missing its metadata: {path}")
    record = json.loads(data)
    if record.get("schema_version") != 1:
        raise ValueError(f"unsupported import record: {path}")
    return record


def plan_import(result, dest):
    base = metadata(dest / RECEIPT, {"files": {}})["files"]
    incoming = incoming_files(result)
    entries = {}
    for name, text in incoming.items():
        current = local_bytes(dest / name)
        new_hash = sha256(text.encode('utf-8'))
        old_hash = sha256(current)
        if old_hash == new_hash:
            action = "unchanged"
        elif old_hash == base.get(name):
            action = "create" if current is None else "update"
        elif new_hash == base.get(name):
            action = "preserve_local"
        else:
            action = "conflict"
        entry = {"action": action, "current_sha256": old_hash, "incoming_sha256": new_hash}
        if action in ("conflict", "update"):
            old_lines = current.decode('utf-8', errors='replace').splitlines(keepends=True) if current else []
            entry["diff"] = "".join(difflib.unified_diff(old_lines, text.splitlines(keepends=True),
                                                          fromfile=name, tofile=f"incoming/{name}"))
        entries[name] = entry
    return entries, incoming, base


def replace_file(path, data):
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def recover_import(dest):
    pending = dest / PENDING
    if pending.is_symlink():
        raise ValueError("import journal must be a local directory")
    transaction = metadata(pending / "plan.json")
    staged = {}
    for name, entry in transaction["writes"].items():
        if not re.fullmatch(r"(?:Chapter-\d+|FrontMatter)\.md", name):
            raise ValueError(f"invalid import destination in journal: {name}")
        data = local_bytes(pending / name)
        current = sha256(local_bytes(dest / name))
        if data is None or sha256(data) != entry["incoming_sha256"]:
            raise ValueError(f"staged import data changed: {name}")
        if current not in (entry["current_sha256"], entry["incoming_sha256"]):
            raise ValueError(f"{name} changed during import; staged copies remain in {pending}")
        if current != entry["incoming_sha256"]:
            staged[name] = data
    for name, data in staged.items():
        expected = transaction["writes"][name]["current_sha256"]
        if sha256(local_bytes(dest / name)) != expected:
            raise ValueError(f"{name} changed during import; staged copies remain in {pending}")
        replace_file(dest / name, data)
    replace_file(dest / RECEIPT, (json.dumps(transaction["receipt"], indent=2) + "\n").encode())
    shutil.rmtree(pending)
    return list(staged)


def export_chapters(analysis_result, target_dir, *, approvals=(), keep=(), recover=False):
    """Stage a revision-aware import and make retries converge on its recorded destinations."""
    dest = Path(target_dir).expanduser().resolve()
    if analysis_result:
        source = Path(analysis_result['source'])
        if dest == source or source.is_file() and source.parent == dest and source.name in incoming_files(analysis_result):
            raise ValueError("choose a destination that leaves the raw manuscript in place")
    dest.mkdir(parents=True, exist_ok=True)
    pending = dest / PENDING
    fd = os.open(dest, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        if recover:
            if not pending.is_dir():
                raise ValueError("no interrupted import to recover")
            return recover_import(dest)
        if pending.exists() or pending.is_symlink():
            raise ValueError("interrupted import exists; inspect preview and use --recover")
        entries, incoming, base = plan_import(analysis_result, dest)
        approved = {}
        for approval in approvals:
            parts = approval.split(':')
            if len(parts) != 3:
                raise ValueError("--replace requires FILE:CURRENT_SHA256:INCOMING_SHA256")
            name, current, new = parts
            if name in approved or name in keep:
                raise ValueError(f"conflicting resolutions for {name}")
            approved[name] = (None if current == 'missing' else current, new)
        if (set(approved) | set(keep)) - set(incoming):
            raise ValueError("import resolutions must name destinations in the current preview")
        writes, new_base = {}, dict(base)
        for name, entry in entries.items():
            action = entry['action']
            if name in keep:
                continue
            if name in approved:
                if approved[name] != (entry['current_sha256'], entry['incoming_sha256']):
                    raise ValueError(f"approved import diff is stale for {name}; run --preview again")
                if action != 'unchanged':
                    action = 'update'
            if action == "conflict":
                raise ValueError(f"import conflict at {name}; inspect --preview and resolve the exact diff")
            if action in ('update', 'create'):
                writes[name] = entry
            if action != 'preserve_local':
                new_base[name] = entry['incoming_sha256']
        if not writes and new_base == base:
            return []
        receipt = {"schema_version": 1, "files": new_base}
        with tempfile.TemporaryDirectory(prefix='.storycraft-import-stage-', dir=dest) as tmp:
            stage = Path(tmp)
            for name in writes:
                replace_file(stage / name, incoming[name].encode('utf-8'))
            replace_file(stage / 'plan.json', (json.dumps(
                {"schema_version": 1, "writes": writes, "receipt": receipt}, indent=2) + "\n").encode())
            stage.rename(pending)
        return recover_import(dest)
    finally:
        os.close(fd)


def main() -> None:
    parser = argparse.ArgumentParser(description="Split or analyze manuscript into chapter units.")
    parser.add_argument("path", nargs="?", help="Path to manuscript file or chapter directory")
    parser.add_argument("--export-chapters", dest="export_dir", help="Target directory to write Chapter-NNN.md files")
    parser.add_argument("--preview", action="store_true", help="Show import destinations and diffs without writing")
    parser.add_argument("--replace", action="append", default=[], metavar="FILE:CURRENT_SHA256:INCOMING_SHA256")
    parser.add_argument("--keep", action="append", default=[], metavar="FILE")
    parser.add_argument("--recover", action="store_true", help="Resume a previously staged import into --export-chapters")
    args = parser.parse_args()
    if (args.preview or args.recover or args.replace or args.keep) and not args.export_dir:
        parser.error("--export-chapters is required for import controls")
    if args.recover:
        if args.preview or args.replace or args.keep:
            parser.error("--recover resumes the recorded operation")
        print(json.dumps({"recovered": export_chapters(None, args.export_dir, recover=True)}))
        return
    if not args.path:
        parser.error("a manuscript path is required")
    result = analyze(args.path)
    clean_result = {k: v for k, v in result.items() if not k.startswith('_')}
    if args.export_dir:
        dest = Path(args.export_dir).expanduser().resolve()
        if dest == Path(result["source"]):
            raise ValueError("choose a chapter destination outside the source chapter directory")
        entries, _, _ = plan_import(result, dest)
        clean_result["import"] = {"destination": str(dest), "files": entries,
                                  "pending_recovery": (dest / PENDING).exists()}
        if not args.preview:
            clean_result["written"] = export_chapters(result, dest, approvals=args.replace, keep=args.keep)
    print(json.dumps(clean_result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        sys.exit(str(exc))
