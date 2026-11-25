"""Pre-draft packet compiler, style policy, and psych/checkpoint parsers."""
import argparse
import re

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


def prose_lines(path):
    """Extract clean prose lines, stripping headings, fences, > callouts, rules, and checkboxes."""
    lines = []
    in_fence = False
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith('```'):
            in_fence = not in_fence
            continue
        if in_fence or line.startswith('#') or line.startswith('>') or line in ('---', '***'):
            continue
        if re.match(r'^[-*] \[', line):
            continue
        lines.append(line)
    return lines


def parse_checkpoints(path, chapter_num, *, book=None, unscoped_ok=True, skipped=None):
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
        for line in sub.group(2).splitlines():
            kv = re.match(r'^\s*[-*]\s*(?:\*\*)?([a-z_]+)(?:\*\*)?:(?:\*\*)?\s*(.+)$', line.strip(), re.I)
            if kv:
                k, v = kv.group(1).lower(), kv.group(2).strip()
                if k in current:
                    entries.append(current)
                    current = {}
                current[k] = v
        if current:
            entries.append(current)
        for entry in entries:
            entry_book = entry.get('book') or entry.get('book_id')
            if book is not None:
                if entry_book:
                    if entry_book.strip().lower() != str(book).strip().lower():
                        continue
                elif not unscoped_ok:
                    if skipped is not None:
                        skipped.append({
                            'character': char_name,
                            'other_character': other,
                            'reason': 'unscoped checkpoint skipped for ' + str(book),
                            'source': path,
                        })
                    continue
            start_m = re.search(r'\d+', str(entry.get('chapter_start', '1')))
            start = int(start_m.group(0)) if start_m else 1
            end_raw = str(entry.get('chapter_end', '(open)')).strip().lower()
            end_m = re.search(r'\d+', end_raw)
            end = None if ('open' in end_raw or not end_m) else int(end_m.group(0))
            if start <= chapter_num and (end is None or chapter_num <= end):
                item = {
                    'character': char_name,
                    'other_character': other,
                    'link_type': entry.get('link_type', ''),
                    'chapter_start': start,
                    'chapter_end': 'open' if end is None else end,
                    'notes': entry.get('notes', ''),
                    'source': path,
                }
                if entry_book:
                    item['book'] = entry_book.strip()
                active.append(item)
    return active


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
    cq = re.search(r'^central_question:[ \t]*["\']?([^"\'\n]+)["\']?', text, re.M)
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
        'central_question': cq.group(1).strip() if cq else None,
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
        span = re.search(r'(\d+)\s*[–-]\s*(\d+)', heading)
        if ch_num is not None and span and not (int(span.group(1)) <= ch_num <= int(span.group(2))):
            continue
        lines = [line.strip() for line in body.splitlines() if line.strip().startswith('-')]
        if ch_num is not None:
            ch_lines = [line for line in lines if re.search(rf'\bch(?:apter)?\.?\s*0*{ch_num}\b', line, re.I)
                        or 'surprise inventory' in line.lower()]
            lines = ch_lines or lines
        if lines:
            entries.append({'act': heading, 'entries': lines})
    return {'path': str(p.relative_to(root)), 'sha256': digest(p), 'acts': entries} if entries else None


def parse_voice_lenses(root, voice_prompts):
    lenses = []
    for vp in voice_prompts:
        p = path_at(root, vp['path'])
        if not p.is_file():
            continue
        sections = _section_map(p.read_text(encoding='utf-8'), level=2)
        notice = sections.get('what they notice', '').strip()
        firewall = sections.get('language firewall', '').strip()
        if notice or firewall:
            lenses.append({
                'pov': vp['pov'],
                'path': vp['path'],
                'what_they_notice': notice[:600],
                'language_firewall': firewall[:600],
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
    chapter_povs = pov_labels(text[:sections[0].start()]) if sections else pov_labels(text)
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
        scope = {'id': scene_id, 'pov': pov,
                 'pov_status': 'RESOLVED' if pov else 'UNRESOLVED' if multi or labels or named else 'UNSPECIFIED'}
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
    ch_num = int(ch_match.group(1)) if ch_match else None
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
    roster = []
    multi = False
    if style_path and style_path.is_file():
        sg_text = style_path.read_text(encoding='utf-8')
        names = re.findall(r'^pov_\d+:[ \t]*["\']?([^"\'\n]+)', sg_text, re.M)
        roster = list(dict.fromkeys(name.strip() for name in names if name.strip().lower() not in ('', 'none')))
        multi = len(roster) > 1 or bool(re.search(r'^pov_mode:[ \t]*["\']?(?:dual|multi)\b', sg_text, re.M | re.I))
    scenes = scene_contexts(stext, psych_povs, roster, multi)
    pov_names = list(dict.fromkeys(scene['pov'] for scene in scenes if scene['pov']))
    multi = multi or len(pov_names) > 1
    if scene_info:
        scene_info.update(scene_count=len(scenes), pov_characters=pov_names)
    voice_prompts = []
    seen_vp = set()
    style_dir = root / 'Wiki' / 'Style'
    for pov in pov_names:
        slug_full = re.sub(r'\s+', '_', pov.strip())
        slug_first = slug_full.split('_')[0]
        for cand_name in (f'voice_prompt_{slug_full}.md', f'voice_prompt_{slug_first}.md',
                          f'voice_prompt_{slug_full.lower()}.md', f'voice_prompt_{slug_first.lower()}.md'):
            vp = path_at(root, style_dir / cand_name)
            if vp.is_file() and vp not in seen_vp:
                seen_vp.add(vp)
                voice_prompts.append({'pov': pov, 'path': str(vp.relative_to(root)), 'sha256': digest(vp)})
                break
    default_vp = style_dir / 'voice_prompt.md'
    if not multi and default_vp.is_file() and default_vp not in seen_vp:
        voice_prompts.append({'pov': 'default', 'path': str(default_vp.relative_to(root)), 'sha256': digest(default_vp)})

    checkpoints = []
    char_dir = root / 'Wiki' / 'Characters'
    if char_dir.is_dir() and ch_num is not None:
        unscoped_ok = book.strip().lower() == 'book-1'
        for cf in sorted(char_dir.glob('*.md')):
            if cf.stem.endswith('_sheet'):
                continue
            for cp in parse_checkpoints(cf, ch_num, book=book, unscoped_ok=unscoped_ok):
                cp['source'] = str(cf.relative_to(root))
                cp['source_sha256'] = digest(cf)
                checkpoints.append(cp)

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
            plines = prose_lines(prev_ch)
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

    somatic_counts = {}
    ngram_counts = {}
    simile_counts = {}
    recent_openers = []
    recent_closers = []
    trail_chapters = book_chapters[max(0, chapter_index - window):chapter_index]
    for trail in trail_chapters:
        t_path = path_at(root, trail['path'])
        if not t_path.is_file():
            continue
        t_lines = prose_lines(t_path)
        if not t_lines:
            continue
        first_w = []
        for l in t_lines:
            w = re.findall(r"[A-Za-z][A-Za-z']+", l)
            if len(w) >= 3:
                first_w = w[:6]
                break
        if first_w:
            recent_openers.append({'chapter': trail.get('display_label', trail['id']), 'chapter_id': trail['id'],
                                   'opener': ' '.join(first_w)})
        last_s = ''
        for l in reversed(t_lines):
            sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', l) if len(s.split()) >= 3]
            if sents:
                last_s = sents[-1]
                break
        if last_s:
            recent_closers.append({'chapter': trail.get('display_label', trail['id']), 'chapter_id': trail['id'],
                                   'closer': last_s})

        prose_blob = ' '.join(t_lines)
        tokens = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z']+", prose_blob)]
        ch_somatic = {}
        for tok in tokens:
            if tok in SOMATIC_TOKENS:
                ch_somatic[tok] = ch_somatic.get(tok, 0) + 1
                somatic_counts[tok] = somatic_counts.get(tok, 0) + 1
        for tok, c in ch_somatic.items():
            if c >= 2 and somatic_counts[tok] < 3:
                somatic_counts[tok] = 3

        for i in range(len(tokens) - 2):
            tri = tokens[i:i + 3]
            if sum(1 for w in tri if w not in STOP_WORDS) >= 2:
                key = ' '.join(tri)
                ngram_counts[key] = ngram_counts.get(key, 0) + 1

        for sm in re.finditer(r'\b(?:like\s+(?:a|an|the)\s+[a-z]+\s+[a-z]+|as\s+if\s+[a-z]+\s+[a-z]+\s+[a-z]+)', prose_blob.lower()):
            phrase = re.sub(r'\s+', ' ', sm.group(0).strip())
            simile_counts[phrase] = simile_counts.get(phrase, 0) + 1

    cooling_list = {
        'window_chapters': window,
        'somatic_hotspots': [
            {'word': k, 'count': v}
            for k, v in sorted(somatic_counts.items(), key=lambda x: (-x[1], x[0]))
            if v >= 3
        ],
        'repeated_ngrams': [
            {'ngram': k, 'count': v}
            for k, v in sorted(ngram_counts.items(), key=lambda x: (-x[1], x[0]))
            if v >= 2
        ][:20],
        'repeated_similes': [
            {'phrase': k, 'count': v}
            for k, v in sorted(simile_counts.items(), key=lambda x: (-x[1], x[0]))
        ][:15],
        'recent_openers': recent_openers,
        'recent_closers': recent_closers,
    }

    ledger_store = ledger_store_module()
    global_knowledge = ledger_store.load_ledger(root, 'Wiki/Story/knowledge-events.json') is not None
    legacy_knowledge = path_at(root, f'Wiki/Story/{book}/knowledge.json').is_file()
    ed_path = path_at(root, 'Wiki/Style/editorial-decisions.json')
    decisions = [item for item in document(ed_path, 'decisions')['decisions'] if item.get('status') == 'active']
    book_ids = (book, book_record['id'])
    chapter_ids = (chapter_scope_id, chapter_record['id'])
    for index, scene in enumerate(scenes):
        scene['voice_prompts'] = [item for item in voice_prompts if item['pov'] in (scene['pov'], 'default')]
        scene['knowledge_as_of'] = scene_knowledge(root, book, ch_num, scene, args,
                                                  global_ledger=global_knowledge,
                                                  legacy_ledger=legacy_knowledge, first=index == 0)
        scene['editorial_decisions'] = [item for item in decisions
                                        if decision_applies(item, book_ids, chapter_ids, scene['pov'],
                                                            chapter_path=chapter_record['path'])]

    relationship_as_of = []
    relationship_events = ledger_store.load_ledger(root, 'Wiki/Story/relationship-events.json')
    if relationship_events is not None:
        if getattr(args, 'story_order', None) is None:
            relationship_as_of = [{'status': 'CHRONOLOGY_UNRESOLVED', 'reason':
                                   'relationship event records exist but this packet has no explicit story order'}]
        else:
            for pov in pov_names:
                query = argparse.Namespace(action='as-of', observer=pov, other=None,
                                           position=args.story_order, scene_id=getattr(args, 'scene_id', None))
                relationship_as_of.append(relationship_state(root, query))

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
        'relationship_checkpoints': checkpoints,
        'relationship_state_as_of': relationship_as_of,
        'continuity_tail': continuity_tail,
        'chapter_format': formatting['contract'],
        'continuity': continuity_report(root, book_record, texts, chapter=chapter_record, keys=keys),
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
