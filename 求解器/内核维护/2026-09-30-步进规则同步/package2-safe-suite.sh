#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
for command in build check clippy; do
    bash run.sh run "p2-final-$command" cargo "$command" --workspace -j 4
done
bash run.sh run p2-final-kernel-lib cargo test -p kernel --lib -j 4 -- --test-threads=1
bash run.sh run p2-final-topology-lib cargo test -p topology --lib -j 4 -- --test-threads=1
bash run.sh run p2-final-reference cargo test -p kernel --test reference -j 4 -- --test-threads=1
bash run.sh run p2-final-validation cargo test -p topology --test validation -j 4 -- --test-threads=1
bash run.sh run p2-final-kernel-doc cargo test -p kernel --doc -j 4 -- --test-threads=1
bash run.sh run p2-final-topology-doc cargo test -p topology --doc -j 4 -- --test-threads=1
bash run.sh run p2-final-catalog python3 数据/工具/formal_catalog.py
bash run.sh run p2-final-catalog-tests python3 数据/工具/test_formal_catalog.py
