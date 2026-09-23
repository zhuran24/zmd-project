#!/usr/bin/env bash
set -u -o pipefail
task_verify_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
task_solver_dir=$(cd -- "$task_verify_dir/../../.." && pwd)
mkdir -p "$task_verify_dir/logs" "$task_verify_dir/tmp"
chmod +x "$task_verify_dir/bin/python"
export PATH="$task_verify_dir/bin:$PATH"
export CARGO_TARGET_DIR="$task_verify_dir/cargo-target"
export CARGO_INCREMENTAL=0 PYTHONDONTWRITEBYTECODE=1 TMPDIR="$task_verify_dir/tmp"
cd "$task_solver_dir"
run_check() {
    local check_label=$1
    shift
    printf '%s\t' "$check_label" >> "$task_verify_dir/test-exits.tsv"
    "$@" > "$task_verify_dir/logs/$check_label.log" 2>&1
    local check_exit=$?
    printf '%s\n' "$check_exit" >> "$task_verify_dir/test-exits.tsv"
    printf '%s exit=%s\n' "$check_label" "$check_exit"
}
run_check build cargo build --workspace --locked --offline -j 4
run_check check cargo check --workspace --locked --offline -j 4
run_check clippy cargo clippy --workspace --locked --offline -j 4
run_check kernel-lib cargo test -p kernel --lib --locked --offline -j 4 -- --test-threads=1
run_check topology-lib cargo test -p topology --lib --locked --offline -j 4 -- --test-threads=1
run_check kernel-reference cargo test -p kernel --test reference --locked --offline -j 4 -- --test-threads=1
run_check topology-validation cargo test -p topology --test validation --locked --offline -j 4 -- --test-threads=1
run_check kernel-doc cargo test -p kernel --doc --locked --offline -j 4 -- --test-threads=1
run_check topology-doc cargo test -p topology --doc --locked --offline -j 4 -- --test-threads=1
run_check catalog-verify python3 -B 数据/工具/formal_catalog.py
run_check catalog-regressions python3 -B "$task_verify_dir/catalog-tests.py"
