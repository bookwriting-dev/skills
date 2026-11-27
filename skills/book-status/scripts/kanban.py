#!/usr/bin/env python3
"""Deterministic per-book Kanban board renderer (Backlog, Ready, Drafting, Review, Done)."""
import argparse
from datetime import date
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from draft_promises import promise_context
from state_core import locked, path_at, project_manifest_module
from state_packets import pov_labels, prose_lines
from state_reviews import dashboard


def _outline_entries(root, book_label, project_type):
    """Index numbered headings and named manifest chapters by their complete label."""
    out = {}
    files = ([path_at(root, f'Wiki/Outline/{book_label}/plan.md'),
              path_at(root, f'Wiki/Outline/{book_label}/outline.md')]
             if project_type == 'NONFICTION'
             else [path_at(root, f'Wiki/Outline/{book_label}/outline.md'),
                   path_at(root, f'Wiki/Outline/{book_label}/plan.md')])
    for p in files:
        if not p.is_file():
            continue
        for heading in re.findall(r'^#{1,3}[ \t]+([^\n]+)', p.read_text(encoding='utf-8'), re.M):
            numbered = re.fullmatch(r'Chapter[- ]+(\d+)(?:\s*(?:[:–—-]|\.(?!\d))\s*(.*))?',
                                    heading.strip(), re.I)
            if numbered:
                out.setdefault(int(numbered[1]), (numbered[2] or '').strip())
            else:
                parts = re.split(r'\s*[:—–]\s*|\s+-\s+', heading.strip(), maxsplit=1)
                out.setdefault(parts[0].casefold(), parts[1].strip() if len(parts) > 1 else '')
    return out


def render_kanban(root, book_id, *, write_board=True):
    root = Path(root).resolve()
    resolver = project_manifest_module()
    book_record = resolver.resolve_book(root, book_id)
    book_label = book_record.get('display_label', book_record['id'])
    dash = dashboard(root, book_id)
    project_type = dash['project_type']
    outline = _outline_entries(root, book_label, project_type)

    agents = path_at(root, 'AGENTS.md')
    series_title = book_label
    if agents.is_file():
        hm = re.search(r'^#[ \t]+([^\n]+)', agents.read_text(encoding='utf-8'), re.M)
        if hm and not hm.group(1).startswith('__'):
            series_title = hm.group(1).strip()

    chapters = {ch['chapter_id']: ch for ch in dash['chapters']}
    rows = []
    numbered_chapters = set()
    for record in book_record['chapters']:
        order = record['reading_order']
        numbered = re.fullmatch(r'Chapter[- ](\d+)', record.get('display_label', ''), re.I)
        number = int(numbered[1]) if numbered else None
        if number is not None:
            numbered_chapters.add(number)
        rows.append((order, number, record))
    if book_record.get('chapter_order') == 'conventional':
        rows.extend((number, number, None) for number in outline
                    if isinstance(number, int) and number not in numbered_chapters)

    columns = {'Backlog': [], 'Ready': [], 'Drafting': [], 'Review': [], 'Done': []}
    highest_draft = None
    for order, num, record in sorted(rows, key=lambda row: row[0]):
        ch = chapters[record['id']] if record else None
        keys = [num]
        if record:
            keys.extend([record.get('display_label', record['id']).casefold(), record['id'].casefold()])
        outline_key = next((key for key in keys if key in outline), None)
        scene_path = record.get('scene_plan_path') if record else None
        if not scene_path and num is not None:
            scene_path = f'Wiki/Outline/{book_label}/Chapter_{num:02d}_Scene.md'
        scene_p = path_at(root, scene_path) if scene_path else None
        has_scene = scene_p is not None and scene_p.is_file()
        has_plan = (outline_key is not None or has_scene) if project_type == 'NONFICTION' else has_scene
        draft_p = path_at(root, ch['chapter']) if ch else None
        has_draft = bool(ch and ch['draft_exists'])
        if has_draft:
            highest_draft = order

        title = outline.get(outline_key, '')
        pov = ''
        words = 0
        if has_draft:
            raw = draft_p.read_text(encoding='utf-8', errors='replace')
            words = len(' '.join(prose_lines(draft_p)).split())
            hm = re.search(r'^#[ \t]+Chapter[ \t]+0*\d+(?:[ \t]*[:.–—-][ \t]*([^\n]+))?', raw, re.M | re.I)
            if hm and hm.group(1) and not title:
                title = hm.group(1).strip()
            povs = pov_labels(raw[:800])
            pov = povs[0] if povs else ''
        elif has_scene:
            stext = scene_p.read_text(encoding='utf-8', errors='replace')
            hm = re.search(r'^#[ \t]+Chapter[ \t]+0*\d+(?:[ \t]*[:.–—-][ \t]*([^\n]+))?', stext, re.M | re.I)
            if hm and hm.group(1) and not title:
                title = hm.group(1).strip()
            povs = pov_labels(stext)
            pov = povs[0] if povs else ''

        flags = []
        if outline_key is None:
            flags.append('no-outline-entry')
        if has_draft and not has_plan and project_type != 'NONFICTION':
            flags.append('no-scene-plan')

        checks = ch['checks'] if ch else []
        any_report = any(path_at(root, c['path']).with_suffix('.md').is_file() or c['verdict'] != 'UNKNOWN'
                         for c in checks)
        if ch and any(c['blocking'] for c in checks):
            flags.append('unapplied-review-findings')

        if ch and ch['ready'] and all(c.get('sealed', True) for c in dash['campaigns'] if not c.get('cancelled')):
            col = 'Done'
            verdict_str = 'PASS'
        elif any_report:
            col = 'Review'
            req = [c['verdict'] for c in checks if c['required']]
            verdict_str = '/'.join(req) if req else 'PENDING'
        elif has_draft:
            col = 'Drafting'
            verdict_str = 'unchecked'
        elif has_plan:
            col = 'Ready'
            verdict_str = ''
        else:
            col = 'Backlog'
            verdict_str = ''

        if num is None:
            parts = [ch['display_label']]
            if title:
                parts.append(title)
        else:
            parts = [f'{num:03d}', title or 'untitled']
        if pov:
            parts.append(f'POV: {pov}')
        if has_draft:
            parts.append(f'{words:,} words')
        if verdict_str:
            parts.append(f'gate: {verdict_str}')
        line = '- `' + ' — '.join(parts) + '`' + ((' [' + ', '.join(flags) + ']') if flags else '')
        columns[col].append(line)

    horizon = highest_draft if highest_draft is not None else max((row[0] for row in rows), default=0)
    promises = promise_context(root, book_record, {'reading_order': horizon})
    overdue = None
    if promises['status'] == 'available':
        overdue = sum(item['status'] == 'overdue' for item in promises['items'])
    overdue_label = overdue if overdue is not None else promises['status']
    counts = {k: len(v) for k, v in columns.items()}
    today = date.today().isoformat()
    book_num_m = re.search(r'\d+', book_label)
    book_num = book_num_m.group(0) if book_num_m else book_label
    lines = [
        f'# {series_title} — Book {book_num} board',
        '',
        (f"Refreshed {today} — Backlog {counts['Backlog']} · Ready {counts['Ready']} · "
         f"Drafting {counts['Drafting']} · Review {counts['Review']} · "
         f"Done {counts['Done']} · Overdue promises {overdue_label}"),
        '',
    ]
    for col in ('Backlog', 'Ready', 'Drafting', 'Review', 'Done'):
        lines.append(f'## {col}')
        lines.append('')
        lines.extend(columns[col] or ['- *(empty)*'])
        lines.append('')
    markdown = '\n'.join(lines)

    out_rel = f'Wiki/Story/{book_label}/kanban.md'
    if write_board:
        out = path_at(root, out_rel)
        with locked(out):
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(markdown, encoding='utf-8')
    return {
        'path': out_rel,
        'written': bool(write_board),
        'refreshed': today,
        'counts': counts,
        'overdue_promises': overdue,
        'promise_ledger_status': promises['status'],
        'markdown': markdown,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--book', default='Book-1')
    ap.add_argument('--no-write', action='store_true')
    a = ap.parse_args()
    print(json.dumps(render_kanban(a.root, a.book, write_board=not a.no_write),
                     indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
