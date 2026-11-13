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


def clean(text, marker, strip_pov=False):
    return reader_text_module().extract(
        text, scene_break=marker, strip_pov=strip_pov
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
    manifest = resolver.load(root)
    books = [b for b in manifest['books'] if b['id'] == a.book or b.get('display_label') == a.book]
    if len(books) != 1:
        raise ValueError('book must resolve uniquely through project manifest: ' + a.book)
    book_record = books[0]
    chapters = []
    for chapter in sorted(book_record['chapters'], key=lambda c: c['reading_order']):
        source_path = s.path_at(root, chapter['path'])
        if cfg.get('chapter_dir') and not source_path.is_relative_to(s.path_at(root, cfg['chapter_dir'])):
            raise ValueError('manifest chapter is outside configured chapter_dir: ' + chapter['path'])
        chapters.append((chapter['reading_order'], source_path, chapter))
    if not chapters:
        raise ValueError('project manifest has no chapters for ' + a.book)
    formats = list(dict.fromkeys(a.format or ['md']))
    pandoc = shutil.which('pandoc')
    if any(f != 'md' for f in formats) and not pandoc:
        raise ValueError('requested format requires pandoc')
    engine = a.pdf_engine or cfg.get('pdf_engine')
    if 'pdf' in formats and (not engine or not shutil.which(engine)):
        raise ValueError('PDF requires an explicitly configured available PDF engine')
    warnings = []
    required = cfg.get('required_checks', ['Gate'])
    if not isinstance(required, list) or not required or not all(re.fullmatch(r'[A-Za-z]+', c) for c in required):
        raise ValueError('required_checks must name at least one configured check')
    for n, p, chapter_record in chapters:
        match = re.search(r'(\d+)', chapter_record.get('display_label', ''))
        legacy_number = int(match.group(1)) if match else n
        for check in required:
            meta = s.path_at(root, f'_Edits/{a.book}/Chapter-{legacy_number:03}_{check}.meta.json')
            status = s.readiness(root, meta, [str(p.relative_to(root))], profile=cfg.get('completion_profile', 'draft_verified'))
            if status['readiness'] != 'ELIGIBLE':
                warnings.append(f'{p.name}: {check} {status}')
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
    if warnings and a.profile != 'beta' and not a.unchecked_preview:
        raise ValueError('release checks incomplete: ' + '; '.join(warnings))
    names = [str(p.relative_to(root)) for _, p, _ in chapters]
    names += cfg.get('front_matter', []) + cfg.get('back_matter', [])
    if cfg.get('reference_doc'):
        names.append(cfg['reference_doc'])
    before = s.evidence(root, names)
    if any(e.get('sha256') is None for e in before):
        raise ValueError('missing source/front/back matter')
    validation_names = list(names) + [resolver.MANIFEST_PATH]
    for _, _, chapter_record in chapters:
        match = re.search(r'(\d+)', chapter_record.get('display_label', ''))
        legacy_number = int(match.group(1)) if match else chapter_record['reading_order']
        for check in required:
            meta_name = f'_Edits/{a.book}/Chapter-{legacy_number:03}_{check}.meta.json'
            validation_names.append(meta_name)
            meta_path = s.path_at(root, meta_name)
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
    # Assemble and validate reader-facing content before either preflight returns
    # or a converter is invoked. This keeps deterministic content failures equal.
    order = cfg.get('front_matter', []) + [str(p.relative_to(root)) for _, p, _ in chapters] + cfg.get('back_matter', [])
    text = '\n\n'.join(
        clean(s.path_at(root, n).read_text(encoding='utf-8'), cfg.get('scene_break', '* * *'))
        for n in order
    )
    reader_text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
    plan = {'schema_version': 1, 'sources': before, 'profile': a.profile, 'formats': formats,
            'warnings': warnings, 'unchecked_preview': a.unchecked_preview,
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
            for fmt in formats:
                target = stage / ('manuscript-combined.' + fmt)
                if fmt != 'md':
                    cmd = [pandoc, str(md), '--from=markdown', '--standalone', '-o', str(target)]
                    if cfg.get('title'):
                        cmd += ['--metadata', 'title=' + cfg['title']]
                    if cfg.get('toc', a.profile != 'submission'):
                        cmd += ['--toc']
                    if fmt == 'pdf':
                        cmd += ['--pdf-engine', engine]
                    if cfg.get('reference_doc') and fmt == 'docx':
                        cmd += ['--reference-doc', str(s.path_at(root, cfg['reference_doc']))]
                    subprocess.run(cmd, check=True, capture_output=True)
                verify(target, fmt)
                plan['structural_checks'][fmt] = 'PASS'
            if s.evidence(root, validation_names) != validation_before:
                raise ValueError('source or required readiness evidence changed during export; rerun preflight')
            if a.config and hashlib.sha256(a.config.read_bytes()).hexdigest() != config_sha256:
                raise ValueError('export configuration changed during conversion; rerun preflight')
            plan['outputs'] = {p.name: s.digest(p) for p in stage.iterdir() if p.suffix[1:] in formats}
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
