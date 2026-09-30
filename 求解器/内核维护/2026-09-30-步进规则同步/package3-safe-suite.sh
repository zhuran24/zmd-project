#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
run=(bash 内核维护/2026-09-30-步进规则同步/run.sh run)
# 本套build已先执行为p3-final-build，用该二进制重生成候选B报告；此处接续其余十项。
"${run[@]}" p3-final-check cargo check --workspace -j 4
"${run[@]}" p3-final-clippy cargo clippy --workspace -j 4
"${run[@]}" p3-final-kernel-lib cargo test -p kernel --lib -j 4 -- --test-threads=1
"${run[@]}" p3-final-topology-lib cargo test -p topology --lib -j 4 -- --test-threads=1
"${run[@]}" p3-final-reference cargo test -p kernel --test reference -j 4 -- --test-threads=1
"${run[@]}" p3-final-validation cargo test -p topology --test validation -j 4 -- --test-threads=1
"${run[@]}" p3-final-kernel-doc cargo test -p kernel --doc -j 4 -- --test-threads=1
"${run[@]}" p3-final-topology-doc cargo test -p topology --doc -j 4 -- --test-threads=1
"${run[@]}" p3-final-catalog python3 数据/工具/formal_catalog.py
"${run[@]}" p3-final-catalog-tests python3 数据/工具/test_formal_catalog.py
