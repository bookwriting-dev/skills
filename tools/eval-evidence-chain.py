#!/usr/bin/env python3
"""Prepare isolated prose-review packets and score their evidence citations."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import secrets

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / 'tools/eval-fixtures/evidence-chain/cases.json'
RULES = (
    'fiction-reviewchapter/SKILL.md',
    'gate-check/SKILL.md',
    'book-status/references/continuity-review.md',
    'book-status/references/evidence-chain.md',
)
TASK = (
    'Use the supplied Storycraft review rules to evaluate the consequential evidence claim in the final excerpt. '
    'Read the supplied manuscript and reference passages. Treat each case as an independent project. '
    'For each case return {case_id, status, reason, citations:[{file,quote}]}. '
    'Status is contradiction for a claim refuted by supplied evidence, unresolved when '
    'support for an asserted conclusion is missing, or supported for a coherent passage '
    '(including appropriately qualified uncertainty). Cite the exact words of the final excerpt '
    'and the relevant establishing passages. Use only these packet contents.'
)


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    data = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    with path.open('xb') as stream:
        stream.write(data)
    return hashlib.sha256(data).hexdigest()


def prepare(base):
    base.mkdir(parents=True)
    rules = {name: (ROOT / 'skills' / name).read_text(encoding='utf-8')
             for name in RULES if (ROOT / 'skills' / name).is_file()}
    groups = [[], []]
    expected = {}
    for pair in read(CASES):
        for group, variant in zip(groups, pair['variants'], strict=True):
            opaque = secrets.token_hex(6)
            sources = {**pair['reference'], 'Final excerpt': variant['text']}
            group.append({'case_id': opaque, 'sources': sources})
            expected[opaque] = {'pair': pair['id'], 'status': variant['status'], 'sources': sources}
    groups_dir = base / 'packets'
    groups_dir.mkdir()
    hashes = {}
    for number, group in enumerate(groups, 1):
        random.SystemRandom().shuffle(group)
        name = f'review-{number}.json'
        hashes[name] = write(groups_dir / name, {'rules': rules, 'task': TASK, 'cases': group})
    write(base / 'private.json', {'case_hash': hashlib.sha256(CASES.read_bytes()).hexdigest(),
                                  'packet_hashes': hashes, 'expected': expected})
    print(groups_dir)


def score(base, paths):
    manifest = read(base / 'private.json')
    for name, sha in manifest['packet_hashes'].items():
        if hashlib.sha256((base / 'packets' / name).read_bytes()).hexdigest() != sha:
            raise ValueError(f'packet digest changed: {name}')
    expected = manifest['expected']
    results = [result for path in paths for result in read(path)]
    if len(results) != len(expected) or {result['case_id'] for result in results} != expected.keys():
        raise ValueError('results must cover every frozen case exactly once')
    rows = []
    for result in results:
        case = expected[result['case_id']]
        sources = case['sources']
        cited = set()
        invalid = 0
        for citation in result['citations']:
            file, quote = citation['file'], citation['quote']
            if quote.strip() and quote in sources.get(file, ''):
                cited.add(file)
            else:
                invalid += 1
        rows.append({'case': case['pair'], 'expected': case['status'], 'actual': result['status'],
                     'citation_coverage': cited == sources.keys(), 'invalid_citations': invalid,
                     'pass': result['status'] == case['status'] and cited == sources.keys()
                     and not invalid and bool(result['reason'].strip())})
    print(json.dumps({'passed': sum(row['pass'] for row in rows), 'total': len(rows), 'cases': rows}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--results', type=Path, nargs='+')
    args = parser.parse_args()
    if args.results:
        score(args.run, args.results)
    else:
        prepare(args.run)


if __name__ == '__main__':
    main()
