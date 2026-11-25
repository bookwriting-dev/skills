"""Chapter-projected review inputs.

A saved review used to hash whole shared files (`promises.yaml`, `editorial-decisions.json`,
`plan.md`, `Wiki/Research/`, the global knowledge ledger) into every chapter's sidecar, so
drafting chapter N turned chapters 1..N-1 STALE. A projection input records a digest of only
the slice of a shared record that can change what a review of one chapter concluded:

* promises:  entries introduced at or before the chapter, with payoffs after it hidden
* events:    knowledge/relationship events sourced from this or an earlier chapter
* decisions: editorial decisions whose scope can apply to this book and chapter
* plan:      the book-level plan's header and this chapter's own section
* research:  files and registry entries the chapter's evidence record or plan names

Everything is read through the committed-ledger store, so a ledger committed as a generation
(which never touches its logical path on disk) invalidates exactly the reviews it affects.
Whenever a record cannot be parsed the projection falls back to a whole-file digest: slicing
is an optimization and must never hide a change.
"""
import hashlib
import json
import re

from state_core import digest, ledger_store_module, path_at

PROJECTION = 'projection'
CANON_DIRS = ('Wiki/Characters', 'Wiki/World', 'Wiki/Locations', 'Wiki/Organizations', 'Wiki/Systems', 'Wiki/Events')
NON_LIFECYCLE_STATUSES = {'abandoned', 'deferred', 'waived', 'cut'}


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8')).hexdigest()


def first_int(value):
    match = re.search(r'\d+', str(value)) if value is not None else None
    return int(match.group(0)) if match else None


def _ledger_bytes(root, logical):
    try:
        return ledger_store_module().load_ledger_bytes(root, logical)
    except (OSError, ValueError):
        return None


def _promise_entries(raw):
    try:
        import yaml
        data = yaml.safe_load(raw.decode('utf-8')) or {}
    except Exception:
        return None
    if not data:
        return []
    entries = data.get('promises', None) if isinstance(data, dict) else None
    if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
        return None
    return entries


def promises_view(entries, chapter):
    view = []
    for entry in entries:
        introduced = first_int(entry.get('introduced_ch'))
        if introduced is not None and introduced > chapter:
            continue
        entry = dict(entry)
        paid = first_int(entry.get('paid_in_ch'))
        later = paid is not None and paid > chapter
        if later:
            entry.pop('paid_in_ch', None)
            entry.pop('paid_how', None)
        status = str(entry.pop('status', '')).strip().lower()
        if status in NON_LIFECYCLE_STATUSES:
            entry['status'] = status
        elif paid is not None and not later:
            entry['status'] = 'resolved'
        # Any other lifecycle status (open/planted/paid...) is derived from the payoff fields above.
        view.append(entry)
    return sorted(view, key=lambda entry: json.dumps(entry, sort_keys=True, default=str))


def _promises(root, item):
    raw = _ledger_bytes(root, item['path'])
    if raw is None:
        return _hash([])
    entries = _promise_entries(raw)
    if entries is None:
        return hashlib.sha256(raw).hexdigest()
    return _hash(promises_view(entries, item['chapter_number']))


def _events(root, item):
    raw = _ledger_bytes(root, item['path'])
    if raw is None:
        return _hash([])
    try:
        events = json.loads(raw.decode('utf-8')).get('events', [])
    except (ValueError, AttributeError):
        return hashlib.sha256(raw).hexdigest()
    sources = set(item['sources'])
    kept = [event for event in events if not isinstance(event, dict) or not event.get('source')
            or event['source'] in sources]
    return _hash(sorted(kept, key=lambda event: json.dumps(event, sort_keys=True, default=str)))


def decision_relevant(decision, book_ids, chapter_ids, chapter_path):
    from state_ledgers import scope_dimensions
    dims = scope_dimensions(decision.get('scope'))
    if dims is None:
        return True
    if 'book_id' in dims and dims['book_id'] not in book_ids:
        return False
    if 'chapter_id' in dims and dims['chapter_id'] not in chapter_ids:
        return False
    source = decision.get('source')
    return not (isinstance(source, str) and source.startswith('Chapters/') and source != chapter_path)


def _decisions(root, item):
    path = path_at(root, item['path'])
    if not path.is_file():
        return _hash([])
    try:
        decisions = json.loads(path.read_text(encoding='utf-8')).get('decisions', [])
    except (ValueError, AttributeError):
        return digest(path)
    kept = [d for d in decisions if not isinstance(d, dict)
            or decision_relevant(d, item['book_ids'], item['chapter_ids'], item['chapter_path'])]
    return _hash(sorted(kept, key=lambda d: json.dumps(d, sort_keys=True, default=str)))


def plan_section(text, chapter):
    heading = re.compile(r'^#{1,3}[ \t]+Chapter[ \t]+0*(\d+)(?=[ \t:\n]|$)[^\n]*$', re.M | re.I)
    matches = list(heading.finditer(text))
    header = text[:matches[0].start()] if matches else text
    section = None
    for index, match in enumerate(matches):
        if int(match.group(1)) == chapter:
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            section = text[match.start():end]
    return header, section


def _plan(root, item):
    path = path_at(root, item['path'])
    if not path.is_file():
        return _hash(None)
    header, section = plan_section(path.read_text(encoding='utf-8'), item['chapter_number'])
    return _hash({'header': header, 'section': section})


def _research(root, item):
    directory = path_at(root, item['path'])
    record = path_at(root, item['record_path'])
    if not directory.is_dir():
        return _hash(None)
    files = sorted(f for f in directory.rglob('*') if f.is_file())
    if not record.is_file():
        # Without the chapter's evidence record nothing says which sources it used.
        return _hash({f.relative_to(directory).as_posix(): digest(f) for f in files})
    needle = record.read_text(encoding='utf-8')
    plan = path_at(root, item['plan_path'])
    if plan.is_file():
        needle += json.dumps(plan_section(plan.read_text(encoding='utf-8'), item['chapter_number']))
    parts = {}
    for file in files:
        rel = file.relative_to(directory).as_posix()
        if file.name in ('sources.yaml', 'sources.yml'):
            raw = file.read_bytes()
            try:
                import yaml
                data = yaml.safe_load(raw.decode('utf-8')) or {}
                entries = data['sources']
                if not isinstance(entries, list):
                    raise ValueError('sources')
                parts[rel] = [e for e in entries if isinstance(e, dict) and str(e.get('id', '')) and str(e['id']) in needle]
            except Exception:
                parts[rel] = hashlib.sha256(raw).hexdigest()
        elif rel in needle or file.name in needle:
            parts[rel] = digest(file)
    return _hash(parts)


PROJECTORS = {'promises': _promises, 'events': _events, 'decisions': _decisions, 'plan': _plan, 'research': _research}


def make(root, kind, path, **params):
    item = {'path': path, 'kind': PROJECTION, 'projection': kind, **params}
    item['sha256'] = PROJECTORS[kind](root, item)
    return item


def current_input(root, item):
    """Re-evaluate one recorded review input: a plain file/directory record or a projection."""
    if item.get('kind') == PROJECTION:
        return dict(item, sha256=PROJECTORS[item['projection']](root, item))
    from state_core import evidence
    return evidence(root, [item['path']])[0]


def current_inputs(root, items):
    return [current_input(root, item) for item in items]


def canon_files(root, chapter_text):
    """Character and world files whose name, alias, or file stem the chapter mentions."""
    found = []
    for folder in CANON_DIRS:
        base = root / folder
        if not base.is_dir():
            continue
        for file in sorted(base.rglob('*.md')):
            raw = file.read_text(encoding='utf-8', errors='replace')
            terms = {file.stem.replace('_', ' ')}
            named = re.search(r'^(?:name|term):[ \t]*["\']?([^"\'\n]+)', raw, re.M)
            if named:
                terms.add(named.group(1).strip())
            for block in re.finditer(r'^(?:also_known_as|aliases):[ \t]*\n((?:[ \t]*-[ \t]*[^\n]+\n?)+)', raw, re.M):
                terms.update(a.strip(' \t"\'') for a in re.findall(r'-[ \t]*([^\n]+)', block.group(1)))
            if folder == 'Wiki/Characters':
                terms.update(t.split()[0] for t in list(terms) if len(t.split()[0]) >= 4)
            if any(len(t) >= 3 and re.search(r'(?<!\w)' + re.escape(t) + r'(?!\w)', chapter_text) for t in terms):
                found.append(file.relative_to(root).as_posix())
    return found
