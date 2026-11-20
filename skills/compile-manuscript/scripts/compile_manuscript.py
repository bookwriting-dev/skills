#!/usr/bin/env python3
"""Build manuscript exports without changing source chapters."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
import sys
sys.dont_write_bytecode = True
import beta_exchange


def state_module():
    p = Path(__file__).resolve().parents[2] / 'book-status/scripts/project_state.py'
    spec = importlib.util.spec_from_file_location('storycraft_state', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def reader_text_module():
    p = Path(__file__).resolve().parents[2] / 'book-status/scripts/reader_text.py'
    spec = importlib.util.spec_from_file_location('storycraft_reader_text', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def manifest_module():
    p = Path(__file__).resolve().parents[2] / 'book-status/scripts/project_manifest.py'
    spec = importlib.util.spec_from_file_location('storycraft_project_manifest', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def clean(text, marker, source, pov_comment_lines=()):
    return reader_text_module().extract(
        text, source=source, scene_break=marker, pov_comment_lines=pov_comment_lines
    )['text']


def verify(path, fmt):
    if not path.exists() or path.stat().st_size == 0:
        raise ValueError('empty export: ' + str(path))
    if fmt in ('docx', 'epub'):
        with zipfile.ZipFile(path) as z:
            if z.testzip():
                raise ValueError('corrupt export ZIP')
            if fmt == 'docx' and 'word/document.xml' not in z.namelist():
                raise ValueError('missing DOCX document')
            if fmt == 'epub' and (z.read('mimetype') != b'application/epub+zip' or not any(n.endswith('.opf') for n in z.namelist())):
                raise ValueError('missing EPUB package')
    if fmt == 'pdf' and not path.read_bytes().startswith(b'%PDF-'):
        raise ValueError('invalid PDF header')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--book', default='Book-1')
    ap.add_argument('--profile', choices=['beta', 'submission', 'publication'], default='beta')
    ap.add_argument('--format', action='append', choices=['md', 'docx', 'epub', 'pdf'])
    ap.add_argument('--config', type=Path)
    ap.add_argument('--pdf-engine')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--unchecked-preview', action='store_true')
    a = ap.parse_args()
    s = state_module()
    root = a.root.resolve()
    if not re.fullmatch(r'Book-\d+', a.book):
        raise ValueError('invalid book')
    cfg = s.load(a.config) if a.config else {'schema_version': 1}
    config_sha256 = hashlib.sha256(a.config.read_bytes()).hexdigest() if a.config else None
    resolver = manifest_module()
    manifest_hash = s.digest(s.path_at(root, resolver.MANIFEST_PATH))
    book_record = resolver.resolve_book(root, a.book)
    missing = resolver.missing_chapters(root, book_record)
    missing_paths = {item['path'] for item in missing if 'path' in item}
    chapters = []
    for chapter in sorted(book_record['chapters'], key=lambda c: c['reading_order']):
        if chapter['path'] in missing_paths:
            continue
        source_path = s.path_at(root, chapter['path'])
        if cfg.get('chapter_dir') and not source_path.is_relative_to(s.path_at(root, cfg['chapter_dir'])):
            raise ValueError('manifest chapter is outside configured chapter_dir: ' + chapter['path'])
        chapters.append((chapter['reading_order'], source_path, chapter))
    if not chapters:
        labels = ', '.join(item['label'] for item in missing)
        raise ValueError('no drafted chapters for ' + a.book + (f'; missing {labels}' if labels else ''))
    formats = list(dict.fromkeys(a.format or ['md']))
    pandoc = shutil.which('pandoc')
    if any(f != 'md' for f in formats) and not pandoc:
        raise ValueError('requested format requires pandoc')
    engine = a.pdf_engine or cfg.get('pdf_engine')
    if 'pdf' in formats and (not engine or not shutil.which(engine)):
        raise ValueError('PDF requires an explicitly configured available PDF engine')
    warnings = [f"missing expected chapter: {item['label']}" for item in missing]
    workflow = resolver.workflow(root, book_record, cfg.get('required_checks'))
    required = workflow['required_checks']
    required_meta = []
    review_results = []
    for _, p, chapter_record in chapters:
        for check in required:
            meta = s.chapter_report_paths(root, a.book, chapter_record, check)[0]
            required_meta.append(meta)
            status = s.readiness(root, meta, [str(p.relative_to(root))], profile=cfg.get('completion_profile', 'draft_verified'))
            review_results.append({'chapter': chapter_record['id'], 'check': check,
                                   'metadata': str(meta.relative_to(root)), **status})
            if status['readiness'] != 'ELIGIBLE':
                reason = ', '.join(status['blocking_reasons'])
                warnings.append(f'{p.name}: {check} {status["readiness"]} ({reason})')
    dash = s.dashboard(root, a.book)
    for chapter in dash['chapters']:
        for check in chapter['checks']:
            if check['blocking']:
                warnings.append('unresolved blocking findings: ' + check['path'])
    for campaign in dash['campaigns']:
        if not campaign['current']:
            warnings.append('campaign verification stale or incomplete: ' + campaign['path'])
    for cp in (root / '_Edits' / a.book / 'campaigns').glob('*/campaign.json'):
        if any(t['status'] != 'complete' for t in s.load(cp)['tasks']):
            warnings.append('unfinished campaign: ' + str(cp.relative_to(root)))
    import_dir = f'Chapters/{a.book}'
    import_receipt = f'{import_dir}/.storycraft-import.json'
    imported_front = f'{import_dir}/FrontMatter.md'
    front_matter = cfg.get('front_matter')
    if front_matter is None:
        receipt = s.path_at(root, import_receipt)
        front_matter = ([imported_front] if receipt.is_file()
                        and 'FrontMatter.md' in s.load(receipt).get('files', {}) else [])
    back_matter = cfg.get('back_matter', [])
    order = front_matter + [str(p.relative_to(root)) for _, p, _ in chapters] + back_matter
    names = list(order)
    if cfg.get('reference_doc'):
        names.append(cfg['reference_doc'])
    before = s.evidence(root, names)
    if any(e.get('sha256') is None for e in before):
        raise ValueError('missing source/front/back matter')
    validation_names = [*names, resolver.MANIFEST_PATH, 'AGENTS.md', import_receipt, *missing_paths]
    if book_record.get('chapter_order') == 'conventional':
        validation_names.extend(resolver.outline_paths(book_record))
    validation_names.append(s.continuity_dir(book_record))
    for meta_path in required_meta:
        validation_names.append(str(meta_path.relative_to(root)))
        if meta_path.is_file():
            meta_record = s.load(meta_path)
            if isinstance(meta_record.get('report'), str):
                validation_names.append(meta_record['report'])
    disposition_path = f'_Edits/{a.book}/decisions.jsonl'
    validation_names.append(disposition_path)
    validation_names.extend(str(p.relative_to(root)) for p in
                            (root / '_Edits' / a.book / 'campaigns').glob('*/campaign.json'))
    validation_names = sorted(set(validation_names))
    validation_before = s.evidence(root, validation_names)
    source_texts = s.manuscript_texts(root, book_record)
    manuscript_hashes = {entry['path']: entry['sha256'] for entry in before}
    if any(hashlib.sha256(raw.encode('utf-8')).hexdigest() != manuscript_hashes[name]
           for name, raw in source_texts.items()):
        raise ValueError('manuscript changed while reading preflight inputs')
    formatting = s.chapter_format_module().audit(book_record, source_texts)
    for finding in formatting['findings']:
        warnings.append(f"{finding['path']}:{finding['line']}: {finding['message']}")
    blockers = list(warnings)
    continuity = s.continuity_report(root, book_record, source_texts)
    validation_map = {entry['path']: entry for entry in validation_before}
    for path, sha256 in continuity['source_inputs'].items():
        observed = {'path': path, 'kind': 'file', 'sha256': sha256}
        if validation_map.setdefault(path, observed) != observed:
            raise ValueError('source evidence changed during export preflight: ' + path)
    validation_names = sorted(validation_map)
    validation_before = [validation_map[name] for name in validation_names]
    if continuity['active']:
        for item in continuity['coverage']:
            if item['status'] != 'CURRENT':
                warning = f"{item['path']}: {item['status'].lower()} continuity review coverage"
                warnings.append(warning)
                blockers.append(warning)
        for finding in continuity['findings']:
            locations = ', '.join(f"{source['path']}:{source['line']}" for source in finding['sources'])
            warning = f"{locations}: {finding['message']}"
            warnings.append(warning)
            if finding['blocking']:
                blockers.append(warning)
    if blockers and a.profile != 'beta' and not a.unchecked_preview:
        raise ValueError('release checks incomplete: ' + '; '.join(blockers))
    # Assemble and validate reader-facing content before either preflight returns
    # or a converter is invoked. This keeps deterministic content failures equal.
    parts = []
    for name in order:
        raw = source_texts[name] if name in source_texts else s.path_at(root, name).read_text(encoding='utf-8')
        parts.append((name, clean(raw, cfg.get('scene_break', '* * *'), name,
                                  formatting['pov_comment_lines'].get(name, ()))))
    text = '\n\n'.join(part for _, part in parts)
    if (s.evidence(root, validation_names) != validation_before
            or s.evidence(root, names) != before
            or s.digest(s.path_at(root, resolver.MANIFEST_PATH)) != manifest_hash
            or resolver.resolve_book(root, a.book) != book_record
            or resolver.missing_chapters(root, book_record) != missing
            or resolver.workflow(root, book_record, cfg.get('required_checks')) != workflow
            or (a.config and s.digest(a.config) != config_sha256)):
        raise ValueError('source or required readiness evidence changed during preflight')
    reader_text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
    plan = {'schema_version': 1, 'sources': before, 'profile': a.profile, 'formats': formats,
            'warnings': warnings, 'unchecked_preview': a.unchecked_preview,
            'missing_chapters': missing, **workflow, 'reviews': review_results,
            'format_findings': formatting['findings'], 'continuity': continuity,
            'pandoc': subprocess.check_output([pandoc, '--version'], text=True).splitlines()[0] if pandoc else None,
            'pdf_engine': engine, 'config': cfg, 'config_sha256': config_sha256,
            'validation_inputs': validation_before, 'reader_text_sha256': reader_text_hash,
            'extractor_version': reader_text_module().EXTRACTOR_VERSION,
            'delivery_status': 'PREFLIGHTED_NOT_BUILT',
            'structural_checks': {fmt: 'NOT_BUILT' for fmt in formats},
            'rendered_review': {'status': 'PENDING',
                                'formats': {fmt: 'PENDING' for fmt in formats},
                                'reason': 'structure checks do not inspect reader-visible layout'}}
    if a.check:
        print(json.dumps(plan, indent=2))
        return
    out = s.path_at(root, f'Chapters/{a.book}/export/{a.profile}')
    out.parent.mkdir(parents=True, exist_ok=True)
    with s.locked(out):
        with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
            stage = Path(tmp)
            md = stage / 'manuscript-combined.md'
            md.write_text(text)
            exchange = None
            if a.profile == 'beta':
                exchange = beta_exchange.build_map(parts, {record['path']: record for _, _, record in chapters},
                                                   manuscript_hashes, cfg.get('scene_break', formatting['contract']['scene_break']))
            for fmt in formats:
                target = stage / ('manuscript-combined.' + fmt)
                if fmt != 'md':
                    source, source_format = md, 'markdown'
                    if exchange is not None and fmt == 'docx':
                        source = beta_exchange.docx_input(pandoc, stage, exchange)
                        source_format = 'json'
                    cmd = [pandoc, str(source), '--from=' + source_format, '--standalone', '-o', str(target)]
                    if cfg.get('title'):
                        cmd += ['--metadata', 'title=' + cfg['title']]
                    if cfg.get('toc', a.profile != 'submission'):
                        cmd += ['--toc']
                    if fmt == 'pdf':
                        cmd += ['--pdf-engine', engine]
                    if cfg.get('reference_doc') and fmt == 'docx':
                        cmd += ['--reference-doc', str(s.path_at(root, cfg['reference_doc']))]
                    converted = subprocess.run(cmd, capture_output=True, text=True)
                    if converted.returncode:
                        raise ValueError(f'Pandoc {fmt} conversion failed: {converted.stderr.strip()}')
                    if exchange is not None and fmt == 'docx':
                        source.unlink()
                        beta_exchange.bind_word_passages(target, exchange)
                verify(target, fmt)
                plan['structural_checks'][fmt] = 'PASS'
            if (s.evidence(root, validation_names) != validation_before
                    or resolver.resolve_book(root, a.book) != book_record
                    or resolver.missing_chapters(root, book_record) != missing):
                raise ValueError('source or required readiness evidence changed during export; rerun preflight')
            if a.config and hashlib.sha256(a.config.read_bytes()).hexdigest() != config_sha256:
                raise ValueError('export configuration changed during conversion; rerun preflight')
            plan['outputs'] = {p.name: s.digest(p) for p in stage.iterdir() if p.suffix[1:] in formats}
            if exchange is not None:
                beta_map = stage / 'beta-passages.json'
                s.write(beta_map, exchange)
                plan['beta_feedback'] = {'export_id': exchange['export_id'],
                                         'map': beta_map.name, 'sha256': s.digest(beta_map)}
            plan['delivery_status'] = 'PREVIEW_UNCHECKED' if a.unchecked_preview else 'BUILT_PENDING_RENDERED_REVIEW'
            s.write(stage / 'export-manifest.json', plan)
            # Keep previous package recoverable until the entire new package is valid.
            backup = out.with_name(out.name + f'.previous-{time.time_ns()}')
            if out.exists():
                out.rename(backup)
            try:
                stage.rename(out)
            except Exception:
                if out.exists():
                    shutil.rmtree(out)
                if backup.exists():
                    backup.rename(out)
                raise
    print(json.dumps({'output': str(out), **plan}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as e:
        raise SystemExit(str(e))
