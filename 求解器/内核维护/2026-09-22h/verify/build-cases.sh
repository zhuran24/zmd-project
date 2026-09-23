#!/usr/bin/env bash
set -euo pipefail
task_verify_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
task_solver_dir=$(cd -- "$task_verify_dir/../../.." && pwd)
export CARGO_TARGET_DIR="$task_verify_dir/cargo-target" CARGO_INCREMENTAL=0 PYTHONDONTWRITEBYTECODE=1 TMPDIR="$task_verify_dir/tmp"
python3 -B "$task_verify_dir/make_cases.py"
cargo run --offline --manifest-path "$task_verify_dir/probe/Cargo.toml" -j 4 -- "$task_solver_dir" "$task_verify_dir" > "$task_verify_dir/logs/build-cases.log" 2>&1
