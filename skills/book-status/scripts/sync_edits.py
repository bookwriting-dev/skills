"""Author-edited diff sync: compare manually edited chapters against a baseline and report affected records."""
import difflib
import json
from pathlib import Path
import re
import subprocess

import editions
from state_core import (
    continuity_module, digest, document, ledger_store_module, load, path_at,
    project_manifest_module,
)
from state_packets import prose_lines
from state_reviews import chapter_report_paths, freshness


def _split_paragraphs(text):
    blocks = [b.strip() for b in re.split(r'\n\s*\n', text.strip()) if b.strip()]
    return blocks


def _surface_metrics(text):
    lines = prose_lines_from_text(text)
    blob = ' '.join(lines)
    words = re.findall(r"[A-Za-z0-9']+", blob)
    sents = [s.strip() for s in re.split(r'[.!?]+(?:\s|$)', blob) if len(s.split()) >= 1]
    similes = len(re.findall(r'\b(?:like\s+(?:a|an|the)\s+[a-z]+|as\s+if\s+)', blob, re.I))
    em_dashes = blob.count('—') + blob.count('--')
    quoted_words = sum(len(re.findall(r"[A-Za-z0-9']+", m.group(1)))
                       for m in re.finditer(r'["“]([^"”]+)["”]', blob))
    return {
        'words': len(words),
        'sentences': len(sents),
        'avg_sentence_len': round(len(words) / len(sents), 2) if sents else 0.0,
        'similes': similes,
        'em_dashes': em_dashes,
        'dialogue_ratio': round(quoted_words / len(words), 3) if words else 0.0,
    }


def prose_lines_from_text(text):
    lines = []
    in_fence = False
    for raw in text.splitlines():
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


def _resolve_baseline(root, book_label, chapter_record, baseline_arg, current_text=None):
    if baseline_arg:
        bp = Path(baseline_arg)
        if not bp.is_absolute():
            bp = path_at(root, baseline_arg)
        if not bp.is_file():
            raise ValueError('baseline file not found: ' + str(baseline_arg))
        return bp.read_text(encoding='utf-8'), f'file:{baseline_arg}'

    # Check latest frozen beta edition archive on disk
    beta_manifest = path_at(root, f'Chapters/{book_label}/export/beta/export-manifest.json')
    if beta_manifest.is_file():
        try:
            export_id = (load(beta_manifest).get('beta_feedback') or {}).get('export_id')
            if export_id:
                beta_ed = editions.open_beta(root, book_label, export_id)
                sec = next((s for s in beta_ed.get('sections', [])
                            if s.get('path') == chapter_record['path'] or s.get('chapter_id') == chapter_record['id']), None)
                if sec and sec.get('reader_text') is not None:
                    return sec['reader_text'], f'edition:{export_id}'
        except (ValueError, OSError):
            pass

    # Check git HEAD (or parent commit if the author already committed their edit)
    if (root / '.git').exists():
        proc = subprocess.run(
            ['git', 'show', f"HEAD:{chapter_record['path']}"],
            cwd=root, capture_output=True, text=True, check=False,
        )
        if proc.returncode == 0:
            if current_text is None or proc.stdout != current_text:
                return proc.stdout, 'git:HEAD'
            log = subprocess.run(
                ['git', 'log', '-n', '2', '--format=%H', '--', chapter_record['path']],
                cwd=root, capture_output=True, text=True, check=False,
            )
            commits = [line.strip() for line in log.stdout.splitlines() if line.strip()]
            if len(commits) >= 2:
                prev = subprocess.run(
                    ['git', 'show', f"{commits[1]}:{chapter_record['path']}"],
                    cwd=root, capture_output=True, text=True, check=False,
                )
                if prev.returncode == 0:
                    return prev.stdout, f'git:{commits[1][:7]}'
            return proc.stdout, 'git:HEAD'

    return None, 'none'


def sync_edits(root, book_id, chapter_selector, *, baseline=None):
    resolver = project_manifest_module()
    book_record, chapter_record = resolver.resolve_chapter(root, book_id, chapter_selector)
    book_label = book_record.get('display_label', book_record['id'])
    ch_path = path_at(root, chapter_record['path'])
    if not ch_path.is_file():
        raise ValueError('chapter file does not exist: ' + chapter_record['path'])
    current_text = ch_path.read_text(encoding='utf-8')
    baseline_text, baseline_source = _resolve_baseline(root, book_label, chapter_record, baseline, current_text)

    changed_paragraphs = []
    candidates = []
    if baseline_text is not None:
        old_paras = _split_paragraphs(baseline_text)
        new_paras = _split_paragraphs(current_text)
        matcher = difflib.SequenceMatcher(None, old_paras, new_paras)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                continue
            before_ex = ' '.join(old_paras[i1:i2])[:200]
            after_ex = ' '.join(new_paras[j1:j2])[:200]
            old_w = len(re.findall(r'\w+', ' '.join(old_paras[i1:i2])))
            new_w = len(re.findall(r'\w+', ' '.join(new_paras[j1:j2])))
            changed_paragraphs.append({
                'index': j1 + 1,
                'status': 'modified' if tag == 'replace' else ('added' if tag == 'insert' else 'removed'),
                'before_excerpt': before_ex,
                'after_excerpt': after_ex,
                'word_delta': new_w - old_w,
            })

        before_m = _surface_metrics(baseline_text)
        after_m = _surface_metrics(current_text)
        if after_m['similes'] < before_m['similes']:
            candidates.append({
                'rule_category': 'simile',
                'signal': f"net removal of {before_m['similes'] - after_m['similes']} simile construction(s)",
                'advisory_only': True,
            })
        if after_m['em_dashes'] < before_m['em_dashes']:
            candidates.append({
                'rule_category': 'punctuation',
                'signal': f"net removal of {before_m['em_dashes'] - after_m['em_dashes']} em-dash/double-dash mark(s)",
                'advisory_only': True,
            })
        len_delta = round(after_m['avg_sentence_len'] - before_m['avg_sentence_len'], 2)
        if abs(len_delta) >= 2.0:
            direction = 'shorter' if len_delta < 0 else 'longer'
            candidates.append({
                'rule_category': 'cadence',
                'signal': f'average sentence length shifted {len_delta:+.2f} words ({direction} sentences)',
                'advisory_only': True,
            })
        dial_delta = round(after_m['dialogue_ratio'] - before_m['dialogue_ratio'], 3)
        if abs(dial_delta) >= 0.05:
            candidates.append({
                'rule_category': 'dialogue',
                'signal': f'dialogue ratio shifted {dial_delta:+.1%}',
                'advisory_only': True,
            })

    # Continuity claims whose quote no longer appears
    affected_continuity = []
    cont_name = continuity_module().filename(chapter_record['id'])
    cont_file = path_at(root, f'_Edits/{book_label}/continuity/{cont_name}')
    if cont_file.is_file():
        cdata = json.loads(cont_file.read_text(encoding='utf-8'))
        for claim in cdata.get('claims', []):
            q = claim.get('quote', '')
            if q and q not in current_text:
                affected_continuity.append({'key': claim.get('key'), 'kind': claim.get('kind'), 'quote': q})

    # Knowledge events referencing this chapter whose quote no longer matches
    affected_knowledge = []
    store = ledger_store_module()
    gk = store.load_ledger(root, 'Wiki/Story/knowledge-events.json')
    events = gk.get('events', []) if gk else []
    legacy_k = path_at(root, f'Wiki/Story/{book_label}/knowledge.json')
    if legacy_k.is_file():
        events = [*events, *document(legacy_k, 'events').get('events', [])]
    for ev in events:
        if ev.get('source') == chapter_record['path']:
            q = ev.get('quote', '')
            if q and q not in current_text:
                affected_knowledge.append({'id': ev.get('id'), 'fact_id': ev.get('fact_id'), 'quote': q})

    # Stale reports
    stale_reports = []
    for meta in chapter_report_paths(root, book_label, chapter_record):
        if meta.is_file():
            st = freshness(root, meta)
            if st['freshness'] != 'CURRENT':
                stale_reports.append({'meta': str(meta.relative_to(root)), **st})

    return {
        'chapter': chapter_record['path'],
        'chapter_sha256': digest(ch_path),
        'baseline_source': baseline_source,
        'changed_paragraphs': changed_paragraphs,
        'affected_continuity_claims': affected_continuity,
        'affected_knowledge_events': affected_knowledge,
        'stale_reports': stale_reports,
        'editorial_memory_candidates': candidates,
    }
