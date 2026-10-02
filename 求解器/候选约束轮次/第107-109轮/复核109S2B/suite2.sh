#!/bin/bash
# 复核109S2B 第二组：库位额度停收 + 末端拒收检查 + 层数读法敏感性
cd "$(dirname "$0")"
{
for spec in "109101 6 mix no 0.7 axis budget" "109102 12 clear no 1.0 axis budget" "109103 3 keep core_per_side 0.8 axis budget" \
            "109104 16 mix no 0.9 axis budget" "109105 1 clear no 1.0 axis budget" "109106 8 keep no 0.5 axis budget" \
            "109201 6 keep no 0.8 cross none" "109202 6 clear no 0.8 rev_undet none"; do
  echo $spec
done
} | xargs -P 3 -L 1 bash -c 'timeout 900 python3 -B run_factory.py $0 $1 $2 $3 $4 $5 $6' > suite2_results.jsonl 2> suite2_err.log
echo done >> suite2_err.log
