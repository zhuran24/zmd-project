#!/usr/bin/env bash
set -eu
base=$(dirname "$0")
python3 -B "$base/compound_modules.py" qplant 12 12 60
python3 -B "$base/compound_modules.py" qplant 12 13 60
python3 -B "$base/compound_modules.py" sand_ore 12 14 90
python3 -B "$base/compound_modules.py" sand_blue 16 15 180
