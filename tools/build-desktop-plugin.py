#!/usr/bin/env python3
"""Build the local ChatGPT Desktop package from the shared Storycraft library."""

import argparse
import json
from pathlib import Path
import subprocess

from plugin_bundle import build, build_marketplace
from skill_lib import ROOT


def install(output):
    root = output.parent
    catalog_path = root / '.agents/plugins/marketplace.json'
    template = json.loads((ROOT / 'plugin/desktop-marketplace.json').read_text(encoding='utf-8'))
    entry = template['plugins'][0]
    entry['source']['path'] = './' + output.name
    name = build_marketplace(output, catalog_path, template, 'desktop')
    subprocess.run(['codex', 'plugin', 'marketplace', 'add', str(root)], check=True)
    subprocess.run(['codex', 'plugin', 'add', f"{entry['name']}@{name}"], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--install', action='store_true', help='register and install from the parent marketplace')
    args = parser.parse_args()
    (install if args.install else build)(args.output.absolute())
