#!/usr/bin/env python3
"""Create provider-neutral editorial packets; score recorded outputs, never invent author scores."""
import argparse
import hashlib
import json
import posixpath
import re
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--packets', type=Path)
    ap.add_argument('--results', type=Path)
    ap.add_argument('--skill', default='fiction-full-editor')
    ap.add_argument('--baseline-ref')
    a = ap.parse_args()
    cases = json.loads((ROOT/'tools/eval-fixtures/editorial-preservation/cases.json').read_text())['cases']
    if a.packets:
        a.packets.mkdir(parents=True, exist_ok=True)
        skillpath = f'skills/{a.skill}/SKILL.md'
        def read_source(name):
            return subprocess.check_output(['git', 'show', f'{a.baseline_ref}:{name}'], cwd=ROOT, text=True) if a.baseline_ref else (ROOT/name).read_text()
        skill = read_source(skillpath)
        bundle = {}
        def collect(name):
            if name in bundle:
                return
            content = read_source(name)
            bundle[name] = content
            for linked in re.findall(r'\]\(([^)#]+\.md)(?:#[^)]*)?\)', content):
                if '://' not in linked and not linked.startswith('/'):
                    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), linked))
                    if not resolved.startswith('skills/'):
                        raise ValueError('evaluation rule link escapes skills: ' + resolved)
                    collect(resolved)
        collect(skillpath)
        hashes = {name: hashlib.sha256(content.encode()).hexdigest() for name,content in bundle.items()}
        for c in cases:
            packet = dict(schema_version=1,id=c['id'],source=c['source'],rules=c['rules'],skill=skill,
                          skill_sha256=hashlib.sha256(skill.encode()).hexdigest(),rule_sources=bundle,rule_hashes=hashes,task='Return findings with exact quote, proposed replacement, and reason. Preserve effective deliberate choices.')
            (a.packets/(c['id']+'.json')).write_text(json.dumps(packet,indent=2)+'\n')
        print(json.dumps({'packets': len(cases), 'labels': 'provisional; keep hidden from candidate contexts'}))
    if a.results:
        data = json.loads(a.results.read_text())
        if not data.get('configuration') or not data.get('repeat_count'):
            raise ValueError('results need recorded configuration and preselected repeat_count')
        by_id = {c['id']: c for c in cases}
        categories = {}
        stats = dict(findings=0,true_positive_findings=0,cases=0,protected=0,harmful=0,defects=0,detected=0,unsupported_quotes=0,author_scored=0,author_accepted=0)
        for r in data['results']:
            c = by_id[r['id']]; stats['cases'] += 1
            stats['protected'] += bool(c['protected_spans']); stats['defects'] += bool(c['defect_spans'])
            findings = r.get('findings', [])
            category = categories.setdefault(c['category'], {'cases':0,'findings':0})
            category['cases'] += 1; category['findings'] += len(findings)
            stats['findings'] += len(findings)
            stats['true_positive_findings'] += sum(bool(f.get('quote')) and any(d in f['quote'] or f['quote'] in d for d in c['defect_spans']) for f in findings)
            stats['unsupported_quotes'] += sum(not f.get('quote') or f['quote'] not in c['source'] for f in findings)
            stats['harmful'] += bool(c['protected_spans'] and any(f.get('quote') and any(p in f.get('quote','') or f.get('quote','') in p for p in c['protected_spans']) for f in findings))
            stats['detected'] += bool(c['defect_spans'] and any(f.get('quote') and any(d in f.get('quote','') or f.get('quote','') in d for d in c['defect_spans']) for f in findings))
            for f in findings:
                if 'author_accept' in f:
                    stats['author_scored'] += 1;stats['author_accepted'] += bool(f['author_accept'])
        print(json.dumps(dict(schema_version=1,counts=stats,categories=categories,precision=stats['true_positive_findings']/stats['findings'] if stats['findings'] else None,recall=stats['detected']/stats['defects'] if stats['defects'] else None,harmful_edit_rate=stats['harmful']/stats['protected'] if stats['protected'] else None,author_acceptance=stats['author_accepted']/stats['author_scored'] if stats['author_scored'] else None,author_evaluation='pending' if not stats['author_scored'] else 'recorded',literary_thresholds='set after author-reviewed pilot; never inferred from this score'),indent=2))
    if not a.packets and not a.results:
        ap.error('choose --packets or --results')


if __name__ == '__main__':
    main()
