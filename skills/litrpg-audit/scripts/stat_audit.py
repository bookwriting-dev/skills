#!/usr/bin/env python3
"""Audit chapter progression against the committed LitRPG ledger and cited events."""
import argparse
import ast
from collections import defaultdict, Counter
import importlib.util
import json
from pathlib import Path
import re


RULES = ('skill_unlock', 'stat_points', 'xp', 'derived_pools', 'resources', 'inventory',
         'incapacitation', 'status_length')
HARD_RULES = {'skill_unlock', 'stat_points', 'derived_pools', 'incapacitation'}
LEDGERS = ('Wiki/World/Systems/ledger.yaml', 'Wiki/World/ledger.yaml', 'ledger.yaml')
EVENTS = {'unlock', 'use_skill', 'allocate', 'level_up', 'xp_gain', 'status', 'spend',
          'recover', 'gain_item', 'lose_item', 'incapacitate', 'revive', 'act'}


def number(value):
    return value if type(value) is int and value >= 0 else None


def key(name):
    return ' '.join(str(name).replace('_', ' ').casefold().split())


def chapter_number(value):
    match = re.fullmatch(r'(?:Chapter[- ]?)?(\d+)(?:\.md)?', str(value), re.I)
    return int(match[1]) if match else None


def locate_ledger(chapter, explicit):
    for root in chapter.parents:
        if (root / 'Wiki').is_dir() or (root / '.storycraft').is_dir():
            book = next((part for part in chapter.relative_to(root).parts
                         if re.fullmatch(r'Book-\d+', part)), None)
            candidates = [*LEDGERS]
            if book:
                candidates.insert(1, f'Wiki/Story/{book}/ledger.yaml')
            if explicit:
                return root, explicit
            store = ledger_module()
            pointer = store.current_pointer(root) if store is not None else None
            committed = (pointer or {}).get('ledgers', {})
            return root, next((root / path for path in candidates if path in committed or (root/path).is_file()), None)
    candidates = [root / name for root in chapter.parents[:3] for name in LEDGERS]
    return None, explicit or next((path for path in candidates if path.is_file()), None)


def ledger_module():
    path = Path(__file__).resolve().parents[2] / 'book-status/scripts/ledger_store.py'
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location('storycraft_litrpg_ledger', path)
    store = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(store)
    return store


def ledger_bytes(path, root):
    if root and path.is_relative_to(root):
        store = ledger_module()
        if store is None:
            raise ValueError('book-status ledger helper is missing from this installation')
        raw = store.load_ledger_bytes(root, path.relative_to(root).as_posix())
        if raw is not None:
            return raw
    return path.read_bytes()


def yaml_mapping(raw, path):
    try:
        import yaml
    except ImportError as exc:
        raise ValueError('PyYAML is required to read the progression ledger') from exc
    try:
        document = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f'cannot read YAML ledger {path}: {exc}') from exc
    if not isinstance(document, dict):
        raise ValueError(f'{path} needs a YAML mapping')
    return document


def system_blocks(lines):
    """Only classify game displays. An ordinary quotation is reader prose."""
    blocks = []
    current = []
    for n, line in enumerate([*lines, ''], 1):
        if line.lstrip().startswith('>'):
            current.append((n, line.lstrip()[1:].strip()))
        elif current:
            content = '\n'.join(text for _, text in current)
            if re.match(r'\[!(?:system|alert|skill|quest|status|level|item|stat)\b', content, re.I) or re.search(
                    r'^(?:\*{0,2})(?:level up|health|hp|mp|sp|str|agility|skill unlocked)\b', content, re.I | re.M):
                blocks.append(current)
            current = []
    return blocks


def skill_records(character):
    skills = character.get('skills')
    if not isinstance(skills, list):
        return None
    records = {}
    for entry in skills:
        if isinstance(entry, str):
            records[key(entry)] = {}
        elif isinstance(entry, dict) and isinstance(entry.get('name'), str):
            records[key(entry['name'])] = entry
        else:
            return None
    return records


def actor_index(characters):
    aliases = defaultdict(set)
    for name, data in characters.items():
        if not isinstance(data, dict):
            raise ValueError(f'invalid character record: {name}')
        display = name.replace('_', ' ')
        names = [display, display.split()[0], *data.get('aliases', [])]
        for alias in names:
            aliases[key(alias)].add(name)
    return {alias: next(iter(names)) for alias, names in aliases.items() if len(names) == 1}


def text_events(lines, actors, displays, default_actor):
    """Recover clearly named actions and display fields with exact line evidence."""
    out = []
    names = sorted(actors, key=len, reverse=True)
    subjects = '|'.join(re.escape(name).replace(r'\ ', '[ _]+') for name in names)
    skill_use = re.compile(
        rf"\b(?P<actor>(?i:{subjects}|he|she|they|I)|[A-Z][\w'’-]*)\s+"
        r"(?i:cast|casts|casted|invoked|invokes|activated|activates|channeled)\s+"
        r"(?P<skill>[A-Z][\w'’-]*(?:[ -]+[A-Z][\w'’-]*){0,5})\b"
    )
    for n, line in enumerate(lines, 1):
        if not line.lstrip().startswith('>'):
            for match in skill_use.finditer(line):
                out.append(dict(type='use_skill', actor=actors.get(key(match['actor'])),
                                skill=match['skill'], line=n, quote=match[0]))
    for block in displays:
        for n, text in block:
            evidence = {'line': n, 'quote': lines[n-1].strip(), 'actor': default_actor}
            text = text.replace('**', '')
            named = re.search(r'^(?:character|actor)\s*:\s*(.+)$', text, re.I)
            if named:
                default_actor = actors.get(key(named[1]))
                continue
            unlock = re.search(r'\bskill\s+(?:unlocked|acquired|learned)\s*:\s*([^|]+)', text, re.I)
            if unlock:
                out.append(dict(evidence, type='unlock', skill=unlock[1].strip()))
            level = re.search(r'\blevel\s+(?:up!?|reached)\s*[:*\s]+(?:\d+\s*(?:->|→)\s*)?(\d+)', text, re.I)
            if level:
                out.append(dict(evidence, type='level_up', level=int(level[1])))
            xp = re.search(r'\+([\d,]+)\s*(?:XP|EXP)\b', text, re.I)
            if xp:
                out.append(dict(evidence, type='xp_gain', amount=int(xp[1].replace(',', ''))))
            allocation = re.search(r'\b([A-Z]{2,4})\s*:?\s*(?:\d+\s*(?:→|->)\s*\d+\s*\()?\+(\d+)\b', text)
            if allocation and allocation[1] not in ('HP', 'MP', 'SP', 'XP', 'EXP'):
                out.append(dict(evidence, type='allocate', attribute=allocation[1], amount=int(allocation[2])))
            pools = dict((pool.upper(), int(maximum or value)) for pool, value, maximum
                         in re.findall(r'\b(?:Max\s+)?(HP|MP|SP)\s*:\**\s*(\d+)(?:\s*/\s*(\d+))?', text, re.I))
            if pools:
                out.append(dict(evidence, type='status', pools=pools))
    return out


def event_list(record, actors, chapter, lines, displays):
    default = actors.get(key(record.get('character', '')))
    if default is None and len(set(actors.values())) == 1:
        default = next(iter(actors.values()))
    extracted = text_events(lines, actors, displays, default)
    supplied = []
    for event in record.get('events', []):
        if not isinstance(event, dict):
            raise ValueError('progression events must be mappings')
        kind = event.get('type') or ('xp_gain' if 'xp_gain' in event else None)
        if kind is None:
            continue
        if kind not in EVENTS:
            raise ValueError(f'unknown progression event type: {kind}')
        row = dict(event, type=kind, actor=actors.get(key(event['actor'])) if 'actor' in event else default)
        if 'xp_gain' in event:
            row['amount'] = event['xp_gain']
        line = event.get('line')
        if line is not None:
            quote = event.get('quote')
            if type(line) is not int or not 1 <= line <= len(lines) or not isinstance(quote, str) or not quote or quote not in lines[line-1]:
                raise ValueError(f'{chapter.name}: progression event has stale line/quote evidence')
        supplied.append(row)
    # Same text and declared event describe a single state transition.
    anchors = {(entry['line'], entry['type']) for entry in supplied if 'line' in entry}
    # Legacy aggregate event lists rarely name lines. A display match to the same XP
    # gain still needs reconciliation before combining those two interpretations.
    legacy_xp = any(row['type'] == 'xp_gain' and 'line' not in row for row in supplied)
    extracted = [row for row in extracted if (row['line'], row['type']) not in anchors
                 and not (legacy_xp and row['type'] == 'xp_gain')]
    return sorted(supplied + extracted, key=lambda row: (row.get('line', 0), 'line' not in row))


def xp_threshold(rules, level):
    if level is None or level < 2:
        return None
    table = rules.get('xp_thresholds', {})
    if isinstance(table, dict) and (value := table.get(level, table.get(str(level)))) is not None:
        return number(value)
    base = number(rules.get('xp_base'))
    if base and rules.get('xp_model') == 'quadratic':
        return base * (level - 1) ** 2
    growth = number(rules.get('xp_growth'))
    if base and growth and rules.get('xp_model') == 'exponential':
        return base * growth ** (level - 2)
    return None


def pool_max(formula, state):
    if not isinstance(formula, dict) or not all(type(coefficient) is int for coefficient in formula.values()):
        return None
    values = {'level': state['level'], **state['attributes']}
    if any(field != 'base' and number(values.get(field)) is None for field in formula):
        return None
    return sum(coefficient * (1 if field == 'base' else values[field])
               for field, coefficient in formula.items())


def markdown_pools(text):
    """Read the additive formulas generated by the original system-rules template."""
    def terms(node):
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return {'base': node.value}
        if isinstance(node, ast.Name):
            return {'level' if node.id.casefold() == 'level' else node.id.upper(): 1}
        if not isinstance(node, ast.BinOp):
            raise ValueError('unsupported arithmetic')
        left = terms(node.left)
        right = terms(node.right)
        if isinstance(node.op, ast.Mult) and len(left) == 1 and 'base' in left:
            return {field: value * left['base'] for field, value in right.items()}
        if isinstance(node.op, ast.Mult) and len(right) == 1 and 'base' in right:
            return {field: value * right['base'] for field, value in left.items()}
        if isinstance(node.op, (ast.Add, ast.Sub)):
            sign = -1 if isinstance(node.op, ast.Sub) else 1
            return {field: left.get(field, 0) + sign * right.get(field, 0)
                    for field in left.keys() | right.keys()}
        raise ValueError('unsupported arithmetic')

    pools = {}
    for pool, formula in re.findall(r'\b(HP|MP|SP)\):\*\*[ \t]*\x60([^\x60\n]+)\x60', text):
        try:
            pools[pool] = terms(ast.parse(formula, mode='eval').body)
        except (SyntaxError, ValueError):
            continue
    return pools


def states(characters, record, n):
    result = {}
    participants = record.get('participants', {})
    for name, sheet in characters.items():
        own = participants.get(name, {})
        entrance = own.get('state_in', record.get('state_in', {}) if name == record.get('character') else {})
        if number(sheet.get('state_chapter')) == n:
            entrance = dict(sheet, **entrance)
        skills = skill_records(sheet)
        available = {}
        unknown = set()
        for skill, details in (skills or {}).items():
            unlock = chapter_number(details.get('unlocked_chapter'))
            if unlock is not None and unlock < n:
                available[skill] = details
            elif unlock is None or unlock == n:
                unknown.add(skill)
        inventory = entrance.get('inventory')
        result[name] = {
            'skills': available, 'registry': skills, 'unknown_skills': unknown,
            'level': number(entrance.get('level', entrance.get('current_level'))),
            'xp': number(entrance.get('xp', entrance.get('total_xp'))),
            'unspent': number(entrance.get('unspent_stats', entrance.get('unspent_stat_points'))),
            'attributes': dict(entrance.get('attributes', {})),
            'resources': {key(k): v for k, v in entrance.get('resources', {}).items()},
            'inventory': {key(k): v for k, v in inventory.items()} if isinstance(inventory, dict) else None,
            'incapacitated': entrance.get('incapacitated'),
        }
    return result


def compare_state_out(record, actors, checks):
    for actor, state in actors.items():
        default = record.get('state_out', {}) if actor == record.get('character') else {}
        ending = record.get('participants', {}).get(actor, {}).get('state_out', default)
        for label, field, rule in (
            ('inventory', 'inventory', 'inventory'), ('resources', 'resources', 'resources'),
            ('xp', 'xp', 'xp'), ('level', 'level', 'xp'), ('unspent_stats', 'unspent', 'stat_points'),
        ):
            if label not in ending:
                continue
            expected, tracked = ending[label], state[field]
            if isinstance(expected, dict):
                expected = {key(name): value for name, value in expected.items() if value != 0}
                if isinstance(tracked, dict):
                    tracked = {name: value for name, value in tracked.items() if value != 0}
            status = ('UNVERIFIED' if tracked is None else 'PASS' if tracked == expected
                      else 'FAIL' if rule in HARD_RULES else 'WARN')
            checks[rule].append({'type': rule.upper(), 'status': status, 'line': None,
                                 'message': f'{actor}: ending {label} is {expected!r}, ledger transitions give {tracked!r}'})


def audit_events(events, actors, rules, checks):
    def result(category, status, message, event):
        checks[category].append({'status': status, 'type': category.upper(), 'message': message,
                                 'line': event.get('line'), 'quote': event.get('quote')})

    incoming_unlocks = Counter((event['actor'], key(event.get('skill', '')))
                               for event in events if event['type'] == 'unlock')
    anchored_spends = {(event['actor'], event.get('line'), key(event.get('resource', '')))
                       for event in events if event['type'] == 'spend' and event.get('line') is not None}
    unanchored_unlocks = set()
    for event in events:
        actor, kind = event.get('actor'), event['type']
        state = actors.get(actor)
        amount = number(event.get('amount'))
        skill = key(event.get('skill', ''))
        category = dict(unlock='skill_unlock', use_skill='skill_unlock', allocate='stat_points',
                        level_up='xp', xp_gain='xp', status='derived_pools', spend='resources',
                        recover='resources', gain_item='inventory', lose_item='inventory',
                        incapacitate='incapacitation', revive='incapacitation', act='incapacitation')[kind]
        if state is None:
            result(category, 'UNVERIFIED', 'cannot identify the acting character', event)
            continue

        def record(status, message, check=category):
            result(check, status, f'{actor}: {message}', event)

        if kind in ('act', 'use_skill'):
            if state['incapacitated'] is None:
                record('UNVERIFIED', 'incapacitation state before action is unknown', 'incapacitation')
            else:
                record('FAIL' if state['incapacitated'] else 'PASS',
                       'acting while incapacitated' if state['incapacitated'] else 'action while able', 'incapacitation')
        if kind in ('incapacitate', 'revive'):
            state['incapacitated'] = kind == 'incapacitate'
            record('PASS', f'{kind} state recorded')
        elif kind == 'unlock':
            incoming_unlocks[(actor, skill)] -= 1
            if 'line' not in event:
                unanchored_unlocks.add((actor, skill))
            details = (state['registry'] or {}).get(skill, {})
            level = number(event.get('requires_level', details.get('requires_level')))
            prerequisites = event.get('requires', details.get('requires', []))
            if not skill or (level is not None and state['level'] is None):
                record('UNVERIFIED', 'skill name or prerequisite state is missing')
            elif (level is not None and state['level'] < level) or any(key(item) not in state['skills'] for item in prerequisites):
                record('FAIL', f'prerequisites unmet for {event["skill"]}')
            else:
                state['skills'][skill] = details
                state['unknown_skills'].discard(skill)
                record('PASS', f'{event["skill"]} unlocked')
        elif kind == 'use_skill':
            if skill in state['skills'] and ('line' not in event or (actor, skill) not in unanchored_unlocks):
                record('PASS', f'{event["skill"]} was available at use')
                detail = state['skills'][skill]
                resource = key(detail.get('cost_type', ''))
                cost = number(detail.get('cost'))
                if resource and cost and (actor, event.get('line'), resource) not in anchored_spends:
                    if type(state['resources'].get(resource)) is not int:
                        record('UNVERIFIED', f'entering {resource} is missing for the skill cost', 'resources')
                    else:
                        state['resources'][resource] -= cost
                        remaining = state['resources'][resource]
                        record('WARN' if remaining < 0 else 'PASS',
                               f'{event["skill"]} spends {cost} {resource}, leaving {remaining}', 'resources')
            elif (incoming_unlocks[(actor, skill)] > 0 or
                  (skill and state['registry'] is not None and skill not in state['unknown_skills']
                   and (actor, skill) not in unanchored_unlocks)):
                record('FAIL', f'{event["skill"]} was not unlocked at use')
            else:
                record('UNVERIFIED', f'unlock position for {event.get("skill", "skill")} is unknown')
        elif kind == 'xp_gain':
            if amount is None or state['xp'] is None:
                record('UNVERIFIED', 'earned or entering XP is missing')
            else:
                state['xp'] += amount
                record('PASS', f'XP increases to {state["xp"]}')
        elif kind == 'level_up':
            level = number(event.get('level'))
            threshold = xp_threshold(rules, level)
            if threshold is None or state['xp'] is None or state['level'] is None:
                record('UNVERIFIED', 'level threshold or prior XP/level is missing')
                state['level'] = level
                state['unspent'] = None
            elif state['xp'] < threshold or level <= state['level']:
                record('WARN', f'level {level} requires {threshold} XP and an increase from level {state["level"]}')
            else:
                per_level = number(rules.get('stat_points_per_level'))
                if state['unspent'] is not None and per_level is not None:
                    state['unspent'] += (level - state['level']) * per_level
                else:
                    state['unspent'] = None
                state['level'] = level
                record('PASS', f'level {level} meets the XP threshold')
        elif kind == 'allocate':
            if state['unspent'] is None or amount is None:
                record('UNVERIFIED', 'available stat points or allocation is missing')
            elif amount > state['unspent']:
                record('FAIL', f'allocates {amount} points with {state["unspent"]} available')
            else:
                state['unspent'] -= amount
                attribute = event.get('attribute', '')
                if attribute in state['attributes']:
                    state['attributes'][attribute] += amount
                record('PASS', f'allocates {amount} earned points')
        elif kind == 'status':
            for pool, printed in event.get('pools', {}).items():
                expected = pool_max(rules.get('pool_formulas', {}).get(pool.upper()), state)
                if expected is None or number(printed) is None:
                    record('UNVERIFIED', f'{pool} formula, attributes, or printed value is missing')
                else:
                    record('PASS' if expected == printed else 'FAIL', f'{pool} printed {printed}, expected {expected}')
        elif kind in ('spend', 'recover'):
            resource = key(event.get('resource', ''))
            previous = state['resources'].get(resource)
            if not resource or type(previous) is not int or amount is None:
                record('UNVERIFIED', f'prior {resource} or amount is missing')
            else:
                remaining = previous - amount if kind == 'spend' else previous + amount
                record('WARN' if remaining < 0 else 'PASS', f'{resource} changes from {previous} to {remaining}')
                state['resources'][resource] = remaining
        elif kind in ('gain_item', 'lose_item'):
            inventory = state['inventory']
            item = key(event.get('item', ''))
            previous = number(inventory.get(item, 0)) if inventory is not None else None
            if not item or amount is None or previous is None:
                record('UNVERIFIED', 'inventory before the transfer or transferred quantity is missing')
            else:
                remaining = previous + amount if kind == 'gain_item' else previous - amount
                record('WARN' if remaining < 0 else 'PASS', f'{item} count changes from {previous} to {remaining}')
                inventory[item] = remaining


def audit_chapter(chapter_path, ledger_path=None, rules_path=None):
    chapter = Path(chapter_path).resolve()
    lines = chapter.read_text(encoding='utf-8').splitlines()
    displays = system_blocks(lines)
    checks = {rule: [] for rule in RULES}
    for block in displays:
        checks['status_length'].append(dict(status='WARN' if len(block) > 25 else 'PASS',
                                           type='STAT_DUMP_PARALYSIS', line=block[0][0],
                                           message=f'system display contains {len(block)} lines (limit 25)'))
    n = chapter_number(chapter.stem)
    coverage_issue = None
    ledger = None
    try:
        project, ledger = locate_ledger(chapter, Path(ledger_path).resolve() if ledger_path else None)
    except (ValueError, OSError, TypeError) as exc:
        coverage_issue = str(exc)
    if not ledger:
        coverage_issue = coverage_issue or 'progression ledger is missing'
    elif n is None:
        coverage_issue = 'chapter number is required for unlock chronology'
    else:
        try:
            data = yaml_mapping(ledger_bytes(ledger, project), ledger)
            characters = data.get('characters')
            if not isinstance(characters, dict) or not characters:
                raise ValueError('ledger needs a nonempty characters mapping')
            record = data.get('chapters', {}).get(f'Chapter-{n:03}', {})
            rules = dict(data.get('system_rules', {}))
            explicit_path = Path(rules_path) if rules_path else None
            if explicit_path and explicit_path.suffix.lower() in ('.yaml', '.yml'):
                explicit = yaml_mapping(explicit_path.read_bytes(), explicit_path)
                rules = explicit.get('system_rules', explicit)
            elif explicit_path or (project and 'pool_formulas' not in rules):
                source = explicit_path or project / 'Wiki/World/Systems/system-rules.md'
                if source.is_file() or explicit_path:
                    rules['pool_formulas'] = markdown_pools(source.read_text(encoding='utf-8'))
            actors = actor_index(characters)
            events = event_list(record, actors, chapter, lines, displays)
            actor_states = states(characters, record, n)
            audit_events(events, actor_states, rules, checks)
            compare_state_out(record, actor_states, checks)
        except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
            coverage_issue = str(exc)
    verdicts = {}
    for rule, findings in checks.items():
        statuses = {item['status'] for item in findings}
        verdicts[rule] = next((status for status in ('FAIL', 'WARN', 'UNVERIFIED', 'PASS') if status in statuses),
                              'UNVERIFIED' if coverage_issue and rule != 'status_length' else 'NOT_APPLICABLE')
    findings = [item for items in checks.values() for item in items]
    hard = [item for item in findings if item['status'] == 'FAIL' and item['type'].lower() in HARD_RULES]
    warnings = [item for item in findings if item['status'] in ('WARN', 'UNVERIFIED')]
    if coverage_issue:
        warnings.append(dict(type='AUDIT_COVERAGE', message=coverage_issue))
    return dict(chapter=str(chapter_path), ledger_found=bool(ledger), ledger_path=str(ledger) if ledger else None,
                status='FAIL' if hard else 'WARN' if warnings else 'PASS',
                system_blocks_count=len(displays), violations=hard, warnings=warnings, notices=[],
                rule_results=verdicts, checked_evidence=checks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('chapter')
    parser.add_argument('--ledger')
    parser.add_argument('--rules', help='explicit YAML rules or legacy Markdown pool formulas')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    report = audit_chapter(args.chapter, args.ledger, args.rules)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f'# LitRPG progression audit\n\n**Status:** {report["status"]}')
        for rule, verdict in report['rule_results'].items():
            print(f'- {rule}: {verdict}')
        for finding in report['violations'] + report['warnings']:
            print(f'- {finding.get("line") or "ledger"} — {finding["message"]}')
    return 1 if report['status'] == 'FAIL' else 0


if __name__ == '__main__':
    raise SystemExit(main())
