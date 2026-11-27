"""Pre-draft packet compiler, style policy, and psych/checkpoint parsers."""
import argparse
import re
from collections import Counter, defaultdict

from draft_promises import promise_context
from state_core import (
    VERSION, chapter_format_module, digest, document, ledger_store_module, locked,
    manuscript_texts, path_at, project_manifest_module, write,
)
from state_ledgers import (
    continuity_report, knowledge, knowledge_event_state, relationship_state, scope_dimensions,
)

SOMATIC_TOKENS = {
    'jaw', 'breath', 'throat', 'pulse', 'ribs', 'chest', 'knuckles', 'stomach',
    'silence', 'stillness', 'ozone', 'copper', 'bile', 'sternum', 'temples',
    'collarbone', 'exhale', 'inhale', 'swallowed', 'clenched', 'unclenched',
    'tightened', 'shiver', 'tremor', 'heartbeat',
}

STOP_WORDS = {
    'a', 'an', 'and', 'the', 'this', 'that', 'these', 'those', 'there', 'here',
    'it', 'its', 'he', 'she', 'they', 'them', 'his', 'her', 'their', 'him',
    'of', 'to', 'in', 'on', 'at', 'by', 'for', 'with', 'from', 'as', 'is',
    'are', 'was', 'were', 'be', 'been', 'being', 'am', 'do', 'does', 'did',
    'have', 'has', 'had', 'will', 'would', 'could', 'should', 'can', 'may',
    'might', 'must', 'not', 'no', 'nor', 'so', 'if', 'but', 'or', 'then',
    'than', 'when', 'while', 'where', 'what', 'which', 'who', 'whom', 'whose',
    'how', 'why', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other',
    'some', 'such', 'only', 'own', 'same', 'too', 'very', 'just', 'now', 'i',
    'you', 'we', 'us', 'our', 'your', 'my', 'me', 'up', 'out', 'off', 'over',
    'under', 'again', 'once', 'about', 'into', 'through', 'during', 'before',
    'after', 'above', 'below', 'between', 'because', 'until', 'against',
}


def prose_lines(path, scene_break='* * *'):
    """Extract clean prose lines, stripping headings, fences, > callouts, rules, and checkboxes."""
    lines = []
    in_fence = False
    source = path.read_text(encoding='utf-8')
    _, slots = chapter_format_module().metadata(source, scene_break)
    markers = {marker[0] for _, marker in slots if marker}
    for number, raw in enumerate(source.splitlines(), 1):
        line = raw.strip()
        if not line or number in markers:
            continue
        if line.startswith('```'):
            in_fence = not in_fence
            continue
        if in_fence or line.startswith('#') or line.startswith('>') or line in ('---', '***', '* * *', scene_break):
            continue
        if re.match(r'^[-*] \[', line):
            continue
        lines.append(line)
    return lines


def parse_checkpoints(path, chapter_num, *, book=None, book_id=None, unscoped_ok=True, skipped=None):
    """Return active relationship_checkpoints for chapter_num from a character Markdown file."""
    text = path.read_text(encoding='utf-8')
    m = re.search(r'^##\s+relationship_checkpoints\b(.*?)(?=^##\s+|\Z)', text, re.M | re.S)
    if not m:
        return []
    char_name = path.stem.replace('_', ' ')
    fm_name = re.search(r'^name:\s*["\']?([^"\'\n]+)["\']?', text, re.M)
    if fm_name:
        char_name = fm_name.group(1).strip()
    active = []
    block = m.group(1)
    for sub in re.finditer(r'^###\s+([^\n]+)\n(.*?)(?=^###\s+|\Z)', block, re.M | re.S):
        other = sub.group(1).strip()
        entries = []
        current = {}
        fields = []
        for line in sub.group(2).splitlines():
            kv = re.match(r'^\s*[-*]\s*(?:\*\*)?([a-z_]+)(?:\*\*)?:(?:\*\*)?\s*(.+)$', line.strip(), re.I)
            if kv:
                fields.append((kv.group(1).lower(), kv.group(2).strip()))
        for index, (key, value) in enumerate(fields):
            # Scoped entries begin with book, including when appended to an older
            # unscoped entry. A book label inside an unfinished entry belongs to it.
            next_key = fields[index + 1][0] if index + 1 < len(fields) else None
            new_book = (key in ('book', 'book_id') and 'chapter_end' in current and next_key in current)
            if key in current or new_book:
                entries.append(current)
                current = {}
            current[key] = value
        if current:
            entries.append(current)
        declared_books = {(row.get('book') or row.get('book_id')).casefold() for row in entries
                          if row.get('book') or row.get('book_id')}
        first_book_aliases = {'book-1'}
        if unscoped_ok and book_id:
            first_book_aliases.add(book_id.casefold())
        ambiguous_legacy = bool(declared_books - first_book_aliases)
        for entry in entries:
            start_m = re.search(r'\d+', str(entry.get('chapter_start', '1')))
            start = int(start_m.group(0)) if start_m else 1
            end_raw = str(entry.get('chapter_end', '(open)')).strip().lower()
            end_m = re.search(r'\d+', end_raw)
            end = None if ('open' in end_raw or not end_m) else int(end_m.group(0))
            if start > chapter_num or (end is not None and chapter_num > end):
                continue
            entry_book = entry.get('book') or entry.get('book_id')
            if book is not None:
                if entry_book:
                    accepted_books = {label.casefold() for label in (book, book_id) if label}
                    if entry_book.casefold() not in accepted_books:
                        continue
                elif ambiguous_legacy or not unscoped_ok:
                    if skipped is not None:
                        skipped.append({
                            'character': char_name,
                            'other_character': other,
                            'chapter_start': start,
                            'reason': ('ambiguous book for unscoped checkpoint in this pair; supply book or book_id'
                                       if ambiguous_legacy else 'unscoped checkpoint skipped for ' + str(book)),
                            'source': path,
                        })
                    continue
            item = {
                'character': char_name, 'other_character': other, 'link_type': entry.get('link_type', ''),
                'chapter_start': start, 'chapter_end': 'open' if end is None else end,
                'notes': entry.get('notes', ''), 'source': path,
            }
            if entry_book:
                item['book'] = entry_book
            if 'turn_scene' in entry:
                value = entry['turn_scene'].strip()
                match = re.fullmatch(r'(?:scene[- ]?)?([1-9]\d*)', value, re.I)
                item['turn_scene'] = int(match[1]) if match else value.casefold()
            active.append(item)
    return active


def relationship_checkpoints_at_scene(checkpoints, chapter, scene_number):
    """A turn changes the planned stance after the scene that earns it."""
    incoming = {}
    turns = []
    unresolved = []
    for point in checkpoints:
        start = point['chapter_start']
        turn = point.get('turn_scene')
        if start == chapter:
            if turn == scene_number:
                turns.append(point)
                continue
            if isinstance(turn, int) and turn > scene_number:
                continue
            if (turn is None and start > 1) or (isinstance(turn, str) and turn != 'opening'):
                unresolved.append(point)
                continue
        pair = (point['character'], point['other_character'])
        order = (start, turn if isinstance(turn, int) else 0)
        if pair not in incoming or incoming[pair][0] < order:
            incoming[pair] = (order, point)
    return [point for _, point in incoming.values()], turns, unresolved


def _section_map(text, level=2):
    hashes = '#' * level
    parts = re.split(rf'^{hashes}[ \t]+([^\n]+)\n', text, flags=re.M)
    return {name.strip().lower(): body for name, body in zip(parts[1::2], parts[2::2])}


def _labeled_block(section, label):
    match = re.search(
        rf'^[ \t]*(?:[-*][ \t]+)?\*\*{re.escape(label)}:\*\*[ \t]*(.*?)(?=\n[ \t]*(?:[-*][ \t]+)?\*\*[A-Za-z][^*\n]*:\*\*|\n---|\Z)',
        section, re.M | re.S | re.I,
    )
    return re.sub(r'\s+', ' ', match.group(1)).strip() if match else ''


def parse_psych(path):
    """Extract full psychological context (states, beat costs, unsaid lines, gaps, bottom line)."""
    text = path.read_text(encoding='utf-8')
    unsaid = [m.group(1).strip() for m in re.finditer(
        r'^\s*[-*]\s*(?:\*\*)?What they won[\'\u2019]t say(?:\*\*)?:(?:\*\*)?\s*(.+)$', text, re.M | re.I
    )]
    gaps = []
    gap_sec = re.search(
        r'^#{2,4}\s+Show[-‐‑\s]+Don[\'\u2019]t[-‐‑\s]+Tell Gaps\b(.*?)(?=^#{2,4}\s+|^---\s*$|\Z)',
        text, re.M | re.S | re.I,
    )
    if gap_sec:
        for line in gap_sec.group(1).splitlines():
            line = line.strip()
            if not line.startswith('|') or re.match(r'^\|\s*[-:]+\s*\|', line):
                continue
            cells = [c.strip() for c in line.strip('|').split('|')]
            if len(cells) >= 3 and cells[0].lower() != 'beat':
                gaps.append({'beat': cells[0], 'reporting_draft': cells[1], 'instead': cells[2]})

    sections = _section_map(text, level=2)
    start_sec = sections.get('start state', '')
    end_sec = sections.get('end state', '')
    start_state = {k: v for k, v in (
        ('surface_affect', _labeled_block(start_sec, 'Surface affect')),
        ('underneath', _labeled_block(start_sec, 'Underneath')),
        ('expression_channel', _labeled_block(start_sec, 'Expression channel')),
    ) if v}
    end_state = {k: v for k, v in (
        ('surface_affect', _labeled_block(end_sec, 'Surface affect')),
        ('underneath', _labeled_block(end_sec, 'Underneath')),
        ('expression_channel', _labeled_block(end_sec, 'Expression channel')),
    ) if v}

    beat_costs = []
    beat_sec = sections.get('beat-by-beat interior cost', '')
    for sub in re.finditer(r'^###[ \t]+([^\n]+)\n(.*?)(?=^###[ \t]+|^---|\Z)', beat_sec, re.M | re.S):
        body = sub.group(2)
        entry = {'beat': sub.group(1).strip()}
        for key, label in (('interior_cost', 'Interior cost'),
                           ('expression_channel', 'Expression channel'),
                           ('body_expression', 'Body expression')):
            val = _labeled_block(body, label)
            if val:
                entry[key] = val
        wont = re.search(r'^\s*[-*]\s*(?:\*\*)?What they won[\'\u2019]t say(?:\*\*)?:(?:\*\*)?\s*(.+)$', body, re.M | re.I)
        if wont:
            entry['what_they_wont_say'] = wont.group(1).strip()
        beat_costs.append(entry)

    bottom_line = re.sub(r'\n?---\s*$', '', sections.get('bottom line', '')).strip()
    return {
        'what_they_wont_say': unsaid,
        'show_dont_tell_gaps': gaps,
        'start_state': start_state,
        'beat_interior_costs': beat_costs,
        'end_state': end_state,
        'bottom_line': bottom_line,
    }


def decision_applies(decision, book_ids, chapter_ids, pov, *, chapter_path=None):
    """Resolve documented legacy scopes and explicit intersection scopes (including passage scope)."""
    required = scope_dimensions(decision.get('scope'))
    if required is None:
        return False
    if 'passage_id' in required:
        if not chapter_path or decision.get('source') != chapter_path:
            return False
    context = {'book_id': book_ids, 'chapter_id': chapter_ids, 'pov_id': (pov,)}
    return all(value in context.get(key, ()) for key, value in required.items() if key != 'passage_id')


REGISTER_PRESETS = {
    'tight-thriller': {
        'max_per_chapter': 3,
        'em_dash': 'Dialogue/thought interruption only',
        'fragments': 'Dialogue and interrupted thoughts only',
        'tricolon': 'Avoid stylistic triples',
        'clock_mode': 'digits',
    },
    'lyrical-literary': {
        'max_per_chapter': None,
        'em_dash': 'Allowed with restraint',
        'fragments': 'Allowed for deliberate cadence',
        'tricolon': 'Allowed when rhythmic',
        'clock_mode': 'words',
    },
    'historical-period': {
        'max_per_chapter': 8,
        'em_dash': 'Allowed in narration and dialogue',
        'fragments': 'Minimal; dialogue only',
        'tricolon': 'Allowed in period rhetoric',
        'clock_mode': 'words',
    },
    'comic-ironic': {
        'max_per_chapter': 10,
        'em_dash': 'Allowed',
        'fragments': 'Allowed for comedic timing',
        'tricolon': 'Allowed for setup-setup-punch',
        'clock_mode': 'words',
    },
    'omniscient-classic': {
        'max_per_chapter': 10,
        'em_dash': 'Allowed',
        'fragments': 'Avoid in narrative exposition',
        'tricolon': 'Allowed',
        'clock_mode': 'words',
    },
}


def style_policy(root, args):
    resolver = project_manifest_module()
    book = resolver.find_book(resolver.load(root), args.book) or {}
    names = ('Wiki/Style/review_guide.md', 'Wiki/Style/Review Guide.md')
    if book.get('review_authority'):
        names = (book['review_authority'],)
    choices = [name for name in names if path_at(root, name).is_file()]
    hashes = {name: digest(path_at(root, name)) for name in choices}
    if len(set(hashes.values())) > 1:
        raise ValueError('conflicting review guides: ' + ', '.join(choices))
    if not choices and book.get('review_authority'):
        raise ValueError('declared review guide is missing: ' + names[0])
    guide = path_at(root, choices[0]).read_text(encoding='utf-8') if choices else ''
    sections = re.split(r'^##[ \t]+([^\n]+)\n', guide, flags=re.M)
    sections = dict(zip((name.strip().lower() for name in sections[1::2]), sections[2::2]))

    style_auth = resolver.resolve_style_guide(root, args.book)
    style_text = ''
    if style_auth.get('status') == 'RESOLVED':
        sp = path_at(root, style_auth['path'])
        if sp.is_file():
            style_text = sp.read_text(encoding='utf-8')

    preset = None
    for source in (guide, style_text):
        pm = re.search(r'^register_preset:[ \t]*["\']?([a-z-]+)["\']?', source, re.M | re.I)
        if pm and pm.group(1).lower() in REGISTER_PRESETS:
            preset = pm.group(1).lower()
            break
    preset_defaults = REGISTER_PRESETS.get(preset or 'tight-thriller', REGISTER_PRESETS['tight-thriller'])

    def fields(section, name):
        return [match.strip() for match in re.findall(
            rf'^[ \t]*[-*][ \t]+(?:\*\*)?{name}(?:\*\*)?:(?:\*\*)?[ \t]*(.+)$',
            sections.get(section, ''), re.M | re.I)]

    def limit(name, default):
        values = fields('simile rule', name)
        if not values:
            return default
        if len(values) == 1:
            value = values[0].strip('"')
            if value.lower() == 'unlimited':
                return None
            if re.fullmatch(r'[0-9]+', value):
                return int(value)
        raise ValueError(f'{name} in the review guide must be one nonnegative integer or unlimited')

    chapter_limit = limit('max_per_chapter', preset_defaults['max_per_chapter'])
    punctuation = {key: value[-1] for key in ('em_dash', 'fragments')
                   if (value := fields('punctuation', key)) and not value[-1].startswith('[')}
    if preset:
        punctuation.setdefault('em_dash', preset_defaults['em_dash'])
        punctuation.setdefault('fragments', preset_defaults['fragments'])
    clock_vals = fields('diction and clock time', 'clock_mode')
    clock_mode = (clock_vals[-1].strip('"` ').lower()
                  if clock_vals and clock_vals[-1].strip('"` ').lower() in ('digits', 'words')
                  else preset_defaults['clock_mode'])
    policy = {
        'register_preset': preset,
        'review_guide': choices[0] if choices else None,
        'inputs': list(names),
        'clock_mode': clock_mode,
        'tricolon': preset_defaults['tricolon'],
        'simile': {'max_per_chapter': chapter_limit, 'max_per_paragraph': limit('max_per_paragraph', 1),
                   'keep_examples': [value for value in fields('simile rule', 'keep_example')
                                     if not value.startswith('[')]},
        'punctuation': punctuation,
    }
    if getattr(args, 'simile_count', None) is not None:
        if args.simile_count < 0:
            raise ValueError('simile count must be nonnegative')
        policy['chapter_simile_budget_exceeded'] = chapter_limit is not None and args.simile_count > chapter_limit
    return policy


def parse_theme(root):
    p = root / 'Wiki' / 'Story' / 'theme.md'
    if not p.is_file():
        return None
    text = p.read_text(encoding='utf-8')
    questions = dict(re.findall(r'^(thematic_question|central_question):[ \t]*(.+)$', text, re.M))
    question = (questions.get('thematic_question') or questions.get('central_question') or '').strip()
    if len(question) >= 2 and question[0] in "'\"" and question[-1] == question[0]:
        question = question[1:-1].replace("''", "'") if question[0] == "'" else question[1:-1]
    motifs = []
    motif_sec = _section_map(text, level=2).get('motifs', '')
    for sub in re.finditer(r'^###[ \t]+([^\n]+)\n(.*?)(?=^###[ \t]+|\Z)', motif_sec, re.M | re.S):
        entry = {'name': sub.group(1).strip()}
        for k in ('type', 'what_it_is'):
            val = _labeled_block(sub.group(2), k)
            if val:
                entry[k] = val
        motifs.append(entry)
    return {
        'path': 'Wiki/Story/theme.md',
        'sha256': digest(p),
        'thematic_question': question or None,
        'central_question': question or None,  # Legacy packet consumers.
        'motifs': motifs,
    }


def parse_surprise_ledger(root, book, ch_num):
    p = root / 'Wiki' / 'Outline' / book / 'surprise-ledger.md'
    if not p.is_file():
        return None
    text = p.read_text(encoding='utf-8')
    entries = []
    for sub in re.finditer(r'^##[ \t]+([^\n]+)\n(.*?)(?=^##[ \t]+|\Z)', text, re.M | re.S):
        heading = sub.group(1).strip()
        body = sub.group(2)
        chapters = re.search(r'\bchapters?\s+([\d,\s–—-]+)', heading, re.I)
        if chapters is None:  # Older headings may only give a bare range.
            chapters = re.search(r'(\d+\s*[–-]\s*\d+)', heading)
        if ch_num is not None and chapters:
            ranges = re.findall(r'(\d+)(?:\s*[–—-]\s*(\d+))?', chapters[1])
            if not any(int(first) <= ch_num <= int(last or first) for first, last in ranges):
                continue
        lines = [line.strip() for line in body.splitlines() if line.strip().startswith('-')]
        if ch_num is not None:
            selected = []
            for line in lines:
                # The first chapter after the entry label owns the turn. A later
                # reference can point back to a setup in a different chapter.
                target = re.match(r'^-\s*(?:\*{0,2}[^:*\n]+:\*{0,2}\s*)?ch(?:apter)?\.?\s*(\d+)\b',
                                  line, re.I)
                if target is None or int(target[1]) == ch_num:
                    selected.append(line)
            lines = selected
        if lines:
            entries.append({'act': heading, 'entries': lines})
    return {'path': str(p.relative_to(root)), 'sha256': digest(p), 'acts': entries} if entries else None


def voice_roster(style_path):
    roster = []
    multi = False
    if style_path and style_path.is_file():
        sg_text = style_path.read_text(encoding='utf-8')
        names = re.findall(r'^pov_\d+:[ \t]*["\']?([^"\'\n]+)', sg_text, re.M)
        roster = list(dict.fromkeys(name.strip() for name in names if name.strip().lower() not in ('', 'none')))
        multi = len(roster) > 1 or bool(re.search(r'^pov_mode:[ \t]*["\']?(?:dual|multi)\b', sg_text, re.M | re.I))
    return roster, multi


def voice_sources(root, pov_names, multi, roster):
    voice_prompts = []
    style_dir = root / 'Wiki' / 'Style'
    watched = []
    known_names = {name.casefold() for name in [*pov_names, *roster]}
    first_names = Counter(name.split()[0] for name in known_names)
    for pov in pov_names:
        slug_full = re.sub(r'\s+', '_', pov.strip())
        slug_first = slug_full.split('_')[0]
        candidates = [slug_full, slug_full.lower()]
        if first_names[slug_first.casefold()] == 1:
            candidates.extend((slug_first, slug_first.lower()))
        for slug in dict.fromkeys(candidates):
            vp = path_at(root, style_dir / f'voice_prompt_{slug}.md')
            watched.append(str(vp.relative_to(root)))
            if vp.is_file():
                voice_prompts.append({'pov': pov, 'path': str(vp.relative_to(root)), 'sha256': digest(vp)})
                break
    default_vp = style_dir / 'voice_prompt.md'
    contrast_index = None
    if multi and default_vp.is_file():
        contrast_index = {'path': str(default_vp.relative_to(root)), 'sha256': digest(default_vp)}
    if not multi and default_vp.is_file():
        voice_prompts.append({'pov': 'default', 'path': str(default_vp.relative_to(root)), 'sha256': digest(default_vp)})
    watched.append('Wiki/Style/voice_prompt.md')
    return voice_prompts, contrast_index, list(dict.fromkeys(watched))


def parse_voice_lenses(root, voice_prompts):
    lenses = []
    for vp in voice_prompts:
        p = path_at(root, vp['path'])
        if not p.is_file():
            continue
        sections = _section_map(p.read_text(encoding='utf-8'), level=2)
        notice = sections.get('what they notice', '').strip()
        firewall = sections.get('language firewall', '').strip()
        anchors = sections.get('author-selected voice anchors', '').strip()
        if notice or firewall or anchors:
            lenses.append({
                'pov': vp['pov'],
                'path': vp['path'],
                'what_they_notice': notice[:600],
                'language_firewall': firewall[:600],
                'author_selected_anchors': anchors,
            })
    return lenses


def pov_labels(text):
    values = re.findall(r'^[ \t]*(?:[-*][ \t]+)?(?:\*\*)?POV(?:\*\*)?:(?:\*\*)?[ \t]*(.+)$',
                        text, re.M | re.I)
    names = (name.strip(' *').split('(')[0].strip()
             for value in values for name in re.split(r'[,/|]| and ', value, flags=re.I))
    return list(dict.fromkeys(name for name in names if name and name.lower() != 'none'))


def scene_contexts(text, psych_povs, roster, multi):
    sections = list(re.finditer(r'^#{2,4}[ \t]+Scene[ \t]+(\d+)\b[^\n]*', text, re.M | re.I))
    preamble = text[:sections[0].start()] if sections else text
    chapter_povs = pov_labels(preamble)
    ch_cadence_m = re.search(
        r'^[ \t]*(?:[-*][ \t]+)?(?:\*\*)?Cadence role(?:\*\*)?:(?:\*\*)?[ \t]*([a-z_]+)',
        preamble, re.M | re.I,
    )
    ch_cadence = ch_cadence_m.group(1).lower() if ch_cadence_m else 'pressure_turn'
    ch_threads_m = re.search(
        r'^[ \t]*(?:[-*][ \t]+)?(?:\*\*)?Subplot threads(?:\*\*)?:(?:\*\*)?[ \t]*([^\n]+)',
        preamble, re.M | re.I,
    )
    ch_threads = [t.strip() for t in ch_threads_m.group(1).split(',') if t.strip()] if ch_threads_m else []

    scopes = [(sec[1], text[sec.end():sections[index + 1].start() if index + 1 < len(sections) else len(text)])
              for index, sec in enumerate(sections)] or [('1', '')]
    named = {pov for _, body in scopes for pov in pov_labels(body)}
    fallback = chapter_povs or psych_povs
    if named - set(fallback) and fallback:
        fallback = []
    if not fallback and len(roster) == 1 and not multi:
        fallback = roster
    result = []
    ids = set()
    for number, body in scopes:
        scene_id = f'scene-{int(number)}'
        if scene_id in ids:
            raise ValueError(f'duplicate scene number in plan: {number}')
        ids.add(scene_id)
        labels = pov_labels(body) or fallback
        pov = labels[0] if len(labels) == 1 else None
        cad_m = re.search(
            r'^[ \t]*(?:[-*][ \t]+)?(?:\*\*)?Cadence role(?:\*\*)?:(?:\*\*)?[ \t]*([a-z_]+)',
            body, re.M | re.I,
        )
        thr_m = re.search(
            r'^[ \t]*(?:[-*][ \t]+)?(?:\*\*)?Subplot threads(?:\*\*)?:(?:\*\*)?[ \t]*([^\n]+)',
            body, re.M | re.I,
        )
        scope = {
            'id': scene_id,
            'pov': pov,
            'pov_status': 'RESOLVED' if pov else 'UNRESOLVED' if multi or labels or named else 'UNSPECIFIED',
            'cadence_role': cad_m.group(1).lower() if cad_m else ch_cadence,
            'subplot_threads': ([t.strip() for t in thr_m.group(1).split(',') if t.strip()]
                                if thr_m else ch_threads),
        }
        ledger_id = re.search(r'^[ \t]*(?:- )?(?:\*\*)?scene id:(?:\*\*)?[ \t]*([^\n]+)', body, re.M | re.I)
        if ledger_id:
            scope['ledger_scene_id'] = ledger_id[1].strip()
        for field in ('story_order', 'reader_order'):
            label = field.replace('_', ' ')
            match = re.search(rf'^[ \t]*(?:-[ \t]+)?(?:\*\*)?{label}:(?:\*\*)?[ \t]*(\d+)[ \t]*$',
                              body, re.M | re.I)
            if match:
                scope[field] = int(match[1])
        result.append(scope)
    return result


def scene_knowledge(root, book, chapter_num, scene, args, *, global_ledger, legacy_ledger, first):
    pov = scene['pov']
    observers = [pov, 'reader'] if pov else ['reader']
    if global_ledger:
        data = {'_coverage': {'status': 'PARTIAL', 'note': 'missing events do not establish ignorance'}}
        for field, observer in zip(('story_order', 'reader_order'), (pov, 'reader')):
            if not observer:
                continue
            position = scene.get(field, getattr(args, field, None) if first else None)
            if position is None:
                data[observer] = {'status': 'CHRONOLOGY_UNRESOLVED', 'reason': f'scene has no explicit {field}'}
            else:
                data[observer] = knowledge_event_state(root, argparse.Namespace(
                    action='as-of', observer=observer, story_order=position, reader_order=position, spec=None))
        return data
    if not legacy_ledger:
        return {}
    if chapter_num is None:
        return {'_coverage': {'status': 'PARTIAL'}, '_story_time': {'status': 'CHRONOLOGY_UNRESOLVED'}}
    result = {}
    for observer in observers:
        position = f'{chapter_num}.0'
        if observer == 'reader' and not first:
            position = f'{chapter_num}.{scene["id"].removeprefix("scene-")}.0'
        known = knowledge(root, argparse.Namespace(
            book=book, action='as-of', observer=observer, position=position))
        if known:
            result[observer] = known
    return result


def repetition_candidates(root, trail_chapters, window, style_path, scene_break):
    keeps = []
    if style_path and style_path.is_file():
        section = _section_map(style_path.read_text(encoding='utf-8')).get('cooling list keeps', '')
        keeps = [line[2:].strip() for line in section.splitlines() if line.startswith('- ') and line[2:].strip()]
    # Literal project phrases and multiword names break candidate spans.
    protected = [r'(?<!\w)' + re.escape(phrase) + r'(?!\w)' for phrase in keeps]
    names = r"\b[A-Z][\w’'-]*(?:[ \t]+[A-Z][\w’'-]*)+\b"
    protected_pattern = re.compile('|'.join([*(f'(?i:{phrase})' for phrase in protected), names]))
    counts = {kind: Counter() for kind in ('somatic_hotspots', 'repeated_ngrams', 'repeated_similes')}
    examples = {kind: defaultdict(list) for kind in counts}
    openers, closers = [], []

    def record(kind, key, chapter_path, context):
        counts[kind][key] += 1
        samples = examples[kind][key]
        sample = {'path': chapter_path, 'quote': context}
        if len(samples) < 2 and sample not in samples:
            samples.append(sample)

    for chapter in trail_chapters:
        path = path_at(root, chapter['path'])
        if not path.is_file():
            continue
        lines = prose_lines(path, scene_break)
        location = {'chapter': chapter.get('display_label', chapter['id']), 'chapter_id': chapter['id']}
        sentences = [sentence.strip() for line in lines for sentence in re.split(r'(?<=[.!?])\s+', line)
                     if sentence.strip()]
        substantive = [sentence for sentence in sentences if len(sentence.split()) >= 3]
        if substantive:
            openers.append({**location, 'opener': ' '.join(substantive[0].split()[:6])})
            closers.append({**location, 'closer': substantive[-1]})
        for sentence in sentences:
            for span in protected_pattern.split(sentence):
                tokens = re.findall(r"[^\W\d_]+(?:[’'][^\W\d_]+)*", span.casefold())
                for word in tokens:
                    if word in SOMATIC_TOKENS:
                        record('somatic_hotspots', word, chapter['path'], sentence)
                for i in range(len(tokens) - 2):
                    triple = tokens[i:i + 3]
                    if sum(word not in STOP_WORDS for word in triple) >= 2:
                        record('repeated_ngrams', ' '.join(triple), chapter['path'], sentence)
                for match in re.finditer(r'\b(?:like\s+(?:a|an|the)\s+[a-z]+\s+[a-z]+|as\s+if\s+[a-z]+\s+[a-z]+\s+[a-z]+)', span.casefold()):
                    record('repeated_similes', ' '.join(match[0].split()), chapter['path'], sentence)
    result = {'window_chapters': window, 'recent_openers': openers, 'recent_closers': closers}
    for kind, label, cap in [('somatic_hotspots', 'word', None), ('repeated_ngrams', 'ngram', 20),
                             ('repeated_similes', 'phrase', 15)]:
        ordered = sorted(counts[kind].items(), key=lambda pair: (-pair[1], pair[0]))
        result[kind] = [{label: key, 'count': count, 'examples': examples[kind][key]}
                        for key, count in ordered if count >= 2][:cap]
    return result


def supported_irony(knowledge_by_observer, pov):
    """Keep confirmed differences distinct from exposure and incomplete ledger coverage."""
    def observed(observer):
        entry = knowledge_by_observer.get(observer, {})
        if entry.get('status') == 'CHRONOLOGY_UNRESOLVED':
            return {}
        # Series events sit under state. Legacy per-book ledgers return a fact map.
        return entry.get('state', entry)

    reader, character = observed('reader'), observed(pov)
    differences = []
    for fact_id, event in sorted(reader.items()):
        if not isinstance(event, dict) or event.get('state') != 'knows' or event.get('truth_status') != 'true':
            continue
        opposing = character.get(fact_id)
        if not isinstance(opposing, dict) or opposing.get('state') not in ('disbelieves', 'forgets'):
            continue
        differences.append({'fact_id': fact_id, 'reader_state': event['state'], 'truth_status': event['truth_status'],
                            'pov_state': opposing['state'], 'source': event['source'], 'quote': event['quote'],
                            'pov_source': opposing['source'], 'pov_quote': opposing['quote']})
    return differences


def draft_packet(root, args):
    resolver = project_manifest_module()
    book_record, chapter_record = resolver.resolve_chapter(root, args.book, args.chapter or 'Chapter 1', allow_new=True)
    texts = manuscript_texts(root, book_record)
    if chapter_record not in book_record['chapters']:
        book_record = {**book_record, 'chapters': [*book_record['chapters'], chapter_record]}
    book = book_record.get('display_label', book_record['id'])
    book_chapters = sorted(book_record['chapters'], key=lambda chapter: chapter['reading_order'])
    chapter_index = book_chapters.index(chapter_record)
    label = chapter_record.get('display_label') or chapter_record['id']
    ch_match = re.fullmatch(r'(?:Chapter[- ]?)?(\d+)', str(label), re.I)
    if ch_match:
        ch_num = int(ch_match.group(1))
    elif book_record.get('chapter_order') == 'declared' and chapter_record.get('reading_order') is not None:
        # Imported EPUB units (Unit-<18hex>.md) use title-based labels; resolve logical unit index.
        ch_num = chapter_record['reading_order']
    else:
        ch_num = None
    chapter_scope_id = f'Chapter-{ch_num:03d}' if ch_num is not None else chapter_record['id']
    window = max(1, int(args.window))

    scene_info = None
    stext = ''
    scene_candidates = ([path_at(root, chapter_record['scene_plan_path'])]
                        if chapter_record.get('scene_plan_path') else [])
    if ch_num is not None:
        scene_candidates.extend((root / 'Wiki' / 'Outline' / book_record.get('display_label', book) / f'Chapter_{ch_num:02d}_Scene.md',
                                 root / 'Wiki' / 'Outline' / book_record.get('display_label', book) / f'Chapter_{ch_num:03d}_Scene.md'))
    for cand in scene_candidates:
        if cand.is_file():
            stext = cand.read_text(encoding='utf-8')
            key_line = re.search(r'^\s*(?:\*\*)?Continuity keys:(?:\*\*)?\s*([^\n]+)', stext, re.M)
            scene_info = {
                'path': str(cand.relative_to(root)),
                'sha256': digest(cand),
                'continuity_keys': [key.strip() for key in key_line[1].split(',') if key.strip()] if key_line else [],
            }
            break

    psych_info = None
    psych_povs = []
    psych_candidates = ([path_at(root, chapter_record['psych_path'])]
                        if chapter_record.get('psych_path') else [])
    if ch_num is not None:
        psych_candidates.extend((root / 'Wiki' / 'Psych' / book_record.get('display_label', book) / f'Chapter_{ch_num:02d}_Psych.md',
                                 root / 'Wiki' / 'Psych' / book_record.get('display_label', book) / f'Chapter_{ch_num:03d}_Psych.md'))
    for cand in psych_candidates:
        if cand.is_file():
            psych_povs = [name for name in pov_labels(cand.read_text(encoding='utf-8'))
                          if not re.fullmatch(r'(?:age[ \t]+)?\d+(?:[ \t]+years?[ \t]+old)?', name, re.I)]
            psych_info = {
                'path': str(cand.relative_to(root)),
                'sha256': digest(cand),
                **parse_psych(cand),
            }
            break

    style_authority = project_manifest_module().resolve_style_guide(root, book)
    style_path = path_at(root, style_authority['path']) if style_authority.get('status') == 'RESOLVED' else None
    roster, multi = voice_roster(style_path)
    scenes = scene_contexts(stext, psych_povs, roster, multi)
    pov_names = list(dict.fromkeys(scene['pov'] for scene in scenes if scene['pov']))
    multi = multi or len(pov_names) > 1
    if scene_info:
        scene_info.update(scene_count=len(scenes), pov_characters=pov_names)
    voice_prompts, contrast_index, _ = voice_sources(root, pov_names, multi, roster)

    checkpoints = []
    skipped_checkpoints = []
    char_dir = root / 'Wiki' / 'Characters'
    if char_dir.is_dir() and ch_num is not None:
        unscoped_ok = book.strip().lower() == 'book-1'
        for cf in sorted(char_dir.glob('*.md')):
            if cf.stem.endswith('_sheet'):
                continue
            for cp in parse_checkpoints(cf, ch_num, book=book, book_id=book_record['id'],
                                        unscoped_ok=unscoped_ok, skipped=skipped_checkpoints):
                cp['source'] = str(cf.relative_to(root))
                cp['source_sha256'] = digest(cf)
                checkpoints.append(cp)
    for item in skipped_checkpoints:
        item['source'] = str(item['source'].relative_to(root))

    scene_break = book_record.get('chapter_format', {}).get('scene_break', '* * *')
    continuity_tail = None
    predecessor_id = resolver.predecessor(book_record, chapter_record)
    predecessor = next((item for item in book_chapters if item.get('id') == predecessor_id), None)
    if predecessor is None and ch_num is not None and ch_num > 1:
        predecessor_path = f'Chapters/{book}/Chapter-{ch_num - 1:03d}.md'
    else:
        predecessor_path = predecessor.get('path') if predecessor else None
    if predecessor_path:
        prev_ch = path_at(root, predecessor_path)
        if prev_ch.is_file():
            plines = prose_lines(prev_ch, scene_break)
            all_words = ' '.join(plines).split()
            tail_words = ' '.join(all_words[-400:]) if all_words else ''
            closing_sentence = ''
            for line in reversed(plines):
                sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', line) if len(s.split()) >= 3]
                if sents:
                    closing_sentence = sents[-1]
                    break
            continuity_tail = {
                'path': str(prev_ch.relative_to(root)),
                'sha256': digest(prev_ch),
                'tail_excerpt': tail_words,
                'closing_sentence': closing_sentence,
            }

    trail_chapters = book_chapters[max(0, chapter_index - window):chapter_index]
    cooling_list = repetition_candidates(root, trail_chapters, window, style_path, scene_break)

    ledger_store = ledger_store_module()
    global_knowledge = ledger_store.load_ledger(root, 'Wiki/Story/knowledge-events.json') is not None
    legacy_knowledge = path_at(root, f'Wiki/Story/{book}/knowledge.json').is_file()
    ed_path = path_at(root, 'Wiki/Style/editorial-decisions.json')
    decisions = [item for item in document(ed_path, 'decisions')['decisions'] if item.get('status') == 'active']
    book_ids = (book, book_record['id'])
    chapter_ids = (chapter_scope_id, chapter_record['id'])
    for index, scene in enumerate(scenes):
        scene['voice_prompts'] = [item for item in voice_prompts if item['pov'] in (scene['pov'], 'default')]
        kn = scene_knowledge(root, book, ch_num, scene, args,
                             global_ledger=global_knowledge,
                             legacy_ledger=legacy_knowledge, first=index == 0)
        scene['knowledge_as_of'] = kn
        scene['dramatic_irony'] = supported_irony(kn, scene['pov']) if scene['pov'] else []
        scene_number = int(scene['id'].removeprefix('scene-'))
        current, turns, uncertain = relationship_checkpoints_at_scene(checkpoints, ch_num, scene_number)
        scene.update(relationship_checkpoints=current, relationship_turns=turns,
                     relationship_timing_unresolved=uncertain)
        scene['editorial_decisions'] = [item for item in decisions
                                        if decision_applies(item, book_ids, chapter_ids, scene['pov'],
                                                            chapter_path=chapter_record['path'])]

    relationship_as_of = []
    relationship_events = ledger_store.load_ledger(root, 'Wiki/Story/relationship-events.json')
    if relationship_events is not None:
        for index, scene in enumerate(scenes):
            position = scene.get('story_order', getattr(args, 'story_order', None) if index == 0 else None)
            if position is None or scene['pov'] is None:
                result = {'status': 'CHRONOLOGY_UNRESOLVED', 'reason': 'scene needs a viewpoint and story order'}
            else:
                query = argparse.Namespace(action='as-of', observer=scene['pov'], other=None, position=position,
                                           scene_id=scene.get('ledger_scene_id') or
                                           (getattr(args, 'scene_id', None) if index == 0 else None) or scene['id'],
                                           book_ids=book_ids)
                result = relationship_state(root, query)
            scene['relationship_state_as_of'] = result
            relationship_as_of.append(result)

    formatting = chapter_format_module().audit(book_record, texts, selected=chapter_record['id'])
    keys = (scene_info or {}).get('continuity_keys', []) + (getattr(args, 'key', None) or [])
    policy_ns = argparse.Namespace(book=book, simile_count=None)
    packet = {
        'schema_version': VERSION,
        'book': book,
        'book_id': book_record['id'],
        'chapter_number': label,
        'chapter_id': chapter_record['id'],
        'chapter_path': chapter_record['path'],
        'report_stem': resolver.report_stem(chapter_record),
        'reading_order': chapter_record['reading_order'],
        'predecessor_id': predecessor_id,
        'scene_plan': scene_info,
        'scenes': scenes,
        'psych': psych_info,
        'theme': parse_theme(root),
        'surprise_ledger': parse_surprise_ledger(root, book, ch_num),
        'style_authority': style_authority,
        'style_policy': style_policy(root, policy_ns),
        'voice_prompts': voice_prompts,
        'pov_lenses': parse_voice_lenses(root, voice_prompts),
        'voice_contrast_index': contrast_index,
        'relationship_checkpoints': checkpoints,
        'unscoped_relationship_checkpoints': skipped_checkpoints,
        'relationship_state_as_of': relationship_as_of,
        'continuity_tail': continuity_tail,
        'chapter_format': formatting['contract'],
        'chapter_format_check': {
            'status': ('PENDING' if chapter_record['path'] not in texts else
                       'FAIL' if formatting['findings'] else 'PASS'),
            'findings': formatting['findings'],
        },
        'continuity': continuity_report(root, book_record, texts, chapter=chapter_record, keys=keys),
        'promises': promise_context(root, book_record, chapter_record),
        'knowledge_as_of': scenes[0]['knowledge_as_of'],
        'editorial_decisions': list({item['id']: item for scene in scenes
                                     for item in scene['editorial_decisions']}.values()),
        'cooling_list': cooling_list,
    }
    if getattr(args, 'output', None):
        out = path_at(root, args.output)
        with locked(out):
            write(out, packet)
    return packet
