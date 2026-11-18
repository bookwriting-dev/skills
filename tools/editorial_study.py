"""Prepare matched editorial runs and bind blind author reviews to recorded outputs."""
import hashlib
import json
from pathlib import Path
import posixpath
import re
import secrets
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS = ROOT / 'tools/eval-fixtures/editorial-preservation/cases.json'
DIMENSIONS = ('useful_repair', 'voice_preserved')
FINDING_FIELDS = ('start', 'end', 'quote', 'replacement', 'reason', 'category')
RESULT_SCHEMA = {
    'type': 'object',
    'properties': {'findings': {'type': 'array', 'items': {
        'type': 'object',
        'properties': {field: {'type': 'integer' if field in ('start', 'end') else 'string'}
                       for field in FINDING_FIELDS},
        'required': list(FINDING_FIELDS), 'additionalProperties': False,
    }}},
    'required': ['findings'], 'additionalProperties': False,
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def document_hash(data):
    return sha(json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode())


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def spans(source, items, *, private=False):
    resolved = []
    for item in items:
        if isinstance(item, str):
            start = source.find(item)
            end = start + len(item)
            if private and (not item or source.count(item) != 1):
                raise ValueError('use exact offsets for a missing or repeated private corpus quote')
        elif isinstance(item, dict):
            start, end = item.get('start'), item.get('end')
            if (type(start) is not int or type(end) is not int or
                    not 0 <= start < end <= len(source) or source[start:end] != item.get('quote')):
                raise ValueError('corpus span needs exact zero-based start/end offsets and quote')
        else:
            raise ValueError('corpus spans must be quote strings or anchored objects')
        if start >= 0:
            resolved.append((start, end))
    return resolved


def load_corpus(path):
    path = Path(path).resolve()
    document = json.loads(path.read_text(encoding='utf-8'))
    cases = document.get('cases')
    if not isinstance(cases, list) or not cases:
        raise ValueError('corpus needs a nonempty cases array')
    ids = set()
    for case in cases:
        if not isinstance(case.get('id'), str) or not case['id'] or case['id'] in ids:
            raise ValueError('corpus case IDs must be nonempty and unique')
        ids.add(case['id'])
        if 'source_file' in case:
            ref = (path.parent / case['source_file']).resolve()
            if not ref.is_relative_to(path.parent):
                raise ValueError('private corpus chapters must be under the corpus directory')
            case['source'] = ref.read_bytes().decode('utf-8')
        if not isinstance(case.get('source'), str) or not case['source'].strip():
            raise ValueError('corpus case requires source or source_file')
        if not isinstance(case.get('category'), str) or 'rules' not in case:
            raise ValueError('corpus case requires category and applicable rules')
        for field in ('defect_spans', 'protected_spans'):
            if not isinstance(case.get(field), list):
                raise ValueError(f'corpus case requires {field} array')
            spans(case['source'], case[field], private=path != DEFAULT_CORPUS)
    return document


def collect_skill(skill, ref):
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', skill):
        raise ValueError('invalid skill name')
    if ref:
        ref = subprocess.check_output(
            ['git', 'rev-parse', '--verify', '--end-of-options', ref + '^{commit}'], cwd=ROOT, text=True).strip()
    skillpath = f'skills/{skill}/SKILL.md'
    bundle = {}

    def collect(name):
        if name in bundle:
            return
        content = (subprocess.check_output(['git', 'show', f'{ref}:{name}'], cwd=ROOT, text=True)
                   if ref else (ROOT / name).read_text(encoding='utf-8'))
        bundle[name] = content
        for linked in re.findall(r'\]\(([^)#]+\.md)(?:#[^)]*)?\)', content):
            if '://' in linked or linked.startswith('/'):
                continue
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), linked))
            if not resolved.startswith('skills/'):
                raise ValueError('evaluation rule link escapes skills: ' + resolved)
            collect(resolved)

    collect(skillpath)
    return bundle[skillpath], bundle, ref


def prepare_packets(args, corpus):
    packets = args.packets.resolve()
    private = packets.parent / ('.' + packets.name + '-private-manifest.json')
    study_manifest = packets.parent / (packets.name + '-study.json')
    if args.configuration and ((packets.exists() and any(packets.iterdir()))
                               or private.exists() or study_manifest.exists()):
        raise ValueError('choose a fresh path for a matched study')
    packets.mkdir(parents=True, exist_ok=True)
    cases = [case for case in corpus['cases'] if args.split == 'all'
             or case.get('split', 'calibration') == args.split]
    if not cases:
        raise ValueError('selected split has no cases')
    mapping = {secrets.token_urlsafe(18): case['id'] for case in cases}
    if args.configuration:
        identities = {secrets.token_hex(6): label for label in ('baseline', 'candidate')}
        config = json.loads(args.configuration.read_text(encoding='utf-8'))
        if not isinstance(config, dict) or not config.get('model') or not config.get('host'):
            raise ValueError('matched study configuration requires model and host')
    else:
        identities = {'': 'baseline'} if args.baseline_ref else {'': 'candidate'}
        config = None

    source_hashes, packet_hashes, skill_hashes, ref_hashes = {}, {}, {}, {}
    for variant, label in identities.items():
        if config and label == 'candidate' and not args.candidate_ref:
            raise ValueError('matched study requires a frozen --candidate-ref')
        ref = args.baseline_ref if label == 'baseline' else args.candidate_ref
        skill, bundle, commit = collect_skill(args.skill, ref)
        hashes = {name: sha(content.encode()) for name, content in bundle.items()}
        skill_hashes[variant] = document_hash(hashes)
        ref_hashes[variant] = commit
        directory = packets / variant
        directory.mkdir(exist_ok=True)
        for opaque_id, case in zip(mapping, cases):
            source_hashes[opaque_id] = sha(case['source'].encode())
            packet = dict(schema_version=1, case_id=opaque_id, source=case['source'], rules=case['rules'],
                          skill=skill, source_sha256=source_hashes[opaque_id], skill_sha256=sha(skill.encode()),
                          rule_sources=bundle, rule_hashes=hashes,
                          task='Return findings with exact source offsets, quote, proposed replacement, and reason. Preserve deliberate choices.')
            path = directory / (opaque_id + '.json')
            write_json(path, packet)
            packet_hashes.setdefault(opaque_id, {})[variant] = sha(path.read_bytes())

    private_data = {'schema_version': 1, 'mapping': mapping}
    if config:
        private_data.update(variants=identities, revisions=ref_hashes)
    write_json(private, private_data)
    summary = {'packets': len(cases) * len(identities), 'split': args.split, 'candidate_visible_labels': False,
               'private_manifest': str(private), 'mapping_sha256': sha(private.read_bytes())}
    if config:
        manifest = {'schema_version': 1, 'study_version': 1, 'run_id': 'study-' + secrets.token_hex(8),
                    'corpus_sha256': document_hash(corpus), 'configuration': config,
                    'configuration_sha256': document_hash(config), 'repeat_count': args.repeats,
                    'expected_case_ids': list(mapping), 'variants': list(identities),
                    'source_hashes': source_hashes, 'packet_hashes': packet_hashes,
                    'skill_hashes': skill_hashes, 'mapping_sha256': summary['mapping_sha256'],
                    'permissions': 'read the assigned packet and return findings',
                    'permitted_context': 'one assigned full chapter and its supplied rules',
                    'span_policy': 'zero-based half-open Unicode code-point offsets',
                    'required_author_dimensions': list(DIMENSIONS)}
        write_json(study_manifest, manifest)
        summary['study_manifest'] = str(study_manifest)
    return summary


def codex_findings(binary, packet, configuration):
    with tempfile.TemporaryDirectory(prefix='storycraft-editorial-') as temporary:
        workspace = Path(temporary)
        schema = workspace / 'schema.json'
        output = workspace / 'result.json'
        write_json(schema, RESULT_SCHEMA)
        command = [binary, '-a', 'never', '-s', 'read-only', '-C', temporary, 'exec',
                   '--skip-git-repo-check', '--json', '--ephemeral', '--ignore-user-config',
                   '--output-schema', str(schema), '--output-last-message', str(output)]
        if configuration['model'] != 'default':
            command.extend(('--model', configuration['model']))
        if configuration.get('reasoning_effort'):
            command.extend(('-c', 'model_reasoning_effort=' + json.dumps(configuration['reasoning_effort'])))
        command.append('-')
        prompt = ('Perform the requested editorial review using the packet below. '
                  'The packet contains the complete permitted text and rules. '
                  'Return JSON findings directly, with exact offsets into the source field.\n\n')
        try:
            result = subprocess.run(command, input=prompt+packet, text=True, capture_output=True,
                                    timeout=configuration.get('timeout_seconds', 240))
        except subprocess.TimeoutExpired as exc:
            raise ValueError('Codex session timed out') from exc
        if result.returncode or not output.is_file():
            raise ValueError('Codex failed to produce a structured editorial reply')
        for line in result.stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get('item', {}).get('type') in ('command_execution', 'mcp_tool_call', 'web_search', 'file_change'):
                raise ValueError('Codex used a tool outside the packet-only editorial assignment')
        findings = json.loads(output.read_text(encoding='utf-8')).get('findings')
        if not isinstance(findings, list):
            raise ValueError('Codex reply did not contain a findings array')
        return findings


def run_study(manifest_path, packet_dir, output_path):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    configuration = manifest['configuration']
    if manifest.get('study_version') != 1 or configuration.get('host') != 'codex':
        raise ValueError('the live runner supports a frozen Codex study; use --results for other hosts')
    if document_hash(configuration) != manifest['configuration_sha256']:
        raise ValueError('frozen study configuration changed')
    binary = shutil.which('codex')
    if not binary:
        raise ValueError('Codex CLI is required to run the study')
    results = []
    completed = set()
    if output_path.exists():
        existing = json.loads(output_path.read_text(encoding='utf-8'))
        if existing.get('manifest') != manifest:
            raise ValueError('existing results belong to another frozen study')
        results = existing['results']
        completed = {(row['case_id'], row['variant'], row['repeat_index']) for row in results}

    def save():
        with tempfile.NamedTemporaryFile(dir=output_path.parent, delete=False) as stream:
            temporary = Path(stream.name)
        try:
            write_json(temporary, {'schema_version': 1, 'manifest': manifest, 'results': results})
            temporary.replace(output_path)
        finally:
            temporary.unlink(missing_ok=True)

    frozen = {}
    for case in manifest['expected_case_ids']:
        for variant in manifest['variants']:
            ref = (packet_dir / variant / (case + '.json')).resolve()
            if not ref.is_relative_to(packet_dir.resolve()):
                raise ValueError('study packet escapes its directory')
            packet = ref.read_bytes()
            digest = sha(packet)
            if digest != manifest['packet_hashes'][case][variant]:
                raise ValueError('study packet differs from its frozen hash')
            frozen[case, variant] = (packet.decode('utf-8'), digest)
    for (case, variant), (packet, digest) in frozen.items():
        for repeat in range(1, manifest['repeat_count'] + 1):
            if (case, variant, repeat) in completed:
                continue
            result = {'case_id': case, 'variant': variant, 'repeat_index': repeat,
                      'attempt_id': secrets.token_hex(12), 'packet_sha256': digest,
                      'source_sha256': manifest['source_hashes'][case],
                      'configuration_sha256': manifest['configuration_sha256']}
            try:
                result.update(status='complete', findings=codex_findings(binary, packet, configuration))
            except (ValueError, OSError, TypeError) as exc:
                result.update(status='failed', error=str(exc))
            results.append(result)
            save()
            print(f'{len(results)} recorded attempts', file=sys.stderr, flush=True)
    return {'results_file': str(output_path), 'attempts': len(results),
            'failed': sum(row['status'] == 'failed' for row in results)}


def review_id(manifest, result):
    return 'review-' + document_hash([manifest['run_id'], result['case_id'], result['variant'],
                                      result['repeat_index'], result['attempt_id'], result['findings']])[:20]


def blind_review(path, manifest, selected, mapping, cases):
    outputs = []
    for result in selected.values():
        if result['status'] == 'complete':
            case = cases[mapping[result['case_id']]]
            outputs.append({'review_id': review_id(manifest, result), 'source': case['source'],
                            'findings': [{key: finding[key] for key in FINDING_FIELDS if key in finding}
                                         for finding in result['findings']]})
    outputs.sort(key=lambda item: item['review_id'])
    write_json(path, {'schema_version': 1, 'outputs': outputs,
                      'rubric': {'useful_repair': 'Would you use the proposed repairs?',
                                 'voice_preserved': 'Do the proposals preserve deliberate choices and voice?'}})


def author_judgments(path, manifest, selected):
    document = json.loads(path.read_text(encoding='utf-8'))
    evaluator = document.get('evaluator_id')
    if not evaluator or not isinstance(document.get('ratings'), list):
        raise ValueError('author scores require evaluator_id and ratings')
    outputs = {review_id(manifest, row): row for row in selected.values() if row['status'] == 'complete'}
    for rating in document['ratings']:
        result = outputs.get(rating.get('review_id'))
        if (not result or rating.get('dimension') not in DIMENSIONS or
                type(rating.get('accepted')) is not bool or not rating.get('reason')):
            raise ValueError('author rating needs a current review_id, rubric dimension, boolean, and rationale')
        kept = rating.get('kept_findings')
        if kept is not None and (rating['dimension'] != 'useful_repair' or not isinstance(kept, list)
                                 or any(type(i) is not int or not 1 <= i <= len(result['findings']) for i in kept)
                                 or len(set(kept)) != len(kept)):
            raise ValueError('kept_findings must list unique one-based finding numbers for useful_repair')
        yield {'run_id': manifest['run_id'], 'evaluator_role': 'author', 'evaluator_id': evaluator,
               'rubric_version': 'chapter-pilot-v1', 'dimension': rating['dimension'],
               'accepted': rating['accepted'], 'reason': rating['reason'],
               'kept_findings': kept, **{name: result[name] for name in
                                         ('case_id', 'variant', 'repeat_index', 'attempt_id')}}
