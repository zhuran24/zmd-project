#!/usr/bin/env bash
set -euo pipefail
task_verify_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
task_solver_dir=$(cd -- "$task_verify_dir/../../.." && pwd)
chmod +x "$task_verify_dir/bin/python"
export PATH="$task_verify_dir/bin:$PATH"
export CARGO_TARGET_DIR="$task_verify_dir/cargo-target" CARGO_INCREMENTAL=0 PYTHONDONTWRITEBYTECODE=1 TMPDIR="$task_verify_dir/tmp"
cd "$task_solver_dir"
cargo test -p topology --test validation --locked --offline -j 4 -- --test-threads=1 > "$task_verify_dir/logs/topology-validation-final.log" 2>&1
