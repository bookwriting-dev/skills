"""Locate dated diction and written-out clock readings for contextual review."""
import argparse
from bisect import bisect_right
import json
from pathlib import Path
import re


SMALL = ('zero one two three four five six seven eight nine ten eleven twelve '
         'thirteen fourteen fifteen sixteen seventeen eighteen nineteen').split()
TENS = {'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50}
VALUES = {word: value for value, word in enumerate(SMALL)}
VALUES.update(TENS, oh=0)

HOUR_12 = '|'.join(SMALL[1:13])
UNIT = '|'.join(SMALL[1:10])
TEN_TO_NINETEEN = '|'.join(SMALL[10:])
# Permit a typographic hyphen or a single Markdown soft wrap between words.
JOIN = r'(?:[-‐‑]|[^\S\n]*\n[^\S\n]*|[^\S\n]+)'
HOUR = rf'twenty{JOIN}(?:one|two|three)|{"|".join(SMALL[1:])}|twenty'
MINUTE = rf'(?:(?:oh|zero){JOIN}(?:zero|{UNIT})|{TEN_TO_NINETEEN}|(?:{"|".join(TENS)})(?:{JOIN}(?:{UNIT}))?)'
MERIDIEM = r'(?:[ap]\.m\b\.?|[ap]m\b)'
DAYPART = r'in the (?:morning|afternoon|evening)\b|at night\b'
CLOCK = re.compile(
    rf'(?<![\w‐‑-])(?:'
    rf'(?:a{JOIN})?(?P<fraction>half{JOIN}past|quarter{JOIN}(?:past|after|to|till)){JOIN}(?P<relative_hour>{HOUR_12})'
    rf"|(?P<hour>{HOUR})(?:{JOIN}(?P<minute>{MINUTE})|{JOIN}o[’']clock"
    rf'|(?=[ \t]+{MERIDIEM})|(?=[ \t]+(?P<daypart>{DAYPART})))'
    rf')(?P<suffix>[ \t]+{MERIDIEM})?(?![\w‐‑-])', re.I)
DICTION = re.compile(
    r'\b(?:fortnight(?:ly|s)?|whilst|amongst|betwixt|ere|hither|thither|mayhap|perchance|'
    r'forsooth|henceforth|thou|thee|thy|thine|hath|doth)\b', re.I)
COUNT_UNIT = re.compile(
    r'[ \t]+(?:seconds?|minutes?|hours?|days?|weeks?|years?|dollars?|cents?|pounds?|feet|foot)\b', re.I)
CLOCK_CUE = re.compile(r'\b(?:at|around|until|clock (?:read|said|showed)|time was)[ \t]+$', re.I)

# Mask source apparatus in place so a finding still quotes the original span.
MARKUP = re.compile(
    r'\A\ufeff?---[ \t]*\r?\n(?=(?:[ \t]*\r?\n|#[^\n]*\n)*[\w-]+:).*?^---[ \t]*\r?$'
    r'|^[ \t]*(?P<fence>`{3,}|~{3,})[^\n]*\n.*?(?:^[ \t]*(?P=fence)[`~]*[ \t]*\r?$|\Z)'
    r'|<!--.*?(?:-->|\Z)'
    r'|(?P<ticks>`+)(?!`)(?:(?!\n[ \t]*\n).)*?(?<!`)(?P=ticks)(?!`)'
    r'|https?://[^\s)>]+'
    r'|^[ \t]*>[ \t]*\[![\w-]+\][^\n]*(?:\n[ \t]*>[^\n]*)*'
    r'|^[ \t]*(?:(?:\*\*)?POV(?:\*\*)?:|[-*][ \t]+\[[ x]\])[^\n]*', re.M | re.S | re.I)

DIALOGUE_SPAN = re.compile(r'["“][^"”\n]*["”]')


def number_value(words):
    return sum(VALUES[word] for word in re.findall(r'[a-z]+', words.lower()))


def clock_digits(match):
    suffix = match['suffix'] or ''
    if match['fraction']:
        hour = VALUES[match['relative_hour'].lower()]
        fraction = match['fraction'].lower()
        if fraction.endswith(('to', 'till')):
            if hour == 12:
                suffix = suffix.translate(str.maketrans('aApP', 'pPaA'))
            hour = hour - 1 or 12
            minute = 45
        else:
            minute = 30 if fraction.startswith('half') else 15
    else:
        hour = number_value(match['hour'])
        minute = number_value(match['minute'] or '')
    return f'{hour}:{minute:02d}{suffix}'


def scan(text, modern, *, clock_mode='digits', skip_dialogue=False):
    visible = MARKUP.sub(lambda match: re.sub(r'[^\r\n]', '\x00', match[0]), text)
    if skip_dialogue:
        visible = DIALOGUE_SPAN.sub(lambda match: re.sub(r'[^\r\n]', '\x00', match[0]), visible)
    newlines = [match.start() for match in re.finditer('\n', text)]
    candidates = []

    def add(match, category, **details):
        line = bisect_right(newlines, match.start())
        line_start = newlines[line - 1] + 1 if line else 0
        candidates.append({'line': line + 1, 'column': match.start() - line_start + 1,
                           'category': category, 'quote': text[match.start():match.end()], **details})

    if modern:
        for match in DICTION.finditer(visible):
            add(match, 'contemporary-diction')
    if clock_mode == 'digits':
        for match in CLOCK.finditer(visible):
            if match['minute'] and COUNT_UNIT.match(visible, match.end()):
                continue
            # A year ("nineteen thirty") or count ("take two at night") can resemble a time.
            prefix = visible[max(0, match.start() - 40):match.start()]
            needs_cue = match['daypart'] or (match['hour'] and number_value(match['hour']) > 12)
            if needs_cue and not CLOCK_CUE.search(prefix):
                continue
            add(match, 'clock-time', digits=clock_digits(match))
    return sorted(candidates, key=lambda item: (item['line'], item['column']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('chapters', nargs='+', type=Path)
    parser.add_argument('--modern', action='store_true', help='also check contemporary diction')
    parser.add_argument('--clock-mode', choices=('digits', 'words'), default='digits',
                        help='digits flags spelled-out clock times; words preserves spelled-out times')
    parser.add_argument('--skip-dialogue', action='store_true',
                        help='mask quoted dialogue spans so spoken diction and clock phrasing are preserved')
    args = parser.parse_args()
    results = []
    for path in args.chapters:
        try:
            text = path.read_bytes().decode('utf-8')
        except (OSError, UnicodeError) as exc:
            parser.exit(2, f'{path}: {exc}\n')
        results.append({'path': str(path), 'candidates': scan(
            text, args.modern, clock_mode=args.clock_mode, skip_dialogue=args.skip_dialogue)})
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
