#!/usr/bin/env python3
"""Real converter integration: beta/submission DOCX, publication EPUB/PDF and Markdown."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT=Path(__file__).resolve().parent.parent


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path);a=ap.parse_args()
    for command in ('pandoc','typst'):
        if not shutil.which(command):
            raise SystemExit('required converter missing: '+command)
    temp=tempfile.TemporaryDirectory()
    root=a.output.resolve() if a.output else Path(temp.name).resolve()
    root.mkdir(parents=True,exist_ok=True)
    shutil.copytree(ROOT/'tools/eval-fixtures/storycraft-book',root,dirs_exist_ok=True)
    spec=importlib.util.spec_from_file_location('state',ROOT/'skills/book-status/scripts/project_state.py')
    state=importlib.util.module_from_spec(spec);spec.loader.exec_module(state)
    for n in range(1,4):
        chapter=f'Chapters/Book-1/Chapter-{n:03}.md'
        report=f'_Edits/Book-1/Chapter-{n:03}_Gate.md'
        p=root/report;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('PASS\nSynthetic fixture gate: conversion test only.\n')
        state.write(p.with_suffix('.meta.json'),dict(schema_version=1,report=report,verdict='PASS',inputs=state.evidence(root,[chapter]),report_sha256=state.digest(p)))
    before=state.evidence(root,[f'Chapters/Book-1/Chapter-{n:03}.md' for n in range(1,4)])
    for profile,formats in [('beta',['md','docx']),('submission',['docx']),('publication',['md','epub','pdf'])]:
        cmd=[sys.executable,str(ROOT/'skills/compile-manuscript/scripts/compile_manuscript.py'),'--root',str(root),'--profile',profile,'--pdf-engine','typst']
        for f in formats:cmd+=['--format',f]
        p=subprocess.run(cmd,capture_output=True,text=True)
        if p.returncode:raise SystemExit(p.stderr+p.stdout)
        print(profile,':',','.join(formats),'verified')
    assert state.evidence(root,[e['path'] for e in before])==before
    print('Sources preserved; output:',root)
    if a.output:
        print('Inspect representative pages before marking layout approved.')


if __name__=='__main__':main()
