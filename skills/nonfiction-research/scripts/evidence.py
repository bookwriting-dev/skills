#!/usr/bin/env python3
"""Validate chapter assertion inventories and derive evidence readiness."""
import argparse
import hashlib
import json
from pathlib import Path

VALID_RESULTS = {
    'pending', 'verified', 'unsupported', 'contradicted', 'misattributed',
    'imprecise', 'unverifiable', 'stale', 'not_empirical',
}
NON_EMPIRICAL_TYPES = {'normative_judgment', 'definition', 'hypothetical_illustration'}
CLAIM_TYPES = {
    'factual', 'quotation_attribution', 'inference', 'definition',
    'testimony', 'normative_judgment', 'hypothetical_illustration',
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def audit(root: Path, record_path: Path) -> dict:
    root = root.resolve()
    record_path = record_path if record_path.is_absolute() else root / record_path
    record_path = record_path.resolve()
    if not record_path.is_relative_to(root):
        raise ValueError('evidence record path escapes project root')
    record_bytes = record_path.read_bytes()
    record = json.loads(record_bytes.decode('utf-8'))
    inputs = {record_path.relative_to(root).as_posix(): sha256(record_bytes)}
    required_envelope = ('record_type', 'schema_version', 'record_id', 'project_id', 'producer', 'operation_id')
    missing_envelope = [field for field in required_envelope if not record.get(field)]
    if missing_envelope:
        raise ValueError('evidence record missing envelope fields: ' + ', '.join(missing_envelope))
    if record['record_type'] != 'chapter_evidence' or record['schema_version'] != 1:
        raise ValueError('unsupported chapter evidence record type/version')

    subject_path = record.get('subject_path')
    if not isinstance(subject_path, str):
        raise ValueError('chapter evidence requires subject_path')
    subject = (root / subject_path).resolve()
    if not subject.is_relative_to(root) or not subject.is_file():
        raise ValueError('chapter evidence subject is missing or escapes project root')
    raw_subject = subject.read_bytes()
    text = raw_subject.decode('utf-8')
    text_hash = sha256(raw_subject)
    inputs[subject.relative_to(root).as_posix()] = text_hash
    stale_subject = text_hash != record.get('subject_sha256')

    sources = record.get('sources', [])
    source_by_id = {}
    source_errors = []
    for source in sources:
        sid = source.get('source_id')
        if not sid or sid in source_by_id:
            source_errors.append(f'missing or duplicate source_id: {sid}')
            continue
        source_by_id[sid] = source
        if not source.get('title') or not source.get('locator'):
            source_errors.append(f'{sid}: missing source title or locator')
        if not source.get('source_type'):
            source_errors.append(f'{sid}: missing source_type')
        if source.get('access_status') not in ('accessible', 'restricted', 'unavailable', 'unknown'):
            source_errors.append(f'{sid}: invalid or missing access_status')
        if not isinstance(source.get('limitations'), str) or not source.get('limitations').strip():
            source_errors.append(f'{sid}: limitations must be recorded (use an explicit none statement when applicable)')
        if source.get('inspection_status') not in ('inspected', 'not_accessible', 'registered_only'):
            source_errors.append(f'{sid}: invalid or missing inspection_status')
        if source.get('inspection_status') == 'inspected' and not source.get('passages'):
            source_errors.append(f'{sid}: inspected source has no retained passages/locators')
        if source.get('inspection_status') == 'inspected' and not (
                source.get('source_revision') or source.get('source_sha256') or source.get('version')):
            source_errors.append(f'{sid}: inspected source has no revision/version identity')
        source_revision = source.get('source_revision') or source.get('source_sha256') or source.get('version')
        snapshot_text = None
        if source.get('snapshot_path'):
            snapshot = (root / source['snapshot_path']).resolve()
            if not snapshot.is_relative_to(root):
                source_errors.append(f'{sid}: retained source snapshot is missing or outside project root')
            else:
                snapshot_bytes = snapshot.read_bytes() if snapshot.is_file() else None
                snapshot_hash = sha256(snapshot_bytes) if snapshot_bytes is not None else None
                inputs[snapshot.relative_to(root).as_posix()] = snapshot_hash
                if snapshot_hash is None or source.get('source_sha256') != snapshot_hash:
                    source_errors.append(f'{sid}: retained source snapshot hash mismatch or missing snapshot')
                elif snapshot.suffix.lower() in ('.md', '.txt'):
                    snapshot_text = snapshot_bytes.decode('utf-8')
        if source.get('rights_status') not in ('permitted', 'restricted', 'unknown'):
            source_errors.append(f'{sid}: invalid or missing rights_status')
        for passage in source.get('passages', []):
            if not passage.get('passage_id') or not (passage.get('quote') or passage.get('locator')):
                source_errors.append(f'{sid}: passage requires passage_id and quote or precise locator')
            if not passage.get('source_revision') or passage.get('source_revision') != source_revision:
                source_errors.append(f'{sid}: passage requires source_revision')
            quote = passage.get('quote')
            if snapshot_text is not None and quote and quote not in snapshot_text:
                source_errors.append(f'{sid}: quoted passage is absent from the retained text snapshot')

    assertions = record.get('assertions', [])
    if not isinstance(assertions, list) or not assertions:
        raise ValueError('chapter evidence requires a nonempty assertion inventory')
    assertion_by_id = {}
    anchor_errors = []
    for assertion in assertions:
        aid = assertion.get('assertion_id')
        if not aid or aid in assertion_by_id:
            anchor_errors.append(f'missing or duplicate assertion_id: {aid}')
            continue
        assertion_by_id[aid] = assertion
        if assertion.get('claim_type') not in CLAIM_TYPES:
            anchor_errors.append(f'{aid}: missing or invalid claim_type')
        anchor = assertion.get('anchor', {})
        start, end, quote = anchor.get('start'), anchor.get('end'), anchor.get('quote')
        if (type(start) is not int or type(end) is not int or start < 0 or end <= start or
                end > len(text) or text[start:end] != quote or anchor.get('subject_sha256') != text_hash):
            anchor_errors.append(f'{aid}: stale or invalid half-open Unicode code-point anchor')

    verification_records = record.get('verifications', [])
    verification_by_id = {}
    verification_errors = []
    for verification in verification_records:
        aid = verification.get('assertion_id')
        if not aid or aid in verification_by_id:
            verification_errors.append(f'missing or duplicate verification for assertion: {aid}')
            continue
        verification_by_id[aid] = verification
        if aid not in assertion_by_id:
            verification_errors.append(f'orphan verification: {aid}')
            continue
        result = verification.get('result')
        if result not in VALID_RESULTS:
            verification_errors.append(f'{aid}: invalid verification result')
            continue
        claim_type = assertion_by_id[aid].get('claim_type')
        if result == 'not_empirical' and claim_type not in NON_EMPIRICAL_TYPES:
            verification_errors.append(f'{aid}: not_empirical is not valid for {claim_type}')
        if result == 'verified':
            refs = verification.get('passage_ids', [])
            source_refs = verification.get('source_ids', [])
            known_passages = {
                passage.get('passage_id'): source.get('source_id')
                for source in source_by_id.values()
                if source.get('inspection_status') == 'inspected'
                for passage in source.get('passages', [])
            }
            if not refs or not source_refs:
                verification_errors.append(f'{aid}: verified result lacks source and passage references')
            if any(ref not in known_passages or known_passages.get(ref) not in source_refs for ref in refs):
                verification_errors.append(f'{aid}: verified result references an unknown/uninspected passage')
            if any(ref not in source_by_id for ref in source_refs):
                verification_errors.append(f'{aid}: verified result references an unknown source')
            if any(source_by_id.get(ref, {}).get('inspection_status') != 'inspected' for ref in source_refs):
                verification_errors.append(f'{aid}: verified result references a source that was not inspected')
        if not verification.get('evaluator') or not verification.get('rules_version') or not verification.get('rationale'):
            verification_errors.append(f'{aid}: missing evaluator, rules_version, or rationale')

    missing_verifications = sorted(set(assertion_by_id) - set(verification_by_id))
    extra_verifications = sorted(set(verification_by_id) - set(assertion_by_id))
    coverage = record.get('inventory_coverage', {})
    if not isinstance(coverage, dict):
        coverage = {}
    coverage_valid = (
        coverage.get('complete') is True and bool(coverage.get('reviewer')) and
        bool(coverage.get('method')) and coverage.get('subject_sha256') == text_hash and
        isinstance(coverage.get('omissions'), list) and not coverage.get('omissions') and
        isinstance(coverage.get('limitations'), str) and bool(coverage.get('limitations').strip())
    )
    ready_results = all(
        verification_by_id.get(aid, {}).get('result') in ('verified', 'not_empirical')
        for aid in assertion_by_id
    )
    blockers = []
    if stale_subject:
        blockers.append('subject revision changed; re-anchor and reverify assertions')
    if source_errors:
        blockers.extend(source_errors)
    if anchor_errors:
        blockers.extend(anchor_errors)
    if verification_errors:
        blockers.extend(verification_errors)
    if missing_verifications:
        blockers.append('missing verification results: ' + ', '.join(missing_verifications))
    if extra_verifications:
        blockers.append('orphan verification results: ' + ', '.join(extra_verifications))
    if not coverage_valid:
        blockers.append('complete chapter-level assertion inventory coverage is not established')
    if not ready_results:
        blockers.append('one or more assertions are not factually ready')
    return {
        'record_id': record['record_id'], 'subject_path': subject_path,
        'subject_sha256': text_hash, 'assertion_count': len(assertion_by_id),
        'source_inputs': inputs,
        'verified_anchors': {aid: assertion_by_id[aid]['anchor'] for aid, record in verification_by_id.items()
                             if aid in assertion_by_id and record.get('result') == 'verified'
                             and not blockers},
        'verification_count': len(verification_by_id), 'source_count': len(source_by_id),
        'coverage': 'COMPLETE' if coverage_valid else 'INCOMPLETE',
        'readiness': 'ELIGIBLE' if not blockers else 'INELIGIBLE',
        'blocking_reasons': blockers,
        'counts': {result: sum(v.get('result') == result for v in verification_by_id.values())
                   for result in sorted(VALID_RESULTS)},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--require-ready', action='store_true')
    args = parser.parse_args()
    result = audit(args.root, args.record)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.require_ready and result['readiness'] != 'ELIGIBLE':
        raise SystemExit(2)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, json.JSONDecodeError, TypeError) as exc:
        print(json.dumps({'error': str(exc)}))
        raise SystemExit(2)
