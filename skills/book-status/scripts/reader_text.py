#!/usr/bin/env python3
"""Shared, fail-closed extraction of reader-facing manuscript text."""
import hashlib
import re


EXTRACTOR_VERSION = 1


def extract(text, *, source='<text>', scene_break='* * *', strip_pov=False):
    """Return classified reader text and a source-map/diagnostic record.

    Only explicitly recognized private apparatus is removed. Unknown comments,
    malformed private fences, and unclosed code fences fail with a line number.
    """
    original = text
    removed = []
    comment_start = text.find('<!--')
    comment_end = text.find('-->')
    if comment_start >= 0 and (comment_end < 0 or comment_end < comment_start):
        line = text.count('\n', 0, comment_start) + 1
        raise ValueError(f'{source}:{line}: unclosed or unknown HTML comment; classify or remove it')

    def classify_comment(match):
        value = match.group(0)
        line = text.count('\n', 0, match.start()) + 1
        if re.match(r'<!--\s*STORYCRAFT:', value, re.S):
            removed.append({'line': line, 'kind': 'private_comment'})
            return ''
        if strip_pov and re.fullmatch(r'<!--\s*POV:.*?-->', value, flags=re.S):
            removed.append({'line': line, 'kind': 'pov_comment'})
            return ''
        raise ValueError(f'{source}:{line}: unknown HTML comment; classify or remove it')

    text = re.sub(r'<!--.*?-->', classify_comment, text, flags=re.S)
    if '<!--' in text:
        offset = text.find('<!--')
        line = text.count('\n', 0, offset) + 1
        raise ValueError(f'{source}:{line}: unclosed HTML comment; classify or remove it')
    lines = text.splitlines()
    out = []
    fence = None
    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        if fence:
            if re.match(r'^\s*' + re.escape(fence) + r'\s*$', line):
                fence = None
            # Storycraft-internal fences are omitted; ordinary code is reader text.
            elif fence == '```storycraft-internal':
                continue
            else:
                out.append(line)
            continue

        if re.match(r'^\s*```storycraft-internal\s*$', line):
            fence = '```storycraft-internal'
            removed.append({'line': number, 'kind': 'private_fence'})
            continue
        if re.match(r'^\s*(```|~~~)', line):
            marker = re.match(r'^\s*(```|~~~)', line).group(1)
            out.append(line)
            fence = marker
            continue
        out.append(line)

    if fence:
        raise ValueError(f'{source}:{len(lines)}: unclosed fenced block; classify or close it')

    result = '\n'.join(out)
    # A recognized separator is a layout token, not private apparatus.
    if scene_break != '* * *':
        result = re.sub(r'(?m)^\s*\* \* \*\s*$', lambda _: scene_break, result)
    result = result.strip() + '\n'
    return {
        'text': result,
        'raw_sha256': hashlib.sha256(original.encode('utf-8')).hexdigest(),
        'reader_text_sha256': hashlib.sha256(result.encode('utf-8')).hexdigest(),
        'extractor_version': EXTRACTOR_VERSION,
        'removed': removed,
    }
