#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

find_project_root() {
  local dir="$1"
  while [[ "${dir}" != "/" ]]; do
    if [[ -f "${dir}/PROJECT_LOCK.md" && -d "${dir}/src/cuts" ]]; then
      printf '%s\n' "${dir}"
      return 0
    fi
    dir="$(dirname "${dir}")"
  done
  return 1
}

if ! PROJECT_ROOT="$(find_project_root "${SCRIPT_DIR}")"; then
  echo "Could not locate project root above ${SCRIPT_DIR}; expected PROJECT_LOCK.md and src/cuts" >&2
  exit 2
fi

if [[ -n "${PYTHON:-}" ]]; then
  PYTHON_BIN="${PYTHON}"
elif [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
  PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
else
  PYTHON_BIN="$(command -v python3)"
fi

cd "${PROJECT_ROOT}"
PYTHONPATH="${PROJECT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}" \
  "${PYTHON_BIN}" -m pytest \
  src/tests/cuts/test_family_power_grid_reach.py::test_generator_no_cut_when_connected -q
