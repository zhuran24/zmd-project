#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "${SCRIPT_DIR}/../../../.." && pwd)"
PYTHON="${ROOT}/.venv/bin/python"
HARNESS="${SCRIPT_DIR}/phase_minus1_v2_harness.py"
ARTIFACT_ROOT="${ROOT}/.artifacts/solver_reasoning_outer_loop_phase_minus1_v2_20260815"

if [[ "${1:-}" == "--worker" ]]; then
  if [[ $# -ne 2 ]]; then
    echo "usage: $0 --worker OUTPUT_DIR" >&2
    exit 64
  fi
  output_dir="$2"
  mkdir -p -- "${output_dir}"
  set +e
  echo "started_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "root=${ROOT}"
  echo "output_dir=${output_dir}"
  echo "protocol_freeze_commit=6c9fc1f4201c2eb79f0ea87b4e5530cfe245897a"
  echo "harness_revision=phase_minus1_v2_high_budget_saturation_v1"
  echo "command=${PYTHON} ${HARNESS} batch --output-dir ${output_dir}"
  "${PYTHON}" "${HARNESS}" batch --output-dir "${output_dir}"
  rc=$?
  echo "exit_code=${rc}"
  echo "finished_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '%s\n' "${rc}" > "${output_dir}/EXIT_CODE"
  touch "${output_dir}/.DONE"
  exit "${rc}"
fi

if [[ $# -gt 1 ]]; then
  echo "usage: $0 [RUN_ID]" >&2
  exit 64
fi

run_id="${1:-phase-minus1-v2-$(date -u +%Y%m%dT%H%M%SZ)}"
output_dir="${ARTIFACT_ROOT}/${run_id}"
if [[ -e "${output_dir}" ]]; then
  echo "refusing to reuse existing output directory: ${output_dir}" >&2
  exit 65
fi
mkdir -p -- "${output_dir}"

setsid nohup bash "$0" --worker "${output_dir}" \
  > "${output_dir}/full.log" 2>&1 < /dev/null &
pid=$!
printf '%s\n' "${pid}" > "${output_dir}/PID"
printf '%s\n' "${run_id}" > "${output_dir}/RUN_ID"
printf '%s\n' "${output_dir}"
printf 'pid=%s\n' "${pid}"
