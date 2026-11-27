"""Build the Storycraft plugin payloads and their shared review evidence."""

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
from importlib.metadata import distribution
import json
import os
from pathlib import Path
import re
import shutil
import shlex
import sys
import tempfile

from skill_lib import ROOT, load_skills


DESKTOP_GUIDANCE = (
    'In commands below, replace `SKILLS_DIR` with the absolute path to this installed '
    "plugin's `skills/` directory. Run from the selected manuscript root and keep its "
    'project-relative file arguments. Replace `python3` with the installed '
    "plugin's `run-python` launcher for direct script calls.\n\n"
)
CLAUDE_RUN = '"${CLAUDE_PLUGIN_ROOT}/run-python"'


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


@contextmanager
def directory_lock(path):
    # Lock the existing directory inode so parallel builds share a lock across renames.
    fd = os.open(path, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def bundle_yaml(target):
    yaml = distribution('PyYAML')
    for entry in yaml.files:
        module = entry.parts[0] == 'yaml' and entry.suffix == '.py'
        license_file = '.dist-info/licenses/' in entry.as_posix()
        if module or license_file:
            output = target / entry
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(entry.locate(), output)


def add_guidance(path, text, guidance):
    if path.name == 'SKILL.md':
        header, separator, body = text[4:].partition('\n---\n')
        return '---\n' + header + separator + '\n' + guidance + body.lstrip('\n')
    return guidance + text


def adapt_desktop_commands(skills, names):
    for name in names:
        if name == 'skill-builder':
            continue
        for path in (skills / name).rglob('*.md'):
            original = path.read_text(encoding='utf-8')
            if '.agents/skills/' not in original:
                continue
            text = original.replace('.agents/skills/', 'SKILLS_DIR/')
            path.write_text(add_guidance(path, text, DESKTOP_GUIDANCE), encoding='utf-8')


def adapt_claude_commands(skills):
    # Claude substitutes these variables in SKILL.md when it loads the skill.
    guidance = (f'For shell commands, run bundled Python helpers with `{CLAUDE_RUN}` from the manuscript root. '
                'Resolve plugin paths in linked reference files from `${CLAUDE_PLUGIN_ROOT}`.\n\n')
    for path in skills.rglob('*.md'):
        skill = skills / path.relative_to(skills).parts[0]
        if skill.name == 'skill-builder':
            continue  # Its examples and output paths belong to the project being authored.
        original = path.read_text(encoding='utf-8')
        text = original.replace(DESKTOP_GUIDANCE, '', 1)
        text = text.replace('SKILLS_DIR/', '${CLAUDE_PLUGIN_ROOT}/skills/')
        text = text.replace('{{SKILL_DIR}}', '${CLAUDE_SKILL_DIR}').replace('<skill-dir>', '${CLAUDE_SKILL_DIR}')
        # Qualify executable examples, including inline commands that omit the interpreter.
        text = re.sub(r'(?:\bpython3? +|(?<=`)|^)"?(\$\{CLAUDE_(?:PLUGIN_ROOT|SKILL_DIR)\}/[\w./-]+\.py)"?',
                      lambda m: f'{CLAUDE_RUN} "{m[1]}"', text, flags=re.MULTILINE)

        def local_script(match):
            name = match[1]
            if (skill / 'scripts' / name).is_file():
                return f'{CLAUDE_RUN} "${{CLAUDE_SKILL_DIR}}/scripts/{name}"'
            return match[0]

        text = re.sub(r'\bpython3? (?:scripts/)?([\w-]+\.py)\b', local_script, text)
        if path.name == 'SKILL.md':
            text = add_guidance(path, text, guidance)
        if text != original:
            path.write_text(text, encoding='utf-8')


def review_digests(skills, records):
    digests = {}
    for name in records:
        files = (file for file in (skills / name).rglob('*') if file.is_file())
        entries = {file.relative_to(skills).as_posix(): hashlib.sha256(file.read_bytes()).hexdigest()
                   for file in sorted(files)}
        digests[name] = hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()

    evidence = {}
    for name in records:
        dependencies = {name, 'book-status'}
        pending = list(dependencies)
        while pending:
            record = records[pending.pop()]
            raw = record['fields']['metadata'].get('bundled-dependencies', '')
            for dep in (part.strip() for part in raw.split(',') if part.strip()):
                if dep not in dependencies:
                    dependencies.add(dep)
                    pending.append(dep)
        evidence[name] = hashlib.sha256(json.dumps(
            {dep: digests[dep] for dep in dependencies}, sort_keys=True
        ).encode()).hexdigest()
    return evidence


def build(output, host='desktop'):
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.storycraft-build-', dir=output.parent) as temp:
        package = Path(temp) / 'bundle'
        shutil.copytree(ROOT / 'plugin' / 'shared', package)
        if host == 'generic':
            for filename in ('plugin.json', 'mcp_config.json'):
                shutil.copy2(ROOT / 'plugin' / filename, package)
            rules = (ROOT / 'templates/AGENTS.md').read_text(encoding='utf-8')
            rules = rules.replace('__SERIES_TITLE__', 'Storycraft Suite')
            rules = rules.replace('__PROJECT_TYPE__', 'FICTION, NONFICTION, or HYBRID')
            (package / 'rules').mkdir()
            (package / 'rules/AGENTS.md').write_text(rules, encoding='utf-8')
        else:
            shutil.copytree(ROOT / 'plugin' / host, package, dirs_exist_ok=True)
        version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
        manifest_path = package / ('.claude-plugin/plugin.json' if host == 'claude' else 'plugin.json')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest['version'] = version
        write_json(manifest_path, manifest)
        launcher = package / 'run-python'
        if host == 'desktop':
            launcher.write_text(
                '#!/bin/sh\nset -eu\n'
                'storycraft_bundle=$(cd -P "$(dirname "$0")" && pwd)\n'
                'export PYTHONPATH="$storycraft_bundle/python${PYTHONPATH:+:$PYTHONPATH}"\n'
                f'exec {shlex.quote(sys._base_executable)} -B "$@"\n',
                encoding='utf-8',
            )
        launcher.chmod(0o755)
        bundle_yaml(package / 'python')
        shutil.copy2(ROOT / 'VERSION', package)
        (package / 'mcp').mkdir()
        shutil.copy2(ROOT / 'mcp' / 'storycraft_mcp.py', package / 'mcp')
        skills = package / 'skills'
        shutil.copytree(ROOT / 'skills', skills, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo', '.DS_Store'))
        records = load_skills()
        # The original desktop release hashed this rendering. Use the same bytes for
        # existing reviews across packages, before substituting Claude's path variables.
        adapt_desktop_commands(skills, records)
        write_json(package / 'review-skill-digests.json', review_digests(skills, records))
        if host == 'claude':
            adapt_claude_commands(skills)

        with directory_lock(output.parent):
            if output.exists():
                old_package = Path(temp) / 'previous'
                output.rename(old_package)
                try:
                    package.rename(output)
                except OSError:
                    old_package.rename(output)
                    raise
            else:
                package.rename(output)
    print(f'Built Storycraft {version} at {output}')


def build_marketplace(output, catalog_path, template, host):
    entry = template['plugins'][0]
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    with directory_lock(catalog_path.parent):
        write_catalog = not catalog_path.exists()
        if write_catalog:
            catalog = template
        else:
            catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
            existing = next((item for item in catalog['plugins'] if item['name'] == entry['name']), None)
            if existing is None:
                catalog['plugins'].append(entry)
                write_catalog = True
            elif existing['source'] != entry['source']:
                raise ValueError(f'Storycraft already points to another source in {catalog_path}')

        build(output, host)
        if write_catalog:
            with tempfile.TemporaryDirectory(prefix='.storycraft-catalog-', dir=catalog_path.parent) as temp:
                updated = Path(temp) / catalog_path.name
                write_json(updated, catalog)
                updated.replace(catalog_path)
    return catalog['name']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Build the generic Storycraft plugin bundle.')
    parser.add_argument('output', type=Path)
    build(parser.parse_args().output.absolute(), 'generic')
