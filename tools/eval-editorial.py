#!/usr/bin/env python3
"""Create provider-neutral editorial packets; score recorded outputs, never invent author scores."""
import argparse
import hashlib
import json
from pathlib import Path

from editorial_study import (DEFAULT_CORPUS, author_judgments, blind_review, blind_review_data,
                              blind_review_html, document_hash, load_corpus, prepare_packets,
                              run_study, spans)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--packets', type=Path)
    ap.add_argument('--results', type=Path)
    ap.add_argument('--mapping', type=Path, help='private opaque-ID map; never place in candidate-visible packets')
    ap.add_argument('--skill', default='fiction-full-editor')
    ap.add_argument('--baseline-ref')
    ap.add_argument('--split', choices=['all', 'calibration', 'held_out'], default='all')
    ap.add_argument('--corpus', type=Path, default=DEFAULT_CORPUS)
    ap.add_argument('--configuration', type=Path, help='model and host settings for a matched study')
    ap.add_argument('--candidate-ref')
    ap.add_argument('--repeats', type=int, default=2)
    ap.add_argument('--run-study', type=Path, help='execute a frozen study with the configured Codex model')
    ap.add_argument('--output-results', type=Path, help='write or resume recorded study results')
    ap.add_argument('--blind-review', type=Path, help='write anonymized author review JSON for --results')
    ap.add_argument('--blind-review-html', type=Path, help='write self-contained HTML blind-review scorecard for --results')
    ap.add_argument('--author-scores', type=Path, help='author ratings keyed by the blind review IDs')
    a = ap.parse_args()
    if a.run_study:
        if not a.packets or not a.output_results or a.results:
            ap.error('--run-study requires --packets and --output-results')
        print(json.dumps(run_study(a.run_study, a.packets, a.output_results)))
        return
    if a.output_results:
        ap.error('--output-results requires --run-study')
    if (a.blind_review or a.blind_review_html or a.author_scores) and not a.results:
        ap.error('blind review and author scores require --results')
    corpus_data = load_corpus(a.corpus)
    cases = corpus_data['cases']
    tolerances = corpus_data.get('category_tolerances', {})
    if a.packets:
        if a.configuration and (not a.baseline_ref or not a.candidate_ref or a.repeats < 2):
            ap.error('a matched study needs baseline and candidate refs and at least two repetitions')
        print(json.dumps(prepare_packets(a, corpus_data)))
    if a.results:
        data = json.loads(a.results.read_text())
        manifest = data.get('manifest', data)
        if not isinstance(manifest.get('configuration'), dict) or type(manifest.get('repeat_count')) is not int or manifest['repeat_count'] <= 0:
            raise ValueError('results need a recorded configuration and positive integer repeat_count')
        by_id = {c['id']: c for c in cases}
        strict = 'expected_case_ids' in manifest or 'variants' in manifest or any('repeat_index' in r for r in data.get('results', []))
        opaque_to_case = {}
        variant_labels = {}
        if strict:
            if not a.mapping:
                raise ValueError('strict scoring requires the private opaque-ID mapping via --mapping')
            private_map = json.loads(a.mapping.read_text())
            if not isinstance(private_map, dict):
                raise ValueError('private opaque-ID mapping must be a JSON object')
            opaque_to_case = private_map.get('mapping', {})
            variant_labels = private_map.get('variants', {})
            if hashlib.sha256(a.mapping.read_bytes()).hexdigest() != manifest.get('mapping_sha256'):
                raise ValueError('private mapping hash does not match frozen run manifest')
            if (not isinstance(opaque_to_case, dict) or not opaque_to_case or
                    len(set(opaque_to_case.values())) != len(opaque_to_case) or
                    any(case_id not in by_id for case_id in opaque_to_case.values())):
                raise ValueError('private opaque-ID mapping is invalid')
        results = data.get('results')
        if not isinstance(results, list):
            raise ValueError('results must be an array')
        coverage = {'status': 'DIAGNOSTIC', 'missing': [], 'duplicates': [], 'unknown': [], 'invalid': []}
        selected = {}
        if strict:
            expected_cases = manifest.get('expected_case_ids')
            variants = manifest.get('variants')
            if (not isinstance(expected_cases, list) or not expected_cases or
                    not all(isinstance(case, str) for case in expected_cases) or len(set(expected_cases)) != len(expected_cases)):
                raise ValueError('manifest expected_case_ids must be a nonempty unique list')
            if (not isinstance(variants, list) or not variants or
                    not all(isinstance(variant, str) for variant in variants) or len(set(variants)) != len(variants)):
                raise ValueError('manifest variants must be a nonempty unique list')
            if not set(expected_cases).issubset(opaque_to_case):
                coverage['invalid'].append({'reason': 'manifest contains IDs absent from private opaque mapping'})
            if manifest.get('study_version') == 1:
                if manifest.get('corpus_sha256') != document_hash(corpus_data):
                    coverage['invalid'].append({'reason': 'frozen corpus hash mismatch'})
                if set(variant_labels) != set(variants) or set(variant_labels.values()) != {'baseline', 'candidate'}:
                    coverage['invalid'].append({'reason': 'frozen variants do not match the private study map'})
            frozen_fields = ('run_id', 'corpus_sha256', 'source_hashes', 'configuration',
                             'skill_hashes', 'packet_hashes', 'span_policy', 'permissions',
                             'permitted_context', 'mapping_sha256')
            for field in frozen_fields:
                if field not in manifest or manifest[field] in (None, '', {}, []):
                    coverage['invalid'].append({'reason': f'manifest missing frozen field: {field}'})
            for field in ('source_hashes', 'configuration', 'skill_hashes', 'packet_hashes'):
                if not isinstance(manifest.get(field), dict):
                    coverage['invalid'].append({'reason': f'manifest {field} must be an object'})
            expected_source_hashes = {
                opaque_id: hashlib.sha256(by_id[opaque_to_case[opaque_id]]['source'].encode()).hexdigest()
                for opaque_id in expected_cases if opaque_id in opaque_to_case
            }
            if manifest.get('source_hashes') != expected_source_hashes:
                coverage['invalid'].append({'reason': 'source hash manifest mismatch'})
            configuration = manifest.get('configuration', {})
            configuration_sha256 = (document_hash(configuration) if manifest.get('study_version') == 1 else
                                    hashlib.sha256(json.dumps(configuration, sort_keys=True,
                                                               separators=(',', ':')).encode()).hexdigest())
            coordinates = [(case, variant, repeat) for case in expected_cases
                           for variant in variants for repeat in range(1, manifest['repeat_count'] + 1)]
            seen = {}
            for result in results:
                coordinate = (result.get('case_id'), result.get('variant'), result.get('repeat_index'))
                if type(result.get('repeat_index')) is not int or result.get('repeat_index') <= 0:
                    coverage['invalid'].append({'coordinate': list(coordinate), 'reason': 'repeat_index must be a positive integer'})
                if coordinate not in coordinates:
                    coverage['unknown'].append(list(coordinate))
                elif coordinate in seen:
                    coverage['duplicates'].append(list(coordinate))
                else:
                    seen[coordinate] = result
                    selected[coordinate] = result
                if result.get('status') not in ('complete', 'failed'):
                    coverage['invalid'].append({'coordinate': list(coordinate), 'reason': 'invalid status'})
                if result.get('status') == 'complete' and not isinstance(result.get('findings'), list):
                    coverage['invalid'].append({'coordinate': list(coordinate), 'reason': 'findings must be an array'})
                if coordinate in coordinates:
                    expected_source = expected_source_hashes.get(result.get('case_id'))
                    if result.get('source_sha256') != expected_source:
                        coverage['invalid'].append({'coordinate': list(coordinate), 'reason': 'source hash mismatch'})
                    if result.get('configuration_sha256') != configuration_sha256:
                        coverage['invalid'].append({'coordinate': list(coordinate), 'reason': 'configuration hash mismatch'})
                    packet_hashes = manifest.get('packet_hashes') if isinstance(manifest.get('packet_hashes'), dict) else {}
                    expected_packet = packet_hashes.get(result.get('case_id'))
                    if isinstance(expected_packet, dict):
                        expected_packet = expected_packet.get(result['variant'])
                    if not result.get('packet_sha256') or expected_packet != result.get('packet_sha256'):
                        coverage['invalid'].append({'coordinate': list(coordinate), 'reason': 'packet hash mismatch'})
                    if not result.get('attempt_id'):
                        coverage['invalid'].append({'coordinate': list(coordinate), 'reason': 'missing attempt_id'})
            coverage['missing'] = [list(c) for c in coordinates if c not in seen]
            coverage['status'] = 'COMPLETE' if not any(coverage[k] for k in ('missing','duplicates','unknown','invalid')) else 'INCOMPLETE'
        if a.blind_review or a.blind_review_html:
            if not strict or coverage['invalid'] or coverage['duplicates'] or coverage['unknown']:
                raise ValueError('blind reviews require strictly bound, unambiguous run results')
            review_data = (blind_review(a.blind_review, manifest, selected, opaque_to_case, by_id)
                           if a.blind_review
                           else blind_review_data(manifest, selected, opaque_to_case, by_id))
            out = {'coverage': coverage}
            if a.blind_review:
                out['review_file'] = str(a.blind_review)
            if a.blind_review_html:
                blind_review_html(a.blind_review_html, review_data)
                out['review_html'] = str(a.blind_review_html)
            print(json.dumps(out))
            return
        categories = {}
        variant_stats = {}
        stats = dict(findings=0,localized_findings=0,repair_judgments=0,successful_repairs=0,cases=0,protected=0,harmful=0,defects=0,detected=0,unsupported_quotes=0,author_scored=0,author_accepted=0,failed_runs=0,scored_outputs=0,author_judgments=0)
        # In strict runs, score exactly the first recorded attempt per frozen
        # coordinate. Duplicate retries remain visible as coverage failures,
        # but cannot replace a terminal failure or improve the denominator.
        scoring_results = list(selected.values()) if strict else results
        for r in scoring_results:
            variant = variant_stats.setdefault(r.get('variant', 'diagnostic'), {
                'scored_outputs': 0, 'failed_runs': 0, 'defects': 0, 'defects_caught': 0,
                'protected_spans': 0, 'protected_spans_targeted': 0,
                'author_scores': {}, 'author_reviewed_repairs': 0, 'fixes_kept': 0,
            })
            case_id = r.get('id') if not strict else opaque_to_case.get(r.get('case_id'))
            if strict and case_id not in by_id:
                continue
            if not strict and case_id not in by_id:
                coverage['unknown'].append(case_id)
                continue
            c = by_id[case_id]
            if r.get('status') == 'failed':
                stats['failed_runs'] += 1
                variant['failed_runs'] += 1
                continue
            stats['scored_outputs'] += 1
            variant['scored_outputs'] += 1
            stats['cases'] += 1
            stats['protected'] += bool(c['protected_spans']); stats['defects'] += bool(c['defect_spans'])
            findings = r.get('findings', [])
            category = categories.setdefault(
                c['category'],
                {'cases': 0, 'findings': 0, 'protected': 0, 'harmful': 0, 'defects': 0, 'detected': 0},
            )
            category['cases'] += 1; category['findings'] += len(findings)
            category['protected'] += int(bool(c['protected_spans']))
            category['defects'] += int(bool(c['defect_spans']))
            stats['findings'] += len(findings)
            valid = []
            for f in findings:
                quote = f.get('quote')
                if strict:
                    start, end = f.get('start'), f.get('end')
                    anchored = (type(start) is int and type(end) is int and 0 <= start < end <= len(c['source'])
                                and c['source'][start:end] == quote)
                else:
                    anchored = bool(quote) and quote in c['source']
                if not anchored:
                    stats['unsupported_quotes'] += 1
                else:
                    valid.append((f, (f.get('start'), f.get('end')) if strict else (c['source'].find(quote), c['source'].find(quote)+len(quote))))
            defect_ranges = spans(c['source'], c['defect_spans'])
            protected_ranges = spans(c['source'], c['protected_spans'])
            variant['defects'] += len(defect_ranges)
            variant['defects_caught'] += sum(any(span[0] < end and start < span[1] for _, span in valid)
                                             for start, end in defect_ranges)
            variant['protected_spans'] += len(protected_ranges)
            variant['protected_spans_targeted'] += sum(
                any(span[0] < end and start < span[1] and finding.get('replacement') != finding['quote']
                    for finding, span in valid) for start, end in protected_ranges)
            localized = [(f, span) for f, span in valid if any(span[0] < end and start < span[1] for start, end in defect_ranges)]
            protected_hits = [(f, span) for f, span in valid if any(span[0] < end and start < span[1] for start, end in protected_ranges)]
            stats['localized_findings'] += len(localized)
            stats['detected'] += bool(localized)
            stats['harmful'] += bool(protected_hits)
            category['detected'] += int(bool(localized))
            category['harmful'] += int(bool(protected_hits))
        human_judgments = data.get('human_judgments', [])
        if not isinstance(human_judgments, list):
            coverage['invalid'].append({'reason': 'human_judgments must be an array'})
            human_judgments = []
        if a.author_scores:
            if not strict:
                raise ValueError('author scores require a frozen study')
            human_judgments += list(author_judgments(a.author_scores, manifest, selected))
        seen_judgments = set()
        valid_author_judgments = []
        for judgment in human_judgments:
            if not isinstance(judgment, dict) or judgment.get('evaluator_role') != 'author' or not judgment.get('evaluator_id'):
                coverage['invalid'].append({'reason': 'human judgment must identify an actual author evaluator'})
                continue
            if (judgment.get('run_id') != manifest.get('run_id') or not judgment.get('rubric_version') or
                    not judgment.get('dimension') or not judgment.get('reason')):
                coverage['invalid'].append({'reason': 'human judgment missing rubric, dimension, or rationale'})
                continue
            if strict:
                coordinate = (judgment.get('case_id'), judgment.get('variant'), judgment.get('repeat_index'))
                result = selected.get(coordinate)
                if (not result or result.get('status') != 'complete' or
                        judgment.get('attempt_id') != result.get('attempt_id')):
                    coverage['invalid'].append({'coordinate': list(coordinate),
                                                'reason': 'human judgment does not bind to a selected complete output'})
                    continue
            dedupe = (judgment.get('case_id'), judgment.get('variant'), judgment.get('repeat_index'),
                      judgment.get('attempt_id'), judgment.get('dimension'), judgment.get('evaluator_id'))
            if dedupe in seen_judgments:
                coverage['invalid'].append({'reason': 'duplicate human judgment for output/dimension/evaluator'})
                continue
            seen_judgments.add(dedupe)
            stats['author_judgments'] += 1
            if type(judgment.get('accepted')) is bool:
                stats['author_scored'] += 1
                stats['author_accepted'] += judgment['accepted']
                valid_author_judgments.append(judgment)
                variant = variant_stats.get(judgment.get('variant', 'diagnostic'))
                if variant is not None:
                    dimension = variant['author_scores'].setdefault(judgment['dimension'], {'reviewed': 0, 'accepted': 0})
                    dimension['reviewed'] += 1
                    dimension['accepted'] += int(judgment['accepted'])
                    if judgment.get('kept_findings') is not None:
                        variant['author_reviewed_repairs'] += 1
                        variant['fixes_kept'] += len(judgment['kept_findings'])
        semantic_judgments = data.get('semantic_judgments', [])
        if not isinstance(semantic_judgments, list):
            coverage['invalid'].append({'reason': 'semantic_judgments must be an array'})
            semantic_judgments = []
        for judgment in semantic_judgments:
            if (not isinstance(judgment, dict) or judgment.get('evaluator_role') not in ('editor', 'expert', 'author') or
                    not judgment.get('evaluator_id') or not judgment.get('rubric_version') or not judgment.get('rationale') or
                    judgment.get('run_id') != manifest.get('run_id') or
                    judgment.get('judgment') not in ('successful', 'unsuccessful')):
                coverage['invalid'].append({'reason': 'invalid attributed semantic repair judgment'})
                continue
            coordinate = (judgment.get('case_id'), judgment.get('variant'), judgment.get('repeat_index'))
            result = selected.get(coordinate) if strict else None
            finding_index = judgment.get('finding_index')
            if (not result or result.get('status') != 'complete' or
                    judgment.get('attempt_id') != result.get('attempt_id') or
                    type(finding_index) is not int or not 0 <= finding_index < len(result.get('findings', []))):
                coverage['invalid'].append({'coordinate': list(coordinate),
                                            'reason': 'semantic judgment does not bind to a selected finding/output'})
                continue
            case = by_id[opaque_to_case.get(judgment.get('case_id'))] if strict and judgment.get('case_id') in opaque_to_case else None
            finding = result['findings'][finding_index]
            start, end, quote = finding.get('start'), finding.get('end'), finding.get('quote')
            if (not case or type(start) is not int or type(end) is not int or
                    not (0 <= start < end <= len(case['source'])) or case['source'][start:end] != quote or
                    not any(start < upper and lower < end
                            for lower, upper in spans(case['source'], case['defect_spans']))):
                coverage['invalid'].append({'coordinate': list(coordinate),
                                            'reason': 'semantic repair judgment does not target a valid localized defect'})
                continue
            stats['repair_judgments'] += 1
            stats['successful_repairs'] += judgment['judgment'] == 'successful'
        release_conditions = manifest.get('release_conditions', [])
        conditions_valid = (isinstance(release_conditions, list) and bool(release_conditions) and
                            all(isinstance(condition, dict) and condition.get('id') and
                                condition.get('status') == 'PASS' and condition.get('evidence')
                                for condition in release_conditions))
        if any(coverage[key] for key in ('duplicates', 'unknown', 'invalid')):
            coverage['status'] = 'INCOMPLETE'
        required_dimensions = manifest.get('required_author_dimensions', [])
        complete_author_coverage = False
        if strict and isinstance(required_dimensions, list) and required_dimensions:
            expected_outputs = {coordinate for coordinate, result in selected.items()
                                if result.get('status') == 'complete'}
            covered = {}
            for judgment in valid_author_judgments:
                coordinate = (judgment.get('case_id'), judgment.get('variant'), judgment.get('repeat_index'))
                if type(judgment.get('accepted')) is bool:
                    covered.setdefault(coordinate, set()).add(judgment.get('dimension'))
            complete_author_coverage = bool(expected_outputs) and all(
                set(required_dimensions).issubset(covered.get(coordinate, set()))
                for coordinate in expected_outputs)
        release_blockers = []
        if not strict or coverage['status'] != 'COMPLETE' or (manifest.get('study_version') and stats['failed_runs']):
            release_blockers.append('complete strict execution coverage is not established')
        if not conditions_valid:
            release_blockers.append('predeclared release conditions are missing or not all PASS')
        if not complete_author_coverage:
            release_blockers.append('required author judgment coverage remains pending or incomplete')
        stats['author_unscored'] = stats['author_judgments'] - stats['author_scored']
        author_status = ('recorded' if complete_author_coverage else
                         'pending' if not stats['author_scored'] else 'partial')
        tolerance_failures = []
        for cat_name, cat_stats in sorted(categories.items()):
            cat_stats['localization_rate'] = cat_stats['detected'] / cat_stats['defects'] if cat_stats['defects'] else None
            cat_stats['harmful_edit_rate'] = cat_stats['harmful'] / cat_stats['protected'] if cat_stats['protected'] else None
            tol = tolerances.get(cat_name)
            if not tol:
                continue
            max_harm = tol.get('max_harmful_edit_rate')
            min_loc = tol.get('min_localization_rate')
            if cat_stats['harmful_edit_rate'] is not None and max_harm is not None and cat_stats['harmful_edit_rate'] > max_harm:
                tolerance_failures.append({
                    'category': cat_name, 'metric': 'harmful_edit_rate',
                    'actual': cat_stats['harmful_edit_rate'], 'threshold': max_harm,
                })
            if cat_stats['localization_rate'] is not None and min_loc is not None and cat_stats['localization_rate'] < min_loc:
                tolerance_failures.append({
                    'category': cat_name, 'metric': 'localization_rate',
                    'actual': cat_stats['localization_rate'], 'threshold': min_loc,
                })
        print(json.dumps(dict(schema_version=1,coverage=coverage,counts=stats,categories=categories,
                              by_variant={variant_labels.get(label, label): values for label, values in variant_stats.items()},
                              category_tolerances=tolerances,
                              tolerance_failures=tolerance_failures,
                              localization_rate=stats['detected']/stats['defects'] if stats['defects'] else None,
                              harmful_edit_rate=stats['harmful']/stats['protected'] if stats['protected'] else None,
                              author_acceptance=stats['author_accepted']/stats['author_scored'] if stats['author_scored'] else None,
                              author_evaluation=author_status,
                              author_judgment_coverage='complete' if complete_author_coverage else 'incomplete',
                              release_eligible=not release_blockers,
                              release_blockers=release_blockers,
                              literary_thresholds='set after author-reviewed pilot; never inferred from this score'),indent=2))
    if not a.packets and not a.results:
        ap.error('choose --packets or --results')


if __name__ == '__main__':
    main()
