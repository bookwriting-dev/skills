"""Validate chapter headings and POV metadata against the book convention."""
import re


POV_PATTERNS = {
    'plain': r'POV:\s*(.*)',
    'bold_label': r'\*\*POV:\*\*\s*(.*)',
    'bold': r'\*\*POV:\s*(.*?)\*\*',
    'comment': r'<!--\s*POV:\s*(.*?)\s*-->',
}
DEFAULT_SCENE_BREAK = '* * *'


def metadata(text, scene_break):
    """Find metadata only at the chapter head and explicit scene seams."""
    lines = text.splitlines()
    start = 0
    if lines and lines[0].lstrip('\ufeff') == '---' and '---' in lines[1:]:
        end = lines.index('---', 1)
        if any(re.match(r'^\w[\w-]*:', line) for line in lines[1:end]):
            start = end + 1
    slots = []
    heading = None
    position = (1, '')
    marker = None
    at_head = True
    fence = None
    comment = False
    for number, original in enumerate(lines[start:], start + 1):
        line = original.strip().lstrip('\ufeff')
        if fence:
            if re.fullmatch(re.escape(fence[0]) + '{' + str(len(fence)) + ',}', line):
                fence = None
            continue
        if comment:
            comment = '-->' not in line
            continue
        if not line:
            continue
        if line.startswith('<!--') and not re.match(r'<!--\s*POV:', line, flags=re.I):
            comment = '-->' not in line
            continue
        if at_head:
            at_head = False
            match = re.fullmatch(r'#\s+(.+?)(?:\s+#+)?', line)
            if match:
                heading = (number, match[1], original)
                position = (number, original)
                continue
            position = (number, original)
        if line in (DEFAULT_SCENE_BREAK, scene_break):
            if position:
                slots.append((position, marker))
            position, marker = (number, original), None
            continue
        if position:
            if re.match(r'^(?:\*\*|<!--\s*)?POV(?:\*\*)?:', line, flags=re.I):
                style, name = None, ''
                for candidate, pattern in POV_PATTERNS.items():
                    match = re.fullmatch(pattern, line)
                    if match:
                        style, name = candidate, match[1].strip()
                        break
                if marker is None:
                    marker = (number, original, style, name)
                else:
                    slots.append(((number, original), (number, original, None, '')))
                continue
            slots.append((position, marker))
            position, marker = None, None
        match = re.match(r'^(`{3,}|~{3,})', line)
        if match:
            fence = match[1]
    if position:
        slots.append((position, marker))
    return heading, slots


def audit(book, texts, selected=None):
    config = book.get('chapter_format', {})
    if not isinstance(config, dict) or set(config) - {'pov_style', 'require_pov', 'scene_break'}:
        raise ValueError('chapter_format accepts pov_style, require_pov, and scene_break')
    style = config.get('pov_style')
    required = config.get('require_pov', False)
    scene_break = config.get('scene_break', DEFAULT_SCENE_BREAK)
    if style is not None and (not isinstance(style, str) or style not in POV_PATTERNS):
        raise ValueError('chapter_format.pov_style must be plain, bold_label, bold, or comment')
    if type(required) is not bool or not isinstance(scene_break, str) or not scene_break.strip() or '\n' in scene_break:
        raise ValueError('chapter_format requires a boolean require_pov and a nonempty, single-line scene_break')
    scene_break = scene_break.strip()
    chapters = sorted(book['chapters'], key=lambda chapter: chapter['reading_order'])
    if selected is not None:
        target = next(chapter for chapter in chapters if chapter['id'] == selected)
        chapters = [chapter for chapter in chapters if chapter['reading_order'] <= target['reading_order']]
    chapters = [chapter for chapter in chapters if chapter['path'] in texts]
    parsed = {chapter['id']: metadata(texts[chapter['path']], scene_break) for chapter in chapters}
    inferred = None
    if style is None:
        for chapter in chapters:
            markers = (marker for _, marker in parsed[chapter['id']][1] if marker and marker[2] and marker[3])
            first = next(markers, None)
            if first:
                style = first[2]
                inferred = {'path': chapter['path'], 'line': first[0], 'quote': first[1]}
                break
    style = style or 'bold_label'
    findings = []
    contract = {'pov_style': style, 'require_pov': required, 'scene_break': scene_break,
                'inferred_from': inferred}
    comment_lines = {}
    for chapter in chapters:
        chapter_id, path = chapter['id'], chapter['path']
        if selected is not None and chapter_id != selected:
            continue
        heading, slots = parsed[chapter_id]
        label = chapter.get('display_label')
        if label and (not heading or not re.match(rf'^{re.escape(label)}(?:$|\s+[—–-]\s+|:\s+)', heading[1])):
            line, quote = (heading[0], heading[2]) if heading else (slots[0][0] if slots else (1, ''))
            findings.append(finding('chapter-heading', path, line, quote, f'Expected a level-one heading beginning with {label!r}.'))
        for position, marker in slots:
            if marker is None:
                if required:
                    findings.append(finding('missing-pov', path, *position, 'Expected a POV tag here.'))
                continue
            line, quote, actual, name = marker
            if actual == 'comment' and name:
                comment_lines.setdefault(path, []).append(line)
            if actual != style or not name:
                message = f'Expected one nonempty POV tag in {style} form at this position.'
                findings.append(finding('pov-format', path, line, quote, message))
    if selected is not None:
        contract['heading_label'] = target.get('display_label')
    return {'contract': contract, 'findings': findings, 'pov_comment_lines': comment_lines,
            'inputs': [chapter['path'] for chapter in chapters]}


def finding(category, path, line, quote, message):
    return {'id': f'{category}:{path}:{line}', 'category': category, 'blocking': True,
            'path': path, 'line': line, 'quote': quote, 'message': message}


def comment_lines(text, scene_break=DEFAULT_SCENE_BREAK):
    return [marker[0] for _, marker in metadata(text, scene_break)[1]
            if marker and marker[2] == 'comment' and marker[3]]
