#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
suite_status=0
safe_step() {
    local step_name="$1"
    shift
    if bash run.sh run "$step_name" "$@"; then
        return
    else
        local step_status=$?
        if [[ -e STOP.json || -e ACTIVE_STOP.json ]]; then
            exit "$step_status"
        fi
        # A logged test failure is reported and does not skip the remaining safe targets.
        # Unlogged wrapper failures stop the suite.
        if ! rg -q -F '"name": "'"$step_name"'"' commands.jsonl; then
            exit "$step_status"
        fi
        suite_status=1
    fi
}
safe_step cargo-check cargo check --workspace -j 4
safe_step cargo-clippy cargo clippy --workspace -j 4
safe_step kernel-lib cargo test -p kernel --lib -j 4 -- --test-threads=1
safe_step topology-lib cargo test -p topology --lib -j 4 -- --test-threads=1
safe_step kernel-reference cargo test -p kernel --test reference -j 4 -- --test-threads=1
safe_step topology-validation cargo test -p topology --test validation -j 4 -- --test-threads=1
safe_step kernel-doc cargo test -p kernel --doc -j 4 -- --test-threads=1
safe_step topology-doc cargo test -p topology --doc -j 4 -- --test-threads=1
safe_step catalog-verify python3 数据/工具/formal_catalog.py
safe_step catalog-regressions python3 数据/工具/test_formal_catalog.py
exit "$suite_status"
