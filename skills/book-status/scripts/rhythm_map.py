"""Whole-book pacing, POV distribution, promise density, and character-absence matrix."""
from collections import Counter
import re
import statistics

from promise_ledger import PromiseChapters, read_entries
from state_core import path_at, project_manifest_module
from state_packets import pov_labels, prose_lines


def _character_roster(root):
    char_dir = root / 'Wiki' / 'Characters'
    if not char_dir.is_dir():
        return []
    roster = []
    for cf in sorted(char_dir.glob('*.md')):
        if cf.stem.endswith('_sheet'):
            continue
        text = cf.read_text(encoding='utf-8')
        fm = re.search(r'^name:\s*["\']?([^"\'\n]+)["\']?', text, re.M)
        name = fm.group(1).strip() if fm else cf.stem.replace('_', ' ')
        first_token = name.split()[0] if name else ''
        terms = [t for t in dict.fromkeys((name, first_token)) if len(t) >= 2]
        if terms:
            roster.append((name, terms))
    return roster


def rhythm_map(root, book_id, *, gap_threshold=4, markdown=False):
    resolver = project_manifest_module()
    book_record = resolver.resolve_book(root, book_id)
    book_label = book_record.get('display_label', book_record['id'])
    ledger_status, promises = read_entries(root, f'Wiki/Story/{book_label}/promises.yaml')
    positions = PromiseChapters(book_record)
    opened = Counter(positions.position(p.get('introduced_ch')) for p in promises or [])
    paid = Counter(positions.position(p.get('paid_in_ch')) for p in promises or [])
    roster = _character_roster(root)

    rows = []
    pov_totals = {}
    char_appearances = {name: [] for name, _ in roster}

    for idx, ch in enumerate(sorted(book_record['chapters'], key=lambda c: c['reading_order']), start=1):
        p = path_at(root, ch['path'])
        if not p.is_file():
            continue
        raw = p.read_text(encoding='utf-8')
        lines = prose_lines(p)
        blob = ' '.join(lines)
        words = len(re.findall(r"[A-Za-z0-9']+", blob))
        breaks = len(re.findall(r'^[ \t]*(?:\*[ \t]*\*[ \t]*\*|---)[ \t]*$', raw, re.M))
        scenes = breaks + 1
        quoted_words = sum(len(re.findall(r"[A-Za-z0-9']+", m.group(1)))
                           for m in re.finditer(r'["“]([^"”]+)["”]', blob))
        dialogue_ratio = round(quoted_words / words, 3) if words else 0.0
        povs = pov_labels(raw[:800]) or ['unspecified']
        primary_pov = povs[0]

        mentioned = []
        for name, terms in roster:
            if any(re.search(rf'\b{re.escape(term)}\b', raw) for term in terms):
                mentioned.append(name)
                char_appearances[name].append(len(rows))

        entry = {
            'chapter': ch.get('display_label', ch['id']),
            'chapter_id': ch['id'],
            'reading_order': ch['reading_order'],
            'path': ch['path'],
            'order': idx,
            'words': words,
            'scenes': scenes,
            'dialogue_ratio': dialogue_ratio,
            'pov': povs,
            'promises_opened': opened[ch['reading_order']] if promises is not None else None,
            'promises_paid': paid[ch['reading_order']] if promises is not None else None,
            'characters': mentioned,
        }
        rows.append(entry)
        bucket = pov_totals.setdefault(primary_pov, {'chapters': 0, 'words': 0})
        bucket['chapters'] += 1
        bucket['words'] += words

    total_words = sum(r['words'] for r in rows)
    pov_share = {
        pov: {**stats, 'pct': round(stats['words'] / total_words * 100, 1) if total_words else 0.0}
        for pov, stats in sorted(pov_totals.items())
    }

    absence_gaps = []
    for name, indices in sorted(char_appearances.items()):
        for a, b in zip(indices, indices[1:]):
            gap = b - a - 1
            if gap > gap_threshold:
                absence_gaps.append({
                    'character': name,
                    'from_chapter': rows[a]['chapter'],
                    'to_chapter': rows[b]['chapter'],
                    'chapters_absent': gap,
                })

    word_counts = [r['words'] for r in rows]
    median_words = statistics.median(word_counts) if word_counts else 0
    word_count_outliers = []
    if median_words > 0:
        for r in rows:
            ratio = (r['words'] - median_words) / median_words
            if abs(ratio) > 0.35:
                word_count_outliers.append({
                    'chapter': r['chapter'],
                    'words': r['words'],
                    'median_words': median_words,
                    'delta_pct': round(ratio * 100, 1),
                })

    dialogue_streaks = []
    streak = []
    for r in rows:
        if r['dialogue_ratio'] < 0.10:
            streak.append(r['chapter'])
        else:
            if len(streak) >= 3:
                dialogue_streaks.append(list(streak))
            streak = []
    if len(streak) >= 3:
        dialogue_streaks.append(list(streak))

    result = {
        'book': book_label,
        'chapter_count': len(rows),
        'promise_ledger_status': ledger_status,
        'total_words': total_words,
        'median_words': median_words,
        'chapters': rows,
        'pov_share': pov_share,
        'absence_gaps': absence_gaps,
        'word_count_outliers': word_count_outliers,
        'dialogue_streaks': dialogue_streaks,
    }
    if markdown:
        lines = [
            f'# Rhythm & Thread Matrix — {book_label}',
            '',
            f'Chapters: {len(rows)} · Total words: {total_words:,} · Median chapter: {int(median_words):,} words',
            '',
            '| Chapter | Words | Scenes | Dialogue | POV | Promises (+ / paid) | Cast |',
            '|---|---:|---:|---:|---|---|---|',
        ]
        for r in rows:
            promise_counts = f"+{r['promises_opened']} / {r['promises_paid']}" if promises is not None else ledger_status
            lines.append(
                f"| {r['chapter']} | {r['words']} | {r['scenes']} | {r['dialogue_ratio']:.0%} | "
                f"{', '.join(r['pov'])} | {promise_counts} | {', '.join(r['characters']) or '—'} |"
            )
        if absence_gaps or word_count_outliers or dialogue_streaks:
            lines.extend(['', '## Macro Alerts', ''])
            for g in absence_gaps:
                lines.append(f"- **Absence gap:** {g['character']} absent {g['chapters_absent']} chapters ({g['from_chapter']} → {g['to_chapter']})")
            for o in word_count_outliers:
                lines.append(f"- **Word-count outlier:** {o['chapter']} ({o['words']} words, {o['delta_pct']:+.1f}% vs median)")
            for s in dialogue_streaks:
                lines.append(f"- **Low-dialogue streak (<10%):** {', '.join(s)}")
        result['markdown'] = '\n'.join(lines) + '\n'
    return result
