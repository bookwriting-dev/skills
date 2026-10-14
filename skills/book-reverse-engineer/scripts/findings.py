#!/usr/bin/env python3
"""Turn a reviewed reverse-analysis.md report into a findings.yaml defect ledger.

Extracts confidence tags, canon gaps, dropped threads, voice breaks, and
continuity contradictions from the reverse analysis markdown file into
a structured YAML defect ledger for _Edits/Book-N/findings.yaml.

Usage:
    python3 findings.py _Edits/Book-1/reverse-analysis.md [-o _Edits/Book-1/findings.yaml]
"""
from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

TAGS = [
    ("CANON CONFLICT", "conflict"),
    ("DROPPED THREAD", "dropped-thread"),
    ("VOICE BREAK", "voice-break"),
    ("CANON GAP", "canon-gap"),
    ("CLAIM GAP", "claim-gap"),
    ("LOW CONFIDENCE", "inconsistency"),
    ("BOUNDARY", "boundary"),
]

TAG_RE = re.compile(
    r"`?(CANON\s+CONFLICT|DROPPED\s+THREAD|VOICE\s+BREAK|CANON\s+GAP|CLAIM\s+GAP|LOW\s+CONFIDENCE|BOUNDARY)`?",
    re.IGNORECASE,
)

_UNIT_RE = re.compile(
    r"\b(chapters?|chs?|sections?|secs?)\.?\s*(\d+)"
    r"(?:\s*(?:[-\u2013\u2014]|to)\s*(\d+))?",
    re.IGNORECASE,
)


def _expand(prefix: str, start: int, end: int | None) -> list[str]:
    hi = end if end is not None and end > start else start
    unit = "ch" if prefix.lower().startswith("ch") else "sec"
    return [f"{unit}{n:02d}" for n in range(start, hi + 1)]


def extract_units(text: str) -> list[str]:
    units: list[str] = []
    for m in _UNIT_RE.finditer(text):
        units.extend(_expand(m.group(1), int(m.group(2)), int(m.group(3)) if m.group(3) else None))
    # Deduplicate while preserving order
    seen = set()
    return [u for u in units if not (u in seen or seen.add(u))]


def parse_report(report_text: str) -> list[dict]:
    findings: list[dict] = []
    counter = 1

    lines = report_text.splitlines()
    current_section = ""

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") or stripped.startswith("### "):
            current_section = stripped.lstrip("#").strip()
            continue

        if not stripped.startswith("- "):
            continue

        bullet_text = stripped[2:].strip()

        # Check for tags
        m = TAG_RE.search(bullet_text)
        if not m:
            continue

        raw_tag = re.sub(r"\s+", " ", m.group(1).upper())
        tag_dict = dict(TAGS)
        kind = tag_dict.get(raw_tag, "other")

        # Clean description
        desc = bullet_text
        units = extract_units(bullet_text)

        severity = "medium"
        if kind in ("conflict", "dropped-thread"):
            severity = "high"
        elif kind in ("canon-gap", "voice-break"):
            severity = "medium"
        elif kind in ("boundary", "inconsistency"):
            severity = "low"

        findings.append({
            "id": f"F{counter:03d}",
            "kind": kind,
            "severity": severity,
            "status": "open",
            "section": current_section,
            "units": units,
            "description": desc,
        })
        counter += 1

    return findings


def format_yaml(findings: list[dict], source_file: str) -> str:
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    lines = [
        f"# Defect & Discrepancy Ledger generated from {source_file}",
        f"# Generated: {now}",
        f"# Total findings: {len(findings)}",
        "",
        "findings:",
    ]
    if not findings:
        lines.append("  []")
        return "\n".join(lines) + "\n"

    for f in findings:
        lines.append(f"  - id: {f['id']}")
        lines.append(f"    kind: {f['kind']}")
        lines.append(f"    severity: {f['severity']}")
        lines.append(f"    status: {f['status']}")
        lines.append(f"    units: {f['units']}")
        lines.append(f"    section: \"{f['section']}\"")
        # Escape quotes in description
        safe_desc = f['description'].replace('"', '\\"')
        lines.append(f"    description: \"{safe_desc}\"")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract findings from reverse-analysis.md into findings.yaml")
    parser.add_argument("report", help="Path to reverse-analysis.md")
    parser.add_argument("-o", "--output", help="Output YAML path")
    args = parser.parse_args()

    report_path = Path(args.report).expanduser().resolve()
    if not report_path.exists():
        print(f"error: file not found: {args.report}", file=sys.stderr)
        sys.exit(1)

    text = report_path.read_text(encoding="utf-8", errors="replace")
    findings = parse_report(text)
    yaml_text = format_yaml(findings, report_path.name)

    if args.output:
        out_path = Path(args.output).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(yaml_text, encoding="utf-8")
        print(f"Wrote {len(findings)} findings to {args.output}")
    else:
        print(yaml_text)


if __name__ == "__main__":
    main()
