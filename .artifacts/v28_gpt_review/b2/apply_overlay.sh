#!/usr/bin/env sh
set -eu
ROOT="${1:-.}"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cp -R "$SCRIPT_DIR/patched_files/." "$ROOT/"
printf '%s\n' "Applied patched_files overlay into $ROOT"
printf '%s\n' "Recommended verification: PYTHONPATH=. python -m pytest src/tests/cuts -q"
