#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
prefix=${1:-revision-final}
runner=内核维护/2026-09-30-步进规则同步/run.sh
for command in build check clippy; do
  bash "$runner" run "${prefix}-$command" cargo "$command" --workspace -j 4
done
bash "$runner" run ${prefix}-kernel-lib cargo test -p kernel --lib -j 4 -- --test-threads=1
bash "$runner" run ${prefix}-topology-lib cargo test -p topology --lib -j 4 -- --test-threads=1
bash "$runner" run ${prefix}-reference cargo test -p kernel --test reference -j 4 -- --test-threads=1
bash "$runner" run ${prefix}-validation cargo test -p topology --test validation -j 4 -- --test-threads=1
bash "$runner" run ${prefix}-kernel-doc cargo test -p kernel --doc -j 4 -- --test-threads=1
bash "$runner" run ${prefix}-topology-doc cargo test -p topology --doc -j 4 -- --test-threads=1
bash "$runner" run ${prefix}-catalog python3 数据/工具/formal_catalog.py
bash "$runner" run ${prefix}-catalog-tests python3 数据/工具/test_formal_catalog.py
