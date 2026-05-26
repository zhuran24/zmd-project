#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
PYTHON_BIN="${PYTHON:-${PROJECT_ROOT}/.venv/bin/python}"

cd "${PROJECT_ROOT}"
PYTHONPATH="${PROJECT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}" \
  "${PYTHON_BIN}" -m pytest \
  src/tests/cuts/test_family_power_grid_reach.py::test_generator_no_cut_when_connected -q
