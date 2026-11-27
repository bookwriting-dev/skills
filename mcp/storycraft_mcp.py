#!/usr/bin/env python3
"""Zero-dependency Python stdlib MCP stdio server for Storycraft state and delivery tools."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True

ROOT_REPO = Path(__file__).resolve().parent.parent
BOOK_STATUS_SCRIPTS = ROOT_REPO / 'skills' / 'book-status' / 'scripts'
if str(BOOK_STATUS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(BOOK_STATUS_SCRIPTS))

import project_state as ps  # noqa: E402
from kanban import render_kanban  # noqa: E402
from rhythm_map import rhythm_map  # noqa: E402
from state_ledgers import reanchor_chapter  # noqa: E402
from state_reviews import REVIEW_TYPE_SKILLS, record_disposition, review_begin, review_finish  # noqa: E402
from sync_edits import sync_edits  # noqa: E402

_VERSION_FILE = ROOT_REPO / 'VERSION'
SERVER_VERSION = _VERSION_FILE.read_text(encoding='utf-8').strip() if _VERSION_FILE.is_file() else '1.1.0'
PDF_ENGINES = ['context', 'groff', 'latexmk', 'lualatex', 'pagedjs-cli', 'pdflatex', 'pdfroff',
               'prince', 'tectonic', 'typst', 'weasyprint', 'wkhtmltopdf', 'xelatex']


TOOLS = [
    {
        'name': 'storycraft_dashboard',
        'description': 'Return chapter readiness, required checks, campaigns, and author reading progress for a book.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'root': {'type': 'string', 'description': 'Absolute path to the book project root.'},
                'book': {'type': 'string', 'default': 'Book-1'},
                'view': {'type': 'string', 'enum': ['full', 'compact'], 'default': 'full',
                         'description': 'Use compact for counts and the first blocker in reading order.'},
                'chapter': {'type': 'string', 'description': 'Show details for a chapter by ID, label or path.'},
            },
            'required': ['root'],
        },
    },
    {
        'name': 'storycraft_draft_packet',
        'description': 'Compile the deterministic pre-draft packet (scene plan, psych, theme, surprise ledger, voice anchors and contrasts, scene relationship turns, knowledge, dramatic irony, due payoffs and repetition examples).',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'root': {'type': 'string'},
                'book': {'type': 'string', 'default': 'Book-1'},
                'chapter': {'type': 'string', 'default': '1'},
                'window': {'type': 'integer', 'default': 3},
                'story_order': {'type': 'integer'},
                'reader_order': {'type': 'integer'},
                'output': {'type': 'string'},
                'key': {'type': 'array', 'items': {'type': 'string'}},
            },
            'required': ['root'],
        },
    },
    {
        'name': 'storycraft_review_begin',
        'description': 'Capture pre-review input hashes for a chapter review/gate and write a prepared manifest.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'root': {'type': 'string'},
                'book': {'type': 'string', 'default': 'Book-1'},
                'chapter': {'type': 'string', 'default': '1'},
                'review_type': {'type': 'string', 'enum': sorted(REVIEW_TYPE_SKILLS)},
                'extra_paths': {'type': 'array', 'items': {'type': 'string'}},
            },
            'required': ['root', 'review_type'],
        },
    },
    {
        'name': 'storycraft_review_finish',
        'description': 'Verify prepared inputs did not drift, hash the saved report, and write .meta.json.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'root': {'type': 'string'},
                'prepared': {'type': 'string'},
                'verdict': {'type': 'string', 'enum': ['PASS', 'WARN', 'FAIL']},
                'report': {'type': 'string'},
                'findings': {'type': 'array', 'items': {'type': 'object'}},
                'operation_id': {'type': 'string'},
            },
            'required': ['root', 'prepared', 'verdict'],
        },
    },
    {
        'name': 'storycraft_record_disposition',
        'description': 'Append an explicit finding disposition (applied/rejected/deferred/superseded) to decisions.jsonl.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'root': {'type': 'string'},
                'book': {'type': 'string', 'default': 'Book-1'},
                'report': {'type': 'string'},
                'finding_id': {'type': 'string'},
                'disposition': {'type': 'string', 'enum': ['applied', 'rejected', 'deferred', 'superseded']},
                'reason': {'type': 'string'},
                'quote': {'type': 'string'},
            },
            'required': ['root', 'report', 'finding_id', 'disposition', 'reason'],
        },
    },
    {
        'name': 'storycraft_rhythm_map',
        'description': 'Compute whole-book chapter pacing, scene counts, dialogue ratio, POV shares, promises, and character absence gaps.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'root': {'type': 'string'},
                'book': {'type': 'string', 'default': 'Book-1'},
                'gap_threshold': {'type': 'integer', 'default': 4},
                'markdown': {'type': 'boolean', 'default': True},
            },
            'required': ['root'],
        },
    },
    {
        'name': 'storycraft_sync_edits',
        'description': 'Diff a manually edited chapter against its baseline and report stale reviews, broken quotes, and advisory preference deltas.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'root': {'type': 'string'},
                'book': {'type': 'string', 'default': 'Book-1'},
                'chapter': {'type': 'string', 'default': '1'},
                'baseline': {'type': 'string'},
            },
            'required': ['root'],
        },
    },
    {
        'name': 'storycraft_promises',
        'description': 'Audit the book Chekhov/promise ledger (overdue, due, open, paid, deferred setups).',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'root': {'type': 'string'},
                'book': {'type': 'string', 'default': 'Book-1'},
                'chapter': {'type': 'string'},
                'ledger': {'type': 'string'},
            },
            'required': ['root'],
        },
    },
    {
        'name': 'storycraft_compile',
        'description': 'Preflight or build a manuscript export package (md, docx, epub, pdf) without modifying sources.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'root': {'type': 'string'},
                'book': {'type': 'string', 'default': 'Book-1'},
                'profile': {'type': 'string', 'enum': ['beta', 'submission', 'publication'], 'default': 'beta'},
                'formats': {'type': 'array', 'items': {'type': 'string', 'enum': ['md', 'docx', 'epub', 'pdf']}},
                'config': {'type': 'string', 'description': 'Project-relative path to an export configuration JSON file.'},
                'pdf_engine': {'type': 'string',
                               'description': 'Installed Pandoc PDF engine name or absolute executable path, e.g. typst. Overrides pdf_engine in the export config.'},
                'check': {'type': 'boolean', 'default': True},
            },
            'required': ['root'],
        },
    },
    {
        'name': 'storycraft_kanban',
        'description': 'Deterministically render Wiki/Story/Book-N/kanban.md from current disk state and gate metadata.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'root': {'type': 'string'},
                'book': {'type': 'string', 'default': 'Book-1'},
                'write_board': {'type': 'boolean', 'default': True},
            },
            'required': ['root'],
        },
    },
    {
        'name': 'storycraft_reanchor',
        'description': 'Re-anchor continuity claims, knowledge events, and relationship events after local prose edits where quotes still match uniquely.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'root': {'type': 'string'},
                'book': {'type': 'string', 'default': 'Book-1'},
                'chapter': {'type': 'string', 'default': '1'},
            },
            'required': ['root'],
        },
    },
    {
        'name': 'storycraft_chapter_preflight',
        'description': 'Run workflow resolution, chapter format check, and draft-packet generation in one call.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'root': {'type': 'string'},
                'book': {'type': 'string', 'default': 'Book-1'},
                'chapter': {'type': 'string', 'default': '1'},
                'window': {'type': 'integer', 'default': 3},
                'story_order': {'type': 'integer'},
                'reader_order': {'type': 'integer'},
                'output': {'type': 'string'},
            },
            'required': ['root'],
        },
    },
    {
        'name': 'storycraft_chapter_finalize',
        'description': 'Run chapter-format, continuity audit, and review-begin input capture in one call.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'root': {'type': 'string'},
                'book': {'type': 'string', 'default': 'Book-1'},
                'chapter': {'type': 'string', 'default': '1'},
                'review_type': {'type': 'string', 'enum': sorted(REVIEW_TYPE_SKILLS)},
                'output': {'type': 'string'},
            },
            'required': ['root'],
        },
    },
    {
        'name': 'storycraft_editor_return',
        'description': 'List an editor\'s tracked changes, untracked edits and comments in a returned beta DOCX, or preview them as Markdown diffs. Saves the report; never writes chapters.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'root': {'type': 'string', 'description': 'Absolute path to the book project root.'},
                'book': {'type': 'string', 'default': 'Book-1'},
                'docx': {'type': 'string', 'description': 'DOCX the editor returned, absolute or project-relative.'},
                'export': {'type': 'string', 'description': 'Beta export ID, needed if the file lost its bookmark.'},
                'view': {'type': 'string', 'enum': ['changes', 'preview', 'untracked', 'comments'], 'default': 'changes'},
                'accepted': {'type': 'boolean', 'default': False,
                             'description': 'With view=preview, show exactly what apply would write and return apply_token.'},
                'changes': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Preview only these change IDs.'},
                'chapter': {'type': 'string', 'description': 'List only this chapter\'s changes, by ID, label or path.'},
                'offset': {'type': 'integer', 'default': 0},
                'limit': {'type': 'integer', 'default': 40},
            },
            'required': ['root', 'docx'],
        },
    },
    {
        'name': 'storycraft_editor_decide',
        'description': 'Record the author\'s decision on editor changes, by ID or by filter. A filter first only shows its matches and a confirm token.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'root': {'type': 'string', 'description': 'Absolute path to the book project root.'},
                'book': {'type': 'string', 'default': 'Book-1'},
                'docx': {'type': 'string', 'description': 'DOCX the editor returned, absolute or project-relative.'},
                'export': {'type': 'string', 'description': 'Beta export ID, needed if the file lost its bookmark.'},
                'status': {'type': 'string', 'enum': ['accepted', 'rejected', 'pending']},
                'changes': {'type': 'array', 'items': {'type': 'string'}},
                'chapter': {'type': 'string'},
                'author': {'type': 'string'},
                'punctuation_only': {'type': 'boolean', 'default': False},
                'confirm': {'type': 'string', 'description': 'Token from the filter preview the author approved.'},
                'offset': {'type': 'integer', 'default': 0},
                'limit': {'type': 'integer', 'default': 40},
            },
            'required': ['root', 'docx', 'status'],
        },
    },
    {
        'name': 'storycraft_editor_apply',
        'description': 'Write accepted editor changes into chapters, keeping a copy of the earlier text. Needs apply_token from the accepted preview the author approved.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'root': {'type': 'string', 'description': 'Absolute path to the book project root.'},
                'book': {'type': 'string', 'default': 'Book-1'},
                'docx': {'type': 'string', 'description': 'DOCX the editor returned, absolute or project-relative.'},
                'export': {'type': 'string', 'description': 'Beta export ID, needed if the file lost its bookmark.'},
                'token': {'type': 'string'},
            },
            'required': ['root', 'docx', 'token'],
        },
    },
]


def _page(items, args):
    offset, limit = max(int(args.get('offset', 0)), 0), max(int(args.get('limit', 40)), 1)
    end = offset + limit
    return {'total': len(items), 'offset': offset, 'next_offset': end if end < len(items) else None,
            'items': items[offset:end]}


def _editor_tool(name: str, root: Path, args: dict):
    """Run the editor-return script and page its output, which can cover a whole novel."""
    script = ROOT_REPO / 'skills' / 'editor-return' / 'scripts' / 'editor_return.py'
    cmd = [sys.executable, str(script), '--root', str(root)]

    def option(flag, value):
        cmd.append(f'{flag}={value}')  # one argument, so a value is never read as another option

    option('--book', args.get('book', 'Book-1'))
    option('--docx', args['docx'])
    if args.get('export'):
        option('--export', args['export'])
    view = args.get('view', 'changes')
    if name == 'storycraft_editor_apply':
        option('--apply', args['token'])
    elif name == 'storycraft_editor_decide':
        option('--mark', args['status'])
        for identifier in args.get('changes') or []:
            option('--change', identifier)
        for key, flag in (('chapter', '--chapter'), ('author', '--author'), ('confirm', '--confirm')):
            if args.get(key):
                option(flag, args[key])
        if args.get('punctuation_only'):
            cmd.append('--punctuation-only')
    elif view == 'preview':
        cmd.append('--preview')
        if args.get('accepted'):
            cmd.append('--accepted')
        for identifier in args.get('changes') or []:
            option('--change', identifier)
    proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise ValueError(proc.stderr.strip() or 'editor_return failed')
    report = json.loads(proc.stdout)
    changes = report['changes']
    statuses = {}
    for change in changes:
        statuses[change['status']] = statuses.get(change['status'], 0) + 1
    result = {key: report[key] for key in ('ledger', 'export_id', 'docx')}
    result['summary'] = {'statuses': statuses, 'manual': sum(not c['supported'] for c in changes),
                         'untracked': len(report['untracked']), 'comments': len(report['comments'])}
    result['storycraft_version'] = SERVER_VERSION
    if name == 'storycraft_editor_apply':
        result['applied'] = report['applied']
    elif name == 'storycraft_editor_decide':
        decision = report['decision']
        result['decision'] = dict(decision, changes=_page(decision['changes'], args))
    elif view == 'preview':
        preview = report['preview']
        result['preview'] = dict(preview, files=_page(preview['files'], args))
    elif view in ('untracked', 'comments'):
        result[view] = _page(report[view], args)
    else:
        wanted = (args.get('chapter') or '').casefold()

        def in_chapter(change):
            location = change.get('location') or {}
            path = location.get('path') or ''
            names = (location.get('chapter_id'), location.get('chapter'), path, Path(path).stem)
            return not wanted or any(n and n.casefold() == wanted for n in names)

        fields = ('id', 'type', 'status', 'supported', 'reason', 'authors', 'before', 'after', 'paragraph_before')
        result['changes'] = _page([
            {key: c[key] for key in fields if key in c} | {'chapter': (c.get('location') or {}).get('chapter')}
            for c in changes if in_chapter(c)], args)
    return result

def _call_tool(name: str, args: dict):
    root = Path(args['root']).resolve()
    if not root.is_dir():
        raise ValueError(f'project root does not exist: {root}')
    book = args.get('book', 'Book-1')

    if name.startswith('storycraft_editor_'):
        return _editor_tool(name, root, args)
    if name == 'storycraft_dashboard':
        return dict(ps.dashboard(root, book, view=args.get('view', 'full'), chapter=args.get('chapter')),
                    storycraft_version=SERVER_VERSION,
                    skills_dir=str(ROOT_REPO / 'skills'))
    if name == 'storycraft_draft_packet':
        ns = argparse.Namespace(
            book=book, chapter=args.get('chapter', '1'),
            window=int(args.get('window', 3)), output=args.get('output'),
            key=args.get('key'), story_order=args.get('story_order'),
            reader_order=args.get('reader_order'),
        )
        return ps.draft_packet(root, ns)
    if name == 'storycraft_review_begin':
        return review_begin(root, book, args.get('chapter', '1'), args['review_type'],
                            extra_paths=args.get('extra_paths'))
    if name == 'storycraft_review_finish':
        return review_finish(root, args['prepared'], args['verdict'],
                             report=args.get('report'), findings=args.get('findings'),
                             operation_id=args.get('operation_id'))
    if name == 'storycraft_record_disposition':
        return record_disposition(root, book, report=args['report'], finding_id=args['finding_id'],
                                  disposition=args['disposition'], reason=args['reason'],
                                  quote=args.get('quote'))
    if name == 'storycraft_rhythm_map':
        return rhythm_map(root, book, gap_threshold=int(args.get('gap_threshold', 4)),
                          markdown=bool(args.get('markdown', True)))
    if name == 'storycraft_sync_edits':
        return sync_edits(root, book, args.get('chapter', '1'), baseline=args.get('baseline'))
    if name == 'storycraft_promises':
        script = ROOT_REPO / 'skills' / 'promise-tracker' / 'scripts' / 'promises.py'
        cmd = [sys.executable, str(script), '--book', book]
        if args.get('chapter'):
            cmd.extend(['--chapter', str(args['chapter'])])
        if args.get('ledger'):
            ledger_p = ps.path_at(root, args['ledger'])
            cmd.extend(['--ledger', str(ledger_p)])
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=False)
        return {'returncode': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr,
                'storycraft_version': SERVER_VERSION}
    if name == 'storycraft_compile':
        script = ROOT_REPO / 'skills' / 'compile-manuscript' / 'scripts' / 'compile_manuscript.py'
        cmd = [sys.executable, str(script), '--root', str(root), '--book', book,
               '--profile', args.get('profile', 'beta')]
        formats = args.get('formats') or ['md']
        engine = args.get('pdf_engine')
        if 'config' in args:
            if Path(args['config']).is_absolute():
                raise ValueError('config must be a project-relative path')
            config = ps.path_at(root, args['config'])
            cmd.extend(['--config', str(config)])
            if 'pdf' in formats and engine is None:
                engine = ps.load(config).get('pdf_engine')
        if 'pdf' in formats and engine is None:
            raise ValueError('PDF requires an installed pdf_engine in the tool arguments or export config')
        if engine is not None:
            engine_path = Path(engine)
            if engine_path.name not in PDF_ENGINES or (engine != engine_path.name and not engine_path.is_absolute()):
                raise ValueError('pdf_engine must be a supported Pandoc engine name or its absolute executable path')
            cmd.extend(['--pdf-engine', engine])
        for fmt in formats:
            cmd.extend(['--format', fmt])
        if args.get('check', True):
            cmd.append('--check')
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise ValueError(proc.stderr.strip() or proc.stdout.strip() or 'compile_manuscript failed')
        return json.loads(proc.stdout)
    if name == 'storycraft_kanban':
        return render_kanban(root, book, write_board=bool(args.get('write_board', True)))
    if name == 'storycraft_reanchor':
        return reanchor_chapter(root, book, args.get('chapter', '1'))
    if name == 'storycraft_chapter_preflight':
        resolver = ps.project_manifest_module()
        ns = argparse.Namespace(
            book=book, chapter=args.get('chapter', '1'),
            window=int(args.get('window', 3)), output=args.get('output'),
            key=None, story_order=args.get('story_order'), reader_order=args.get('reader_order'),
        )
        pkt = ps.draft_packet(root, ns)
        book_rec, ch_rec = resolver.resolve_chapter(root, book, args.get('chapter', '1'), allow_new=True)
        wf = resolver.workflow(root, book_rec, chapter=ch_rec)
        return {'workflow': wf, 'draft_packet': pkt, 'storycraft_version': SERVER_VERSION}
    if name == 'storycraft_chapter_finalize':
        resolver = ps.project_manifest_module()
        book_rec, ch_rec = resolver.resolve_chapter(root, book, args.get('chapter', '1'))
        wf = resolver.workflow(root, book_rec, chapter=ch_rec)
        rtype = args.get('review_type') or wf['required_checks'][0]
        fmt = ps.chapter_format_module().audit(book_rec, ps.manuscript_texts(root, book_rec), selected=ch_rec['id'])
        cont = ps.continuity_report(root, book_rec, ps.manuscript_texts(root, book_rec), chapter=ch_rec)
        prep = review_begin(root, book, ch_rec['id'], rtype, output=args.get('output'))
        return {'workflow': wf, 'chapter_format': fmt, 'continuity': cont, 'prepared': prep}
    raise ValueError(f'unknown tool: {name}')


def _read_message():
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None, None
        stripped = line.strip()
        if stripped:
            break
    if b':' in stripped and not stripped.startswith(b'{'):
        headers = [stripped]
        while True:
            hdr = sys.stdin.buffer.readline()
            if not hdr or hdr in (b'\r\n', b'\n'):
                break
            if hdr.strip():
                headers.append(hdr.strip())
        length = None
        for h in headers:
            if h.lower().startswith(b'content-length:'):
                length = int(h.split(b':', 1)[1].strip())
                break
        if length is None:
            raise ValueError('LSP header frame missing Content-Length')
        payload = sys.stdin.buffer.read(length)
        return json.loads(payload.decode('utf-8')), 'lsp'
    return json.loads(stripped.decode('utf-8')), 'jsonl'


def _write_message(msg: dict, framing: str):
    raw = json.dumps(msg, ensure_ascii=False).encode('utf-8')
    if framing == 'lsp':
        sys.stdout.buffer.write(f'Content-Length: {len(raw)}\r\n\r\n'.encode('ascii') + raw)
    else:
        sys.stdout.buffer.write(raw + b'\n')
    sys.stdout.buffer.flush()


def serve():
    while True:
        msg, framing = _read_message()
        if msg is None:
            break
        req_id = msg.get('id')
        method = msg.get('method', '')
        params = msg.get('params') or {}
        if req_id is None:
            continue  # JSON-RPC notification
        try:
            if method == 'initialize':
                result = {
                    'protocolVersion': '2024-11-05',
                    'capabilities': {'tools': {}},
                    'serverInfo': {'name': 'storycraft-state', 'version': SERVER_VERSION},
                }
            elif method == 'ping':
                result = {}
            elif method == 'tools/list':
                result = {'tools': TOOLS}
            elif method == 'tools/call':
                tool_name = params.get('name', '')
                tool_args = params.get('arguments') or {}
                output = _call_tool(tool_name, tool_args)
                result = {
                    'content': [{'type': 'text', 'text': json.dumps(output, indent=2, ensure_ascii=False)}],
                    'isError': False,
                }
            else:
                _write_message({'jsonrpc': '2.0', 'id': req_id,
                                'error': {'code': -32601, 'message': f'Method not found: {method}'}}, framing)
                continue
            _write_message({'jsonrpc': '2.0', 'id': req_id, 'result': result}, framing)
        except Exception as exc:
            if method == 'tools/call':
                _write_message({
                    'jsonrpc': '2.0', 'id': req_id,
                    'result': {'content': [{'type': 'text', 'text': json.dumps({'error': str(exc)})}], 'isError': True},
                }, framing)
            else:
                _write_message({'jsonrpc': '2.0', 'id': req_id,
                                'error': {'code': -32603, 'message': str(exc)}}, framing)


if __name__ == '__main__':
    serve()
