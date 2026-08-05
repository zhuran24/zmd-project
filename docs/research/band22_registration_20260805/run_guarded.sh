#!/usr/bin/env bash
# Hard resource envelope for registration_driver.py (cgroup, not a sampler).
#
# The driver's memory sampler observes; it does not limit, and its SIGALRM
# guard cannot interrupt a native CP-SAT call. This wrapper is the actual
# boundary: a transient systemd user unit with MemoryMax / MemorySwapMax /
# RuntimeMaxSec around the whole process tree, plus an outer receipt written
# even when the inner process is OOM-killed or hard-timed-out (in which case
# the driver never gets to write its own receipt).
#
# Usage:
#   ./run_guarded.sh --tag full --outer-seconds 21600 --memory-max 24G -- \
#       --binding-seconds 600 --routing-seconds 600 --max-gate-wall-seconds 20400
#
# Everything after `--` is passed to the driver verbatim. The inner gate
# deadline must be smaller than --outer-seconds; leave a real margin (the
# default check below demands >= 600s) so the driver can still write its
# result, fsync it and land its terminal receipt.
set -u -o pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
PY="$ROOT/.venv-uvbolt-backup/bin/python"
OUT_ROOT="$ROOT/.artifacts/band22_registration_20260805"

TAG="full"
OUTER_SECONDS=21600
MEMORY_MAX="24G"
DRIVER_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag) TAG="$2"; shift 2 ;;
    --outer-seconds) OUTER_SECONDS="$2"; shift 2 ;;
    --memory-max) MEMORY_MAX="$2"; shift 2 ;;
    --) shift; DRIVER_ARGS=("$@"); break ;;
    *) echo "unknown wrapper argument: $1" >&2; exit 2 ;;
  esac
done

if ! [[ "$TAG" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]]; then
  echo "--tag must be a strict leaf name" >&2; exit 2
fi
if ! command -v systemd-run >/dev/null 2>&1; then
  echo "systemd-run is required: this wrapper IS the resource envelope" >&2; exit 2
fi

# The inner gate guard must expire before the outer runtime limit.
INNER_GUARD=0
for ((i = 0; i < ${#DRIVER_ARGS[@]}; i++)); do
  if [[ "${DRIVER_ARGS[$i]}" == "--max-gate-wall-seconds" ]]; then
    INNER_GUARD="${DRIVER_ARGS[$((i + 1))]:-0}"
  fi
done
if [[ "${INNER_GUARD%.*}" -eq 0 ]]; then
  echo "pass --max-gate-wall-seconds to the driver: the inner deadline must be" \
       "smaller than --outer-seconds so the driver can still write its receipt" >&2
  exit 2
fi
if (( ${INNER_GUARD%.*} + 600 > OUTER_SECONDS )); then
  echo "--max-gate-wall-seconds (${INNER_GUARD}) must be at least 600s below" \
       "--outer-seconds (${OUTER_SECONDS})" >&2
  exit 2
fi

mkdir -p "$OUT_ROOT"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
UNIT="band22reg-${TAG}-${STAMP}"
OUTER_LOG="$OUT_ROOT/${UNIT}.outer.log"
OUTER_RECEIPT="$OUT_ROOT/${UNIT}.OUTER_RECEIPT.json"

echo "unit=$UNIT memory_max=$MEMORY_MAX outer_seconds=$OUTER_SECONDS" | tee "$OUTER_LOG"

STARTED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
systemd-run --user --scope --unit="$UNIT" \
  -p MemoryMax="$MEMORY_MAX" \
  -p MemorySwapMax=0 \
  -p RuntimeMaxSec="$OUTER_SECONDS" \
  env -u PYTHONPATH -u PYTHONHOME -u TMPDIR \
      $(env | sed -n 's/^\(EXACT_[A-Za-z0-9_]*\)=.*/-u \1/p') \
  "$PY" "$HERE/registration_driver.py" --tag "$TAG" "${DRIVER_ARGS[@]}" \
  >>"$OUTER_LOG" 2>&1
RC=$?
FINISHED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

LATEST_PTR="$OUT_ROOT/${TAG}.LATEST"
RUN_DIR=""
[[ -f "$LATEST_PTR" ]] && RUN_DIR="$(cat "$LATEST_PTR")"
INNER_RECEIPT=""
[[ -n "$RUN_DIR" && -f "$RUN_DIR/${TAG}.DONE" ]] && INNER_RECEIPT="$RUN_DIR/${TAG}.DONE"

# 137 = SIGKILL (the OOM killer or RuntimeMaxSec), 124/143 = SIGTERM paths.
STATE="COMPLETED"
if [[ -z "$INNER_RECEIPT" ]]; then STATE="FAILED_NO_INNER_RECEIPT"; fi
if [[ $RC -ne 0 && $RC -ne 1 ]]; then STATE="FAILED_SIGNAL_OR_LIMIT"; fi

python3 - "$OUTER_RECEIPT" <<EOF
import json, sys
json.dump({
    "receipt": "band22_registration_outer",
    "unit": "$UNIT",
    "state": "$STATE",
    "exit_code": $RC,
    "started_utc": "$STARTED",
    "finished_utc": "$FINISHED",
    "memory_max": "$MEMORY_MAX",
    "memory_swap_max": "0",
    "runtime_max_sec": $OUTER_SECONDS,
    "inner_receipt": "$INNER_RECEIPT",
    "run_dir": "$RUN_DIR",
    "outer_log": "$OUTER_LOG",
    "note": ("state FAILED_* means the inner driver never landed a terminal "
             "receipt (OOM kill, RuntimeMaxSec, or signal): no verdict exists "
             "for this run"),
}, open(sys.argv[1], "w"), ensure_ascii=False, indent=2)
EOF

echo "outer receipt: $OUTER_RECEIPT (state=$STATE rc=$RC)"
exit $RC
