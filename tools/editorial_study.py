"""Prepare matched editorial runs and bind blind author reviews to recorded outputs."""
import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request


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


def _validate_findings_payload(findings):
    if not isinstance(findings, list):
        raise ValueError('reply did not contain a findings array')
    for item in findings:
        if not isinstance(item, dict):
            raise ValueError('each finding must be an object')
        for field in FINDING_FIELDS:
            if field not in item:
                raise ValueError(f'finding missing required field: {field}')
        if type(item['start']) is not int or type(item['end']) is not int:
            raise ValueError('finding start and end must be integers')
    return findings


def _parse_json_response(raw_text):
    text = raw_text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text, flags=re.S).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', text, flags=re.S)
        if not m:
            raise ValueError('model reply did not contain valid JSON')
        return json.loads(m.group(0))


def openai_compatible_findings(packet, configuration):
    endpoint = configuration.get('endpoint', 'http://localhost:11434/v1/chat/completions')
    model = configuration['model']
    headers = {'Content-Type': 'application/json'}
    api_key_env = configuration.get('api_key_env')
    if api_key_env:
        token = os.environ.get(api_key_env)
        if not token:
            raise ValueError(f'missing environment variable for API key: {api_key_env}')
        headers['Authorization'] = f'Bearer {token}'
    prompt = ('Perform the requested editorial review using the packet below. '
              'Return ONLY a JSON object matching {"findings":[{"start":int,"end":int,'
              '"quote":str,"replacement":str,"reason":str,"category":str}]} '
              'with exact zero-based Unicode code-point offsets into the source field.\n\n' + packet)
    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': 'You are a literary editor returning strict JSON findings.'},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': configuration.get('temperature', 0),
        'response_format': {
            'type': 'json_schema',
            'json_schema': {'name': 'editorial_findings', 'strict': True, 'schema': RESULT_SCHEMA},
        },
    }
    req = urllib.request.Request(endpoint, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
    timeout = configuration.get('timeout_seconds', 240)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise ValueError(f'OpenAI-compatible endpoint failed: {exc}') from exc
    choices = body.get('choices') or []
    if not choices:
        raise ValueError('OpenAI-compatible response contained no choices')
    content = choices[0].get('message', {}).get('content', '')
    parsed = _parse_json_response(content)
    return _validate_findings_payload(parsed.get('findings'))


def cli_findings(host, binary, packet, configuration):
    prompt = ('Perform the requested editorial review using the packet below. '
              'The packet contains the complete permitted text and rules. '
              'Return ONLY a JSON object with a "findings" array matching '
              '{"findings":[{"start":int,"end":int,"quote":str,"replacement":str,"reason":str,"category":str}]}.\n\n' + packet)
    if host == 'claude':
        command = [binary, '-p', '--output-format', 'text', '--tools', '']
        if configuration['model'] != 'default':
            command.extend(('--model', configuration['model']))
    elif host == 'gemini':
        command = [binary, '-p', '-', '--output-format', 'text']
        if configuration['model'] != 'default':
            command.extend(('-m', configuration['model']))
    else:
        raise ValueError(f'unsupported CLI host: {host}')
    try:
        result = subprocess.run(command, input=prompt, text=True, capture_output=True,
                                timeout=configuration.get('timeout_seconds', 240))
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f'{host} session timed out') from exc
    if result.returncode:
        raise ValueError(f'{host} CLI failed to produce an editorial reply')
    parsed = _parse_json_response(result.stdout)
    return _validate_findings_payload(parsed.get('findings'))


def dispatch_findings(packet, configuration):
    host = configuration.get('host')
    if host == 'codex':
        binary = shutil.which('codex')
        if not binary:
            raise ValueError('Codex CLI is required to run the study')
        return codex_findings(binary, packet, configuration)
    if host in ('openai_compatible', 'ollama'):
        return openai_compatible_findings(packet, configuration)
    if host in ('claude', 'gemini'):
        binary = shutil.which(host)
        if not binary:
            raise ValueError(f'{host} CLI is required to run the study')
        return cli_findings(host, binary, packet, configuration)
    raise ValueError(f'unsupported study host: {host}')


def run_study(manifest_path, packet_dir, output_path):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    configuration = manifest['configuration']
    supported_hosts = ('codex', 'openai_compatible', 'ollama', 'claude', 'gemini')
    if manifest.get('study_version') != 1 or configuration.get('host') not in supported_hosts:
        raise ValueError('unsupported frozen study version or host; use --results for external hosts')
    if document_hash(configuration) != manifest['configuration_sha256']:
        raise ValueError('frozen study configuration changed')
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
                result.update(status='complete', findings=dispatch_findings(packet, configuration))
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


def blind_review_data(manifest, selected, mapping, cases):
    outputs = []
    for result in selected.values():
        if result['status'] == 'complete':
            case = cases[mapping[result['case_id']]]
            outputs.append({'review_id': review_id(manifest, result), 'source': case['source'],
                            'findings': [{key: finding[key] for key in FINDING_FIELDS if key in finding}
                                         for finding in result['findings']]})
    outputs.sort(key=lambda item: item['review_id'])
    return {'schema_version': 1, 'outputs': outputs,
            'rubric': {'useful_repair': 'Would you use the proposed repairs?',
                       'voice_preserved': 'Do the proposals preserve deliberate choices and voice?'}}


def blind_review(path, manifest, selected, mapping, cases):
    data = blind_review_data(manifest, selected, mapping, cases)
    write_json(path, data)
    return data


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Storycraft Blind Editorial Review</title>
<style>
  :root { --bg:#f7f5f0; --card:#fff; --ink:#1f2328; --muted:#57606a; --border:#d8d3c8; --accent:#235789; --hit:#fff3bf; --hit-border:#e6a700; }
  body { margin:0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:var(--bg); color:var(--ink); line-height:1.55; }
  header { position:sticky; top:0; z-index:10; background:var(--card); border-bottom:1px solid var(--border); padding:12px 24px; display:flex; gap:16px; align-items:center; flex-wrap:wrap; }
  header h1 { font-size:1.05rem; margin:0; margin-right:auto; }
  .controls { display:flex; gap:12px; align-items:center; flex-wrap:wrap; }
  input[type="text"], textarea { border:1px solid var(--border); border-radius:6px; padding:6px 10px; font:inherit; }
  button { background:var(--accent); color:#fff; border:none; border-radius:6px; padding:8px 14px; font:inherit; font-weight:600; cursor:pointer; }
  button:disabled { opacity:0.5; cursor:not-allowed; }
  main { max-width:980px; margin:24px auto; padding:0 16px 64px; display:grid; gap:20px; }
  .card { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:20px; box-shadow:0 1px 2px rgba(0,0,0,0.04); }
  .card-head { display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; border-bottom:1px solid var(--border); padding-bottom:8px; }
  .badge { font-family:ui-monospace, SFMono-Regular, monospace; font-size:0.82rem; background:#eef2f6; padding:2px 8px; border-radius:4px; }
  .prose { background:#fbfaf7; border:1px solid var(--border); border-radius:8px; padding:14px 16px; white-space:pre-wrap; font-family: Georgia, "Times New Roman", serif; font-size:1rem; }
  mark.span-hit { background:var(--hit); border-bottom:2px solid var(--hit-border); padding:0 2px; border-radius:2px; }
  .idx { font-family:ui-monospace, monospace; font-size:0.75rem; font-weight:700; color:#7c4a03; margin-right:2px; }
  .findings { margin:14px 0; display:grid; gap:10px; }
  .finding { border:1px solid var(--border); border-radius:8px; padding:10px 12px; background:#fff; }
  .finding label { display:flex; gap:10px; align-items:flex-start; cursor:pointer; }
  .diff { font-family:ui-monospace, monospace; font-size:0.88rem; margin-top:4px; }
  .del { background:#ffe3e3; padding:1px 4px; border-radius:3px; }
  .add { background:#d3f9d8; padding:1px 4px; border-radius:3px; }
  .rubric { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:12px; margin-top:14px; padding-top:12px; border-top:1px solid var(--border); }
  .dim { border:1px solid var(--border); border-radius:8px; padding:10px 12px; background:#fafafa; display:grid; gap:8px; }
  .dim-title { font-weight:600; font-size:0.92rem; }
  .radio-row { display:flex; gap:14px; }
  .status { font-size:0.88rem; color:var(--muted); }
</style>
</head>
<body>
<header>
  <h1>Storycraft Blind Editorial Scorecard</h1>
  <div class="controls">
    <label>Evaluator ID: <input id="evaluator" type="text" placeholder="author-id"></label>
    <span id="progress" class="status">0 / 0 complete</span>
    <button id="download" type="button">Download ratings.json</button>
  </div>
</header>
<main id="app"></main>
<script id="review-payload" type="application/json">__PAYLOAD__</script>
<script>
(function(){
  const payload = JSON.parse(document.getElementById('review-payload').textContent);
  const storeKey = 'storycraft-blind-' + payload.outputs.map(o => o.review_id).join(',').slice(0, 64);
  const saved = JSON.parse(localStorage.getItem(storeKey) || '{}');
  const state = saved.items || {};
  const evalInput = document.getElementById('evaluator');
  evalInput.value = saved.evaluator_id || 'author';

  function persist() {
    localStorage.setItem(storeKey, JSON.stringify({ evaluator_id: evalInput.value.trim(), items: state }));
    updateProgress();
  }
  evalInput.addEventListener('input', persist);

  function renderHighlighted(source, findings) {
    const chars = Array.from(source);
    const marks = findings.map((f, idx) => ({
      idx: idx + 1,
      start: typeof f.start === 'number' ? f.start : -1,
      end: typeof f.end === 'number' ? f.end : -1,
    })).filter(m => m.start >= 0 && m.end > m.start && m.end <= chars.length)
      .sort((a, b) => a.start - b.start);
    const frag = document.createDocumentFragment();
    let cursor = 0;
    for (const m of marks) {
      if (m.start < cursor) continue;
      if (m.start > cursor) frag.appendChild(document.createTextNode(chars.slice(cursor, m.start).join('')));
      const mk = document.createElement('mark');
      mk.className = 'span-hit';
      const badge = document.createElement('span');
      badge.className = 'idx';
      badge.textContent = '[' + m.idx + ']';
      mk.appendChild(badge);
      mk.appendChild(document.createTextNode(chars.slice(m.start, m.end).join('')));
      frag.appendChild(mk);
      cursor = m.end;
    }
    if (cursor < chars.length) frag.appendChild(document.createTextNode(chars.slice(cursor).join('')));
    return frag;
  }

  function itemState(id) {
    if (!state[id]) {
      state[id] = { kept: [], useful_repair: { accepted: null, reason: '' }, voice_preserved: { accepted: null, reason: '' } };
    }
    return state[id];
  }

  function updateProgress() {
    const total = payload.outputs.length;
    const done = payload.outputs.filter(o => {
      const s = itemState(o.review_id);
      return typeof s.useful_repair.accepted === 'boolean' && s.useful_repair.reason.trim() &&
             typeof s.voice_preserved.accepted === 'boolean' && s.voice_preserved.reason.trim();
    }).length;
    document.getElementById('progress').textContent = done + ' / ' + total + ' outputs rated';
  }

  const app = document.getElementById('app');
  payload.outputs.forEach((out, cardIdx) => {
    const st = itemState(out.review_id);
    const card = document.createElement('section');
    card.className = 'card';
    const head = document.createElement('div');
    head.className = 'card-head';
    head.innerHTML = '<strong>Output ' + (cardIdx + 1) + ' of ' + payload.outputs.length + '</strong><span class="badge">' + out.review_id + '</span>';
    card.appendChild(head);

    const prose = document.createElement('div');
    prose.className = 'prose';
    prose.appendChild(renderHighlighted(out.source, out.findings));
    card.appendChild(prose);

    const list = document.createElement('div');
    list.className = 'findings';
    if (!out.findings.length) {
      const empty = document.createElement('div');
      empty.className = 'status';
      empty.textContent = 'No edits proposed for this output.';
      list.appendChild(empty);
    }
    out.findings.forEach((f, fIdx) => {
      const num = fIdx + 1;
      const box = document.createElement('div');
      box.className = 'finding';
      const lbl = document.createElement('label');
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = st.kept.includes(num);
      cb.addEventListener('change', () => {
        if (cb.checked) { if (!st.kept.includes(num)) st.kept.push(num); }
        else { st.kept = st.kept.filter(n => n !== num); }
        st.kept.sort((a, b) => a - b);
        persist();
      });
      const body = document.createElement('div');
      const meta = document.createElement('div');
      meta.innerHTML = '<strong>[' + num + '] ' + (f.category || 'edit') + '</strong> — ';
      meta.appendChild(document.createTextNode(f.reason || ''));
      const diff = document.createElement('div');
      diff.className = 'diff';
      const del = document.createElement('span'); del.className = 'del'; del.textContent = f.quote || '';
      const add = document.createElement('span'); add.className = 'add'; add.textContent = f.replacement || '';
      diff.appendChild(del); diff.appendChild(document.createTextNode(' → ')); diff.appendChild(add);
      body.appendChild(meta); body.appendChild(diff);
      lbl.appendChild(cb); lbl.appendChild(body);
      box.appendChild(lbl);
      list.appendChild(box);
    });
    card.appendChild(list);

    const rubric = document.createElement('div');
    rubric.className = 'rubric';
    ['useful_repair', 'voice_preserved'].forEach(dim => {
      const wrap = document.createElement('div');
      wrap.className = 'dim';
      const title = document.createElement('div');
      title.className = 'dim-title';
      title.textContent = dim + ' — ' + (payload.rubric[dim] || '');
      const row = document.createElement('div');
      row.className = 'radio-row';
      [true, false].forEach(val => {
        const l = document.createElement('label');
        const r = document.createElement('input');
        r.type = 'radio';
        r.name = out.review_id + '-' + dim;
        r.checked = st[dim].accepted === val;
        r.addEventListener('change', () => { st[dim].accepted = val; persist(); });
        l.appendChild(r);
        l.appendChild(document.createTextNode(val ? ' Accept' : ' Reject'));
        row.appendChild(l);
      });
      const reason = document.createElement('input');
      reason.type = 'text';
      reason.placeholder = 'Reason (required)';
      reason.value = st[dim].reason || '';
      reason.addEventListener('input', () => { st[dim].reason = reason.value; persist(); });
      wrap.appendChild(title); wrap.appendChild(row); wrap.appendChild(reason);
      rubric.appendChild(wrap);
    });
    card.appendChild(rubric);
    app.appendChild(card);
  });
  updateProgress();

  document.getElementById('download').addEventListener('click', () => {
    const evaluator_id = evalInput.value.trim() || 'author';
    const ratings = [];
    for (const out of payload.outputs) {
      const s = itemState(out.review_id);
      if (typeof s.useful_repair.accepted !== 'boolean' || !s.useful_repair.reason.trim() ||
          typeof s.voice_preserved.accepted !== 'boolean' || !s.voice_preserved.reason.trim()) {
        alert('Please rate both dimensions and provide a reason for every output before downloading.');
        return;
      }
      ratings.push({
        review_id: out.review_id,
        dimension: 'useful_repair',
        accepted: s.useful_repair.accepted,
        reason: s.useful_repair.reason.trim(),
        kept_findings: s.kept.slice(),
      });
      ratings.push({
        review_id: out.review_id,
        dimension: 'voice_preserved',
        accepted: s.voice_preserved.accepted,
        reason: s.voice_preserved.reason.trim(),
      });
    }
    const blob = new Blob([JSON.stringify({ evaluator_id, ratings }, null, 2) + '\\n'], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'ratings.json';
    a.click();
  });
})();
</script>
</body>
</html>
"""


def blind_review_html(path, review_data):
    payload = json.dumps(review_data, ensure_ascii=False).replace('</', '<\\/')
    path.write_text(_HTML_TEMPLATE.replace('__PAYLOAD__', payload), encoding='utf-8')
    return path


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
