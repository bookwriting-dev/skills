#!/usr/bin/env python3
"""Shared, fail-closed extraction of reader-facing manuscript text."""
import hashlib
import re


EXTRACTOR_VERSION = 2


def extract(text, *, source='<text>', scene_break='* * *', strip_pov=False, pov_comment_lines=()):
    """Return classified reader text and a source-map/diagnostic record.

    Only explicitly recognized private apparatus is removed. Unknown comments,
    malformed private fences, and unclosed code fences fail with a line number.
    """
    original = text
    removed = []
    hidden = []
    comment_start = text.find('<!--')
    comment_end = text.find('-->')
    if comment_start >= 0 and (comment_end < 0 or comment_end < comment_start):
        line = text.count('\n', 0, comment_start) + 1
        raise ValueError(f'{source}:{line}: unclosed or unknown HTML comment; classify or remove it')

    def classify_comment(match):
        value = match.group(0)
        hidden.append((match.start(), match.end()))
        line = text.count('\n', 0, match.start()) + 1
        if re.match(r'<!--\s*STORYCRAFT:', value, re.S):
            removed.append({'line': line, 'kind': 'private_comment'})
            return ''
        if (strip_pov or line in pov_comment_lines) and re.fullmatch(r'<!--\s*POV:.*?-->', value, flags=re.S):
            removed.append({'line': line, 'kind': 'pov_comment'})
            return ''
        raise ValueError(f'{source}:{line}: unknown HTML comment; classify or remove it')

    text = re.sub(r'<!--.*?-->', classify_comment, text, flags=re.S)
    if '<!--' in text:
        offset = text.find('<!--')
        line = text.count('\n', 0, offset) + 1
        raise ValueError(f'{source}:{line}: unclosed HTML comment; classify or remove it')
    # Reject Obsidian %% ... %% comments and CriticMarkup {>>...<<} notes rather than
    # leaking private authoring markup into reader builds.
    for marker_name, pat in (
        ('Obsidian comment', re.compile(r'%%.*?%%', re.S)),
        ('unclosed Obsidian comment', re.compile(r'%%')),
        ('CriticMarkup annotation', re.compile(r'\{(?:>>|==|\+\+|--|~~).*?(?:<<|==|\+\+|--|~~)\}', re.S)),
    ):
        m = pat.search(text)
        if m:
            line = text.count('\n', 0, m.start()) + 1
            raise ValueError(f'{source}:{line}: unknown {marker_name}; classify or remove it')
    # Preserve source line coordinates even when a private comment spans several lines.
    raw_lines = [1]
    skip = iter(hidden)
    span = next(skip,None)
    for raw_line,match in enumerate(re.finditer(r'\r\n|\r|\n',original),2):
        while span and span[1] <= match.start():
            span = next(skip,None)
        if not span or match.start() < span[0]:
            raw_lines.append(raw_line)
    lines = text.splitlines()
    source_rows = []
    out = []
    fence = None
    for number, line in zip(raw_lines,lines):
        stripped = line.strip()
        if fence:
            if re.fullmatch(re.escape(fence[0]) + '{' + str(len(fence)) + ',}', stripped):
                fence = None
            if not private:
                out.append(line)
                source_rows.append(number)
            continue
        opening = re.match(r'^\s*(\x60{3,}|~{3,})(.*)$', line)
        if opening:
            fence = opening[1]
            private = opening[2].strip() == 'storycraft-internal'
            if private:
                removed.append({'line':number, 'kind':'private_fence'})
                continue
        out.append(line)
        source_rows.append(number)

    if fence:
        raise ValueError(f'{source}:{len(lines)}: unclosed fenced block; classify or close it')

    result = '\n'.join(out)
    # A recognized separator is a layout token, not private apparatus.
    if scene_break != '* * *':
        result = re.sub(r'(?m)^[ \t]*\* \* \*[ \t]*$', lambda _: scene_break, result)
    leading = result[:len(result)-len(result.lstrip())].count('\n')
    result = result.strip() + '\n'
    source_rows = source_rows[leading:leading+len(result.splitlines())]
    return {
        'text': result,
        'raw_sha256': hashlib.sha256(original.encode('utf-8')).hexdigest(),
        'reader_text_sha256': hashlib.sha256(result.encode('utf-8')).hexdigest(),
        'extractor_version': EXTRACTOR_VERSION,
        'removed': removed,
        'source_lines': source_rows,
    }
