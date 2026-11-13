#!/usr/bin/env python3
"""Markov chain name generator."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import defaultdict
from pathlib import Path


def build_model(names: list[str], order: int) -> dict:
    model = defaultdict(list)
    for name in names:
        name = name.strip().lower()
        if len(name) < order + 1:
            continue
        padded = "\x00" * order + name + "\x01"  # \x00 = start, \x01 = end
        for i in range(len(padded) - order):
            key = padded[i : i + order]
            model[key].append(padded[i + order])
    return model


def generate_name(model: dict, order: int, min_len: int, max_len: int, max_attempts: int = 200) -> str | None:
    for _ in range(max_attempts):
        key = "\x00" * order
        result = []
        for _ in range(max_len + order):
            choices = model.get(key)
            if not choices:
                break
            next_char = random.choice(choices)
            if next_char == "\x01":
                break
            result.append(next_char)
            key = key[1:] + next_char
        name = "".join(result)
        if min_len <= len(name) <= max_len:
            return name.capitalize()
    return None


def load_names(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    names = [line.strip() for line in text.splitlines() if line.strip()]
    if not names:
        print(f"Error: no names found in {path}", file=sys.stderr)
        sys.exit(1)
    return names


def eligible_attestations(records: list[dict], mode: str, *, region: str | None,
                          language: str | None, start_year: int | None,
                          end_year: int | None) -> list[dict]:
    """Filter exact source records; membership never synthesizes a form."""
    eligible = []
    for record in records:
        name = record.get("exact_form")
        if not isinstance(name, str) or not name:
            continue
        if (record.get("inspection_status") != "inspected" or not record.get("source_id") or
                not record.get("source_title") or not record.get("source_locator")):
            continue
        if region and record.get("region") != region:
            continue
        if language and record.get("language") != language:
            continue
        try:
            year = int(record.get("date_year"))
        except (TypeError, ValueError):
            continue
        if start_year is None or end_year is None or not start_year <= year <= end_year:
            continue
        if mode == "contemporary_grounded" and not (region or language):
            continue
        if mode == "historical_attested" and not (region or language):
            continue
        eligible.append(record)
    # Keep one exact spelling and attach all eligible citations for that form.
    grouped = {}
    for record in eligible:
        grouped.setdefault(record["exact_form"], []).append({
            key: record.get(key) for key in
            ("source_id", "source_title", "creator", "source_locator", "date_year",
             "region", "language", "historical_context", "uncertainty")
        })
    return [{"name": name, "provenance": grouped[name]} for name in sorted(grouped)]


def main():
    parser = argparse.ArgumentParser(description="Markov chain name generator")
    parser.add_argument("--list", type=Path, help="Path to name list .txt file (invented mode only)")
    parser.add_argument("--count", type=int, default=10, help="Number of names to generate")
    parser.add_argument("--min-len", type=int, default=4, help="Minimum name length")
    parser.add_argument("--max-len", type=int, default=12, help="Maximum name length")
    parser.add_argument("--order", type=int, default=2, choices=[1, 2, 3], help="Markov chain order")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--mode", choices=["invented", "contemporary_grounded", "historical_attested"], default="invented")
    parser.add_argument("--evidence", type=Path, help="Inspected attestation records JSON for evidence-based modes")
    parser.add_argument("--region", help="Exact requested locale/region context")
    parser.add_argument("--language", help="Exact requested language context")
    parser.add_argument("--start-year", type=int, help="Inclusive evidence window start")
    parser.add_argument("--end-year", type=int, help="Inclusive evidence window end")
    parser.add_argument("--json", action="store_true", help="Emit mode and provenance metadata")
    args = parser.parse_args()

    if args.count < 1 or args.min_len < 1 or args.max_len < args.min_len:
        parser.error("count must be positive and length bounds must be valid")

    if args.mode != "invented":
        if not args.evidence or not args.evidence.is_file():
            parser.error("grounded/attested modes require --evidence JSON; invented fallback is disabled")
        if args.start_year is None or args.end_year is None or args.start_year > args.end_year:
            parser.error("evidence modes require a valid inclusive --start-year/--end-year window")
        if not args.region and not args.language:
            parser.error("evidence modes require a requested region or language context")
        try:
            evidence_data = json.loads(args.evidence.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            parser.error(f"cannot read evidence records: {exc}")
        records = evidence_data.get("records") if isinstance(evidence_data, dict) else None
        if not isinstance(records, list):
            parser.error("evidence file must contain a records array")
        candidates = eligible_attestations(records, args.mode, region=args.region,
            language=args.language, start_year=args.start_year, end_year=args.end_year)
        candidates.sort(key=lambda candidate: candidate['name'])
        if args.seed is not None:
            random.Random(args.seed).shuffle(candidates)
        selected = candidates[:args.count]
        result = {"mode": args.mode, "requested": args.count, "candidates": selected,
                  "shortfall": max(0, args.count - len(selected)),
                  "seed": args.seed,
                  "evidence_sha256": hashlib.sha256(args.evidence.read_bytes()).hexdigest(),
                  "attestation_validation": "record eligibility only; source truth requires expert review"}
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            for candidate in selected:
                print(candidate["name"])
            if result["shortfall"]:
                print(f"(shortfall: {result['shortfall']} eligible attested name(s) unavailable)", file=sys.stderr)
        return

    if not args.list:
        parser.error("invented mode requires --list name corpus")

    if args.seed is not None:
        random.seed(args.seed)

    if not args.list.exists():
        print(f"Error: file not found: {args.list}", file=sys.stderr)
        sys.exit(1)

    names = load_names(args.list)
    model = build_model(names, args.order)

    generated = []
    seen = set()
    attempts = 0
    max_total_attempts = args.count * 500

    while len(generated) < args.count and attempts < max_total_attempts:
        attempts += 1
        name = generate_name(model, args.order, args.min_len, args.max_len)
        if name and name.lower() not in seen:
            seen.add(name.lower())
            generated.append(name)

    if not generated:
        print("Could not generate any names. Try a larger name list or different parameters.", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps({"mode": "invented", "seed": args.seed,
            "corpus_sha256": hashlib.sha256(args.list.read_bytes()).hexdigest(),
            "parameters": {"count": args.count, "min_len": args.min_len,
                           "max_len": args.max_len, "order": args.order},
            "candidates": generated}, ensure_ascii=False, indent=2))
    else:
        for name in generated:
            print(name)

    if len(generated) < args.count:
        print(f"\n(Only {len(generated)} unique names could be generated with these parameters)", file=sys.stderr)


if __name__ == "__main__":
    main()
