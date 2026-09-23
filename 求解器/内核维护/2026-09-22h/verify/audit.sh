#!/usr/bin/env bash
set -euo pipefail
task_verify_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export PYTHONDONTWRITEBYTECODE=1
python3 -B "$task_verify_dir/audit.py" "$@"
