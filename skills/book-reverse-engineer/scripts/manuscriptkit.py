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
import json
import re
import sys
from pathlib import Path

HEADING_PATTERNS = [
    re.compile(r"^#{1,3}\s*Chapter\s+([A-Za-z0-9]+)\b.*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^#{1,3}\s*Part\s+([A-Za-z0-9]+)\b.*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^#{1,3}\s*Section\s+([A-Za-z0-9]+)\b.*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^#{1,3}\s*(\d+)[\.:]?\s+\S.*$", re.MULTILINE),
]

UNIT_FILENAME = re.compile(
    r"^(?:ch(?:apter)?|sec(?:tion)?)?[\s_\-]*0*(\d+)", re.IGNORECASE
)


def count_words(text: str) -> int:
    return len([w for w in re.split(r"\s+", text) if w.strip()])


def _natural_key(name: str) -> tuple:
    return tuple(int(p) if p.isdigit() else p for p in re.split(r"(\d+)", name))


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

    best_matches: list[re.Match] = []
    for pattern in HEADING_PATTERNS:
        matches = list(pattern.finditer(text))
        if len(matches) > len(best_matches):
            best_matches = matches
        if len(matches) >= 2:
            break

    if len(best_matches) < 2:
        warnings.append(
            "Could not find 2+ chapter headings in this file. "
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

    starts = [text.count("\n", 0, m.start()) + 1 for m in best_matches]
    if starts[0] > 1:
        lead = "\n".join(lines[: starts[0] - 1]).strip()
        if lead and count_words(lead) > 50:
            warnings.append(
                f"{count_words(lead)} words of front matter before the first "
                "detected heading — review whether it is preface, title page, or ch1."
            )

    units: list[dict] = []
    for i, (match, start_line) in enumerate(zip(best_matches, starts)):
        end_line = (starts[i + 1] - 1) if i + 1 < len(starts) else len(lines)
        body = "\n".join(lines[start_line - 1 : end_line]).strip()
        units.append({
            "n": i + 1,
            "title": match.group(0).lstrip("#").strip(),
            "start_line": start_line,
            "end_line": end_line,
            "word_count": count_words(body),
            "body": body,
        })

    return units, warnings


def list_dir_units(directory: Path) -> tuple[list[dict], list[str]]:
    """Enumerate a directory of per-chapter files in natural order."""
    files = sorted(
        (f for f in directory.iterdir() if f.is_file() and not f.name.startswith(".")),
        key=lambda f: _natural_key(f.name),
    )
    warnings: list[str] = []
    unordered = [f for f in files if not UNIT_FILENAME.match(f.name)]
    if unordered:
        warnings.append(
            "Files with no recognizable chapter number in the name: "
            + ", ".join(f.name for f in unordered)
            + " — confirm reading order manually."
        )

    units = []
    for i, f in enumerate(files):
        text = f.read_text(encoding="utf-8", errors="replace").strip()
        units.append({
            "n": i + 1,
            "title": f.stem,
            "source": f.name,
            "word_count": count_words(text),
            "body": text,
        })
    return units, warnings


def analyze(path: str) -> dict:
    target = locate(path)
    if target.is_dir():
        units, warnings = list_dir_units(target)
        mode = "directory"
    else:
        text = target.read_text(encoding="utf-8", errors="replace")
        units, warnings = split_file(text)
        mode = "single-file"

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
        "_raw_units": units,
    }


def export_chapters(analysis_result: dict, target_dir: str) -> list[str]:
    """Write normalized chapters to target_dir (e.g. Chapters/Book-1/Chapter-001.md)."""
    dest = Path(target_dir).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)
    created = []
    for u in analysis_result.get("_raw_units", []):
        n = u["n"]
        filename = f"Chapter-{n:03d}.md"
        out_path = dest / filename
        body = u.get("body", "")
        # If body doesn't start with heading, add one
        if not body.startswith("#"):
            body = f"# Chapter {n}: {u['title']}\n\n{body}"
        out_path.write_text(body + "\n", encoding="utf-8")
        created.append(str(out_path))
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Split or analyze manuscript into chapter units.")
    parser.add_argument("path", help="Path to manuscript file or chapter directory")
    parser.add_argument("--export-chapters", dest="export_dir", help="Target directory to write Chapter-NNN.md files")
    args = parser.parse_args()

    result = analyze(args.path)
    if args.export_dir:
        written = export_chapters(result, args.export_dir)
        print(f"Exported {len(written)} chapters to {args.export_dir}")

    # Don't print the raw bodies in stdout JSON
    clean_result = {k: v for k, v in result.items() if k != "_raw_units"}
    print(json.dumps(clean_result, indent=2))


if __name__ == "__main__":
    main()
