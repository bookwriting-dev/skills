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
import zipfile
import sys
sys.dont_write_bytecode = True


def state_module():
    p = Path(__file__).resolve().parents[2] / 'book-status/scripts/project_state.py'
    spec = importlib.util.spec_from_file_location('storycraft_state', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def clean(text, marker, strip_pov=False):
    # Only explicitly marked internal apparatus is disposable.
    text = re.sub(r'<!--\s*STORYCRAFT:.*?-->', '', text, flags=re.S)
    text = re.sub(r'^```storycraft-internal\s*\n.*?^```\s*$', '', text, flags=re.M | re.S)
    if '<!--' in text or '```storycraft-internal' in text:
        raise ValueError('unknown or unclosed internal apparatus; configure or remove explicitly')
    if strip_pov:
        text = re.sub(r'^<!--\s*POV:.*?-->\s*$', '', text, flags=re.M)
    lines = text.splitlines()
    fence = False
    for i, line in enumerate(lines):
        if re.match(r'^\s*(```|~~~)', line):
            fence = not fence
        if not fence and line.strip() == '* * *':
            lines[i] = marker
    return '\n'.join(lines).strip() + '\n'


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
    chapter_dir = s.path_at(root, cfg.get('chapter_dir', f'Chapters/{a.book}'))
    chapters = []
    for p in chapter_dir.glob('Chapter-*.md'):
        match = re.fullmatch(r'Chapter-(\d+)\.md', p.name)
        if not match:
            raise ValueError('ambiguous chapter filename: ' + p.name)
        chapters.append((int(match[1]), p))
    chapters.sort()
    nums = [n for n, _ in chapters]
    if not nums or nums != list(range(1, max(nums)+1)):
        raise ValueError('missing or duplicate chapter numbering')
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
    for n, p in chapters:
        for check in required:
            meta = s.path_at(root, f'_Edits/{a.book}/Chapter-{n:03}_{check}.meta.json')
            status = s.freshness(root, meta)
            if status['freshness'] != 'CURRENT' or status.get('verdict') != 'PASS':
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
    names = [str(p.relative_to(root)) for _, p in chapters]
    names += cfg.get('front_matter', []) + cfg.get('back_matter', [])
    if cfg.get('reference_doc'):
        names.append(cfg['reference_doc'])
    before = s.evidence(root, names)
    if any(e.get('sha256') is None for e in before):
        raise ValueError('missing source/front/back matter')
    plan = {'schema_version': 1, 'sources': before, 'profile': a.profile, 'formats': formats,
            'warnings': warnings, 'unchecked_preview': a.unchecked_preview,
            'pandoc': subprocess.check_output([pandoc, '--version'], text=True).splitlines()[0] if pandoc else None,
            'pdf_engine': engine, 'config': cfg}
    if a.check:
        print(json.dumps(plan, indent=2))
        return
    order = cfg.get('front_matter', []) + [str(p.relative_to(root)) for _, p in chapters] + cfg.get('back_matter', [])
    text = '\n\n'.join(clean(s.path_at(root, n).read_text(), cfg.get('scene_break', '* * *')) for n in order)
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
            if s.evidence(root, names) != before:
                raise ValueError('sources changed during export')
            plan['outputs'] = {p.name: s.digest(p) for p in stage.iterdir() if p.suffix[1:] in formats}
            s.write(stage / 'export-manifest.json', plan)
            # Keep previous package recoverable until the entire new package is valid.
            backup = out.with_name(out.name + '.previous')
            if backup.exists():
                shutil.rmtree(backup)
            if out.exists():
                out.rename(backup)
            try:
                shutil.copytree(stage, out)
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
