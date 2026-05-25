#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../_phase1_2_pkg_v12/project" 2>/dev/null || cd _phase1_2_pkg_v12/project
python -m pytest src/tests/cuts/test_family_power_grid_reach.py::test_generator_no_cut_when_connected -q
