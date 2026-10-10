#!/usr/bin/env bash
# Check our skills/ against the upstream Open Storycraft ZIP.
#
# Upstream (https://storycraft.lanternkey.fyi/) has no repo or changelog — the
# structured ZIP is its only distribution channel. This script downloads it
# (or reads a local copy), diffs it against skills/, and classifies every
# difference:
#
#   ours (expected)    — a file we've changed or added; listed in sync-manifest.txt
#                        and accounted for in CHANGELOG.md
#   UPSTREAM DRIFT     — a file changed upstream that we have NOT touched.
#                        Review it: port the improvement if it's good (add the
#                        file to sync-manifest.txt + a CHANGELOG entry when you
#                        do), or note why we're skipping it.
#   NEW UPSTREAM       — a file upstream has that we don't.
#   FORK ADDITION      — a file only we have (expected for everything we've added).
#
# Usage:
#   ./sync-check.sh                    # download the current upstream ZIP
#   ./sync-check.sh /path/to/zip      # check against a local copy
#
# Exit status: 0 when everything is accounted for, 1 when unexplained drift
# or new upstream files exist (so it can gate a periodic check).
set -euo pipefail

LIBRARY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST="$LIBRARY_DIR/sync-manifest.txt"
ZIP_SRC="${1:-https://storycraft.lanternkey.fyi/open-storycraft-structured.zip}"

if [[ ! -f "$MANIFEST" ]]; then
  echo "error: $MANIFEST not found — it lists the files we own that may differ" >&2
  exit 2
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

echo "Fetching upstream ZIP: $ZIP_SRC"
if [[ "$ZIP_SRC" == http* ]]; then
  curl -fsSL -o "$WORKDIR/up.zip" "$ZIP_SRC"
else
  cp "$ZIP_SRC" "$WORKDIR/up.zip"
fi
unzip -q "$WORKDIR/up.zip" -d "$WORKDIR/up"

UP_SKILLS="$(find "$WORKDIR/up" -type d -name skills | head -1)"
if [[ -z "$UP_SKILLS" ]]; then
  echo "error: no skills/ directory found in the upstream ZIP" >&2
  exit 2
fi

ours=0; drift=0; new_upstream=0; additions=0
have_findings=0

while IFS= read -r line; do
  case "$line" in
    "Files "*)
      up_path="${line#Files }"; up_path="${up_path%% and *}"
      loc_path="${line#* and }"; loc_path="${loc_path%% differ*}"
      rel="${loc_path#"$LIBRARY_DIR/skills/"}"
      if grep -Fqx "skills/$rel" "$MANIFEST"; then
        ours=$((ours+1))
        echo "  ours (expected):   skills/$rel"
      else
        drift=$((drift+1)); have_findings=1
        echo "  UPSTREAM DRIFT:    skills/$rel — changed upstream, we haven't touched it"
      fi
      ;;
    "Only in "*)
      dir="${line#Only in }"; dir="${dir%: *}"
      name="${line##*: }"
      if [[ "$dir" == "$UP_SKILLS" ]]; then
        new_upstream=$((new_upstream+1)); have_findings=1
        echo "  NEW UPSTREAM:      skills/$name"
      else
        rel_dir="${dir#"$LIBRARY_DIR/skills/"}"
        if [[ "$rel_dir" == "$dir" ]]; then rel_dir="."; fi
        additions=$((additions+1))
        if [[ "$rel_dir" == "." ]]; then
          echo "  fork addition:     skills/$name"
        else
          echo "  fork addition:     skills/$rel_dir/$name"
        fi
      fi
      ;;
  esac
done < <(diff -rq "$UP_SKILLS" "$LIBRARY_DIR/skills" || true)

echo
echo "Summary: $ours ours (expected), $additions fork additions, $drift upstream drift, $new_upstream new upstream."

if [[ "$have_findings" -eq 1 ]]; then
  echo
  echo "Unexplained findings above. For each: review the upstream change, port it if"
  echo "it's an improvement (then add the file to sync-manifest.txt and record it in"
  echo "CHANGELOG.md), or record why we're skipping it. This repo is the source of"
  echo "truth — upstream drift is an offer, not an obligation."
  exit 1
fi
echo "Everything is accounted for."
