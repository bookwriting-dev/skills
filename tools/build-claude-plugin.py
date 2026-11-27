#!/usr/bin/env python3
"""Build Storycraft and its local Claude Code marketplace."""

import argparse
import json
from pathlib import Path

from plugin_bundle import build_marketplace
from skill_lib import ROOT


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('marketplace', type=Path)
    root = parser.parse_args().marketplace.absolute()
    template = json.loads((ROOT / 'plugin/claude-marketplace.json').read_text(encoding='utf-8'))
    entry = template['plugins'][0]
    name = build_marketplace(root / entry['source'], root / '.claude-plugin/marketplace.json', template, 'claude')
    print(f"Claude marketplace: {root} ({entry['name']}@{name})")
