#!/usr/bin/env bash
set -euo pipefail
task_verify_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
python3 -B "$task_verify_dir/finalize.py" > "$task_verify_dir/finalize.log"
