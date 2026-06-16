#!/usr/bin/env bash
# P2 #31 Pumpkin LCG PoC runner
# 跑 INFEASIBLE 6 约束 demo, 验证:
#   1. 报 UNSAT
#   2. --proof 输出 DRCP 证书
#   3. (如果 CLI 支持) extract unsat core 出 3 约束 MUS

set -euo pipefail

DIR="$(dirname "$(realpath "$0")")"
DEMO="$DIR/infeasible_demo.fzn"
PROOF="$DIR/proof.drcp"
LOG="$DIR/run_log.txt"

[[ -f "$DEMO" ]] || { echo "ERROR: $DEMO 不存在" >&2; exit 1; }

echo "=== Pumpkin PoC: INFEASIBLE FlatZinc demo ===" | tee "$LOG"
echo "Pumpkin version:" | tee -a "$LOG"
pumpkin-solver --version 2>&1 | tee -a "$LOG"

echo "" | tee -a "$LOG"
echo "=== --help (CLI capabilities) ===" | tee -a "$LOG"
pumpkin-solver --help 2>&1 | tee -a "$LOG" | head -40

echo "" | tee -a "$LOG"
echo "=== 跑 demo (期望 UNSAT) ===" | tee -a "$LOG"
# 试 --proof
pumpkin-solver --proof-path "$PROOF" --proof-type full "$DEMO" 2>&1 | tee -a "$LOG" || echo "(exit non-zero, 预期 UNSAT 通常 exit 1)" | tee -a "$LOG"

echo "" | tee -a "$LOG"
echo "=== 检查 proof ===" | tee -a "$LOG"
if [[ -f "$PROOF" ]]; then
    wc -l "$PROOF" | tee -a "$LOG"
    echo "Proof preview (前 30 行):" | tee -a "$LOG"
    head -30 "$PROOF" | tee -a "$LOG"
else
    echo "(没有 proof 文件输出)" | tee -a "$LOG"
fi

echo "" | tee -a "$LOG"
echo "=== Done. log -> $LOG ===" | tee -a "$LOG"
