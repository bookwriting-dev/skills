#!/usr/bin/env python3
"""Extract paragraph/section-aware editing passages with exact source offsets."""
import argparse
import hashlib
import json
import re
from pathlib import Path


def _id(text, occurrence):
    normalized = re.sub(r'\s+', ' ', text).strip()
    digest = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:12]
    return f'p-{digest}-{occurrence}'


def _split_sentences(text, start):
    """Split at conservative sentence boundaries; all output retains source spans."""
    cuts = [m.end() for m in re.finditer(r'[.!?](?:["”’\']?)(?=\s|$)', text)]
    spans = []
    cursor = 0
    for cut in cuts:
        left, right = cursor, cut
        while right < len(text) and text[right].isspace():
            right += 1
        if text[left:right].strip():
            spans.append((start + left, start + cut))
        cursor = right
    if text[cursor:].strip():
        spans.append((start + cursor, start + len(text)))
    return spans or [(start, start + len(text))]


def extract(text, *, chapter_id='chapter', budget=12000):
    if type(budget) is not int or budget < 1:
        raise ValueError('passage budget must be a positive integer')
    raw_units = []
    offset = 0
    current = []
    current_start = 0
    in_fence = False

    def flush(end):
        nonlocal current
        if current:
            content = ''.join(current)
            raw_units.append((current_start, end, content))
            current = []

    lines = text.splitlines(keepends=True)
    for line in lines:
        body = line.rstrip('\r\n')
        stripped = body.strip()
        if not stripped:
            flush(offset)
            offset += len(line)
            continue
        is_heading = bool(re.match(r'^\s{0,3}#{1,6}\s+', body))
        is_scene_break = stripped in ('* * *', '---', '***')
        is_fence = bool(re.match(r'^\s*(```|~~~)', body))
        if not in_fence and (is_heading or is_scene_break):
            flush(offset)
            raw_units.append((offset, offset + len(line), line))
            offset += len(line)
            continue
        if not in_fence and not current:
            current_start = offset
        current.append(line)
        if is_fence:
            in_fence = not in_fence
        offset += len(line)
    flush(offset)
    if offset < len(text) and not lines:
        raw_units.append((0, len(text), text))

    occurrences = {}
    passages = []
    for start, end, value in raw_units:
        content = value.rstrip('\r\n')
        if not content.strip():
            continue
        normalized = re.sub(r'\s+', ' ', content).strip()
        occurrence = occurrences.get(normalized, 0) + 1
        occurrences[normalized] = occurrence
        parent_id = _id(content, occurrence)
        stripped = content.strip()
        kind = 'heading' if re.match(r'^#{1,6}\s+', stripped) else (
            'scene_break' if stripped in ('* * *', '---', '***') else 'paragraph')
        # Preserve lineation as-is. Classify likely verse rather than joining it.
        lines_in_passage = [line.strip() for line in content.splitlines() if line.strip()]
        if (kind == 'paragraph' and len(lines_in_passage) >= 3 and
                max(map(len, lines_in_passage), default=0) <= 60):
            kind = 'lineated'
        content_start = start + len(value) - len(value.lstrip())
        content_end = content_start + len(content.lstrip())
        if content_end - content_start <= budget or kind in ('heading', 'scene_break', 'lineated'):
            passages.append({'passage_id': parent_id, 'parent_id': parent_id, 'kind': kind,
                             'start': content_start, 'end': content_end,
                             'text': text[content_start:content_end], 'normalized': normalized})
            continue
        for index, (piece_start, piece_end) in enumerate(_split_sentences(text[content_start:content_end], content_start), 1):
            passages.append({'passage_id': f'{parent_id}-s{index}', 'parent_id': parent_id,
                             'kind': 'sentence_split', 'start': piece_start, 'end': piece_end,
                             'text': text[piece_start:piece_end], 'normalized':
                             re.sub(r'\s+', ' ', text[piece_start:piece_end]).strip()})

    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    for passage in passages:
        passage['chapter_id'] = chapter_id
        passage['subject_sha256'] = digest
        passage['coordinate_convention'] = 'zero-based half-open Unicode code points'
    # Prove that every non-whitespace source character belongs to exactly one passage.
    coverage = [0] * len(text)
    for passage in passages:
        for i in range(passage['start'], passage['end']):
            if not text[i].isspace():
                coverage[i] += 1
    uncovered = [i for i, char in enumerate(text) if not char.isspace() and coverage[i] != 1]
    if uncovered:
        raise ValueError(f'passage extraction did not cover source exactly once at offset {uncovered[0]}')
    return {'chapter_id': chapter_id, 'subject_sha256': digest,
            'coordinate_convention': 'zero-based half-open Unicode code points',
            'passages': passages, 'coverage': 'COMPLETE'}


def packets(result, target_ids, context_count=1):
    passages = result['passages']
    index = {p['passage_id']: i for i, p in enumerate(passages)}
    missing = [pid for pid in target_ids if pid not in index]
    if missing:
        raise ValueError('unknown target passage IDs: ' + ', '.join(missing))
    out = []
    for pid in target_ids:
        i = index[pid]
        out.append({'target': passages[i],
                    'context_before': passages[max(0, i-context_count):i],
                    'context_after': passages[i+1:i+1+context_count]})
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chapter', type=Path, required=True)
    parser.add_argument('--chapter-id', default='chapter')
    parser.add_argument('--budget', type=int, default=12000)
    parser.add_argument('--target', action='append')
    parser.add_argument('--context-count', type=int, default=1)
    args = parser.parse_args()
    text = args.chapter.read_text(encoding='utf-8')
    result = extract(text, chapter_id=args.chapter_id, budget=args.budget)
    if args.target:
        result['packets'] = packets(result, args.target, args.context_count)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as exc:
        print(json.dumps({'error': str(exc)}))
        raise SystemExit(2)
