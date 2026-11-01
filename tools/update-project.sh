#!/usr/bin/env bash
# Safe dry-run/apply update; retains local changes and unknown historical bases.
set -euo pipefail
exec python3 "$(dirname "${BASH_SOURCE[0]}")/update-project.py" "$@"
