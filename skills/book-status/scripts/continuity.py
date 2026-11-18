"""Reconcile reviewed manuscript claims, with evidence from both sides of a conflict."""
from collections import defaultdict
from datetime import date
from decimal import Decimal
import hashlib
from itertools import groupby
import json
import math
from pathlib import PurePath
import re


def source_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def filename(chapter_id):
    return source_hash(chapter_id) + '.json'


def validate_claims(claims, text):
    if not isinstance(claims, list):
        raise ValueError('continuity review requires a claims list (empty when reviewed and none apply)')
    lines = text.splitlines()
    fields = {
        'identifier': ({'key', 'value'}, {'canonical', 'aliases'}),
        'state': ({'key', 'value', 'position', 'operation'}, set()),
        'clock': ({'key', 'clock', 'value'}, {'unit'}),
        'duration': ({'clock', 'start', 'end', 'value'}, {'tolerance', 'unit', 'minimum'}),
        'count': ({'key', 'snapshot', 'scope', 'value'}, set()),
        'date': ({'key', 'value'}, set()),
        'year_span': ({'start', 'end', 'value'}, set()),
        'exclusion': ({'clock', 'start', 'end', 'event'}, set()),
        'attribute': ({'key', 'stage', 'attribute', 'value'}, {'unit'}),
        'bundle': ({'key', 'snapshot', 'members', 'complete'}, set()),
        'support': ({'key', 'basis', 'assessment', 'rationale', 'references'}, {'research'}),
    }
    seen = set()
    for claim in claims:
        kind = claim.get('kind') if isinstance(claim, dict) else None
        if not isinstance(kind, str) or kind not in fields:
            raise ValueError('unknown continuity claim kind')
        required, optional = fields[kind]
        common = {'kind', 'line', 'quote'}
        if not (common | required) <= claim.keys() or claim.keys() - (common | required | optional):
            raise ValueError(f'invalid fields for {kind} continuity claim')
        line, quote = claim['line'], claim['quote']
        if type(line) is not int or not 1 <= line <= len(lines) or not phrase(quote) or quote not in lines[line - 1]:
            raise ValueError(f'continuity claim requires an exact nonempty quote on its source line ({line!r})')
        for field in required & {'key', 'clock', 'start', 'end', 'event', 'snapshot', 'stage', 'attribute'}:
            if not phrase(claim[field]):
                raise ValueError(f'continuity {kind} requires a nonempty {field}')
        value = claim.get('value')
        if kind in ('identifier', 'state') and not phrase(value):
            raise ValueError(f'continuity {kind} requires a nonempty value')
        if kind in ('clock', 'duration', 'count', 'year_span') and (type(value) is not int or kind != 'clock' and value < 0):
            raise ValueError(f'continuity {kind} requires an integer value (nonnegative for duration/count)')
        if kind == 'identifier':
            aliases = claim.get('aliases', [])
            canonical = claim.get('canonical', False)
            if (type(canonical) is not bool or not isinstance(aliases, list)
                    or not all(phrase(alias) for alias in aliases) or (aliases and not canonical)):
                raise ValueError('identifier aliases require an explicitly canonical claim')
        if kind == 'state':
            position = claim['position']
            if (not isinstance(position, list) or len(position) != 3
                    or not all(type(part) is int and part >= 0 for part in position)
                    or claim['operation'] not in ('set', 'assert')):
                raise ValueError('state requires a three-part story position and a set or assert operation')
        if kind == 'duration' and (type(claim.get('tolerance', 0)) is not int or claim.get('tolerance', 0) < 0):
            raise ValueError('duration tolerance must be a nonnegative number of minutes')
        if kind == 'count' and claim['scope'] is not None and not phrase(claim['scope']):
            raise ValueError('count scope must be a nonempty key or null when unclear to the reader')
        if kind in ('clock', 'duration') and claim.get('unit', 'minutes') not in ('minutes', 'seconds'):
            raise ValueError('clock and duration unit must be minutes or seconds')
        if kind == 'duration' and type(claim.get('minimum', False)) is not bool:
            raise ValueError('duration minimum must be boolean')
        if kind == 'date':
            if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                raise ValueError('calendar date must use YYYY-MM-DD')
            date.fromisoformat(value)
        if kind == 'attribute':
            unit = claim.get('unit')
            if type(value) is int or (type(value) is float and math.isfinite(value)):
                if not phrase(unit):
                    raise ValueError('numeric attributes require a unit')
            elif not phrase(value) or unit is not None:
                raise ValueError('attributes require a text value or a finite numeric value with a unit')
        if kind == 'bundle':
            members = claim['members']
            if (not isinstance(members, list) or not all(phrase(item) for item in members)
                    or len(members) != len(set(members)) or type(claim['complete']) is not bool):
                raise ValueError('bundles require unique member keys and a boolean complete flag')
        if kind == 'support':
            validate_support(claim)
        # Quotes on the same line can establish several different facts.
        identity = json.dumps(claim, sort_keys=True)
        if identity in seen:
            raise ValueError(f'duplicate continuity claim on line {line}')
        seen.add(identity)


def phrase(value):
    return isinstance(value, str) and bool(value.strip()) and '\n' not in value and '\r' not in value


def reference_path(value):
    return phrase(value) and not PurePath(value).is_absolute() and '..' not in PurePath(value).parts


def sha256(value):
    return isinstance(value, str) and bool(re.fullmatch(r'[0-9a-f]{64}', value))


def validate_support(claim):
    references = claim['references']
    if claim['assessment'] not in ('supported', 'contradiction', 'unresolved') or not phrase(claim['rationale']):
        raise ValueError('support requires an assessment and its rationale')
    if claim['basis'] not in ('story', 'research'):
        raise ValueError('support basis must be story or research')
    if not isinstance(references, list):
        raise ValueError('support references must be a list')
    for ref in references:
        if (not isinstance(ref, dict) or set(ref) != {'path', 'line', 'quote', 'source_sha256'}
                or not reference_path(ref['path']) or not sha256(ref['source_sha256'])
                or type(ref['line']) is not int or ref['line'] < 1 or not phrase(ref['quote'])):
            raise ValueError('support reference requires a project-relative path, line, quote, and source_sha256')
    research = claim.get('research')
    if research is not None and (
            not isinstance(research, dict) or set(research) != {'path', 'sha256', 'assertion_id'}
            or not reference_path(research['path']) or not sha256(research['sha256'])
            or not phrase(research['assertion_id'])):
        raise ValueError('research requires a project-relative evidence record, sha256, and assertion_id')
    if claim['assessment'] == 'contradiction' and not references:
        raise ValueError('a support contradiction requires a competing source passage')
    if research is not None and claim['basis'] != 'research':
        raise ValueError('research evidence requires the research basis')
    if claim['assessment'] == 'supported':
        if claim['basis'] == 'story' and not references:
            raise ValueError('a supported story claim requires an establishing source passage')
        if claim['basis'] == 'research' and research is None:
            raise ValueError('a supported research claim requires an inspected assertion record')


def current_claims(chapters, texts, records):
    coverage, claims = [], []
    for chapter in chapters:
        path, chapter_id = chapter['path'], chapter['id']
        record = records.get(chapter_id)
        sha256 = source_hash(texts[path]) if path in texts else None
        status = 'MISSING'
        if record is not None and sha256 is not None:
            status = 'STALE'
            if (record.get('chapter_id'), record.get('path'), record.get('source_sha256')) == (chapter_id, path, sha256):
                validate_claims(record.get('claims'), texts[path])
                status = 'CURRENT'
                claims.extend(dict(claim, path=path, chapter_id=chapter_id, source_sha256=sha256)
                              for claim in record['claims'])
        coverage.append({'chapter_id': chapter_id, 'path': path, 'source_sha256': sha256, 'status': status})
    return coverage, claims


def context(coverage, claims, keys):
    def claim_keys(claim):
        return {claim[field] for field in ('key', 'clock', 'start', 'end', 'event') if field in claim}

    return {
        'known_keys': sorted({key for claim in claims for key in claim_keys(claim)}),
        'claims': [claim for claim in claims if keys.intersection(claim_keys(claim))],
        'coverage_gaps': [item for item in coverage if item['status'] != 'CURRENT'],
    }


def finding(category, message, claims, blocking=True):
    subjects = [{field: claim[field] for field in ('chapter_id', 'path', 'line', 'quote', 'source_sha256')}
                for claim in claims]
    identity = '\n'.join(f"{source['path']}:{source['line']}:{source['quote']}" for source in subjects)
    finding_id = source_hash(message + '\n' + identity)[:16]
    return {'id': f'{category}-{finding_id}', 'category': category,
            'blocking': blocking, 'message': message, 'sources': subjects}


def by(claims, *fields):
    groups = defaultdict(list)
    for claim in claims:
        groups[tuple(claim[field] for field in fields)].append(claim)
    return groups.items()


def identifiers(claims):
    for (key,), group in by(claims, 'key'):
        baseline = next((claim for claim in group if claim.get('canonical')), group[0])
        allowed = {baseline['value']}
        for claim in group:
            if claim['value'] == baseline['value']:
                allowed.update(claim.get('aliases', []))
        for claim in group:
            if claim['value'] not in allowed:
                yield finding('identifier-conflict', f"{key}: {claim['value']!r} conflicts with {baseline['value']!r}.",
                              [baseline, claim])


def states(claims):
    for (key,), group in by(claims, 'key'):
        last = None
        for _, same_position in groupby(sorted(group, key=lambda claim: claim['position']),
                                         key=lambda claim: claim['position']):
            events = list(same_position)
            if len({claim['value'] for claim in events}) > 1:
                yield finding('state-order-unclear', f'{key}: conflicting claims share a story position. Verify event order.',
                              events, blocking=False)
                last = None
                continue
            change = next((claim for claim in events if claim['operation'] == 'set'), None)
            if change or last is None:
                last = change or events[0]
            elif events[0]['value'] != last['value']:
                for claim in events:
                    yield finding('state-conflict', f"{key}: {claim['value']!r} conflicts with last established state "
                                  f"{last['value']!r}. Verify an intervening change.", [last, claim])


def seconds(claim, field='value'):
    return claim.get(field, 0) * (1 if claim.get('unit') == 'seconds' else 60)


def time_value(value, unit):
    return f'{value // 60} minutes' if unit == 'minutes' else f'{value} seconds'


def timeline(clocks, durations, exclusions):
    anchors = {}
    for identity, group in by(clocks, 'clock', 'key'):
        baseline = group[0]
        conflicts = [claim for claim in group if seconds(claim) != seconds(baseline)]
        if conflicts:
            for claim in conflicts:
                difference = abs(seconds(claim) - seconds(baseline))
                unit = 'minutes' if difference % 60 == 0 else 'seconds'
                yield finding('clock-conflict', f"{identity[0]} / {identity[1]}: clock anchors disagree by "
                              f'{time_value(difference, unit)}.', [baseline, claim])
        else:
            anchors[identity] = baseline
    for claim in durations:
        start = anchors.get((claim['clock'], claim['start']))
        end = anchors.get((claim['clock'], claim['end']))
        if start is None or end is None:
            yield finding('duration-unresolved', f"{claim['start']} → {claim['end']}: verify both anchors on "
                          f"{claim['clock']}.", [claim] + [anchor for anchor in (start, end) if anchor], blocking=False)
            continue
        elapsed = seconds(end) - seconds(start)
        excess = seconds(claim) - elapsed
        if not claim.get('minimum'):
            excess = abs(excess)
        if elapsed < 0 or excess > seconds(claim, 'tolerance'):
            unit = 'seconds' if elapsed % 60 or claim.get('unit') == 'seconds' else 'minutes'
            qualifier = 'at least ' if claim.get('minimum') else ''
            yield finding('duration-conflict', f"{claim['start']} → {claim['end']}: stated {qualifier}"
                          f'{time_value(seconds(claim), unit)}; clock anchors give {time_value(elapsed, unit)}.',
                          [claim, start, end])
    for claim in exclusions:
        event, start, end = (anchors.get((claim['clock'], claim[field]))
                             for field in ('event', 'start', 'end'))
        known = [anchor for anchor in (event, start, end) if anchor]
        if len(known) != 3 or seconds(end) < seconds(start):
            yield finding('exclusion-unresolved', f"{claim['event']}: verify the event and both window boundaries.",
                          [claim, *known], blocking=False)
        elif seconds(start) <= seconds(event) <= seconds(end):
            yield finding('exclusion-conflict', f"{claim['event']}: an established occurrence falls inside the "
                          'claimed exclusion window.', [claim, event, start, end])


def calendar_checks(dates, spans):
    anchors = {}
    for (key,), group in by(dates, 'key'):
        baseline = group[0]
        conflicts = [claim for claim in group if claim['value'] != baseline['value']]
        for claim in conflicts:
            yield finding('date-conflict', f"{key}: {baseline['value']} conflicts with {claim['value']}.",
                          [baseline, claim])
        if not conflicts:
            anchors[key] = baseline
    for claim in spans:
        start, end = (anchors.get(claim[field]) for field in ('start', 'end'))
        if not start or not end:
            known = [anchor for anchor in (start, end) if anchor]
            yield finding('year-span-unresolved', 'Verify both dates for the stated calendar-year interval.',
                          [claim, *known], blocking=False)
            continue
        first, last = date.fromisoformat(start['value']), date.fromisoformat(end['value'])
        years = last.year - first.year - ((last.month, last.day) < (first.month, first.day))
        if years != claim['value']:
            yield finding('year-span-conflict', f'{years} completed calendar years elapsed; '
                          f"the text states {claim['value']}.", [claim, start, end])


def attribute_value(claim):
    return f"{claim['value']} {claim.get('unit', '')}".rstrip()


def attributes(claims):
    frequency = {'Hz': 1, 'kHz': 1000, 'MHz': 1000000}
    for (key, stage, attribute), group in by(claims, 'key', 'stage', 'attribute'):
        baseline = group[0]
        for claim in group[1:]:
            unit, established_unit = claim.get('unit'), baseline.get('unit')
            new, established = claim['value'], baseline['value']
            subject = f'{key} / {stage} / {attribute}'
            if unit in frequency and established_unit in frequency:
                new = Decimal(str(new)) * frequency[unit]
                established = Decimal(str(established)) * frequency[established_unit]
            elif unit != established_unit:
                yield finding('attribute-units-unresolved', f'{subject}: verify comparable units.',
                              [baseline, claim], blocking=False)
                continue
            if new != established:
                yield finding('attribute-conflict', f'{subject}: {attribute_value(claim)} conflicts with '
                              f'established {attribute_value(baseline)}.', [baseline, claim])


def bundles(claims):
    for (key, snapshot), group in by(claims, 'key', 'snapshot'):
        baseline = next((claim for claim in group if claim['complete']), None)
        if baseline is None:
            continue
        established = set(baseline['members'])
        for claim in group:
            observed = set(claim['members'])
            if observed - established or (claim['complete'] and observed != established):
                yield finding('bundle-conflict', f'{key} ({snapshot}): the asserted contents conflict with the '
                              'complete inventory for that revision.', [baseline, claim])


def counts(claims):
    for (key, snapshot), group in by(claims, 'key', 'snapshot'):
        scoped = {}
        for claim in group:
            scope = claim['scope']
            if scope is None:
                other = next((item for item in group if item['value'] != claim['value']), None)
                if other:
                    yield finding('count-scope-unclear', f'{key} ({snapshot}): clarify which set this count covers.',
                                  [claim, other], blocking=False)
            else:
                baseline = scoped.setdefault(scope, claim)
                if baseline['value'] != claim['value']:
                    yield finding('count-conflict', f'{key} ({snapshot}, {scope}): competing counts of '
                                  f"{baseline['value']} and {claim['value']}.", [baseline, claim])


def reconcile(claims):
    kinds = defaultdict(list)
    for claim in claims:
        kinds[claim['kind']].append(claim)
    return [*identifiers(kinds['identifier']), *states(kinds['state']),
            *timeline(kinds['clock'], kinds['duration'], kinds['exclusion']), *counts(kinds['count']),
            *calendar_checks(kinds['date'], kinds['year_span']), *attributes(kinds['attribute']),
            *bundles(kinds['bundle'])]
