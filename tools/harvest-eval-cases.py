#!/usr/bin/env python3
"""Harvest real author-taste preservation benchmarks from Storycraft book repos.

Turns _Edits/Book-N/decisions.jsonl (rejected/applied findings) and
Wiki/Style/editorial-decisions.json (active deliberate choices) into an
eval-editorial.py-compatible preservation corpus of protected and defect spans.

Usage:
    python3 tools/harvest-eval-cases.py --project ~/Projects/Books/my-book \
        --output /tmp/my-book-eval-cases.json
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import sys


def _infer_category(finding_id: str, report_path: str, rule_cat: str = '') -> str:
    if rule_cat and rule_cat.strip():
        return re.sub(r'[^a-z0-9-]+', '-', rule_cat.strip().lower()).strip('-') or 'editorial'
    combined = f'{finding_id} {report_path}'.lower()
    for token, cat in (
        ('frag', 'fragment'),
        ('rep', 'repetition'),
        ('sim', 'metaphor'),
        ('metaphor', 'metaphor'),
        ('dial', 'dialect'),
        ('quiet', 'quiet-ending'),
        ('pov', 'pov'),
        ('know', 'knowledge'),
        ('sens', 'sensory'),
        ('sil', 'silence'),
        ('sub', 'subtext-unsaid'),
        ('neg', 'negation'),
    ):
        if token in combined:
            return cat
    return 'style'


def _window_around(chapter_text: str, quote: str, max_chars: int = 2400) -> str:
    """Return full-chapter context if compact, else a paragraph-aligned window around quote."""
    if len(chapter_text) <= max_chars or quote not in chapter_text:
        return chapter_text
    idx = chapter_text.find(quote)
    half = max_chars // 2
    lo = max(0, idx - half)
    hi = min(len(chapter_text), idx + len(quote) + half)
    if lo > 0:
        para_start = chapter_text.rfind('\n\n', 0, idx)
        if para_start != -1 and idx - para_start < half:
            lo = para_start + 2
        else:
            nl = chapter_text.find('\n', lo)
            if nl != -1 and nl < idx:
                lo = nl + 1
    if hi < len(chapter_text):
        para_end = chapter_text.find('\n\n', idx + len(quote), hi + 400)
        if para_end != -1:
            hi = para_end
    return chapter_text[lo:hi].strip()


def _resolve_chapter_for_report(root: Path, book: str, report_rel: str) -> Path | None:
    meta_p = (root / report_rel).with_suffix('.meta.json')
    if meta_p.is_file():
        try:
            meta = json.loads(meta_p.read_text(encoding='utf-8'))
            for subj in meta.get('subject_paths', []):
                cand = root / subj
                if cand.is_file():
                    return cand
        except (OSError, json.JSONDecodeError):
            pass
    stem = Path(report_rel).name.split('_')[0]
    cand = root / 'Chapters' / book / f'{stem}.md'
    return cand if cand.is_file() else None


def harvest(project_root: Path, *, book: str | None = None, full_chapter: bool = False) -> dict:
    root = project_root.resolve()
    if not root.is_dir():
        raise ValueError(f'project directory does not exist: {root}')

    books = [book] if book else sorted(
        p.name for p in (root / '_Edits').glob('Book-*') if p.is_dir()
    )
    cases: list[dict] = []
    seen_sources: dict[tuple[str, str, str], dict] = {}
    categories: set[str] = set()

    style_rules = 'Honor project style guide and active editorial decisions.'
    sg = root / 'Wiki' / 'Style' / 'style_guide.md'
    if sg.is_file():
        style_rules = sg.read_text(encoding='utf-8', errors='replace')[:800].strip()

    for bk in books:
        dec_log = root / '_Edits' / bk / 'decisions.jsonl'
        if not dec_log.is_file():
            continue
        latest: dict[tuple[str, str], dict] = {}
        for line in dec_log.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = (str(item.get('report_sha256', '')), str(item.get('finding_id', '')))
            latest[key] = item

        for idx, ((_, fid), item) in enumerate(sorted(latest.items()), 1):
            disp = item.get('disposition')
            quote = (item.get('quote') or '').strip()
            reason = (item.get('reason') or '').strip() or 'Author disposition record'
            report_rel = str(item.get('report') or '')
            if disp not in ('rejected', 'applied') or not quote:
                continue
            ch_path = _resolve_chapter_for_report(root, bk, report_rel) if report_rel else None
            ch_text = ch_path.read_text(encoding='utf-8', errors='replace') if ch_path else ''
            cat = _infer_category(fid, report_rel)
            categories.add(cat)
            if disp == 'rejected' and ch_text and quote in ch_text:
                excerpt = ch_text if full_chapter else _window_around(ch_text, quote)
                case = {
                    'id': f'{bk}-{fid}-keep-{idx:03d}',
                    'category': cat,
                    'source': excerpt,
                    'protected_spans': [quote],
                    'defect_spans': [],
                    'rationale': reason,
                    'rules': style_rules,
                    'split': 'calibration' if idx % 2 else 'held_out',
                    'label_status': 'author-harvested',
                    'origin': {'book': bk, 'report': report_rel, 'finding_id': fid, 'disposition': disp},
                }
                cases.append(case)
            elif disp == 'applied':
                # An applied fix usually removed the quote from current prose; retain the
                # defect span cleanly anchored to its report/excerpt context.
                excerpt = (ch_text if full_chapter else _window_around(ch_text, quote)) if (ch_text and quote in ch_text) else quote
                case = {
                    'id': f'{bk}-{fid}-fix-{idx:03d}',
                    'category': cat,
                    'source': excerpt,
                    'protected_spans': [],
                    'defect_spans': [quote],
                    'rationale': reason,
                    'rules': style_rules,
                    'split': 'calibration' if idx % 2 else 'held_out',
                    'label_status': 'author-harvested',
                    'origin': {'book': bk, 'report': report_rel, 'finding_id': fid, 'disposition': disp},
                }
                cases.append(case)

    ed_file = root / 'Wiki' / 'Style' / 'editorial-decisions.json'
    if ed_file.is_file():
        try:
            ed_data = json.loads(ed_file.read_text(encoding='utf-8'))
            for idx, dec in enumerate(ed_data.get('decisions', []), 1):
                if dec.get('status') != 'active':
                    continue
                quote = (dec.get('quote') or dec.get('example') or '').strip()
                src_rel = dec.get('source') or ''
                src_p = root / src_rel if src_rel else None
                if not quote or not src_p or not src_p.is_file():
                    continue
                ch_text = src_p.read_text(encoding='utf-8', errors='replace')
                if quote not in ch_text:
                    continue
                cat = _infer_category(dec.get('id', ''), '', dec.get('rule_category', ''))
                categories.add(cat)
                excerpt = ch_text if full_chapter else _window_around(ch_text, quote)
                dedup_key = (str(dec.get('id', idx)), quote)
                if dedup_key in seen_sources:
                    continue
                case = {
                    'id': f'ed-{dec.get("id", idx)}-keep',
                    'category': cat,
                    'source': excerpt,
                    'protected_spans': [quote],
                    'defect_spans': [],
                    'rationale': dec.get('reason', 'Active editorial-memory decision'),
                    'rules': style_rules,
                    'split': 'held_out' if idx % 2 == 0 else 'calibration',
                    'label_status': 'author-harvested',
                    'origin': {'decision_id': dec.get('id'), 'source': src_rel},
                }
                seen_sources[dedup_key] = case
                cases.append(case)
        except (OSError, json.JSONDecodeError):
            pass

    tolerances = {
        cat: {'max_harmful_edit_rate': 0.0, 'min_localization_rate': 0.8, 'status': 'author-harvested'}
        for cat in sorted(categories)
    }
    return {
        'schema_version': 1,
        'corpus_status': 'author-harvested',
        'project': str(root),
        'category_tolerances': tolerances,
        'cases': cases,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project', required=True, type=Path, help='Path to a Storycraft book repository')
    ap.add_argument('--book', help='Filter decisions to one Book-N folder (default: all Book-* folders)')
    ap.add_argument('--full-chapter', action='store_true', help='Include full chapter text instead of paragraph windows')
    ap.add_argument('--output', type=Path, help='Write JSON corpus to file (defaults to stdout)')
    args = ap.parse_args()
    corpus = harvest(args.project, book=args.book, full_chapter=args.full_chapter)
    rendered = json.dumps(corpus, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding='utf-8')
        print(f"Harvested {len(corpus['cases'])} case(s) to {args.output}")
    else:
        print(rendered, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
