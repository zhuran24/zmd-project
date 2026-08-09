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
umask 077

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
PY="$ROOT/.venv/bin/python"
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
if ! command -v flock >/dev/null 2>&1; then
  echo "flock is required: prod-scale solves must hold the global mutex" >&2; exit 2
fi
if ! [[ "$OUTER_SECONDS" =~ ^[1-9][0-9]*$ ]]; then
  echo "--outer-seconds must be a positive integer" >&2; exit 2
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
UNIT="band22reg-${TAG}-${STAMP}-$$"
OUTER_LOG="$OUT_ROOT/${UNIT}.outer.log"
OUTER_RECEIPT="$OUT_ROOT/${UNIT}.OUTER_RECEIPT.json"
LOCK_PATH="/run/user/$UID/zmd-pj-prod-scale-solve.lock"
LOCK_STARTED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [[ ! -d "/run/user/$UID" || -L "$LOCK_PATH" ]]; then
  echo "prod-scale lock path is unavailable or unsafe: $LOCK_PATH" >&2; exit 2
fi
exec {LOCK_FD}<>"$LOCK_PATH" || {
  echo "cannot open prod-scale lock: $LOCK_PATH" >&2; exit 2;
}
if ! flock -n "$LOCK_FD"; then
  HOLDER="$(tr '\n' ' ' < "$LOCK_PATH" 2>/dev/null || true)"
  [[ -n "$HOLDER" ]] || HOLDER="holder identity unavailable"
  echo "prod-scale lock busy: $LOCK_PATH; holder: $HOLDER" >&2
  exit 2
fi
: > "$LOCK_PATH"
printf 'pid=%s unit=%s tag=%s started_utc=%s\n' \
  "$$" "$UNIT" "$TAG" "$LOCK_STARTED" >&"$LOCK_FD"

if [[ -e "$OUTER_LOG" || -e "$OUTER_RECEIPT" ]]; then
  echo "refusing to overwrite outer artifact for unit $UNIT" >&2; exit 2
fi
: > "$OUTER_LOG"

DRIVER_OUT_DIR="$OUT_ROOT"
for ((i = 0; i < ${#DRIVER_ARGS[@]}; i++)); do
  case "${DRIVER_ARGS[$i]}" in
    --out-dir) DRIVER_OUT_DIR="${DRIVER_ARGS[$((i + 1))]:-$OUT_ROOT}" ;;
    --out-dir=*) DRIVER_OUT_DIR="${DRIVER_ARGS[$i]#--out-dir=}" ;;
  esac
done
[[ "$DRIVER_OUT_DIR" = /* ]] || DRIVER_OUT_DIR="$ROOT/$DRIVER_OUT_DIR"
DRIVER_OUT_DIR="$(readlink -m -- "$DRIVER_OUT_DIR")"
LATEST_PTR="$DRIVER_OUT_DIR/${TAG}.LATEST"
LATEST_BEFORE=""
[[ -f "$LATEST_PTR" ]] && IFS= read -r LATEST_BEFORE < "$LATEST_PTR"

echo "unit=$UNIT memory_max=$MEMORY_MAX outer_seconds=$OUTER_SECONDS" | tee -a "$OUTER_LOG"

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

RUN_DIR=""
[[ -f "$LATEST_PTR" ]] && IFS= read -r RUN_DIR < "$LATEST_PTR"
INNER_RECEIPT=""
if [[ -n "$RUN_DIR" && "$RUN_DIR" != "$LATEST_BEFORE" && -f "$RUN_DIR/${TAG}.DONE" ]]; then
  INNER_RECEIPT="$RUN_DIR/${TAG}.DONE"
fi

# 137 = SIGKILL (the OOM killer or RuntimeMaxSec), 124/143 = SIGTERM paths.
STATE="COMPLETED"
if [[ -z "$INNER_RECEIPT" ]]; then STATE="FAILED_NO_INNER_RECEIPT"; fi
if [[ $RC -ne 0 && $RC -ne 1 ]]; then STATE="FAILED_SIGNAL_OR_LIMIT"; fi

if ! "$PY" - "$OUTER_RECEIPT" "$UNIT" "$STATE" "$RC" "$STARTED" \
    "$FINISHED" "$MEMORY_MAX" "$OUTER_SECONDS" "$INNER_RECEIPT" "$RUN_DIR" \
    "$OUTER_LOG" "$LOCK_PATH" "$$" "$LOCK_STARTED" "$TAG" <<'PY'
import json, os, sys
payload = {
    "receipt": "band22_registration_outer",
    "unit": sys.argv[2],
    "state": sys.argv[3],
    "exit_code": int(sys.argv[4]),
    "started_utc": sys.argv[5],
    "finished_utc": sys.argv[6],
    "memory_max": sys.argv[7],
    "memory_swap_max": "0",
    "runtime_max_sec": int(sys.argv[8]),
    "inner_receipt": sys.argv[9],
    "run_dir": sys.argv[10],
    "outer_log": sys.argv[11],
    "prod_scale_singleton": {
        "path": sys.argv[12], "acquired": True,
        "holder": {"pid": int(sys.argv[13]), "unit": sys.argv[2],
                   "tag": sys.argv[15], "started_utc": sys.argv[14]},
    },
    "note": ("state FAILED_* means the inner driver never landed a terminal "
             "receipt (OOM kill, RuntimeMaxSec, or signal): no verdict exists "
             "for this run"),
}
with open(sys.argv[1], "x", encoding="utf-8") as handle:
    json.dump(payload, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
    handle.flush()
    os.fsync(handle.fileno())
PY
then
  echo "failed to land no-overwrite outer receipt: $OUTER_RECEIPT" >&2
  exit 2
fi

echo "outer receipt: $OUTER_RECEIPT (state=$STATE rc=$RC)"
exit $RC
