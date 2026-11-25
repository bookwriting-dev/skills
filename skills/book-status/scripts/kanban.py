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

from state_core import locked, path_at, project_manifest_module
from state_packets import pov_labels, prose_lines
from state_reviews import dashboard


def _outline_entries(root, book_label, project_type):
    """Return {chapter_num: title} from outline.md (fiction/hybrid) or plan.md (nonfiction)."""
    out = {}
    files = ([path_at(root, f'Wiki/Outline/{book_label}/plan.md'),
              path_at(root, f'Wiki/Outline/{book_label}/outline.md')]
             if project_type == 'NONFICTION'
             else [path_at(root, f'Wiki/Outline/{book_label}/outline.md'),
                   path_at(root, f'Wiki/Outline/{book_label}/plan.md')])
    for p in files:
        if not p.is_file():
            continue
        for m in re.finditer(r'^#{1,3}[ \t]+Chapter[ \t]+0*(\d+)(?:[ \t]*[:.–—-][ \t]*([^\n]+))?',
                             p.read_text(encoding='utf-8'), re.M | re.I):
            num = int(m.group(1))
            if num not in out:
                out[num] = (m.group(2) or '').strip()
    return out


def _overdue_promises(root, book_label, highest_ch):
    p = path_at(root, f'Wiki/Story/{book_label}/promises.yaml')
    if not p.is_file() or highest_ch < 1:
        return 0
    try:
        import yaml
        data = yaml.safe_load(p.read_text(encoding='utf-8')) or {}
    except Exception:
        return 0
    overdue = 0
    for item in data.get('promises') or []:
        if not isinstance(item, dict) or not str(item.get('promise') or '').strip():
            continue
        if str(item.get('paid_in_ch') or '').strip() or item.get('deferred_to_series'):
            continue
        m = re.search(r'\d+', str(item.get('payoff_by_ch') or ''))
        if m and int(m.group(0)) < highest_ch:
            overdue += 1
    return overdue


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

    by_num = {}
    for ch in dash['chapters']:
        m = re.search(r'\d+', ch.get('report_stem') or ch.get('display_label') or '')
        num = int(m.group(0)) if m else None
        if num is not None:
            by_num[num] = ch
    all_nums = sorted(set(outline) | set(by_num))

    columns = {'Backlog': [], 'Ready': [], 'Drafting': [], 'Review': [], 'Done': []}
    highest_draft = 0
    for num in all_nums:
        ch = by_num.get(num)
        scene_p = path_at(root, f'Wiki/Outline/{book_label}/Chapter_{num:02d}_Scene.md')
        has_plan = (num in outline) if project_type == 'NONFICTION' else scene_p.is_file()
        draft_p = path_at(root, ch['chapter']) if ch else None
        has_draft = bool(ch and ch['draft_exists'] and draft_p and draft_p.is_file())
        if has_draft:
            highest_draft = max(highest_draft, num)

        title = outline.get(num) or ''
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
        elif scene_p.is_file():
            stext = scene_p.read_text(encoding='utf-8', errors='replace')
            hm = re.search(r'^#[ \t]+Chapter[ \t]+0*\d+(?:[ \t]*[:.–—-][ \t]*([^\n]+))?', stext, re.M | re.I)
            if hm and hm.group(1) and not title:
                title = hm.group(1).strip()
            povs = pov_labels(stext)
            pov = povs[0] if povs else ''

        title = title or 'untitled'
        flags = []
        if num not in outline:
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

        parts = [f'{num:03d}', title]
        if pov:
            parts.append(f'POV: {pov}')
        if has_draft:
            parts.append(f'{words:,} words')
        if verdict_str:
            parts.append(f'gate: {verdict_str}')
        line = '- `' + ' — '.join(parts) + '`' + ((' [' + ', '.join(flags) + ']') if flags else '')
        columns[col].append(line)

    overdue = _overdue_promises(root, book_label, highest_draft or (max(all_nums) if all_nums else 0))
    counts = {k: len(v) for k, v in columns.items()}
    today = date.today().isoformat()
    book_num_m = re.search(r'\d+', book_label)
    book_num = book_num_m.group(0) if book_num_m else book_label
    lines = [
        f'# {series_title} — Book {book_num} board',
        '',
        (f"Refreshed {today} — Backlog {counts['Backlog']} · Ready {counts['Ready']} · "
         f"Drafting {counts['Drafting']} · Review {counts['Review']} · "
         f"Done {counts['Done']} · Overdue promises {overdue}"),
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
